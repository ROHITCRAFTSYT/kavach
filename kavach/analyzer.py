"""LLM reasoning steps: evidence extraction, localisation, grounded Q&A, complaint drafting."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from . import grounding, languages, scoring, signals
from .models import Action, Analysis, Finding, KeyFact, Localized, Source
from .patterns import PATTERNS, taxonomy_for_prompt
from .sarvam import SarvamError, SarvamGateway

log = logging.getLogger("kavach.analyzer")

DOC_KINDS = ["phone_call", "voice_note", "sms_or_chat", "email", "official_notice", "bill_or_invoice",
             "bank_communication", "legal_document", "government_scheme", "medical", "advertisement", "other"]
FACT_KINDS = ["deadline", "amount", "reference_id", "contact", "organisation", "person", "date",
              "account_or_upi", "link", "other"]

ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["document_kind", "claimed_sender", "summary", "suspected_caller_speaker", "findings",
                 "legitimacy_indicators", "key_facts", "recommended_actions"],
    "properties": {
        "document_kind": {"type": "string", "enum": DOC_KINDS},
        "claimed_sender": {"type": "string"},
        "summary": {"type": "string"},
        "suspected_caller_speaker": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["pattern_id", "segment_id", "quote", "explanation", "severity"],
                "properties": {
                    "pattern_id": {"type": "string", "enum": list(PATTERNS)},
                    "segment_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "explanation": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "legitimacy_indicators": {"type": "array", "items": {"type": "string"}},
        "key_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "label", "value", "segment_id"],
                "properties": {
                    "kind": {"type": "string", "enum": FACT_KINDS},
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                    "segment_id": {"type": "string"},
                },
            },
        },
        "recommended_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "priority"],
                "properties": {"text": {"type": "string"},
                               "priority": {"type": "string", "enum": ["now", "soon", "optional"]}},
            },
        },
    },
}

ANALYSIS_SYSTEM = f"""You are Kavach, a careful fraud analyst and paperwork explainer for people in India, many of whom have limited literacy.
You receive the content of a phone call transcript, voice note, message, notice, bill or letter. It is split into segments tagged like [u3 speaker=1 t=15s] or [p1b2 page=1].

Do two jobs:
1. EXPLAIN: what this is, who it claims to be from, and the concrete facts (deadlines, amounts, reference numbers, contacts, accounts/UPI IDs, links).
2. DETECT FRAUD: report red flags using ONLY these pattern ids:
{taxonomy_for_prompt()}

Strict rules:
- Many inputs are genuine (real bills, notices, bank messages, OTP messages, court papers). Do not invent red flags. A due date or a disconnection warning alone is normal in a genuine bill. If there are no concrete red flags, return an empty findings list.
- Safety advice is a sign of a GENUINE message, never a red flag: "do not share this OTP", "the bank never asks for your PIN", "visit your branch", "use the official website". An OTP delivery ("Your OTP is 482913, valid for 10 minutes") is normal. Flag CREDENTIAL_REQUEST only when someone ASKS the person to reveal, read out, type or forward a credential. SECRECY_ISOLATION means hiding the matter itself from family or police, not keeping an OTP private. A validity period on an OTP is not URGENCY_PRESSURE. Mentioning RBI rules or a bank is not AUTHORITY_IMPERSONATION unless the sender pretends to be an official making demands.
- Every finding and key fact must cite the segment_id it comes from.
- "quote" must be copied EXACTLY from that segment, character for character, in its ORIGINAL script and language. Never translate, transliterate or paraphrase the quote. Keep it short (the decisive phrase, max ~20 words).
- One finding per distinct red flag; do not repeat the same pattern for the same sentence.
- For calls with several speakers, set suspected_caller_speaker to the speaker id of the person making demands, else "".
- claimed_sender: the organisation or person it claims to be from, or "" if unclear.
- summary: 2-3 plain English sentences saying what the content says and asks for.
- recommended_actions: 2-5 short, practical steps for someone in India. For likely fraud include not paying/sharing OTP, disconnecting, and reporting to the 1930 helpline or cybercrime.gov.in. For genuine paperwork explain what to do and by when, using official channels only.
- Write explanations, summary and actions in English."""


def _findings_from_llm(raw: dict, source: Source) -> tuple[list[Finding], list[Finding]]:
    verified, rejected = [], []
    seen: set[tuple[str, str]] = set()
    for item in raw.get("findings") or []:
        pid = item.get("pattern_id")
        if pid not in PATTERNS:
            continue
        evidence = grounding.verify(item.get("quote", ""), item.get("segment_id"), source.segments)
        key = (pid, evidence.segment_id or "")
        if evidence.verified and key in seen:
            continue
        seen.add(key)
        finding = Finding(
            pattern_id=pid, pattern_name=PATTERNS[pid].name, source="ai",
            severity=item.get("severity") if item.get("severity") in ("high", "medium", "low") else "medium",
            explanation=item.get("explanation", "").strip(), evidence=evidence,
        )
        (verified if evidence.verified else rejected).append(finding)
    return verified, rejected


def _facts(raw: dict, source: Source) -> list[KeyFact]:
    """Regex facts are exact; LLM facts are kept only if their value can be found in the cited text."""
    facts = signals.extract_facts(source.segments)
    have = {re.sub(r"\s+", "", f.value.lower()) for f in facts}
    for item in raw.get("key_facts") or []:
        value = (item.get("value") or "").strip()
        norm = re.sub(r"\s+", "", value.lower())
        if not value or norm in have:
            continue
        ev = grounding.verify(value, item.get("segment_id"), source.segments)
        # Dates/deadlines are often normalised by the model ("15 Oct 2026"), so accept them when
        # the segment exists; everything else must be found in the source.
        if ev.verified or (item.get("kind") in ("deadline", "date", "organisation") and source.segment(item.get("segment_id"))):
            have.add(norm)
            facts.append(KeyFact(kind=item.get("kind", "other"), label=item.get("label") or item.get("kind", "Fact"),
                                 value=value, segment_id=ev.segment_id or item.get("segment_id")))
    return facts


async def analyse(source: Source, gw: SarvamGateway) -> Analysis:
    rules = signals.detect(source.segments)
    try:
        raw = await gw.chat_json(
            name="kavach_analysis", system=ANALYSIS_SYSTEM,
            user=f"Content to analyse ({source.modality.value}, detected language: {source.language or 'unknown'}):\n\n{source.for_prompt()}",
            schema=ANALYSIS_SCHEMA,
        )
        degraded = False
    except SarvamError as exc:
        log.warning("LLM analysis unavailable, falling back to rules only: %s", exc)
        raw, degraded = {}, True

    ai_findings, rejected = _findings_from_llm(raw, source)
    findings = scoring.merge(ai_findings, rules)
    risk, verdict, breakdown = scoring.score(findings, ai_ran=not degraded)
    findings.sort(key=lambda f: scoring.contribution(f, not degraded), reverse=True)

    actions = [Action(text=a["text"], priority=a.get("priority", "soon"))
               for a in raw.get("recommended_actions") or [] if a.get("text")]
    if degraded or not actions:
        actions = default_actions(verdict.value)

    return Analysis(
        document_kind=raw.get("document_kind") or ("phone_call" if source.modality.value == "audio" else "other"),
        claimed_sender=raw.get("claimed_sender", ""),
        summary=raw.get("summary") or "Automatic explanation is unavailable right now; showing rule-based checks only.",
        findings=findings, rejected_claims=rejected,
        legitimacy_indicators=raw.get("legitimacy_indicators") or [],
        key_facts=_facts(raw, source), actions=actions,
        suspected_caller=raw.get("suspected_caller_speaker") or None,
        risk_score=risk, verdict=verdict, score_breakdown=breakdown, degraded=degraded,
    )


def default_actions(verdict: str) -> list[Action]:
    if verdict == "low_risk":
        return [Action(text="If anything asks for money or personal details, verify it using the official website or helpline number.", priority="soon")]
    return [
        Action(text="Do not pay any money and do not share any OTP, PIN or bank details.", priority="now"),
        Action(text="Disconnect the call or stop replying. Real police or banks never demand payment over calls or chats.", priority="now"),
        Action(text="Call the national cyber-fraud helpline 1930 or report at cybercrime.gov.in.", priority="soon"),
    ]


# ------------------------------------------------------------------------ localisation
LOCALIZE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "explanation", "actions"],
    "properties": {
        "headline": {"type": "string"},
        "explanation": {"type": "string"},
        "actions": {"type": "array", "items": {"type": "string"}},
    },
}

VERDICT_WORDS = {
    "scam": "This is very likely a SCAM.",
    "suspicious": "This looks SUSPICIOUS. Be careful.",
    "low_risk": "No strong signs of fraud were found.",
}


def _localize_prompt(analysis: Analysis, lang_name: str) -> str:
    flags = "\n".join(f"- {f.pattern_name}: {f.explanation}" for f in analysis.findings[:6]) or "- none"
    facts = "\n".join(f"- {k.label}: {k.value}" for k in analysis.key_facts[:8]) or "- none"
    actions = "\n".join(f"- {a.text}" for a in analysis.actions[:5])
    return f"""Write for an ordinary person in India who reads and speaks {lang_name}. This text will also be read aloud.

Verdict (already decided, do not change it): {VERDICT_WORDS[analysis.verdict.value]} Risk {analysis.risk_score}/100.
What it is: {analysis.summary}
Claims to be from: {analysis.claimed_sender or 'unclear'}
Red flags:
{flags}
Key facts:
{facts}
Recommended actions:
{actions}

Return JSON with, ALL in {lang_name} (native script; keep numbers, amounts, dates, UPI IDs and phone numbers as digits exactly as given):
- headline: one short sentence stating the verdict.
- explanation: 3-6 short, simple spoken sentences (max ~90 words): what this is, the main warning signs or key facts, and what to do. No markdown, no bullet symbols, no emojis.
- actions: the recommended actions, each one short sentence."""


async def localize(analysis: Analysis, language: str, gw: SarvamGateway) -> Localized:
    lang = languages.get(language)
    for model in (gw.settings.reasoning_model, gw.settings.chat_model):
        try:
            raw = await gw.chat_json(
                name="kavach_localize", model=model, schema=LOCALIZE_SCHEMA, max_tokens=2000, temperature=0.2,
                system=f"You are a kind, clear assistant who writes only in {lang.name}.",
                user=_localize_prompt(analysis, lang.name),
            )
        except SarvamError:
            continue
        loc = Localized(language=lang.code, headline=raw.get("headline", ""), explanation=raw.get("explanation", ""),
                        actions=[a for a in raw.get("actions") or [] if a], method="llm")
        # Guard observed failure: model answering in the wrong language/script.
        if loc.explanation and languages.is_in_language(loc.headline + " " + loc.explanation, lang.code):
            return loc
        log.warning("localisation came back in the wrong script for %s (model=%s)", lang.code, model)
    return await _translate_fallback(analysis, lang.code, gw)


async def _translate_fallback(analysis: Analysis, language: str, gw: SarvamGateway) -> Localized:
    headline = VERDICT_WORDS[analysis.verdict.value]
    explanation = analysis.summary
    actions = [a.text for a in analysis.actions[:5]]
    if language == "en-IN":
        return Localized(language=language, headline=headline, explanation=explanation, actions=actions, method="english")
    try:
        # Translate each part separately so the headline/explanation/actions structure can't be lost.
        parts = await asyncio.gather(*[gw.translate(t, "en-IN", language) for t in [headline, explanation, *actions]])
        return Localized(language=language, headline=parts[0], explanation=parts[1], actions=list(parts[2:]),
                         method="translated")
    except SarvamError:
        return Localized(language=language, headline=headline, explanation=explanation, actions=actions, method="english")


def speech_text(loc: Localized) -> str:
    return f"{loc.headline} {loc.explanation}".strip()


# ------------------------------------------------------------------------ Q&A
async def answer(question: str, source: Source, analysis: Analysis, history: list[dict], language: str,
                 gw: SarvamGateway) -> str:
    lang = languages.get(language)
    system = f"""You are Kavach, helping a person in India understand a {analysis.document_kind.replace('_', ' ')} they received.
Answer ONLY from the content and analysis below. If the answer is not there, say you cannot tell from this content and suggest how to verify through official channels.
Reply in {lang.name} (native script), in 1-4 short, simple sentences suitable for reading aloud. No markdown.
Never tell the person to pay, share an OTP/PIN, or call numbers found inside the content. For fraud, the official helpline is 1930 and the portal is cybercrime.gov.in.

Verdict: {analysis.verdict.value} (risk {analysis.risk_score}/100). Summary: {analysis.summary}
Red flags: {'; '.join(f.pattern_name + ' — ' + f.evidence.quote for f in analysis.findings[:8]) or 'none'}

CONTENT:
{source.for_prompt()[:20000]}"""
    messages = [{"role": "system", "content": system}, *history[-8:], {"role": "user", "content": question}]
    reply = await gw.chat_text(name="kavach_qa", messages=messages, max_tokens=2500)
    if language != "en-IN" and not languages.is_in_language(reply, lang.code, threshold=0.5):
        try:
            reply = await gw.translate(reply, "en-IN", lang.code)
        except SarvamError:
            pass
    return reply


# ------------------------------------------------------------------------ complaint
def complaint(source: Source, analysis: Analysis) -> str:
    """Deterministic draft for cybercrime.gov.in / 1930. Built from verified data only: no LLM prose."""
    now = datetime.now(timezone.utc).astimezone().strftime("%d %b %Y, %H:%M")
    by_kind: dict[str, list[str]] = {}
    for f in analysis.key_facts:
        by_kind.setdefault(f.label, []).append(f.value)
    lines = [
        "COMPLAINT DRAFT - suspected cyber fraud",
        "(Prepared with Kavach. Review and add your details before submitting at https://cybercrime.gov.in or when calling 1930.)",
        "",
        f"Date/time of report preparation: {now}",
        f"Medium: {analysis.document_kind.replace('_', ' ')}",
        f"Suspect claimed to be: {analysis.claimed_sender or 'not stated'}",
        f"Kavach risk assessment: {analysis.verdict.value.replace('_', ' ')} ({analysis.risk_score}/100)",
        "",
        "Suspect identifiers found in the content:",
    ]
    ident = [f"  - {label}: {', '.join(values)}" for label, values in by_kind.items()]
    lines += ident or ["  - none found"]
    lines += ["", "What happened (summary):", f"  {analysis.summary}", "", "Evidence (quoted exactly from the content):"]
    for f in analysis.findings:
        seg = source.segment(f.evidence.segment_id)
        where = ""
        if seg and seg.start is not None:
            where = f" [at {int(seg.start // 60)}:{int(seg.start % 60):02d}"
            where += f", speaker {seg.speaker}]" if seg.speaker else "]"
        elif seg and seg.page:
            where = f" [page {seg.page}]"
        lines.append(f"  - {f.pattern_name}{where}: \"{f.evidence.quote}\"")
    lines += [
        "",
        "Complainant details (fill in): Name / Mobile / Email / Address / Bank & transaction IDs if money was lost",
        "",
        "If money was transferred, call 1930 immediately: quick reporting improves the chance of freezing the funds.",
        "Suspected fraud calls/SMS/WhatsApp can also be reported on the Sanchar Saathi portal (Chakshu).",
    ]
    return "\n".join(lines)

from kavach import analyzer, languages
from kavach.ingest import from_text
from kavach.models import Verdict


async def test_analyse_verbatim_quotes_is_scam(settings, fake_gateway, scam_text):
    source = from_text(scam_text, settings)
    gw = fake_gateway()
    result = await analyzer.analyse(source, gw)

    assert result.verdict == Verdict.scam
    assert not result.degraded
    assert result.claimed_sender == "CBI"
    ai = {f.pattern_id: f for f in result.findings if f.source == "ai"}
    assert {"DIGITAL_ARREST", "PAYMENT_TO_UNOFFICIAL"} <= set(ai)
    for f in ai.values():
        seg = source.segment(f.evidence.segment_id)
        assert f.evidence.verified
        assert seg.text[f.evidence.start_char:f.evidence.end_char]
    # both AI and rules flagged these -> corroborated
    assert ai["DIGITAL_ARREST"].corroborated
    # findings sorted by contribution, one entry per pattern
    pids = [f.pattern_id for f in result.findings]
    assert len(pids) == len(set(pids))
    assert gw.json_calls and gw.json_calls[0]["name"] == "kavach_analysis"
    assert "[t2]" in gw.json_calls[0]["user"]


async def test_hallucinated_quote_is_rejected(settings, fake_gateway, scam_text, hallucinated_quote):
    source = from_text(scam_text, settings)
    result = await analyzer.analyse(source, fake_gateway())
    rejected = [r for r in result.rejected_claims if r.evidence.quote == hallucinated_quote]
    assert rejected and not rejected[0].evidence.verified
    assert not any(f.evidence.quote == hallucinated_quote for f in result.findings)
    # rejected claims never count toward the score
    assert all(b["source"] != "ai" or b["pattern_id"] != "SECRECY_ISOLATION" for b in result.score_breakdown)


async def test_unknown_pattern_ids_ignored(settings, fake_gateway, scam_text, scam_response):
    raw = scam_response()
    raw["findings"].append({"pattern_id": "MADE_UP", "segment_id": "t1", "quote": "सीबीआई अधिकारी",
                            "explanation": "?", "severity": "high"})
    result = await analyzer.analyse(from_text(scam_text, settings), fake_gateway(analysis=raw))
    assert all(f.pattern_id != "MADE_UP" for f in result.findings + result.rejected_claims)


async def test_llm_failure_is_degraded_rule_scoring(settings, fake_gateway, scam_text):
    source = from_text(scam_text, settings)
    result = await analyzer.analyse(source, fake_gateway(fail_json=True))
    assert result.degraded is True
    assert result.findings and all(f.source == "rule" for f in result.findings)
    assert result.risk_score > 0
    assert result.verdict in (Verdict.scam, Verdict.suspicious)
    assert result.actions and any("1930" in a.text for a in result.actions)
    assert result.rejected_claims == []
    # regex facts still extracted without the LLM
    assert any(k.value == "cbi.verify@okaxis" for k in result.key_facts)


async def test_benign_text_with_empty_llm_findings_is_low_risk(settings, fake_gateway):
    raw = {"document_kind": "bill_or_invoice", "claimed_sender": "TNEB", "summary": "An electricity bill.",
           "suspected_caller_speaker": "", "findings": [], "legitimacy_indicators": ["Official bill format"],
           "key_facts": [], "recommended_actions": []}
    source = from_text("Your electricity bill of Rs 450 is due on 15 October.", settings)
    result = await analyzer.analyse(source, fake_gateway(analysis=raw))
    assert result.verdict == Verdict.low_risk and result.risk_score == 0
    assert result.actions  # default actions when the LLM gave none


async def test_llm_key_facts_must_be_grounded(settings, fake_gateway, scam_text, scam_response):
    raw = scam_response()
    raw["key_facts"] = [
        {"kind": "reference_id", "label": "Case number", "value": "CBI/2026/7781", "segment_id": "t2"},  # not in source
        {"kind": "organisation", "label": "Agency", "value": "सीबीआई", "segment_id": "t1"},
    ]
    result = await analyzer.analyse(from_text(scam_text, settings), fake_gateway(analysis=raw))
    values = {k.value for k in result.key_facts}
    assert "CBI/2026/7781" not in values
    assert "सीबीआई" in values


async def test_localize_uses_llm_when_script_matches(settings, fake_gateway, scam_text):
    gw = fake_gateway()
    analysis = await analyzer.analyse(from_text(scam_text, settings), gw)
    loc = await analyzer.localize(analysis, "hi-IN", gw)
    assert loc.method == "llm" and loc.language == "hi-IN"
    assert languages.is_in_language(loc.explanation, "hi-IN")
    assert gw.translate_calls == []


async def test_localize_falls_back_to_translate_on_wrong_script(settings, fake_gateway, scam_text):
    english = {"headline": "This is a scam.", "explanation": "Do not pay anything. Call 1930.", "actions": ["Hang up"]}
    gw = fake_gateway(localized=english)
    analysis = await analyzer.analyse(from_text(scam_text, settings), gw)
    loc = await analyzer.localize(analysis, "ta-IN", gw)
    assert loc.method == "translated"
    assert loc.language == "ta-IN"
    assert gw.translate_calls and gw.translate_calls[0][1:] == ("en-IN", "ta-IN")
    assert languages.is_in_language(loc.headline + " " + loc.explanation, "ta-IN")
    # both models were tried before falling back
    assert [c["model"] for c in gw.json_calls if c["name"] == "kavach_localize"] == [
        settings.reasoning_model, settings.chat_model]


async def test_localize_english_target_when_llm_down(settings, fake_gateway, scam_text):
    gw = fake_gateway(fail_json=True)
    analysis = await analyzer.analyse(from_text(scam_text, settings), gw)
    loc = await analyzer.localize(analysis, "en-IN", gw)
    assert loc.method == "english"
    assert loc.headline == analyzer.VERDICT_WORDS[analysis.verdict.value]


async def test_answer_translates_wrong_language_reply(settings, fake_gateway, scam_text):
    gw = fake_gateway()
    source = from_text(scam_text, settings)
    analysis = await analyzer.analyse(source, gw)
    reply = await analyzer.answer("क्या यह असली है?", source, analysis, [], "hi-IN", gw)
    assert languages.is_in_language(reply, "hi-IN", threshold=0.5)
    assert gw.translate_calls == []


async def test_complaint_contains_identifiers_quotes_and_helpline(settings, fake_gateway, scam_text):
    source = from_text(scam_text, settings)
    analysis = await analyzer.analyse(source, fake_gateway())
    text = analyzer.complaint(source, analysis)
    assert "1930" in text
    assert "cybercrime.gov.in" in text
    assert "cbi.verify@okaxis" in text
    assert "+91 98765 43210" in text
    assert "गिरफ्तारी वारंट जारी हुआ है" in text
    assert "CBI" in text
    # rejected (hallucinated) claims must never be presented as evidence
    for r in analysis.rejected_claims:
        assert r.evidence.quote not in text


async def test_complaint_audio_timestamps(settings, fake_gateway):
    from kavach.models import Modality, Segment, Source
    source = Source(modality=Modality.audio, segments=[
        Segment(id="u1", text="आपके नाम पर गिरफ्तारी वारंट जारी हुआ है", start=75.0, end=79.0, speaker="1")])
    raw = {"document_kind": "phone_call", "claimed_sender": "", "summary": "s", "suspected_caller_speaker": "1",
           "findings": [{"pattern_id": "DIGITAL_ARREST", "segment_id": "u1", "quote": "गिरफ्तारी वारंट",
                         "explanation": "e", "severity": "high"}],
           "legitimacy_indicators": [], "key_facts": [], "recommended_actions": []}
    analysis = await analyzer.analyse(source, fake_gateway(analysis=raw))
    text = analyzer.complaint(source, analysis)
    assert "[at 1:15, speaker 1]" in text
    assert analysis.suspected_caller == "1"

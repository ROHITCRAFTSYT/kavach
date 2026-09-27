"""Deterministic, offline red-flag detectors and fact extractors.

These run on every input, cost nothing, and keep working if the LLM is down.
They also corroborate (or fail to corroborate) the LLM's findings, which is
reflected in the score. Lexicons include native-script transliterations of
English terms because Saaras normalises spoken "OTP"/"KYC" into the speaker's
script (e.g. Tamil: ஓடிபி, கேவைசி), which we observed in testing.
"""

from __future__ import annotations

import re
import unicodedata

from .models import Evidence, Finding, KeyFact, Segment
from .patterns import PATTERNS

_DROP = {"़", "়", "਼", "઼", "଼", "‌", "‍", "​"}  # nuktas, ZWJ/ZWNJ


def normalise(text: str) -> tuple[str, list[int]]:
    """Casefold + NFC + drop nuktas/joiners. Returns the normalised string and a map back to original offsets."""
    text = unicodedata.normalize("NFC", text)
    out, index = [], []
    for i, ch in enumerate(text):
        if ch in _DROP:
            continue
        for c in ch.casefold():
            out.append(c)
            index.append(i)
    return "".join(out), index


# pattern_id -> (rule severity, phrases). Phrases are matched after normalise().
LEXICON: dict[str, tuple[str, list[str]]] = {
    "DIGITAL_ARREST": ("high", [
        "digital arrest", "डिजिटल अरेस्ट", "डिजिटल गिरफ्तारी", "டிஜிட்டல் அரெஸ்ட்", "డిజిటల్ అరెస్ట్",
        "ডিজিটাল অ্যারেস্ট", "arrest warrant", "गिरफ्तारी वारंट", "गिरफ़्तारी वारंट", "अरेस्ट वारंट",
        "you will be arrested", "गिरफ्तार कर", "கைது செய்", "అరెస్ట్ చేస్తా", "গ্রেফতার কর",
    ]),
    "CREDENTIAL_REQUEST": ("high", [
        "otp", "one time password", "ओटीपी", "ஓடிபி", "ఓటీపీ", "ওটিপি", "ಒಟಿಪಿ", "ഒടിപി", "ઓટીપી", "ਓਟੀਪੀ",
        "cvv", "upi pin", "atm pin", "यूपीआई पिन", "एटीएम पिन", "पिन बता", "card number", "कार्ड नंबर",
        "net banking password", "पासवर्ड बता",
    ]),
    "REMOTE_ACCESS": ("high", [
        "anydesk", "any desk", "teamviewer", "team viewer", "quicksupport", "rustdesk", "screen share",
        "एनीडेस्क", "स्क्रीन शेयर", ".apk",
    ]),
    "PAYMENT_TO_UNOFFICIAL": ("medium", [
        "safe account", "सुरक्षित खाते", "सुरक्षित खाता", "secure account", "verification fee", "सत्यापन शुल्क",
        "clearance fee", "processing fee", "security deposit", "gift card", "bitcoin", "usdt", "crypto wallet",
    ]),
    "SECRECY_ISOLATION": ("medium", [
        "don't tell anyone", "do not tell anyone", "dont tell anyone", "keep this confidential",
        "किसी को न बताएं", "किसी को ना बताएं", "किसी को मत बता", "किसी को कुछ मत बता", "किसी से मत कह", "गोपनीय",
        "யாரிடமும் சொல்ல", "ఎవరికీ చెప్పవద్దు", "কাউকে বলবেন না",
        "do not disconnect", "don't disconnect", "कॉल बंद मत", "कॉल मत काट", "फोन मत काट",
    ]),
    "PARCEL_CONTRABAND": ("medium", [
        "parcel", "पार्सल", "பார்சல்", "పార్సెల్", "পার্সেল", "courier", "कूरियर", "fedex", "फेडेक्स",
        "drugs", "ड्रग्स", "fake passport", "फर्जी पासपोर्ट", "नकली पासपोर्ट",
    ]),
    "AUTHORITY_IMPERSONATION": ("low", [
        "cbi", "सीबीआई", "केंद्रीय अन्वेषण ब्यूरो", "enforcement directorate", "प्रवर्तन निदेशालय",
        "narcotics", "नारकोटिक्स", "customs", "कस्टम", "trai", "ट्राई", "cyber crime", "साइबर क्राइम",
        "crime branch", "क्राइम ब्रांच", "rbi", "आरबीआई", "reserve bank", "रिज़र्व बैंक", "रिजर्व बैंक",
        "supreme court", "सुप्रीम कोर्ट", "சிபிஐ", "சைபர் கிரைம்",
    ]),
    "KYC_ACCOUNT_BLOCK": ("medium", [
        "kyc", "केवाईसी", "கேவைசி", "కేవైసీ", "কেওয়াইসি", "ಕೆವೈಸಿ", "കെവൈസി", "કેવાયસી", "ਕੇਵਾਈਸੀ",
        "account will be blocked", "account will be suspended", "खाता बंद", "खाता ब्लॉक", "अकाउंट ब्लॉक",
        "sim will be blocked", "सिम बंद", "सिम ब्लॉक", "முடக்கப்படும்",
    ]),
    "PRIZE_REFUND_LURE": ("medium", [
        "lottery", "लॉटरी", "லாட்டரி", "kbc", "कौन बनेगा करोड़पति", "you have won", "you've won",
        "आपने जीत", "lucky draw", "prize money", "इनाम राशि", "cashback", "कैशबैक",
    ]),
    "JOB_INVESTMENT_LURE": ("medium", [
        "work from home", "part time job", "part-time job", "daily income", "earn daily", "like youtube videos",
        "guaranteed return", "guaranteed profit", "double your money", "पैसा डबल", "रोज़ कमाएं", "रोज कमाएं",
        "घर बैठे कमाएं", "trading tips", "ipo allotment",
    ]),
    "URGENCY_PRESSURE": ("low", [
        "immediately", "urgent", "तुरंत", "फौरन", "உடனே", "వెంటనే", "এখনই", "legal action",
        "कानूनी कार्रवाई", "वरना", "otherwise you",
    ]),
    "UNOFFICIAL_CONTACT": ("low", ["whatsapp", "व्हाट्सएप", "वॉट्सऐप"]),
}

_DEADLINE = re.compile(
    r"(?:(?:within|in|next)\s+)?(?:\d+|one|two|एक|दो|तीन)\s*"
    r"(?:hours?|hrs?|minutes?|mins?|घंटे|घंटों|मिनट|மணி\s*நேர|గంటల|ঘণ্টা)"
    r"(?:\s*(?:के भीतर|के अंदर|में))?",
    re.IGNORECASE,
)

# --- fact extractors (run on original text so values are exact) -----------------------
# Trailing context may be sentence punctuation ("... to cbi.verify@okaxis."), but not a domain (".com").
UPI_RE = re.compile(r"(?<![\w.@-])[a-zA-Z0-9][\w.-]{1,255}@[a-zA-Z][a-zA-Z0-9]{1,63}(?![\w@-]|\.[A-Za-z0-9])")
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>\"']+|\b(?:bit\.ly|tinyurl\.com|t\.ly|is\.gd|cutt\.ly|rb\.gy|shorturl\.at)/\S+", re.I)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:रुपये|रुपए|rupees|ரூபாய்|రూపాయలు|টাকা)", re.I)
SHORTENER_RE = re.compile(r"bit\.ly|tinyurl|t\.ly|is\.gd|cutt\.ly|rb\.gy|shorturl|\.apk\b", re.I)


def _evidence(seg: Segment, start: int, end: int) -> Evidence:
    return Evidence(segment_id=seg.id, quote=seg.text[start:end], score=100.0, verified=True,
                    start_char=start, end_char=end)


# Advisory sentences ("banks never ask for your OTP", "do not share your PIN") mention the same
# keywords as scams (a false positive we hit on a genuine Hindi bank SMS). The check is done per
# CLAUSE around each keyword hit, so "you will never get this offer again, share the OTP now"
# is still flagged: the advisory words and the demand sit in different clauses.
ADVISORY = [
    "never ask", "never share", "do not share", "don't share", "dont share", "never call", "never disclose",
    "not share", "not ask", "नहीं मांग", "नहीं माँग", "नहीं पूछ", "साझा न", "शेयर न", "साझा ना", "न बताएं",
    "ना बताएं", "न बताएँ", "nahi maang", "nahi mang", "nahin maang", "share na kare", "share mat kare",
    "share na karein", "kisi ko na bataye", "kisi ke saath share na", "பகிர வேண்டாம்", "கேட்பதில்லை", "షేర్ చేయవద్దు", "అడగదు", "শেয়ার করবেন না",
    "চায় না", "शेअर करू नका", "ಹಂಚಿಕೊಳ್ಳಬೇಡಿ", "പങ്കിടരുത്", "શેર ન કરો", "ਸਾਂਝਾ ਨਾ",
]
ADVISORY_SENSITIVE = {"CREDENTIAL_REQUEST", "KYC_ACCOUNT_BLOCK", "REMOTE_ACCESS", "AUTHORITY_IMPERSONATION"}
_CLAUSE_BREAK = re.compile(r"[,;:।.!?\n]|\s(?:but|just|and|और|लेकिन|बस|पर)\s", re.IGNORECASE)
_ADVISORY_NORM = [normalise(a)[0] for a in ADVISORY]


def clause_at(text: str, start: int, end: int) -> str:
    """The clause of `text` containing the span [start, end)."""
    left = 0
    for m in _CLAUSE_BREAK.finditer(text, 0, start):
        left = m.end()
    m = _CLAUSE_BREAK.search(text, end)
    return text[left : m.start() if m else len(text)]


def is_advisory(text: str) -> bool:
    norm, _ = normalise(text)
    return any(a in norm for a in _ADVISORY_NORM)


# Request verbs: a clause containing one of these is a demand, even inside an advisory sentence
# ("do not share this with anyone, just tell me the OTP").
_REQUEST = re.compile(
    r"\b(?:tell|share|send|give|provide|enter|type|read|forward|say)\b|बताइए|बताओ|बताइये|भेजिए|भेजो|दीजिए|"
    r"बोलिए|शेयर कीजिए|सொல்லுங்கள்|அனுப்புங்கள்|சொல்லவும்|చెప్పండి|పంపండి|বলুন|পাঠান|सांगा|पाठवा",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(r"[।.!?\n]")


def sentence_at(text: str, start: int, end: int) -> str:
    left = 0
    for m in _SENTENCE_BREAK.finditer(text, 0, start):
        left = m.end()
    m = _SENTENCE_BREAK.search(text, end)
    return text[left : m.start() if m else len(text)]


_CODE = re.compile(r"(?<!\d)\d{4,8}(?!\d)")
_VALIDITY = re.compile(r"valid|validity|मान्य|वैध|செல்லுபடி|చెల్లుబాటు|বৈধ", re.IGNORECASE)


def advisory_context(text: str, start: int, end: int) -> bool:
    """True when the keyword at [start, end) is part of a warning or an OTP delivery rather than a demand."""
    clause = clause_at(text, start, end)
    if is_advisory(clause):
        return True
    # OTP *delivery* ("Your OTP is 739204", "482913 is your OTP") carries the code itself; a scammer asks for it.
    if _CODE.search(clause) and not _REQUEST.search(clause):
        return True
    return not _REQUEST.search(clause) and is_advisory(sentence_at(text, start, end))


def _occurrences(norm: str, needle: str):
    pos = norm.find(needle)
    while pos != -1:
        yield pos
        pos = norm.find(needle, pos + 1)


def detect(segments: list[Segment]) -> list[Finding]:
    """Return at most one rule finding per pattern (the first qualifying hit), with exact evidence spans."""
    found: dict[str, Finding] = {}

    def add(pid: str, severity: str, seg: Segment, s: int, e: int, why: str) -> None:
        if pid in found:
            return
        p = PATTERNS[pid]
        found[pid] = Finding(pattern_id=pid, pattern_name=p.name, source="rule", severity=severity,
                             explanation=why, evidence=_evidence(seg, s, e))

    for seg in segments:
        norm, idx = normalise(seg.text)
        for pid, (severity, phrases) in LEXICON.items():
            if pid in found:
                continue
            for phrase in phrases:
                pn, _ = normalise(phrase)
                hit = None
                for pos in _occurrences(norm, pn):
                    if pn.isascii() and not _word_bounded(norm, pos, len(pn)):
                        continue  # e.g. "otp" inside "hotpot"
                    s, e = idx[pos], idx[pos + len(pn) - 1] + 1
                    if pid in ADVISORY_SENSITIVE and advisory_context(seg.text, s, e):
                        continue  # "bank never asks for your OTP"
                    hit = (s, e)
                    break
                if hit:
                    s, e = hit
                    add(pid, severity, seg, s, e, f"Contains the phrase “{seg.text[s:e]}”.")
                    break
        m = _DEADLINE.search(seg.text)
        if m and not _VALIDITY.search(clause_at(seg.text, m.start(), m.end())):  # "valid for 10 minutes" is no threat
            add("URGENCY_PRESSURE", "medium", seg, m.start(), m.end(), "Sets a deadline of hours or minutes.")
        for m in UPI_RE.finditer(seg.text):
            if not EMAIL_RE.fullmatch(m.group(0)):
                add("PAYMENT_TO_UNOFFICIAL", "high", seg, m.start(), m.end(),
                    "Asks for money to be sent to a UPI ID. Government agencies never collect fines or fees this way.")
                break
        if m := SHORTENER_RE.search(seg.text):
            add("SUSPICIOUS_LINK", "medium", seg, m.start(), m.end(), "Contains a shortened link or an app file.")
    return list(found.values())


def _word_bounded(text: str, pos: int, length: int) -> bool:
    before = text[pos - 1] if pos > 0 else " "
    after = text[pos + length] if pos + length < len(text) else " "
    return not before.isalnum() and not after.isalnum()


def extract_facts(segments: list[Segment]) -> list[KeyFact]:
    facts: list[KeyFact] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, label: str, value: str, seg: Segment) -> None:
        key = (kind, re.sub(r"\s+", "", value.lower()))
        if key not in seen:
            seen.add(key)
            facts.append(KeyFact(kind=kind, label=label, value=value.strip(), segment_id=seg.id))

    for seg in segments:
        for m in URL_RE.finditer(seg.text):
            add("link", "Link", m.group(0).rstrip(".,)"), seg)
        for m in EMAIL_RE.finditer(seg.text):
            add("contact", "Email", m.group(0), seg)
        for m in UPI_RE.finditer(seg.text):
            if not EMAIL_RE.fullmatch(m.group(0)):
                add("account_or_upi", "UPI ID", m.group(0), seg)
        for m in PHONE_RE.finditer(seg.text):
            add("contact", "Phone number", m.group(0), seg)
        for m in AMOUNT_RE.finditer(seg.text):
            add("amount", "Amount", m.group(0), seg)
    return facts

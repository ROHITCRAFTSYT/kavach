import pytest

from kavach import signals
from kavach.ingest import from_text
from kavach.models import Segment


def seg(text: str, sid: str = "t1") -> Segment:
    return Segment(id=sid, text=text)


def ids(findings) -> set[str]:
    return {f.pattern_id for f in findings}


def by_id(findings, pid):
    return next(f for f in findings if f.pattern_id == pid)


def test_hindi_digital_arrest_detects_core_patterns(scam_text, settings):
    source = from_text(scam_text, settings)
    found = signals.detect(source.segments)
    assert {"DIGITAL_ARREST", "SECRECY_ISOLATION", "PAYMENT_TO_UNOFFICIAL", "URGENCY_PRESSURE"} <= ids(found)
    assert all(f.source == "rule" and f.evidence.verified for f in found)
    assert "cbi.verify@okaxis" in by_id(found, "PAYMENT_TO_UNOFFICIAL").evidence.quote
    assert "2 घंटे" in by_id(found, "URGENCY_PRESSURE").evidence.quote


def test_deadline_phrase_detected():
    found = signals.detect([seg("2 घंटे के भीतर भुगतान करें")])
    assert "URGENCY_PRESSURE" in ids(found)


def test_one_finding_per_pattern():
    found = signals.detect([seg("OTP बताइए।", "t1"), seg("फिर से OTP बताइए।", "t2")])
    assert [f.pattern_id for f in found].count("CREDENTIAL_REQUEST") == 1
    assert by_id(found, "CREDENTIAL_REQUEST").evidence.segment_id == "t1"


def test_tamil_otp_is_credential_request():
    found = signals.detect([seg("உங்கள் ஓடிபி எண்ணை உடனே சொல்லுங்கள்")])
    assert "CREDENTIAL_REQUEST" in ids(found)
    assert by_id(found, "CREDENTIAL_REQUEST").evidence.quote == "ஓடிபி"


@pytest.mark.parametrize("text", [
    "आपके नाम पर गिरफ्तारी वारंट जारी हुआ है। 2 घंटे के भीतर ₹95,000 cbi.verify@okaxis पर भेजें।",
    "Your KYC has expired. Share the OTP immediately or your account will be blocked. Install AnyDesk.",
    "உங்கள் ஓடிபி சொல்லுங்கள், bit.ly/xyz पर क्लिक करें, गोपनीय रखें",
    "गिरफ़्तारी वारंट जारी है",  # nukta variant: offsets must map back to the original text
])
def test_evidence_spans_match_quotes(text):
    s = seg(text)
    found = signals.detect([s])
    assert found
    for f in found:
        ev = f.evidence
        assert ev.segment_id == "t1"
        assert s.text[ev.start_char:ev.end_char] == ev.quote


def test_nukta_variant_matches_lexicon():
    found = signals.detect([seg("आपके खिलाफ गिरफ़्तारी वारंट है")])
    assert "DIGITAL_ARREST" in ids(found)


def test_otp_not_matched_inside_word():
    found = signals.detect([seg("We had hotpot for dinner with friends")])
    assert "CREDENTIAL_REQUEST" not in ids(found)


def test_otp_word_detected_case_insensitive():
    assert "CREDENTIAL_REQUEST" in ids(signals.detect([seg("Please share the Otp you received")]))


def test_otp_detected_after_embedded_occurrence():
    found = signals.detect([seg("We ate hotpot. Now share your OTP please")])
    assert "CREDENTIAL_REQUEST" in ids(found)


def test_email_is_not_upi():
    s = seg("For queries write to help@sbi.co.in from your registered email")
    assert "PAYMENT_TO_UNOFFICIAL" not in ids(signals.detect([s]))
    facts = signals.extract_facts([s])
    assert not [f for f in facts if f.label == "UPI ID"]
    assert any(f.label == "Email" and f.value == "help@sbi.co.in" for f in facts)


def test_upi_followed_by_full_stop():
    s = seg("Pay ₹95,000 to cbi.verify@okaxis.")
    assert "PAYMENT_TO_UNOFFICIAL" in ids(signals.detect([s]))
    assert any(f.value == "cbi.verify@okaxis" for f in signals.extract_facts([s]))


def test_deadline_quote_has_no_leading_whitespace():
    found = signals.detect([seg("कृपया 2 घंटे के भीतर भुगतान करें")])
    q = by_id(found, "URGENCY_PRESSURE").evidence.quote
    assert q == q.strip()


def test_extract_facts():
    s = seg("Pay ₹95,000 to cbi.verify@okaxis now. Call +91 98765 43210 or open https://bit.ly/abc123 today")
    facts = signals.extract_facts([s])
    values = {(f.label, f.value) for f in facts}
    assert ("UPI ID", "cbi.verify@okaxis") in values
    assert ("Phone number", "+91 98765 43210") in values
    assert ("Amount", "₹95,000") in values
    assert ("Link", "https://bit.ly/abc123") in values
    assert all(f.segment_id == "t1" for f in facts)


def test_extract_facts_dedupes_across_segments():
    facts = signals.extract_facts([seg("Call 9876543210", "t1"), seg("Again call 98765 43210", "t2")])
    phones = [f for f in facts if f.label == "Phone number"]
    assert len(phones) == 1 and phones[0].segment_id == "t1"


def test_benign_text_has_no_findings():
    assert signals.detect([seg("Your electricity bill of Rs 450 is due on 15 October.")]) == []


@pytest.mark.parametrize("text", [
    "बैंक कभी भी आपका OTP या PIN नहीं मांगता।",
    "We will never ask for your OTP or PIN.",
    "Never share your OTP, CVV or UPI PIN with anyone.",
])
def test_advisory_negation_not_flagged(text):
    assert signals.is_advisory(text)
    assert "CREDENTIAL_REQUEST" not in ids(signals.detect([seg(text)]))


def test_advisory_only_suppresses_its_own_segment():
    found = signals.detect([seg("बैंक कभी भी आपका OTP नहीं मांगता।", "t1"), seg("अभी अपना OTP बताइए", "t2")])
    assert by_id(found, "CREDENTIAL_REQUEST").evidence.segment_id == "t2"


def test_non_advisory_text():
    assert not signals.is_advisory("अपना OTP तुरंत बताइए")
    assert not signals.is_advisory("Share the OTP you received")


@pytest.mark.parametrize("text", [
    "आपको कभी भी गिरफ्तार किया जा सकता है, तुरंत OTP बताइए",
    "You will never get this offer again, share the OTP now",
    "Do not share this with anyone, just tell me the OTP now",
])
def test_scam_demand_with_advisory_words_still_flagged(text):
    assert "CREDENTIAL_REQUEST" in ids(signals.detect([seg(text)]))


def test_normalise_offsets_map_back():
    text = "गिरफ़्तारी‍ OTP"
    norm, index = signals.normalise(text)
    assert "‍" not in norm and "़" not in norm
    assert len(norm) == len(index)
    assert all(0 <= i < len(text) for i in index)
    assert norm.endswith("otp")

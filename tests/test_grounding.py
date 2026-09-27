import pytest

from kavach.grounding import verify
from kavach.models import Segment

SEGMENTS = [
    Segment(id="t1", text="मैं सीबीआई अधिकारी बोल रहा हूँ।"),
    Segment(id="t2", text="आपके नाम पर गिरफ़्तारी वारंट जारी हुआ है।"),  # contains nukta (फ़)
    Segment(id="t3", text="यह मामला गोपनीय है, किसी को न बताएं।"),
]


def test_exact_quote_verified_with_span():
    ev = verify("किसी को न बताएं", "t3", SEGMENTS)
    assert ev.verified and ev.segment_id == "t3"
    assert ev.score >= 95
    assert SEGMENTS[2].text[ev.start_char:ev.end_char] == "किसी को न बताएं"


def test_surrounding_quote_marks_are_stripped():
    ev = verify("“किसी को न बताएं”", "t3", SEGMENTS)
    assert ev.verified and ev.quote == "किसी को न बताएं"


def test_nukta_and_zero_width_variants_verified():
    # quote without the nukta and with a stray zero-width joiner/space
    ev = verify("गिरफ्तारी‍ वारंट​ जारी", "t2", SEGMENTS)
    assert ev.verified and ev.segment_id == "t2"
    assert "वारंट" in SEGMENTS[1].text[ev.start_char:ev.end_char]


def test_precomposed_nukta_codepoint_verified():
    segs = [Segment(id="x", text="गिरफ़तारी वारंट")]  # precomposed U+095E
    assert verify("गिरफ्तारी वारंट", "x", segs).verified


def test_english_translation_not_verified():
    ev = verify("An arrest warrant has been issued in your name", "t2", SEGMENTS)
    assert not ev.verified
    assert ev.start_char is None and ev.end_char is None


def test_transliteration_not_verified():
    assert not verify("aapke naam par giraftari warrant jari hua hai", "t2", SEGMENTS).verified


def test_wrong_segment_cited_is_corrected():
    ev = verify("किसी को न बताएं", "t1", SEGMENTS)
    assert ev.verified
    assert ev.segment_id == "t3"
    assert SEGMENTS[2].text[ev.start_char:ev.end_char] == "किसी को न बताएं"


def test_unknown_segment_cited_is_corrected():
    ev = verify("सीबीआई अधिकारी", "zz9", SEGMENTS)
    assert ev.verified and ev.segment_id == "t1"


@pytest.mark.parametrize("quote", ["", "   ", "है", "OTP", "“ ”"])
def test_too_short_quote_not_verified(quote):
    ev = verify(quote, "t3", SEGMENTS)
    assert not ev.verified
    assert ev.score == 0.0


def test_quote_not_in_any_segment():
    assert not verify("आपका बिजली कनेक्शन काट दिया जाएगा", "t1", SEGMENTS).verified


def test_fabricated_long_quote_not_verified_by_short_segment():
    segs = [Segment(id="u1", text="नमस्ते"), Segment(id="u2", text="OTP")]
    ev = verify("please share your OTP with me right now for verification", "u2", segs)
    assert not ev.verified

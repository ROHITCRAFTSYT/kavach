"""Scoring properties. Rule-only weights are being retuned, so no exact numbers for rule findings."""

import itertools

from kavach import scoring
from kavach.models import Evidence, Finding, Verdict
from kavach.patterns import PATTERNS


def make(pid: str, *, source: str = "ai", severity: str = "high", verified: bool = True,
         seg: str = "t1") -> Finding:
    return Finding(
        pattern_id=pid, pattern_name=PATTERNS[pid].name, source=source, severity=severity,
        explanation="x", evidence=Evidence(segment_id=seg, quote="q", verified=verified, score=100.0 if verified else 10.0),
    )


def risk(findings) -> int:
    return scoring.score(findings)[0]


def test_empty_is_low_risk_zero():
    r, verdict, breakdown = scoring.score([])
    assert (r, verdict, breakdown) == (0, Verdict.low_risk, [])


def test_unverified_findings_contribute_nothing():
    unverified = [make(p, verified=False) for p in ("DIGITAL_ARREST", "CREDENTIAL_REQUEST", "PAYMENT_TO_UNOFFICIAL")]
    assert scoring.score(unverified) == (0, Verdict.low_risk, [])
    base = [make("URGENCY_PRESSURE", severity="low")]
    assert risk(base + unverified) == risk(base)


def test_digital_arrest_plus_payment_is_scam():
    r, verdict, breakdown = scoring.score([make("DIGITAL_ARREST"), make("PAYMENT_TO_UNOFFICIAL")])
    assert verdict == Verdict.scam
    assert r >= scoring.SCAM_THRESHOLD
    assert {b["pattern_id"] for b in breakdown} == {"DIGITAL_ARREST", "PAYMENT_TO_UNOFFICIAL"}


def test_single_low_signal_is_not_scam():
    assert scoring.score([make("UNOFFICIAL_CONTACT", severity="low")])[1] == Verdict.low_risk


def _monotonic(findings):
    for perm in itertools.islice(itertools.permutations(findings), 30):
        prev = 0
        for i in range(1, len(perm) + 1):
            cur = risk(list(perm[:i]))
            assert cur >= prev, [f.pattern_id for f in perm[:i]]
            prev = cur


def test_noisy_or_monotonic_ai_findings():
    _monotonic([
        make("URGENCY_PRESSURE", severity="low"), make("SECRECY_ISOLATION", severity="medium"),
        make("DIGITAL_ARREST"), make("PAYMENT_TO_UNOFFICIAL"), make("OTHER_RED_FLAG", severity="low"),
        make("DIGITAL_ARREST", severity="low", seg="t2"),
    ])


def test_noisy_or_monotonic_rule_findings():
    _monotonic([
        make("URGENCY_PRESSURE", source="rule", severity="low"), make("CREDENTIAL_REQUEST", source="rule"),
        make("KYC_ACCOUNT_BLOCK", source="rule", severity="medium"), make("SUSPICIOUS_LINK", source="rule", severity="medium"),
    ])


def test_risk_bounded():
    everything = [make(pid) for pid in PATTERNS]
    r, verdict, _ = scoring.score(everything)
    assert 0 <= r <= 100 and verdict == Verdict.scam


def test_duplicates_do_not_inflate():
    one = [make("CREDENTIAL_REQUEST")]
    many = [make("CREDENTIAL_REQUEST", seg=f"t{i}") for i in range(5)]
    assert risk(many) == risk(one)
    assert len(scoring.score(many)[2]) == 1


def test_duplicate_keeps_strongest():
    mixed = [make("CREDENTIAL_REQUEST", severity="low"), make("CREDENTIAL_REQUEST", severity="high")]
    assert risk(mixed) == risk([make("CREDENTIAL_REQUEST", severity="high")])


def test_severity_ordering():
    assert risk([make("DIGITAL_ARREST", severity="high")]) > risk([make("DIGITAL_ARREST", severity="medium")]) \
        > risk([make("DIGITAL_ARREST", severity="low")]) > 0


def test_rule_only_not_weightier_than_ai():
    for pid in ("DIGITAL_ARREST", "CREDENTIAL_REQUEST", "PAYMENT_TO_UNOFFICIAL"):
        assert risk([make(pid, source="rule")]) <= risk([make(pid, source="ai")])


def test_merge_marks_corroborated_without_duplicates():
    ai = [make("DIGITAL_ARREST"), make("SECRECY_ISOLATION", severity="medium")]
    rules = [make("DIGITAL_ARREST", source="rule"), make("URGENCY_PRESSURE", source="rule", severity="low")]
    merged = scoring.merge(ai, rules)
    pids = [f.pattern_id for f in merged]
    assert sorted(pids) == sorted(set(pids)) == ["DIGITAL_ARREST", "SECRECY_ISOLATION", "URGENCY_PRESSURE"]
    da = next(f for f in merged if f.pattern_id == "DIGITAL_ARREST")
    assert da.source == "ai" and da.corroborated
    assert not next(f for f in merged if f.pattern_id == "SECRECY_ISOLATION").corroborated
    assert next(f for f in merged if f.pattern_id == "URGENCY_PRESSURE").source == "rule"


def test_corroboration_does_not_lower_risk():
    ai = [make("DIGITAL_ARREST", severity="medium")]
    plain = risk(ai)
    merged = scoring.merge([make("DIGITAL_ARREST", severity="medium")], [make("DIGITAL_ARREST", source="rule")])
    assert risk(merged) >= plain


# ------------------------------------------------------------------ ai_ran discount
def test_rule_only_weaker_when_ai_ran():
    rule = make("CREDENTIAL_REQUEST", source="rule")
    assert scoring.contribution(rule, ai_ran=True) < scoring.contribution(rule, ai_ran=False)
    assert scoring.score([rule], ai_ran=True)[0] < scoring.score([rule], ai_ran=False)[0]


def test_ai_findings_unaffected_by_ai_ran():
    ai = [make("DIGITAL_ARREST"), make("PAYMENT_TO_UNOFFICIAL")]
    assert scoring.score(ai, ai_ran=True) == scoring.score(ai, ai_ran=False)


def test_monotonic_mixed_sources_with_ai_ran():
    findings = [make("DIGITAL_ARREST", source="rule"), make("SECRECY_ISOLATION", severity="medium"),
                make("URGENCY_PRESSURE", source="rule", severity="low"), make("PAYMENT_TO_UNOFFICIAL")]
    for flag in (True, False):
        prev = 0
        for i in range(1, len(findings) + 1):
            cur = scoring.score(findings[:i], ai_ran=flag)[0]
            assert cur >= prev
            prev = cur


def test_lone_rule_hit_not_scam_when_ai_disagreed():
    # The LLM read everything and flagged nothing; a single keyword hit must not produce a scam verdict.
    assert scoring.score([make("CREDENTIAL_REQUEST", source="rule")], ai_ran=True)[1] != Verdict.scam

"""Explainable risk scoring: the LLM finds evidence, arithmetic decides the verdict.

We deliberately do NOT let the LLM output the verdict or risk number: in testing
it produced self-contradictory pairs (verdict "suspicious" with risk 1, and
"suspicious" with risk 95). Instead each *verified* finding contributes its
pattern weight x severity factor, combined with noisy-OR:

    risk = 1 - prod(1 - w_i)

Rule-only findings count at half weight (they're context-free); a pattern
flagged by both the LLM and the rules gets a corroboration boost.
"""

from __future__ import annotations

from .models import Finding, Verdict
from .patterns import PATTERNS, SEVERITY_FACTOR

SCAM_THRESHOLD = 70
SUSPICIOUS_THRESHOLD = 35
RULE_DISCOUNT = 0.5
# When the LLM read the full context and chose not to flag a pattern, a lone keyword hit is weaker evidence.
RULE_ONLY_WITH_AI_DISCOUNT = 0.3
CORROBORATION_BOOST = 1.15
MAX_CONTRIBUTION = 0.95


def contribution(f: Finding, ai_ran: bool = False) -> float:
    w = PATTERNS[f.pattern_id].weight * SEVERITY_FACTOR[f.severity]
    if f.source == "rule":
        w *= RULE_ONLY_WITH_AI_DISCOUNT if ai_ran else RULE_DISCOUNT
    if f.corroborated:
        w *= CORROBORATION_BOOST
    return min(w, MAX_CONTRIBUTION)


def merge(ai: list[Finding], rules: list[Finding]) -> list[Finding]:
    """Keep all verified AI findings; add rule findings for patterns the AI missed; mark overlaps."""
    ai_patterns = {f.pattern_id for f in ai}
    rule_patterns = {f.pattern_id for f in rules}
    for f in ai:
        f.corroborated = f.pattern_id in rule_patterns
    return ai + [r for r in rules if r.pattern_id not in ai_patterns]


def score(findings: list[Finding], ai_ran: bool = False) -> tuple[int, Verdict, list[dict]]:
    """`ai_ran`: the LLM analysed this content (not degraded), so rule-only hits are discounted further."""
    def c_of(f: Finding) -> float:
        return contribution(f, ai_ran)

    # Only the strongest finding per pattern counts, so repetition can't inflate the score.
    best: dict[str, Finding] = {}
    for f in findings:
        if f.evidence.verified and (f.pattern_id not in best or c_of(f) > c_of(best[f.pattern_id])):
            best[f.pattern_id] = f
    survive = 1.0
    breakdown = []
    for f in sorted(best.values(), key=c_of, reverse=True):
        c = c_of(f)
        survive *= 1 - c
        breakdown.append({"pattern_id": f.pattern_id, "pattern": f.pattern_name, "source": f.source,
                          "severity": f.severity, "corroborated": f.corroborated, "weight": round(c, 3)})
    risk = round(100 * (1 - survive))
    if risk >= SCAM_THRESHOLD:
        verdict = Verdict.scam
    elif risk >= SUSPICIOUS_THRESHOLD:
        verdict = Verdict.suspicious
    else:
        verdict = Verdict.low_risk
    return risk, verdict, breakdown

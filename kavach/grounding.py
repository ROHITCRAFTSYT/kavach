"""Verify that every quote the LLM cites actually exists in the source.

In testing, Sarvam-105B sometimes paraphrased or translated "verbatim" quotes,
and OCR introduces small errors (e.g. misplaced vowel signs). We therefore use
fuzzy partial alignment on normalised text: a quote is *verified* when it aligns
with a span of the cited segment (or, failing that, any segment) above a
threshold. Unverified claims are shown to the user as such and never raise the
risk score.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from .models import Evidence, Segment
from .signals import normalise

VERIFY_THRESHOLD = 82.0
MIN_QUOTE_CHARS = 4


MAX_WINDOW = 3  # a quote may legitimately span up to 3 consecutive segments (e.g. STT phrase chunks)


def _align(quote_norm: str, window: list[Segment]) -> tuple[float, Segment | None, int | None, int | None]:
    """Align the quote against the concatenated text of consecutive segments.

    Returns (score, segment where the match starts, start, end) with start/end as char offsets into
    that segment's original text (clipped to it). If the quote is longer than the window text we use
    a FULL ratio, so a fabricated quote that merely contains a short segment does not verify.
    """
    text_norm = ""
    owners: list[tuple[Segment, int]] = []  # per normalised char: (segment, original index)
    for seg in window:
        if text_norm:
            text_norm += " "
            owners.append(owners[-1])
        norm, index = normalise(seg.text)
        text_norm += norm
        owners.extend((seg, i) for i in index)
    if not text_norm or not quote_norm:
        return 0.0, None, None, None
    if len(quote_norm) > len(text_norm):
        return fuzz.ratio(quote_norm, text_norm), window[0], 0, len(window[0].text)
    res = fuzz.partial_ratio_alignment(quote_norm, text_norm)
    if res is None or res.dest_end <= res.dest_start:
        return 0.0, None, None, None
    seg, start = owners[res.dest_start]
    end_seg, end_idx = owners[min(res.dest_end, len(owners)) - 1]
    end = end_idx + 1 if end_seg is seg else len(seg.text)
    return res.score, seg, start, end


def verify(quote: str, segment_id: str | None, segments: list[Segment]) -> Evidence:
    quote = (quote or "").strip().strip("\"'“”‘’")
    quote_norm, _ = normalise(quote)
    evidence = Evidence(segment_id=segment_id, quote=quote)
    if len(quote_norm.strip()) < MIN_QUOTE_CHARS:
        return evidence

    cited = next((i for i, s in enumerate(segments) if s.id == segment_id), None)
    order = ([cited] if cited is not None else []) + [i for i in range(len(segments)) if i != cited]
    best: tuple[float, Segment | None, int | None, int | None] = (0.0, None, None, None)
    for i in order:
        for size in range(1, MAX_WINDOW + 1):
            if i + size > len(segments):
                break
            result = _align(quote_norm, segments[i : i + size])
            if result[0] > best[0] + 0.01:  # prefer the smallest window / cited segment on ties
                best = result
            if result[0] >= 99.5:
                break
        if i == cited and best[0] >= VERIFY_THRESHOLD:
            break  # the model cited the right place; don't hunt further

    score, seg, start, end = best
    evidence.score = round(score, 1)
    if seg is not None and score >= VERIFY_THRESHOLD:
        evidence.verified = True
        evidence.segment_id = seg.id
        evidence.start_char, evidence.end_char = start, end
    return evidence

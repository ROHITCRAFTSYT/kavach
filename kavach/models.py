"""Domain models shared by the pipeline, the API and the eval harness."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Modality(str, Enum):
    text = "text"
    image = "image"
    pdf = "pdf"
    audio = "audio"


class Segment(BaseModel):
    """One addressable unit of source content: an OCR block, a call utterance, a text line.

    Every piece of evidence the system shows is tied back to a Segment, so the
    UI can highlight the exact region of the image or seek to the exact moment
    in the recording.
    """

    id: str
    text: str
    page: int | None = None
    bbox: list[float] | None = None  # normalised [x1, y1, x2, y2] on the page image
    start: float | None = None  # seconds, audio only
    end: float | None = None
    speaker: str | None = None


class Source(BaseModel):
    modality: Modality
    language: str | None = None
    language_confidence: float | None = None
    segments: list[Segment]
    filename: str | None = None
    duration: float | None = None
    pages: int | None = None

    @property
    def text(self) -> str:
        return "\n".join(s.text for s in self.segments)

    def segment(self, seg_id: str | None) -> Segment | None:
        return next((s for s in self.segments if s.id == seg_id), None)

    def for_prompt(self) -> str:
        lines = []
        for s in self.segments:
            tag = s.id
            if s.speaker is not None:
                tag += f" speaker={s.speaker}"
            if s.start is not None:
                tag += f" t={s.start:.0f}s"
            if s.page is not None:
                tag += f" page={s.page}"
            lines.append(f"[{tag}] {s.text}")
        return "\n".join(lines)


Severity = Literal["high", "medium", "low"]


class Evidence(BaseModel):
    segment_id: str | None = None
    quote: str
    score: float = 0.0  # fuzzy match score 0..100 against the source
    verified: bool = False
    start_char: int | None = None  # span of the quote inside the segment text
    end_char: int | None = None


class Finding(BaseModel):
    """A red flag, from either the LLM (source='ai') or the rule engine (source='rule')."""

    pattern_id: str
    pattern_name: str
    source: Literal["ai", "rule"]
    severity: Severity
    explanation: str
    evidence: Evidence
    corroborated: bool = False  # flagged by both AI and rules


class KeyFact(BaseModel):
    kind: str
    label: str
    value: str
    segment_id: str | None = None


class Action(BaseModel):
    text: str
    priority: Literal["now", "soon", "optional"] = "soon"


class Localized(BaseModel):
    language: str
    headline: str
    explanation: str
    actions: list[str] = Field(default_factory=list)
    method: Literal["llm", "translated", "english"] = "llm"


class Verdict(str, Enum):
    scam = "scam"
    suspicious = "suspicious"
    low_risk = "low_risk"


class Analysis(BaseModel):
    document_kind: str
    claimed_sender: str
    summary: str
    findings: list[Finding]
    rejected_claims: list[Finding] = Field(default_factory=list)  # AI claims not found in source
    legitimacy_indicators: list[str] = Field(default_factory=list)
    key_facts: list[KeyFact] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    suspected_caller: str | None = None
    risk_score: int
    verdict: Verdict
    score_breakdown: list[dict] = Field(default_factory=list)
    degraded: bool = False  # True when the LLM was unavailable and only rules ran

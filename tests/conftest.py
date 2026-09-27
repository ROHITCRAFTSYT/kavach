"""Shared fixtures for the offline Kavach test suite.

No test may touch the network: SARVAM_API_KEY is stubbed before any kavach import,
all Sarvam calls go through FakeGateway, and outbound non-loopback sockets are blocked.
"""

from __future__ import annotations

import io
import ipaddress
import os
import socket
import struct
import wave

os.environ.setdefault("SARVAM_API_KEY", "test-key")

import pytest  # noqa: E402

from kavach.config import get_settings  # noqa: E402
from kavach.sarvam import SarvamError  # noqa: E402

# A Hindi "digital arrest" message. Segments after ingest.from_text:
#   t1 authority claim, t2 arrest warrant, t3 secrecy, t4 deadline + payment, t5 phone
SCAM_TEXT_HI = (
    "मैं सीबीआई अधिकारी बोल रहा हूँ। "
    "आपके नाम पर गिरफ्तारी वारंट जारी हुआ है। "
    "यह मामला गोपनीय है, किसी को न बताएं। "
    "2 घंटे के भीतर ₹95,000 cbi.verify@okaxis पर भेजें। "
    "संपर्क करें +91 98765 43210"
)

HALLUCINATED_QUOTE = "Do not tell anyone about this"


def scam_llm_response() -> dict:
    """What a well-behaved LLM returns for SCAM_TEXT_HI, plus one translated (hallucinated) quote."""
    return {
        "document_kind": "sms_or_chat",
        "claimed_sender": "CBI",
        "summary": "Someone claiming to be CBI says there is an arrest warrant and demands money via UPI.",
        "suspected_caller_speaker": "",
        "findings": [
            {"pattern_id": "DIGITAL_ARREST", "segment_id": "t2", "quote": "गिरफ्तारी वारंट जारी हुआ है",
             "explanation": "Threatens arrest.", "severity": "high"},
            {"pattern_id": "PAYMENT_TO_UNOFFICIAL", "segment_id": "t4", "quote": "₹95,000 cbi.verify@okaxis पर भेजें",
             "explanation": "Money to a UPI id.", "severity": "high"},
            {"pattern_id": "SECRECY_ISOLATION", "segment_id": "t3", "quote": HALLUCINATED_QUOTE,
             "explanation": "Secrecy (translated quote).", "severity": "medium"},
        ],
        "legitimacy_indicators": [],
        "key_facts": [],
        "recommended_actions": [
            {"text": "Do not pay. Call 1930.", "priority": "now"},
        ],
    }


HINDI_LOCALIZED = {
    "headline": "यह लगभग निश्चित रूप से धोखाधड़ी है।",
    "explanation": "कोई पैसा न भेजें। किसी को ओटीपी न बताएं। तुरंत 1930 पर कॉल करें।",
    "actions": ["पैसे न भेजें", "1930 पर कॉल करें"],
}


def make_wav(seconds: float, rate: int = 8000, channels: int = 1) -> bytes:
    """A tiny silent-ish 16-bit PCM WAV."""
    n = int(seconds * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 100) * n * channels)
    return buf.getvalue()


class FakeGateway:
    """Duck-typed stand-in for SarvamGateway. Records calls; never touches the network."""

    def __init__(self, *, analysis: dict | None = None, localized: dict | None = None,
                 fail_json: bool = False, translate_prefix: str = "தமிழ் மொழிபெயர்ப்பு"):
        self.settings = get_settings()
        self.analysis = analysis if analysis is not None else scam_llm_response()
        self.localized = localized if localized is not None else HINDI_LOCALIZED
        self.fail_json = fail_json
        self.translate_prefix = translate_prefix
        self.json_calls: list[dict] = []
        self.translate_calls: list[tuple[str, str, str]] = []
        self.tts_calls: list[tuple[str, str]] = []

    async def chat_json(self, *, name, system, user, schema, model=None, **kwargs) -> dict:
        self.json_calls.append({"name": name, "model": model, "user": user})
        if self.fail_json:
            raise SarvamError("The AI service is temporarily unavailable. Please try again.", status=503)
        if name == "kavach_analysis":
            return dict(self.analysis)
        if name == "kavach_localize":
            return dict(self.localized)
        raise AssertionError(f"unexpected chat_json name {name}")

    async def chat_text(self, *, name, messages, model=None, **kwargs) -> str:
        return "यह धोखाधड़ी है। 1930 पर कॉल करें।"

    async def translate(self, text: str, source: str, target: str) -> str:
        self.translate_calls.append((text, source, target))
        return "\n".join(f"{self.translate_prefix} {i}" for i, _ in enumerate(text.split("\n")))

    async def tts(self, text: str, language: str, speaker: str | None = None, pace: float = 0.95) -> bytes:
        self.tts_calls.append((text, language))
        return make_wav(0.2)

    async def identify_language(self, text: str) -> str | None:
        return None


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly if anything tries to reach a non-loopback host."""
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        try:
            if isinstance(host, str) and not ipaddress.ip_address(host).is_loopback:
                raise RuntimeError(f"network access blocked in tests: {address!r}")
        except ValueError:  # hostname, not an IP literal
            if host not in ("localhost",):
                raise RuntimeError(f"network access blocked in tests: {address!r}") from None
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def wav():
    return make_wav


@pytest.fixture
def fake_gateway():
    return FakeGateway


@pytest.fixture
def scam_text():
    return SCAM_TEXT_HI


@pytest.fixture
def scam_response():
    return scam_llm_response


@pytest.fixture
def hallucinated_quote():
    return HALLUCINATED_QUOTE

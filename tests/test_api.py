import base64
import json

import pytest
from fastapi.testclient import TestClient

import kavach.app as app_module
from kavach.store import RateLimiter


@pytest.fixture
def fake(fake_gateway):
    return fake_gateway()


@pytest.fixture
def client(monkeypatch, fake, settings):
    monkeypatch.setattr(app_module, "gateway", fake)
    monkeypatch.setattr(app_module, "limiter", RateLimiter(10_000))
    with TestClient(app_module.app) as c:
        yield c


def _events(resp) -> list[dict]:
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def _analyze(client, text):
    resp = client.post("/api/analyze", data={"text": text, "language": "auto"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    return _events(resp)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_config(client):
    body = client.get("/api/config").json()
    assert len(body["languages"]) == 23
    assert {"code", "name", "native", "tts"} <= set(body["languages"][0])
    assert body["samples"] and all("id" in s and "kind" in s for s in body["samples"])
    assert body["limits"]["max_upload_mb"] > 0


def test_security_headers(client):
    r = client.get("/api/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_analyze_text_streams_ndjson(client, fake, scam_text):
    events = _analyze(client, scam_text)
    types = [e["type"] for e in events]
    assert types[-1] == "done"
    assert "error" not in types
    for t in ("stage", "source", "analysis", "localized", "speech", "trace"):
        assert t in types, t
    assert types.index("source") < types.index("analysis") < types.index("localized")

    source = next(e for e in events if e["type"] == "source")
    assert source["language"] == "hi-IN"
    assert source["source"]["segments"][0]["id"] == "t1"

    analysis = next(e for e in events if e["type"] == "analysis")["analysis"]
    assert analysis["verdict"] == "scam"
    assert analysis["rejected_claims"]

    localized = next(e for e in events if e["type"] == "localized")["localized"]
    assert localized["method"] == "llm" and localized["language"] == "hi-IN"

    stages = [(e["id"], e["status"]) for e in events if e["type"] == "stage"]
    assert ("read", "done") in stages and ("check", "done") in stages and ("explain", "done") in stages
    assert fake.tts_calls and fake.tts_calls[0][1] == "hi-IN"


def test_analyze_explicit_language(client, scam_text):
    resp =client.post("/api/analyze", data={"text": scam_text, "language": "ta-IN"})
    events = _events(resp)
    assert next(e for e in events if e["type"] == "source")["language"] == "ta-IN"
    # Hindi fake localisation is the wrong script for Tamil -> translated fallback
    assert next(e for e in events if e["type"] == "localized")["localized"]["method"] == "translated"
    assert events[-1]["type"] == "done"


def test_analyze_llm_down_still_completes(client, monkeypatch, fake_gateway, scam_text):
    monkeypatch.setattr(app_module, "gateway", fake_gateway(fail_json=True))
    events = _analyze(client, scam_text)
    assert events[-1]["type"] == "done"
    analysis = next(e for e in events if e["type"] == "analysis")["analysis"]
    assert analysis["degraded"] is True
    assert analysis["verdict"] in ("scam", "suspicious")


def test_analyze_text_sample(client):
    events = _events(client.post("/api/analyze", data={"sample": "text:job"}))
    assert events[-1]["type"] == "done"


def test_analyze_unknown_sample_404(client):
    r = client.post("/api/analyze", data={"sample": "nope"})
    assert r.status_code == 404 and "error" in r.json()


def test_analyze_no_input_400(client):
    r = client.post("/api/analyze", data={"language": "auto"})
    assert r.status_code == 400
    body = r.json()
    assert set(body) == {"error"} and body["error"]


def test_analyze_blank_text_400(client):
    r = client.post("/api/analyze", data={"text": "   "})
    assert r.status_code == 400 and "error" in r.json()


def test_analyze_unsupported_file_415(client):
    r = client.post("/api/analyze", files={"file": ("x.bin", b"this is not a supported media file", "application/octet-stream")})
    assert r.status_code == 415
    assert "Unsupported" in r.json()["error"]


def test_analyze_heic_415(client):
    r = client.post("/api/analyze", files={"file": ("p.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32, "image/heic")})
    assert r.status_code == 415 and "HEIC" in r.json()["error"]


def test_rate_limit_429(client, monkeypatch):
    monkeypatch.setattr(app_module, "limiter", RateLimiter(1))
    assert client.post("/api/analyze", data={}).status_code == 400
    r = client.post("/api/analyze", data={})
    assert r.status_code == 429 and "error" in r.json()


def _context(events) -> dict:
    source = next(e for e in events if e["type"] == "source")["source"]
    analysis = next(e for e in events if e["type"] == "analysis")["analysis"]
    return {"source": source, "analysis": analysis}


def test_removed_session_endpoints_are_gone(client):
    for path in ("/api/sessions/bad/speech", "/api/sessions/bad/complaint"):
        assert client.get(path).status_code in (404, 405), path


def test_stateless_followups(client, scam_text):
    events = _analyze(client, scam_text)
    speech = next(e for e in events if e["type"] == "speech")
    assert speech["mime"] == "audio/wav"
    assert base64.b64decode(speech["audio_b64"]).startswith(b"RIFF")
    ctx = _context(events)

    r = client.post("/api/complaint", json=ctx)
    assert r.status_code == 200
    assert "1930" in r.text and "cbi.verify@okaxis" in r.text

    history = [{"role": "user", "content": "पहला सवाल"}, {"role": "assistant", "content": "जवाब"}]
    r = client.post("/api/ask", data={"question": "क्या यह असली है?", "context": json.dumps({**ctx, "history": history})})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] and base64.b64decode(body["audio_b64"]).startswith(b"RIFF")


def test_ask_rejects_bad_context(client):
    r = client.post("/api/ask", data={"question": "hi", "context": "{not json"})
    assert r.status_code == 400 and "error" in r.json()
    r = client.post("/api/ask", data={"question": "hi", "context": "x" * 700_000})
    assert r.status_code == 413
    r = client.post("/api/ask", data={"question": "hi"})
    assert r.status_code == 422  # context is required


def test_ask_empty_question_400(client, scam_text):
    ctx = _context(_analyze(client, scam_text))
    r = client.post("/api/ask", data={"question": "  ", "context": json.dumps(ctx)})
    assert r.status_code == 400 and "error" in r.json()


def test_complaint_rejects_invalid_body(client):
    assert client.post("/api/complaint", json={"source": {}}).status_code == 422


def test_genuine_bank_sample_is_low_risk(client, monkeypatch, fake_gateway):
    no_flags = {"document_kind": "bank_communication", "claimed_sender": "Bank", "summary": "A debit alert.",
                "suspected_caller_speaker": "", "findings": [], "legitimacy_indicators": ["Advises never sharing OTP"],
                "key_facts": [], "recommended_actions": []}
    monkeypatch.setattr(app_module, "gateway", fake_gateway(analysis=no_flags))
    events = _events(client.post("/api/analyze", data={"sample": "text:bank"}))
    assert events[-1]["type"] == "done"
    analysis = next(e for e in events if e["type"] == "analysis")["analysis"]
    assert analysis["verdict"] == "low_risk"
    assert all(f["pattern_id"] != "CREDENTIAL_REQUEST" for f in analysis["findings"])

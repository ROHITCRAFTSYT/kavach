"""HTTP API + static web app.

    uvicorn kavach.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import tempfile
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from fastapi.staticfiles import StaticFiles

from . import analyzer, ingest, languages, pipeline
from .config import get_settings
from .models import Analysis, Modality, Source
from .sarvam import SarvamError, SarvamGateway
from .store import RateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("kavach")

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SAMPLES = ROOT / "samples"

settings = get_settings()
gateway = SarvamGateway(settings)
limiter = RateLimiter(settings.rate_limit_per_minute)

app = FastAPI(title="Kavach", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

SAMPLE_CATALOG = [
    {"id": "scam_call_hi.wav", "title": "“Digital arrest” call", "subtitle": "Hindi · 45 s · 2 speakers", "kind": "audio"},
    {"id": "kyc_voicenote_ta.wav", "title": "Bank KYC voice note", "subtitle": "Tamil · 16 s", "kind": "audio"},
    {"id": "cbi_notice_hi.png", "title": "“CBI” notice", "subtitle": "Hindi · photo", "kind": "document"},
    {"id": "power_notice_ta.png", "title": "Electricity notice", "subtitle": "Tamil · photo", "kind": "document"},
    {"id": "text:job", "title": "Part-time job SMS", "subtitle": "English", "kind": "text",
     "text": "Congratulations! You are selected for a part-time job. Earn Rs 3,000 daily by liking YouTube videos. "
             "Pay a refundable registration fee of Rs 499 to hr.desk@ybl and contact our HR on WhatsApp +91 91234 56789. "
             "Offer valid for 30 minutes only."},
    {"id": "text:bank", "title": "Genuine bank SMS", "subtitle": "Hindi", "kind": "text",
     "text": "प्रिय ग्राहक, आपके खाते XX4321 से 26-09-2026 को ₹1,250.00 डेबिट किए गए। यदि यह लेनदेन आपने नहीं किया है, "
             "तो कृपया अपने बैंक की आधिकारिक हेल्पलाइन पर संपर्क करें। बैंक कभी भी आपका OTP या PIN नहीं मांगता।"},
]


# ------------------------------------------------------------------ middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(self), geolocation=()")
    if not request.url.path.startswith("/api/docs"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
            "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
            "script-src 'self'; connect-src 'self'",
        )
    return response


TRUST_PROXY = os.environ.get("KAVACH_TRUST_PROXY", "").lower() in ("1", "true", "yes")


def client_id(request: Request) -> str:
    # X-Forwarded-For is client-controlled; only honour it behind a proxy we run (KAVACH_TRUST_PROXY=1).
    forwarded = request.headers.get("x-forwarded-for") if TRUST_PROXY else None
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def _rate_limit(request: Request) -> None:
    if not limiter.allow(client_id(request)):
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")


# ------------------------------------------------------------------ API
@app.get("/api/health")
async def health():
    return {"status": "ok", "stateless": True, "models": {
        "reasoning": settings.reasoning_model, "chat": settings.chat_model,
        "stt": settings.stt_model, "tts": settings.tts_model, "vision": "sarvam-vision (doc-ai v1)"}}


@app.get("/api/config")
async def config():
    return {
        "languages": [{"code": l.code, "name": l.name, "native": l.native, "tts": l.tts} for l in languages.LANGUAGES.values()],
        "samples": SAMPLE_CATALOG,
        "limits": {"max_upload_mb": settings.max_upload_mb, "max_audio_seconds": settings.max_audio_seconds},
    }


@app.post("/api/analyze")
async def analyze(request: Request, file: UploadFile | None = File(None), text: str | None = Form(None),
                  language: str = Form("auto"), sample: str | None = Form(None)):
    _rate_limit(request)
    data, filename = None, ""
    if sample:
        entry = next((s for s in SAMPLE_CATALOG if s["id"] == sample), None)
        if not entry:
            raise HTTPException(404, "Unknown sample.")
        if entry["kind"] == "text":
            text = entry["text"]
        else:
            data, filename = (SAMPLES / entry["id"]).read_bytes(), entry["id"]
    elif file is not None:
        data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        filename = file.filename or "upload"
    if not data and not (text and text.strip()):
        raise HTTPException(400, "Provide a file, a sample, or some text.")

    kind_hint = None
    if data:
        try:
            kind_hint = "audio" if ingest.sniff(data, filename) == Modality.audio else "document"
        except ingest.InputError as exc:
            raise HTTPException(415, str(exc)) from None

    async def stream():
        async for event in pipeline.run(gw=gateway, settings=settings, text=text, data=data,
                                        filename=filename, language=language, kind_hint=kind_hint):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


MAX_CONTEXT_BYTES = 600_000


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class Context(BaseModel):
    """What the browser sends back: the server keeps no state between requests."""
    source: Source
    analysis: Analysis
    history: list[Turn] = Field(default_factory=list, max_length=20)


def _context(raw: str) -> Context:
    if len(raw.encode()) > MAX_CONTEXT_BYTES:
        raise HTTPException(413, "This result is too large to ask about.")
    try:
        return Context.model_validate_json(raw)
    except ValidationError:
        raise HTTPException(400, "Invalid result context. Please analyse the content again.") from None


@app.post("/api/ask")
async def ask(request: Request, context: str = Form(...), question: str | None = Form(None),
              audio: UploadFile | None = File(None), language: str | None = Form(None)):
    _rate_limit(request)
    ctx = _context(context)
    lang = languages.get(language or ctx.source.language)
    try:
        if audio is not None:
            question = await _transcribe_question(await audio.read(10 * 1024 * 1024), audio.filename or "q.webm")
        if not question or not question.strip():
            raise HTTPException(400, "Please ask a question.")
        question = question.strip()[:1000]
        history = [t.model_dump() for t in ctx.history]
        reply = await analyzer.answer(question, ctx.source, ctx.analysis, history, lang.code, gateway)
    except SarvamError as exc:
        raise HTTPException(503, exc.user_message) from None
    except ingest.InputError as exc:
        raise HTTPException(400, str(exc)) from None
    audio_b64 = None
    if lang.tts:
        try:
            audio_b64 = base64.b64encode(await gateway.tts(reply, lang.code, lang.speaker)).decode()
        except SarvamError:
            pass
    return {"question": question, "answer": reply, "language": lang.code, "mime": "audio/wav", "audio_b64": audio_b64}


async def _transcribe_question(data: bytes, filename: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        src, wav = Path(tmp) / ("q" + (Path(filename).suffix or ".webm")), Path(tmp) / "q.wav"
        src.write_bytes(data)
        duration = await asyncio.to_thread(ingest.normalise_audio, src, wav, 29)
        if duration < 0.4:
            raise ingest.InputError("I couldn't hear a question. Please try again.")
        result = await gateway.transcribe(wav)
    return (result.get("transcript") or "").strip()


class ComplaintRequest(BaseModel):
    source: Source
    analysis: Analysis


@app.post("/api/complaint", response_class=PlainTextResponse)
async def complaint(request: Request, body: ComplaintRequest = Body(...)):
    if int(request.headers.get("content-length") or 0) > MAX_CONTEXT_BYTES:
        raise HTTPException(413, "Request too large.")
    return analyzer.complaint(body.source, body.analysis)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# ------------------------------------------------------------------ static
app.mount("/samples", StaticFiles(directory=SAMPLES), name="samples")
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})

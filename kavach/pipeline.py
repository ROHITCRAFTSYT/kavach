"""End-to-end orchestration, streamed as progress events so the UI stays alive during long jobs."""

from __future__ import annotations

import base64
import logging
import time
import uuid
from collections.abc import AsyncIterator

from . import analyzer, languages, trace
from .config import Settings
from .ingest import InputError, ingest
from .models import Modality
from .sarvam import SarvamError, SarvamGateway

log = logging.getLogger("kavach.pipeline")


def _stage(stage_id: str, label: str, status: str, **extra) -> dict:
    return {"type": "stage", "id": stage_id, "label": label, "status": status, **extra}


def resolve_language(requested: str | None, detected: str | None) -> str:
    if requested and requested != "auto" and requested in languages.LANGUAGES:
        return requested
    if detected in languages.LANGUAGES:
        return detected
    return languages.DEFAULT_LANGUAGE


async def run(*, gw: SarvamGateway, settings: Settings, text: str | None,
              data: bytes | None, filename: str, language: str | None, kind_hint: str | None = None) -> AsyncIterator[dict]:
    request_id = uuid.uuid4().hex[:12]
    tr = trace.start(request_id)
    t0 = time.perf_counter()
    read_label = {
        "audio": "Listening to the recording (Saaras v3)",
        "document": "Reading the document (Sarvam Vision)",
    }.get(kind_hint or "", "Reading the message")
    try:
        yield _stage("read", read_label, "active")
        source, _ = await ingest(gw=gw, settings=settings, text=text, data=data, filename=filename)
        target = resolve_language(language, source.language)
        yield _stage("read", read_label, "done")
        # Stateless: the client keeps source + analysis and sends them back for Q&A / complaint,
        # so any serverless instance can serve any request and nothing is stored server-side.
        yield {"type": "source", "session_id": request_id, "language": target,
               "source": source.model_dump(mode="json")}

        yield _stage("check", "Checking for fraud patterns (Sarvam-105B + rules)", "active")
        analysis = await analyzer.analyse(source, gw)
        yield _stage("check", "Checking for fraud patterns (Sarvam-105B + rules)", "done")
        yield {"type": "analysis", "analysis": analysis.model_dump(mode="json")}

        lang = languages.get(target)
        explain_label = f"Explaining in {lang.name}"
        yield _stage("explain", explain_label, "active")
        localized = await analyzer.localize(analysis, target, gw)
        yield _stage("explain", explain_label, "done")
        yield {"type": "localized", "localized": localized.model_dump(mode="json")}

        if lang.tts:
            yield _stage("speak", f"Recording a voice explanation (Bulbul v3, {lang.name})", "active")
            try:
                wav = await gw.tts(analyzer.speech_text(localized), lang.code, lang.speaker)
                yield _stage("speak", f"Recording a voice explanation (Bulbul v3, {lang.name})", "done")
                yield {"type": "speech", "mime": "audio/wav", "audio_b64": base64.b64encode(wav).decode()}
            except SarvamError as exc:
                yield _stage("speak", "Voice explanation unavailable", "failed", message=exc.user_message)
        else:
            yield {"type": "notice", "message": f"Voice output is not available for {lang.name} yet; showing text."}

        yield {"type": "trace", "request_id": request_id, "total_ms": int((time.perf_counter() - t0) * 1000),
               "spans": tr.as_list(), "modality": source.modality.value,
               "path": _path_label(source.modality, source.duration, settings)}
        yield {"type": "done"}
    except InputError as exc:
        yield {"type": "error", "message": str(exc)}
    except SarvamError as exc:
        yield {"type": "error", "message": exc.user_message}
    except Exception:
        log.exception("pipeline failed (request %s)", request_id)
        yield {"type": "error", "message": f"Something went wrong. Please try again. (ref {request_id})"}


def _path_label(modality: Modality, duration: float | None, settings: Settings) -> str:
    if modality == Modality.audio:
        if duration is not None and duration <= settings.rest_stt_max_seconds:
            return "Saaras v3 REST (<=30 s)"
        return "Saaras v3 Batch + speaker diarization"
    if modality in (Modality.image, Modality.pdf):
        return "Sarvam Vision Document Intelligence"
    return "Text"

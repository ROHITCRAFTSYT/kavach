"""Thin, resilient gateway over the official `sarvamai` SDK.

Every Sarvam call in the app goes through here, so retries, timeouts,
concurrency caps and tracing live in exactly one place. The SDK is
synchronous; calls run in worker threads so the async web server never blocks.

Endpoint behaviour verified live against api.sarvam.ai (Sep 2026):
  * STT REST (saaras:v3): <= 30 s audio, returns language_code + probability.
  * STT Batch: diarized_transcript.entries[{transcript, start/end_time_seconds, speaker_id}].
    NOTE: SDK create_job() defaults to the legacy 'saarika:v2.5' model, so we always pass model.
  * Doc AI v1 digitise: async job; results(format=json) -> documents[].pages[].blocks[] with bbox_norm.
  * Chat: json_schema structured output is accepted, but content must still be validated.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import random
import re
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import httpx
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

from . import trace
from .config import Settings

log = logging.getLogger("kavach.sarvam")

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
TTS_CHUNK_CHARS = 450  # well under Bulbul's 2,500 cap; smaller chunks synthesise in parallel
TTS_SAMPLE_RATE = 22050


class SarvamError(RuntimeError):
    """A Sarvam call failed after retries. `user_message` is safe to show to end users."""

    def __init__(self, user_message: str, *, status: int | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.status = status


def _status(exc: Exception) -> int | None:
    return exc.status_code if isinstance(exc, ApiError) else None


def _retry_after(exc: Exception) -> float | None:
    if isinstance(exc, ApiError) and exc.headers:
        value = exc.headers.get("retry-after") or exc.headers.get("Retry-After")
        try:
            return float(value) if value else None
        except ValueError:
            return None
    return None


def _friendly(exc: Exception) -> str:
    status = _status(exc)
    if status == 429:
        return "The AI service is busy right now. Please try again in a minute."
    if status in (401, 403):
        return "The AI service rejected our credentials. Please contact the operator."
    if status in (400, 422):
        body = getattr(exc, "body", None)
        detail = ""
        if isinstance(body, dict):
            err = body.get("error") or {}
            detail = err.get("message", "") if isinstance(err, dict) else str(err)
            detail = detail or body.get("detail", "") or body.get("title", "")
        return f"The input could not be processed{': ' + detail if detail else '.'}"
    return "The AI service is temporarily unavailable. Please try again."


class SarvamGateway:
    def __init__(self, settings: Settings, client: SarvamAI | None = None):
        self.settings = settings
        self.client = client or SarvamAI(
            api_subscription_key=settings.sarvam_api_key,
            timeout=settings.request_timeout_seconds,
        )
        # Concurrency caps keep us inside the Starter-plan limits documented at
        # docs.sarvam.ai/api/getting-started/ratelimits (Vision is 10 req/min on every plan).
        self._sem = {
            "llm": asyncio.Semaphore(6),
            "tts": asyncio.Semaphore(6),
            "stt": asyncio.Semaphore(4),
            "vision": asyncio.Semaphore(2),
            "text": asyncio.Semaphore(8),
        }

    # ------------------------------------------------------------------ core
    async def _call(self, name: str, api: str, fn, *args, attempts: int = 3, **kwargs):
        async with self._sem[api]:
            with trace.span(name, api) as sp:
                for attempt in range(1, attempts + 1):
                    try:
                        return await asyncio.to_thread(fn, *args, **kwargs)
                    except (ApiError, httpx.TransportError, httpx.TimeoutException) as exc:
                        status = _status(exc)
                        retryable = status is None or status in RETRYABLE_STATUS
                        if not retryable or attempt == attempts:
                            sp.detail = f"status={status} {str(exc)[:160]}"
                            log.warning("sarvam %s failed: status=%s %s", name, status, str(exc)[:300])
                            raise SarvamError(_friendly(exc), status=status) from exc
                        delay = _retry_after(exc) or min(8.0, 0.8 * 2 ** (attempt - 1)) + random.random() * 0.4
                        log.info("sarvam %s retry %d in %.1fs (status=%s)", name, attempt, delay, status)
                        await asyncio.sleep(delay)

    # ------------------------------------------------------------------ chat
    async def chat_json(
        self,
        *,
        name: str,
        system: str,
        user: str,
        schema: dict,
        model: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.1,
        reasoning_effort: str | None = None,
    ) -> dict:
        """Structured-output chat call that always returns a parsed dict or raises SarvamError.

        Reasoning is disabled by default (explicit None, per the API docs). Measured on our analysis
        prompt: no reasoning 12 s with 5/5 quotes verified vs 166-255 s with 'low'/default effort, where
        reasoning tokens also exhausted max_tokens and truncated the JSON. Grounding catches quality slips.
        """
        kwargs: dict[str, Any] = dict(
            model=model or self.settings.reasoning_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
        )
        kwargs["reasoning_effort"] = reasoning_effort
        last_error = "empty response"
        # Measured: a normal analysis is 230-1,170 tokens, but ~1 in 6 generations falls into a
        # repetition loop until the cap. A 2,000-token cap makes a loop fail fast (~15 s); retries add
        # a frequency penalty, which broke loops in testing without hurting verbatim quotes (14/14 verified).
        for attempt in range(3):
            resp = await self._call(f"chat.{name}", "llm", self.client.chat.completions, **kwargs)
            choice = resp.choices[0]
            content = choice.message.content or ""
            try:
                return parse_json(content)
            except ValueError as exc:
                last_error = f"{exc} (finish_reason={choice.finish_reason})"
                log.warning("chat %s attempt %d returned invalid JSON: %s", name, attempt + 1, last_error)
                kwargs["frequency_penalty"] = 0.5
                kwargs["temperature"] = min(kwargs["temperature"] + 0.2, 0.7)
                if attempt == 1:  # last try: a different model (same API schema) to escape a persistent loop
                    kwargs["model"] = self.settings.chat_model
        raise SarvamError("The AI returned an unreadable answer. Please try again.") from ValueError(last_error)

    async def chat_text(self, *, name: str, messages: list[dict], model: str | None = None,
                        max_tokens: int = 1500, temperature: float = 0.3) -> str:
        resp = await self._call(
            f"chat.{name}", "llm", self.client.chat.completions,
            model=model or self.settings.chat_model, messages=messages,
            max_tokens=max_tokens, temperature=temperature, reasoning_effort=None,
        )
        return clean_text(resp.choices[0].message.content or "")

    # ------------------------------------------------------------------ text
    async def identify_language(self, text: str) -> str | None:
        resp = await self._call("text.identify_language", "text", self.client.text.identify_language, input=text[:1000])
        return resp.language_code

    async def translate(self, text: str, source: str, target: str) -> str:
        """Translate arbitrarily long text; sarvam-translate:v1 covers all 22 languages (2,000 chars/request)."""
        if source == target or not text.strip():
            return text
        chunks = chunk_text(text, 1800)
        results = await asyncio.gather(*[
            self._call(
                "text.translate", "text", self.client.text.translate,
                input=c, source_language_code=source, target_language_code=target, model="sarvam-translate:v1",
            )
            for c in chunks
        ])
        return "\n".join(r.translated_text for r in results)

    # ------------------------------------------------------------------ speech
    async def transcribe(self, path: Path, language: str | None = None) -> dict:
        """REST STT for clips up to 30 s. Returns the raw response as a dict."""
        def run():
            with open(path, "rb") as fh:
                return self.client.speech_to_text.transcribe(
                    file=fh, model=self.settings.stt_model, mode="transcribe",
                    language_code=language or "unknown", with_timestamps=True,
                )
        resp = await self._call("stt.transcribe", "stt", run)
        return resp.model_dump()

    async def transcribe_batch(self, path: Path, language: str | None = None, num_speakers: int | None = None) -> dict:
        """Batch STT with speaker diarization (up to 2 h). Returns the parsed output JSON."""
        timeout = self.settings.job_timeout_seconds

        def run():
            job = self.client.speech_to_text_job.create_job(
                model=self.settings.stt_model, mode="transcribe", language_code=language or "unknown",
                with_diarization=True, with_timestamps=True, num_speakers=num_speakers,
            )
            job.upload_files([str(path)])
            job.start()
            status = job.wait_until_complete(poll_interval=3, timeout=timeout)
            if not job.is_successful():
                raise SarvamError(f"Transcription job failed ({getattr(status, 'job_state', 'unknown')}).")
            with tempfile.TemporaryDirectory() as out:
                job.download_outputs(out)
                files = list(Path(out).glob("*.json"))
                if not files:
                    raise SarvamError("Transcription job returned no output.")
                return json.loads(files[0].read_text(encoding="utf-8"))

        return await self._call("stt.batch_diarized", "stt", run, attempts=2)

    async def tts(self, text: str, language: str, speaker: str | None = None, pace: float = 0.95) -> bytes:
        """Synthesise speech with Bulbul v3; long text is chunked and stitched into one WAV."""
        chunks = chunk_text(text, TTS_CHUNK_CHARS)

        def one(chunk: str) -> bytes:
            resp = self.client.text_to_speech.convert(
                text=chunk, language_code=language, model=self.settings.tts_model,
                speaker=speaker or "shubh", pace=pace, speech_sample_rate=TTS_SAMPLE_RATE,
                output_audio_codec="wav",
            )
            return base64.b64decode("".join(resp.audios))

        wavs = await asyncio.gather(*[self._call("tts.convert", "tts", one, c) for c in chunks])
        return concat_wavs(wavs)

    # ------------------------------------------------------------------ vision
    async def digitise(self, data: bytes, filename: str, mime: str, language: str | None = None) -> dict:
        """Sarvam Vision document digitisation. Returns results JSON with per-block bounding boxes."""
        timeout = self.settings.job_timeout_seconds

        def start():
            kwargs: dict[str, Any] = dict(file=[(filename, data, mime)], output_format="md")
            if language:
                kwargs["language"] = language
            return self.client.doc_ai.digitise(**kwargs)

        job = await self._call("vision.digitise", "vision", start)
        deadline = time.monotonic() + timeout
        delay = 2.0
        while True:
            await asyncio.sleep(delay)
            status = await self._call("vision.status", "vision", self.client.doc_ai.get_status, job.job_id)
            if status.status in ("completed", "partially_completed"):
                break
            if status.status in ("failed", "rejected"):
                raise SarvamError("The document could not be read. Try a clearer photo or a PDF under 10 pages.")
            if time.monotonic() > deadline:
                raise SarvamError("Reading the document took too long. Please try again.")
            delay = min(delay * 1.4, 6.0)  # Vision is 10 req/min on all plans: back off
        result = await self._call("vision.results", "vision", self.client.doc_ai.get_results, job.job_id, format="json")
        return result.model_dump()


# ---------------------------------------------------------------------- helpers
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def clean_text(text: str) -> str:
    """Drop U+FFFD replacement chars and zero-width noise that occasionally appear in model output."""
    return text.replace("�", "").replace("​", "").strip()


def parse_json(content: str) -> dict:
    content = clean_text(_FENCE.sub("", content.strip()))
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in response") from None
        try:
            data = json.loads(content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("JSON root is not an object")
    return data


_SENTENCE_END = re.compile(r"(?<=[.!?।॥\n])(\s+)")


def chunk_text(text: str, limit: int) -> list[str]:
    """Split on sentence boundaries (incl. Devanagari danda) into chunks <= limit chars.

    Separators are preserved inside a chunk, so line breaks survive (the translation fallback relies on them).
    """
    parts = _SENTENCE_END.split(text.strip())
    units = [(parts[i], parts[i + 1] if i + 1 < len(parts) else "") for i in range(0, len(parts), 2)]
    chunks: list[str] = []
    current = ""
    for sentence, sep in units:
        while len(sentence) > limit:  # pathological run-on sentence: hard split on whitespace
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            if current.strip():
                chunks.append(current.strip())
                current = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + len(sentence) > limit:
            chunks.append(current.strip())
            current = ""
        current += sentence + sep
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]


def concat_wavs(wavs: list[bytes]) -> bytes:
    if len(wavs) == 1:
        return wavs[0]
    frames, params = [], None
    for raw in wavs:
        with wave.open(io.BytesIO(raw)) as w:
            params = params or w.getparams()
            frames.append(w.readframes(w.getnframes()))
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setparams(params)
        gap = b"\x00" * int(params.framerate * 0.25) * params.sampwidth * params.nchannels
        w.writeframes(gap.join(frames))
    return out.getvalue()

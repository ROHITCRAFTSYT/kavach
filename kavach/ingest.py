"""Turn any user input (text, photo, PDF, recording) into a normalised `Source` of segments."""

from __future__ import annotations

import asyncio
import io

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

from . import languages
from .config import Settings
from .models import Modality, Segment, Source
from .sarvam import SarvamError, SarvamGateway

log = logging.getLogger("kavach.ingest")

MAX_IMAGE_SIDE = 2400


class InputError(ValueError):
    """Bad user input; the message is safe to show."""


def sniff(data: bytes, filename: str = "") -> Modality:
    head = data[:16]
    if head.startswith(b"%PDF"):
        return Modality.pdf
    if head.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8")) or (head[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        return Modality.image
    if head[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"heif"):
        raise InputError("HEIC photos are not supported yet. Please share the photo as JPG or PNG.")
    if (
        (head[:4] == b"RIFF" and data[8:12] == b"WAVE")
        or head.startswith((b"ID3", b"OggS", b"fLaC", b"\x1a\x45\xdf\xa3", b"#!AMR"))
        or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xf1", b"\xff\xf9")
        or head[4:8] == b"ftyp"
    ):
        return Modality.audio
    raise InputError("Unsupported file. Upload a photo (JPG/PNG), a PDF, or an audio recording.")


# ---------------------------------------------------------------------------- text
_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")


def from_text(text: str, settings: Settings) -> Source:
    text = text.strip()
    if not text:
        raise InputError("Please paste the message you want checked.")
    if len(text) > settings.max_text_chars:
        raise InputError(f"Text is too long (max {settings.max_text_chars} characters).")
    parts = [p.strip() for p in _SPLIT.split(text) if p and p.strip()]
    segments = [Segment(id=f"t{i + 1}", text=p) for i, p in enumerate(parts)]
    return Source(modality=Modality.text, segments=segments, language=languages.detect_script_language(text))


# ---------------------------------------------------------------------------- documents
def normalise_image(data: bytes) -> bytes:
    """Re-encode to PNG: fixes EXIF rotation, strips metadata (GPS etc.), caps resolution."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except Exception as exc:  # corrupt/unsupported image
        raise InputError("That image could not be opened. Please try another photo.") from exc
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def blocks_to_segments(result: dict) -> tuple[list[Segment], int]:
    segments: list[Segment] = []
    pages = 0
    for doc in result.get("documents") or []:
        for page in doc.get("pages") or []:
            pages += 1
            blocks = sorted(page.get("blocks") or [], key=lambda b: b.get("reading_order") or 0)
            for block in blocks:
                text = (block.get("text") or "").strip()
                if not text:
                    continue
                segments.append(Segment(
                    id=f"p{page.get('page_num', pages)}b{len(segments) + 1}",
                    text=text,
                    page=page.get("page_num", pages),
                    bbox=block.get("bbox_norm"),
                ))
    return segments, pages


async def from_document(data: bytes, modality: Modality, filename: str, gw: SarvamGateway) -> Source:
    if modality == Modality.image:
        data, filename, mime = normalise_image(data), Path(filename or "photo").stem + ".png", "image/png"
    else:
        mime = "application/pdf"
        filename = filename or "document.pdf"
    result = await gw.digitise(data, filename, mime)
    segments, pages = blocks_to_segments(result)
    if not segments:
        raise InputError("No readable text was found. Try a sharper, well-lit photo.")
    text = "\n".join(s.text for s in segments)
    return Source(
        modality=modality, segments=segments, filename=filename, pages=pages,
        language=languages.detect_script_language(text),
    )


# ---------------------------------------------------------------------------- audio
def _ffmpeg() -> str:
    """System ffmpeg if present, else the static build bundled by imageio-ffmpeg (serverless hosts)."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("ffmpeg is required for audio input but was not found.") from exc


def normalise_audio(src: Path, dst: Path, max_seconds: int) -> float:
    """Convert anything ffmpeg understands to 16 kHz mono WAV (the rate Saaras works best at)."""
    cmd = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
           "-vn", "-ac", "1", "-ar", "16000", "-t", str(max_seconds), str(dst)]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    if proc.returncode != 0 or not dst.exists():
        log.warning("ffmpeg failed: %s", proc.stderr[-400:])
        raise InputError("That recording could not be read. Try an MP3, M4A, OGG or WAV file.")
    return wav_duration(dst)


def wav_duration(path: Path) -> float:
    import wave

    with wave.open(str(path)) as w:
        return w.getnframes() / float(w.getframerate())


def utterances_from_batch(result: dict) -> list[Segment]:
    entries = ((result.get("diarized_transcript") or {}).get("entries")) or []
    segments = [
        Segment(
            id=f"u{i + 1}", text=e["transcript"].strip(), speaker=str(e.get("speaker_id")),
            start=e.get("start_time_seconds"), end=e.get("end_time_seconds"),
        )
        for i, e in enumerate(entries)
        if (e.get("transcript") or "").strip()
    ]
    if not segments and result.get("transcript"):
        segments = utterances_from_rest(result)
    return segments


def utterances_from_rest(result: dict) -> list[Segment]:
    ts = result.get("timestamps") or {}
    words, starts, ends = ts.get("words") or [], ts.get("start_time_seconds") or [], ts.get("end_time_seconds") or []
    if words and len(words) == len(starts) == len(ends):
        return [
            Segment(id=f"u{i + 1}", text=w.strip(), start=s, end=e)
            for i, (w, s, e) in enumerate(zip(words, starts, ends))
            if w.strip()
        ]
    text = (result.get("transcript") or "").strip()
    return [Segment(id="u1", text=text, start=0.0)] if text else []


async def from_audio(data: bytes, filename: str, gw: SarvamGateway, settings: Settings,
                     language: str | None = None) -> tuple[Source, bytes]:
    """Returns the Source plus the normalised WAV (kept for in-browser playback of evidence)."""
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / ("input" + (Path(filename).suffix or ".bin"))
        raw.write_bytes(data)
        wav = Path(tmp) / "audio.wav"
        duration = await asyncio.to_thread(normalise_audio, raw, wav, settings.max_audio_seconds)
        if duration < 0.5:
            raise InputError("The recording is empty or too short.")
        if duration <= settings.rest_stt_max_seconds:
            result = await gw.transcribe(wav, language)
            segments = utterances_from_rest(result)
        else:
            result = await gw.transcribe_batch(wav, language)
            segments = utterances_from_batch(result)
        wav_bytes = wav.read_bytes()
    if not segments:
        raise InputError("No speech was detected in the recording.")
    source = Source(
        modality=Modality.audio, segments=segments, filename=filename, duration=round(duration, 2),
        language=result.get("language_code"), language_confidence=result.get("language_probability"),
    )
    return source, wav_bytes


async def ingest(*, gw: SarvamGateway, settings: Settings, text: str | None = None,
                 data: bytes | None = None, filename: str = "") -> tuple[Source, bytes | None]:
    if data:
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise InputError(f"File is too large (max {settings.max_upload_mb} MB).")
        modality = sniff(data, filename)
        if modality == Modality.audio:
            return await from_audio(data, filename, gw, settings)
        return await from_document(data, modality, filename, gw), None
    return from_text(text or "", settings), None


__all__ = ["InputError", "SarvamError", "ingest", "sniff", "from_text"]

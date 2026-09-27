import io
import shutil

import pytest
from PIL import Image

from kavach import ingest
from kavach.ingest import InputError, blocks_to_segments, from_text, sniff, utterances_from_batch, utterances_from_rest
from kavach.models import Modality


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return buf.getvalue()


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="JPEG")
    return buf.getvalue()


# ------------------------------------------------------------------ sniff
@pytest.mark.parametrize("data,expected", [
    (_png(), Modality.image),
    (_jpeg(), Modality.image),
    (b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj", Modality.pdf),
    (b"OggS\x00\x02" + b"\x00" * 30, Modality.audio),
    (b"\x1a\x45\xdf\xa3" + b"\x00" * 30, Modality.audio),  # webm / matroska
    (b"ID3\x04\x00" + b"\x00" * 30, Modality.audio),
    (b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 30, Modality.audio),
])
def test_sniff_magic_bytes(data, expected):
    assert sniff(data) == expected


def test_sniff_wav(wav):
    assert sniff(wav(0.1), "x.wav") == Modality.audio


def test_sniff_heic_rejected():
    heic = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic"
    with pytest.raises(InputError, match="HEIC"):
        sniff(heic, "photo.heic")


@pytest.mark.parametrize("data", [b"hello, this is definitely not a media file", bytes(range(40)), b""])
def test_sniff_unknown_rejected(data):
    with pytest.raises(InputError):
        sniff(data, "x.bin")


# ------------------------------------------------------------------ text
def test_from_text_segments(settings):
    src = from_text("  पहला वाक्य। दूसरा वाक्य.\nThird line here!  Fourth? ", settings)
    assert src.modality == Modality.text
    assert [s.id for s in src.segments] == ["t1", "t2", "t3", "t4"]
    assert [s.text for s in src.segments] == ["पहला वाक्य।", "दूसरा वाक्य.", "Third line here!", "Fourth?"]


def test_from_text_detects_language(settings, scam_text):
    assert from_text(scam_text, settings).language == "hi-IN"
    assert from_text("Your parcel has drugs.", settings).language == "en-IN"


def test_from_text_empty_and_too_long(settings):
    with pytest.raises(InputError):
        from_text("   \n  ", settings)
    with pytest.raises(InputError, match="too long"):
        from_text("a" * (settings.max_text_chars + 1), settings)


def test_source_for_prompt_tags(settings):
    src = from_text("one. two.", settings)
    assert src.for_prompt() == "[t1] one.\n[t2] two."
    assert src.segment("t2").text == "two." and src.segment("nope") is None


# ------------------------------------------------------------------ documents
def test_blocks_to_segments():
    result = {"documents": [{"pages": [
        {"page_num": 1, "blocks": [
            {"block_id": "p1-b2", "text": "second block", "reading_order": 2, "bbox_norm": [0.1, 0.3, 0.5, 0.4]},
            {"block_id": "p1-b1", "text": "  CBI NOTICE  ", "reading_order": 1, "bbox_norm": [0.1, 0.1, 0.5, 0.2]},
            {"block_id": "p1-b3", "text": "   ", "reading_order": 3},
        ]},
        {"page_num": 2, "blocks": [{"block_id": "p2-b1", "text": "page two", "reading_order": 1}]},
    ]}]}
    segments, pages = blocks_to_segments(result)
    assert pages == 2
    assert [s.text for s in segments] == ["CBI NOTICE", "second block", "page two"]
    assert segments[0].bbox == [0.1, 0.1, 0.5, 0.2] and segments[0].page == 1
    assert segments[2].page == 2
    assert len({s.id for s in segments}) == 3


def test_blocks_to_segments_empty():
    assert blocks_to_segments({}) == ([], 0)
    assert blocks_to_segments({"documents": [{"pages": []}]}) == ([], 0)


def test_normalise_image_reencodes_png():
    out = ingest.normalise_image(_jpeg())
    assert out.startswith(b"\x89PNG")


def test_normalise_image_rejects_garbage():
    with pytest.raises(InputError):
        ingest.normalise_image(b"\x89PNG not really")


# ------------------------------------------------------------------ audio
def test_utterances_from_batch():
    result = {"diarized_transcript": {"entries": [
        {"transcript": " नमस्ते, मैं सीबीआई से बोल रहा हूँ ", "start_time_seconds": 0.0, "end_time_seconds": 2.0, "speaker_id": "1"},
        {"transcript": "  ", "start_time_seconds": 2.0, "end_time_seconds": 2.5, "speaker_id": "0"},
        {"transcript": "जी बोलिए", "start_time_seconds": 2.5, "end_time_seconds": 4.0, "speaker_id": 0},
    ]}}
    segs = utterances_from_batch(result)
    assert len(segs) == 2 and len({s.id for s in segs}) == 2 and segs[0].id == "u1"
    assert segs[0].text == "नमस्ते, मैं सीबीआई से बोल रहा हूँ"
    assert (segs[0].start, segs[0].end, segs[0].speaker) == (0.0, 2.0, "1")
    assert segs[1].speaker == "0"


def test_utterances_from_batch_falls_back_to_transcript():
    segs = utterances_from_batch({"transcript": "hello there"})
    assert [(s.id, s.text) for s in segs] == [("u1", "hello there")]


def test_utterances_from_rest_words():
    segs = utterances_from_rest({"timestamps": {"words": ["a", "b"], "start_time_seconds": [0, 1],
                                                "end_time_seconds": [1, 2]}})
    assert [(s.text, s.start, s.end) for s in segs] == [("a", 0, 1), ("b", 1, 2)]


def test_utterances_from_rest_mismatched_timestamps_uses_transcript():
    segs = utterances_from_rest({"transcript": " full text ", "timestamps": {"words": ["a"], "start_time_seconds": [],
                                                                           "end_time_seconds": []}})
    assert [(s.id, s.text, s.start) for s in segs] == [("u1", "full text", 0.0)]
    assert utterances_from_rest({}) == []


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_normalise_audio_ffmpeg(tmp_path, wav):
    src, dst = tmp_path / "in.wav", tmp_path / "out.wav"
    src.write_bytes(wav(1.0, rate=8000))
    duration = ingest.normalise_audio(src, dst, max_seconds=30)
    assert duration == pytest.approx(1.0, abs=0.05)
    import wave
    with wave.open(str(dst)) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_normalise_audio_bad_input(tmp_path):
    src = tmp_path / "in.ogg"
    src.write_bytes(b"OggS" + b"\x00" * 64)
    with pytest.raises(InputError):
        ingest.normalise_audio(src, tmp_path / "out.wav", max_seconds=30)


async def test_ingest_rejects_oversized_upload(settings, fake_gateway):
    too_big = b"\x00" * (settings.max_upload_mb * 1024 * 1024 + 1)
    with pytest.raises(InputError, match="too large"):
        await ingest.ingest(gw=fake_gateway(), settings=settings, data=too_big, filename="x")

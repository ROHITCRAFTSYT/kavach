import io
import wave
from types import SimpleNamespace

import pytest

from kavach import sarvam
from kavach.sarvam import SarvamGateway, chunk_text, clean_text, concat_wavs, parse_json


# ------------------------------------------------------------------ chunk_text
def test_chunk_text_respects_limit_and_keeps_content():
    text = " ".join(f"Sentence number {i} is here." for i in range(40))
    chunks = chunk_text(text, 100)
    assert len(chunks) > 1
    assert all(0 < len(c) <= 100 for c in chunks)
    assert " ".join(chunks).split() == text.split()


def test_chunk_text_splits_on_danda():
    text = "पहला वाक्य यहाँ है। दूसरा वाक्य यहाँ है। तीसरा वाक्य यहाँ है।"
    chunks = chunk_text(text, 25)
    assert chunks == ["पहला वाक्य यहाँ है।", "दूसरा वाक्य यहाँ है।", "तीसरा वाक्य यहाँ है।"]


def test_chunk_text_splits_on_full_stop():
    chunks = chunk_text("One two three. Four five six. Seven eight nine.", 17)
    assert chunks == ["One two three.", "Four five six.", "Seven eight nine."]


def test_chunk_text_short_text_single_chunk():
    assert chunk_text("  Hello there.  ", 1800) == ["Hello there."]
    assert chunk_text("", 100) == []


def test_chunk_text_long_run_on_string():
    run_on = " ".join(["word"] * 500)  # 2,499 chars, no sentence end
    chunks = chunk_text(run_on, 100)
    assert all(len(c) <= 100 for c in chunks)
    assert " ".join(chunks).split() == run_on.split()


def test_chunk_text_run_on_without_spaces_hard_splits():
    blob = "x" * 1050
    chunks = chunk_text(blob, 100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == blob


# ------------------------------------------------------------------ parse_json / clean_text
def test_parse_json_plain():
    assert parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_code_fence():
    assert parse_json('```json\n{"a": 1, "b": [1, 2]}\n```') == {"a": 1, "b": [1, 2]}
    assert parse_json('```\n{"a": 2}\n```') == {"a": 2}


def test_parse_json_surrounding_prose():
    content = 'Sure! Here is the analysis:\n{"verdict": "scam", "n": 3}\nHope this helps.'
    assert parse_json(content) == {"verdict": "scam", "n": 3}


def test_parse_json_with_replacement_chars():
    assert parse_json('{"t": "ab�c"}') == {"t": "abc"}


@pytest.mark.parametrize("bad", ["", "no json here", "{not: valid}", "[1, 2, 3]", '{"a": 1'])
def test_parse_json_invalid_raises_value_error(bad):
    with pytest.raises(ValueError):
        parse_json(bad)


def test_clean_text_removes_replacement_char():
    assert clean_text("  नम�स्ते​ ") == "नमस्ते"
    assert "�" not in clean_text("��hello�")


# ------------------------------------------------------------------ concat_wavs
def _duration(raw: bytes) -> float:
    with wave.open(io.BytesIO(raw)) as w:
        return w.getnframes() / w.getframerate()


def test_concat_wavs_duration_is_sum_plus_gap(wav):
    a, b = wav(0.5), wav(0.25)
    out = concat_wavs([a, b])
    assert _duration(out) == pytest.approx(0.5 + 0.25 + 0.25, abs=0.01)
    with wave.open(io.BytesIO(out)) as w:
        assert w.getframerate() == 8000 and w.getnchannels() == 1 and w.getsampwidth() == 2


def test_concat_wavs_three_parts(wav):
    out = concat_wavs([wav(0.1), wav(0.1), wav(0.1)])
    assert _duration(out) == pytest.approx(0.3 + 2 * 0.25, abs=0.01)


def test_concat_wavs_single_passthrough(wav):
    a = wav(0.3)
    assert concat_wavs([a]) is a


# ------------------------------------------------------------------ gateway with a fake SDK client
class _FakeTextAPI:
    def __init__(self):
        self.inputs = []

    def translate(self, *, input, source_language_code, target_language_code, model):
        self.inputs.append(input)
        return SimpleNamespace(translated_text=f"<{input}>")


def _gateway(settings):
    client = SimpleNamespace(text=_FakeTextAPI())
    return SarvamGateway(settings, client=client), client


async def test_translate_same_language_is_noop(settings):
    gw, client = _gateway(settings)
    assert await gw.translate("hello", "en-IN", "en-IN") == "hello"
    assert client.text.inputs == []


async def test_translate_chunks_long_text(settings):
    gw, client = _gateway(settings)
    text = " ".join(f"This is sentence {i}." for i in range(400))
    await gw.translate(text, "en-IN", "hi-IN")
    assert len(client.text.inputs) > 1
    assert all(len(c) <= 1800 for c in client.text.inputs)


async def test_translate_preserves_line_structure(settings):
    gw, _ = _gateway(settings)
    out = await gw.translate("This is very likely a SCAM.\nDo not pay.\nCall 1930.", "en-IN", "ta-IN")
    assert len([p for p in out.split("\n") if p.strip()]) == 3


def test_friendly_messages_never_leak_internals():
    msg = sarvam._friendly(RuntimeError("secret stack trace"))
    assert "secret" not in msg


# ------------------------------------------------------------------ chat_json / chat_text with a fake SDK
class _FakeCompletions:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        content, finish = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)])


def _chat_gateway(settings, replies):
    completions = _FakeCompletions(replies)
    return SarvamGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=completions))), completions


async def test_chat_json_parses_fenced_output(settings):
    gw, comp = _chat_gateway(settings, [('```json\n{"ok": true}\n```', "stop")])
    out = await gw.chat_json(name="t", system="s", user="u", schema={"type": "object"})
    assert out == {"ok": True}
    call = comp.calls[0]
    assert call["model"] == settings.reasoning_model
    assert call["response_format"]["type"] == "json_schema"
    assert "reasoning_effort" in call and call["reasoning_effort"] is None


async def test_chat_json_retries_on_truncation_then_succeeds(settings):
    gw, comp = _chat_gateway(settings, [('{"a": ', "length"), ('{"a": 1}', "stop")])
    assert await gw.chat_json(name="t", system="s", user="u", schema={}, max_tokens=1000) == {"a": 1}
    assert len(comp.calls) == 2
    # the retry must change something (budget or temperature), not repeat the identical request
    first, second = comp.calls
    assert (second["max_tokens"], second["temperature"]) != (first["max_tokens"], first["temperature"])


async def test_chat_json_unparsable_three_times_raises_sarvam_error(settings):
    gw, comp = _chat_gateway(settings, [("nope", "stop"), ("still nope", "length"), ("again", "length")])
    with pytest.raises(sarvam.SarvamError):
        await gw.chat_json(name="t", system="s", user="u", schema={})
    assert len(comp.calls) == 3
    assert comp.calls[1].get("frequency_penalty") == 0.5  # retries break repetition loops


async def test_chat_text_cleans_output(settings):
    gw, comp = _chat_gateway(settings, [(" नमस्ते� ", "stop")])
    out = await gw.chat_text(name="qa", messages=[{"role": "user", "content": "hi"}])
    assert out == "नमस्ते"
    assert comp.calls[0]["model"] == settings.chat_model

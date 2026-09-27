"""Generate the demo/eval sample files in samples/.

Audio is synthesised with Sarvam Bulbul v3 (two different voices for the two
parties in a call), documents are rendered from HTML with headless Edge/Chrome
so Indic scripts are shaped correctly.

    python scripts/make_samples.py
"""

from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kavach.config import get_settings  # noqa: E402
from sarvamai import SarvamAI  # noqa: E402

OUT = ROOT / "samples"
RATE = 16000

# A classic "digital arrest" call: impersonated officer, fake case, secrecy,
# a "safe RBI account" transfer and a deadline. >30 s, so it exercises the
# batch + diarization path.
SCAM_CALL_HI = [
    ("rahul", "नमस्ते, मैं मुंबई साइबर क्राइम ब्रांच से इंस्पेक्टर विक्रम सिंह बोल रहा हूँ। आपके आधार कार्ड से एक पार्सल बुक हुआ है जिसमें ड्रग्स और फर्जी पासपोर्ट मिले हैं।"),
    ("priya", "क्या? मैंने तो कोई पार्सल नहीं भेजा।"),
    ("rahul", "आपके नाम पर मनी लॉन्ड्रिंग का केस दर्ज है। अभी आपको डिजिटल अरेस्ट किया जा रहा है। वीडियो कॉल बंद मत कीजिए और किसी को कुछ मत बताइए।"),
    ("priya", "लेकिन मैं क्या करूँ? मुझे बहुत डर लग रहा है।"),
    ("rahul", "जाँच पूरी होने तक आपके खाते का सारा पैसा आरबीआई के सुरक्षित खाते में ट्रांसफर करना होगा। जाँच के बाद पैसा वापस मिल जाएगा।"),
    ("priya", "कितना पैसा भेजना है?"),
    ("rahul", "अभी एक घंटे के अंदर चार लाख रुपये इस खाते में भेजिए, वरना पुलिस आपके घर पहुँच जाएगी।"),
]

# Short (<30 s) Tamil voice note: fake bank KYC + OTP request. Exercises REST STT.
KYC_NOTE_TA = [
    ("kavitha", "வணக்கம், நான் உங்கள் வங்கியிலிருந்து பேசுகிறேன். உங்கள் KYC காலாவதியாகிவிட்டது. இன்று மாலைக்குள் உங்கள் கணக்கு முடக்கப்படும். உங்கள் மொபைலுக்கு வந்த OTP எண்ணை உடனே சொல்லுங்கள்."),
]

CBI_NOTICE_HI = """
<h2>केंद्रीय अन्वेषण ब्यूरो (CBI) — नोटिस</h2>
<p>संदर्भ संख्या: CBI/ML/2026/4471</p>
<p>आपके आधार नंबर से जुड़े बैंक खाते में मनी लॉन्ड्रिंग पाई गई है।
आपके खिलाफ गिरफ्तारी वारंट जारी किया गया है।</p>
<p><b>गिरफ्तारी से बचने के लिए 2 घंटे के भीतर ₹95,000 सत्यापन शुल्क
UPI ID: cbi.verify@okaxis पर भेजें।</b></p>
<p>यह मामला गोपनीय है, किसी को न बताएं।</p>
<p>संपर्क: +91 98765 43210 (केवल WhatsApp)</p>
"""

# A genuine-looking utility notice: nothing fraudulent, the value is in
# explaining the deadline, amount and what to do.
POWER_NOTICE_TA = """
<h2>மின் இணைப்பு துண்டிப்பு முன்னறிவிப்பு</h2>
<p>நுகர்வோர் எண்: 04-123-456-789</p>
<p>நிலுவைத் தொகை: ₹2,340 &nbsp;&nbsp; கடைசி தேதி: 15-10-2026</p>
<p>மேற்கண்ட தேதிக்குள் அருகிலுள்ள பிரிவு அலுவலகத்திலோ அல்லது அதிகாரப்பூர்வ
இணையதளத்திலோ தொகையைச் செலுத்தாவிட்டால், மின் இணைப்பு துண்டிக்கப்படும்.
மறு இணைப்புக் கட்டணம் ₹150 வசூலிக்கப்படும்.</p>
<p>உதவிப் பொறியாளர், பிரிவு அலுவலகம், மதுரை.</p>
"""

PAGE = """<!doctype html><meta charset="utf-8"><style>
body{{margin:0;background:#fff;font-family:'Nirmala UI','Noto Sans',sans-serif;color:#111}}
.doc{{width:860px;padding:40px 48px;font-size:22px;line-height:1.55}}
h2{{font-size:28px;border-bottom:2px solid #333;padding-bottom:8px}}
</style><div class="doc">{body}</div>"""


def tts_pcm(client: SarvamAI, text: str, speaker: str, lang: str) -> bytes:
    resp = client.text_to_speech.convert(
        text=text,
        language_code=lang,
        model="bulbul:v3",
        speaker=speaker,
        speech_sample_rate=RATE,
        output_audio_codec="wav",
    )
    raw = base64.b64decode("".join(resp.audios))
    with wave.open(io.BytesIO(raw)) as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1, "unexpected TTS format"
        return w.readframes(w.getnframes())


def make_dialogue(client: SarvamAI, turns, lang: str, path: Path) -> None:
    gap = b"\x00\x00" * int(RATE * 0.45)
    pcm = b"".join(tts_pcm(client, text, spk, lang) + gap for spk, text in turns)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    print(f"wrote {path.name} ({len(pcm) / 2 / RATE:.1f}s)")


def find_browser() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        shutil.which("google-chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    return next((c for c in candidates if c and Path(c).exists()), None)


def render(html_body: str, path: Path, height: int) -> None:
    browser = find_browser()
    if not browser:
        print(f"skip {path.name}: no Edge/Chrome found for rendering")
        return
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "doc.html"
        src.write_text(PAGE.format(body=html_body), encoding="utf-8")
        subprocess.run(
            [browser, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--screenshot={path}", f"--window-size=960,{height}", src.as_uri()],
            check=True, capture_output=True, timeout=60,
        )
    print(f"wrote {path.name}")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    client = SarvamAI(api_subscription_key=get_settings().sarvam_api_key)
    make_dialogue(client, SCAM_CALL_HI, "hi-IN", OUT / "scam_call_hi.wav")
    make_dialogue(client, KYC_NOTE_TA, "ta-IN", OUT / "kyc_voicenote_ta.wav")
    render(CBI_NOTICE_HI, OUT / "cbi_notice_hi.png", 560)
    render(POWER_NOTICE_TA, OUT / "power_notice_ta.png", 520)


if __name__ == "__main__":
    os.chdir(ROOT)
    main()

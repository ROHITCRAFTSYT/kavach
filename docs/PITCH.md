# Kavach (कवच): 3-minute demo script

**Setup before going on stage**
- Server running (`uvicorn kavach.app:app --port 8000`), with `http://localhost:8000` open in the browser.
- Volume up. Mic permission already granted.
- A second tab open at `/api/docs`, as a backup.
- Run `python scripts/smoke.py` once to warm up the connections.

---

## 0:00–0:25 · Hook

> "Imagine your grandmother gets a call. The man says he's from the **CBI**, that a parcel in her name had drugs in it, and that she's under **'digital arrest'**. I4C and RBI both warn about this pattern. He keeps her on a video call for hours, tells them they're under arrest, and drains their savings. Those calls happen in **Hindi, Tamil, Bengali**, not in English. And the people being targeted often can't read the notice they're being shown.
>
> **Kavach** is a shield for them. Give it the call, the voice note, a photo of the notice or the SMS. It tells you, **in your own language and out loud**, whether it's a scam, and it **shows you the proof**."

## 0:25–1:35 · Live demo

1. **Tap "Digital arrest call"** (Hindi, 45 s, two speakers).
   > "It's a real-sounding call between two voices. Watch the pipeline stream. **Saaras v3 Batch** is diarizing who said what. **Sarvam-105B** is extracting evidence. Bulbul is getting ready to speak."
2. **Result: Scam 100/100.** Point at the red flags.
   > "Six red flags. Every one of them is a **word-for-word quote** from the call, and each one was flagged independently by the AI *and* by our rule engine." Tap one and the audio **jumps to that second**. "That's the caller, at that exact moment, saying it." *(Read out the speaker and timestamp shown on screen.)*
3. **Press play on the Hindi voice explanation.** Let it run about 5 s.
4. **Ask by voice:** *"क्या मुझे पैसे भेजने चाहिए?"* ("Should I send money?")
   > "The answer comes only from this call, and it's spoken back in Hindi. Kavach never tells anyone to call a number that came from the scammer."
5. **Open Complaint draft.**
   > "It's ready for **1930** or **cybercrime.gov.in**, with timestamps and exact quotes. It's built from verified data only. There's no AI-written text in a police complaint."
6. **Tap the "CBI notice" photo.** Red flags **light up as boxes on the image**, from Sarvam Vision's bounding boxes.
7. **Tap the Tamil electricity notice.**
   > "This one is **genuine**. Risk 0. Kavach explains in Tamil how much is due and by when. It's not just an alarm bell. It helps people understand real paperwork too."

## 1:35–2:15 · The "we don't trust the LLM" moment

Open the **Trace panel** and the **Discarded claims** section.

> "Here's what we learned building this. When we tested Sarvam-105B, it sometimes returned **'suspicious' with risk 1**, and on another input **'suspicious' with risk 95**. It also sometimes **translated** quotes it had been asked to copy word for word.
>
> So **the LLM never decides the verdict.** It only extracts findings against a fixed 14-pattern taxonomy taken from I4C and RBI advisories. Every quote is **fuzzy-aligned back to the source**. If it isn't really there, it shows up here as **discarded** and it never raises the risk. The score is plain arithmetic: a noisy-OR over verified evidence, boosted when the AI and the rules agree.
>
> This panel lists every Sarvam call: STT, Vision, 105B, translate and Bulbul, with its latency. If the LLM goes down, the rule engine keeps working in degraded mode."

## 2:15–2:45 · Impact

> - "**22 languages understood, 11 spoken.** Built on Sarvam end to end: Saaras, Vision, 105B, Translate and Bulbul.
> - **Works with what people actually receive**: a phone call, a WhatsApp voice note, a photo of a notice.
> - **Stateless: nothing is stored on the server.** Your content stays in your browser, and *Clear this page* wipes it. Photos have their GPS stripped. It runs on Vercel serverless or in Docker.
> - On our samples it gets the Hindi call, the Tamil KYC voice note, the fake CBI notice and the job SMS right: **scam at 97 to 100**. And the genuine Tamil bill gets **0**."

## 2:45–3:00 · Ask

> "Next, we want to put Kavach where scams actually arrive: a **WhatsApp bot** and a **phone line** that anyone can forward a call to, using **Sarvam Voice Agents**. We'd love Sarvam's help with voice-agent access, and introductions to cyber cells and NGOs for real evaluation data. **Kavach: a shield in every language.**"

---

## Likely judge Q&A

**Q: Why not just ask the LLM "is this a scam?"**
We tried. In testing, verdict and risk contradicted each other ("suspicious"/1 and "suspicious"/95). Grounded extraction plus deterministic scoring is reproducible and explainable, and every point of risk traces back to a quote.

**Q: How do you stop hallucinated evidence?**
Every quote is aligned against the source segments using `rapidfuzz` partial alignment. Before matching, the text is NFC-normalised and nuktas and ZWJ are removed, so small OCR vowel-sign errors don't cause false rejections. A match score below 82 means the claim is discarded, shown to the user as such, and scored at zero.

**Q: What if Sarvam's API is slow or down?**
- We turned off Sarvam-105B's reasoning mode. We measured about 12 s instead of 166–255 s, and quotes were still verified 5/5.
- About 1 in 6 generations fell into a repetition loop. We cap output at 2,000 tokens (a normal answer is 230–1,170) so a loop fails fast. Then we retry up to 3 times with a frequency penalty. In testing that broke the loops, and 14/14 quotes were still verified.
- Retries with exponential backoff and jitter, honouring `Retry-After`.
- Concurrency limits for each API, sized to the documented rate limits (Vision is 10/min).
- Progress streams to the UI, so it never looks frozen.
- If the LLM fails, the offline multilingual rule engine still returns a verdict, marked "degraded".

**Q: Why the rule engine, if you have a 105B model?**
Three reasons. It corroborates the AI: agreement boosts the score. It is free, instant and offline. And it catches script-specific quirks: Saaras writes spoken "OTP" as ओटीपी or ஓடிபி, so the lexicon includes native-script transliterations.

**Q: How do you handle long calls?**
Clips up to 30 s go to Saaras REST, which is fast (a 16 s clip takes 2.2 s). Longer calls go to Saaras Batch with speaker diarization (a 45 s call takes 7.4 s). The SDK's batch job defaults to the legacy `saarika:v2.5`, so we pin `saaras:v3` explicitly.

**Q: What stops the output coming back in the wrong language?**
We check the Unicode script ratio of the output. We saw a case where we asked for Tamil and got Hindi. If the check fails, we retry with `sarvam-105b-conversations`, and then with `sarvam-translate:v1`.

**Q: Privacy? These are sensitive calls.**
- **Stateless: nothing is stored on the server.** No session store, no database, no TTL.
- The browser keeps the result and sends it back only when you ask a question or want the complaint draft. Those requests are validated and capped at 600 KB.
- *Clear this page* wipes everything.
- Images are re-encoded, which strips EXIF and GPS.
- File types are checked by magic bytes, with size limits.
- Strict CSP and per-IP rate limiting.
- Links inside the content are never clickable.
- The API key only exists at runtime.

**Q: How accurate is it?**
The bundled samples give the expected verdicts (scam 97–100 for all four scams, 0 for the genuine notice). On a 40-case multilingual eval set (with hard negatives) the fused system scored 90% on the first run and 100% after fixing what that run exposed (a development-set score, since we tuned on it). The test suite has 151 passing tests. It caught real bugs, including a grounding hole where a long made-up quote could match a short segment. That's now fixed with windowed alignment. We're honest that the eval set is small. Growing it with real anonymised cases is our top roadmap item.

**Q: False positives on genuine messages, like bank alerts?**
Legitimate content with no verified red flags scores close to 0. The Tamil electricity notice scores 0. The bundled genuine Hindi bank SMS sample is there to show this live. Rule-only hits count at half weight, so one keyword can't turn something into a scam.

**Q: Could scammers game it?**
Paraphrasing can get past a lexicon, but not the LLM extraction. Invented evidence can't get past grounding. Because the taxonomy is fixed, we can extend it as I4C publishes new modus operandi.

**Q: How would this scale?**
It's already fully stateless and live on Vercel serverless, so any instance can serve any request. There's also a Docker image for self-hosting: non-root, health-checked, with the key passed at runtime. The only per-instance state is the rate-limit counters, and moving them to a shared store is next. Sarvam does the heavy lifting.

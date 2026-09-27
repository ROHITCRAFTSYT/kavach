/* Kavach · कवच — frontend (vanilla JS, CSP-safe: no innerHTML with content, no inline handlers) */
(() => {
  "use strict";

  // ------------------------------------------------------------------ helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const SVGNS = "http://www.w3.org/2000/svg";

  /** Build a DOM element. attrs: class, text, dataset, style (object), on (events), any attribute. */
  function h(tag, attrs, ...children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === null || v === undefined || v === false) continue;
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k === "dataset") Object.assign(node.dataset, v);
        else if (k === "style") Object.assign(node.style, v);
        else if (k === "on") for (const [ev, fn] of Object.entries(v)) node.addEventListener(ev, fn);
        else if (v === true) node.setAttribute(k, "");
        else node.setAttribute(k, String(v));
      }
    }
    appendAll(node, children);
    return node;
  }
  function appendAll(node, children) {
    for (const c of children.flat(Infinity)) {
      if (c === null || c === undefined || c === false) continue;
      node.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return node;
  }
  function svg(pathD, cls) {
    const s = document.createElementNS(SVGNS, "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("aria-hidden", "true");
    s.setAttribute("focusable", "false");
    if (cls) s.setAttribute("class", cls);
    const p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", pathD);
    s.append(p);
    return s;
  }
  const ICON = {
    check: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z",
    cross: "m6.4 5 5.6 5.6L17.6 5 19 6.4 13.4 12l5.6 5.6-1.4 1.4-5.6-5.6L6.4 19 5 17.6l5.6-5.6L5 6.4z",
    alert: "M1 21h22L12 2 1 21Zm12-3h-2v-2h2v2Zm0-4h-2v-4h2v4Z",
    shieldCheck: "M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Zm-1.3 14L7 12.3l1.4-1.4 2.3 2.3 4.9-4.9L17 9.7 10.7 16Z",
    eye: "M12 5C7 5 2.7 8.1 1 12.5 2.7 16.9 7 20 12 20s9.3-3.1 11-7.5C21.3 8.1 17 5 12 5Zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10Zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
    play: "M8 5v14l11-7z",
    rupee: "M6 3h12v2h-4.3c.6.6 1 1.3 1.2 2H18v2h-3.1A5 5 0 0 1 10 13h-.6l6.3 7h-2.7l-6.3-7V11H10a3 3 0 0 0 2.8-2H6V7h6.8A3 3 0 0 0 10 5H6z",
    clock: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 10.4 3.5 2.1-.8 1.3L11 13V7h2v5.4Z",
    phone: "M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1l-2.3 2.2Z",
    bank: "M12 2 2 7v2h20V7L12 2ZM4 11v7h3v-7H4Zm6.5 0v7h3v-7h-3ZM17 11v7h3v-7h-3ZM2 20v2h20v-2H2Z",
    link: "M10.6 13.4a1 1 0 0 0 1.4 0l3.5-3.5a3 3 0 0 0-4.2-4.2l-1 1 1.4 1.4 1-1a1 1 0 0 1 1.4 1.4L10.6 12a1 1 0 0 0 0 1.4ZM13.4 10.6a1 1 0 0 0-1.4 0l-3.5 3.5a3 3 0 0 0 4.2 4.2l1-1-1.4-1.4-1 1a1 1 0 0 1-1.4-1.4L13.4 12a1 1 0 0 0 0-1.4Z",
    tag: "M21.4 11.6 12.4 2.6A2 2 0 0 0 11 2H4a2 2 0 0 0-2 2v7c0 .6.2 1.1.6 1.4l9 9a2 2 0 0 0 2.8 0l7-7a2 2 0 0 0 0-2.8ZM6.5 8a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3Z",
    info: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15h-2v-6h2v6Zm0-8h-2V7h2v2Z",
  };

  const fmtTime = (sec) => {
    if (sec === null || sec === undefined || !isFinite(sec)) return "";
    const s = Math.max(0, Math.floor(sec));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  const fmtBytes = (n) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);
  const humanize = (s) => String(s || "").replace(/[_-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
  };

  let toastTimer = 0;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
  }

  async function errorFrom(res) {
    try {
      const j = await res.json();
      if (j && j.error) return String(j.error);
    } catch { /* ignore */ }
    if (res.status === 413) return "That file is too large.";
    if (res.status === 429) return "Too many requests. Please wait a minute and try again.";
    return `The server returned an error (${res.status}). Please try again.`;
  }

  // ------------------------------------------------------------------ state
  const S = {
    config: null,
    langs: new Map(),
    limits: { max_upload_mb: 25, max_audio_seconds: 900 },
    pendingFile: null,
    pendingUrl: null,
    run: null, // current analysis run
  };

  function newRun(input) {
    return {
      input,               // {file?, text?, sample?, sampleKind?}
      mediaUrl: input.mediaUrl || null,
      ownsUrl: !!input.ownsUrl,
      controller: new AbortController(),
      sessionId: null,
      language: null,
      source: null,
      analysis: null,
      localized: null,
      trace: null,
      finished: false,
      failed: false,
      startedAt: performance.now(),
      timer: 0,
      segEls: new Map(),   // segment id -> element
      boxEls: new Map(),   // segment id -> [bbox elements]
      sourceAudio: null,
      speechAudio: null,
    };
  }

  // ------------------------------------------------------------------ config / init
  async function loadConfig() {
    try {
      const res = await fetch("/api/config", { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(await errorFrom(res));
      S.config = await res.json();
    } catch (e) {
      S.config = { languages: [], samples: [], limits: S.limits };
      showInputError("Could not reach the Kavach server. Please check your connection and reload.");
    }
    S.limits = Object.assign(S.limits, S.config.limits || {});
    $("#dz-limit").textContent = `Up to ${S.limits.max_upload_mb} MB · audio up to ${Math.round(S.limits.max_audio_seconds / 60)} min`;
    populateLanguages();
    renderSamples();
  }

  function populateLanguages() {
    const sel = $("#language");
    for (const l of S.config.languages || []) {
      S.langs.set(l.code, l);
      const label = `${l.native} — ${l.name}${l.tts ? "" : " (text only, no voice)"}`;
      sel.append(h("option", { value: l.code, text: label, lang: l.code }));
    }
    const saved = store.get("kavach.lang");
    if (saved && (saved === "auto" || S.langs.has(saved))) sel.value = saved;
    sel.addEventListener("change", () => store.set("kavach.lang", sel.value));
  }
  const langName = (code) => {
    const l = S.langs.get(code);
    return l ? `${l.native} (${l.name})` : code || "";
  };

  function renderSamples() {
    const grid = $("#sample-grid");
    grid.replaceChildren();
    const samples = (S.config && S.config.samples) || [];
    if (!samples.length) {
      grid.append(h("p", { class: "muted", text: "Examples are unavailable right now." }));
      return;
    }
    for (const s of samples) {
      let thumb;
      const kindLabel = s.kind === "audio" ? "Recording" : s.kind === "document" ? "Photo" : "Message";
      if (s.kind === "document") {
        thumb = h("img", { src: `/samples/${encodeURIComponent(s.id)}`, alt: `Preview of ${s.title || "sample document"}`, loading: "lazy" });
      } else if (s.kind === "audio") {
        thumb = h("audio", { controls: true, preload: "none", src: `/samples/${encodeURIComponent(s.id)}`, "aria-label": `Listen to ${s.title || "sample"}` });
      } else {
        thumb = h("p", { class: "snippet", text: s.text || "" });
        if (s.subtitle && /hindi/i.test(s.subtitle)) thumb.lang = "hi";
      }
      const btn = h("button", { type: "button", class: "btn btn-secondary" }, svg(ICON.shieldCheck), "Check this example");
      btn.addEventListener("click", () => {
        const mediaUrl = s.kind === "text" ? null : `/samples/${encodeURIComponent(s.id)}`;
        startAnalysis({ sample: s.id, sampleKind: s.kind, mediaUrl, label: s.title });
      });
      grid.append(h("article", { class: "sample" },
        h("div", { class: "sample-thumb" }, thumb, h("span", { class: "badge badge-neutral sample-kind", text: kindLabel })),
        h("div", { class: "sample-body" },
          h("h3", { class: "sample-title", text: s.title || s.id }),
          s.subtitle ? h("p", { class: "sample-sub", text: s.subtitle }) : null,
          btn)));
    }
  }

  // ------------------------------------------------------------------ tabs
  function initTabs() {
    const tabs = Array.from(document.querySelectorAll(".tab"));
    const select = (tab, focus) => {
      for (const t of tabs) {
        const on = t === tab;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
        $("#" + t.getAttribute("aria-controls")).hidden = !on;
      }
      if (focus) tab.focus();
      hideInputError();
    };
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => select(t));
      t.addEventListener("keydown", (e) => {
        let j = null;
        if (e.key === "ArrowRight") j = (i + 1) % tabs.length;
        else if (e.key === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
        else if (e.key === "Home") j = 0;
        else if (e.key === "End") j = tabs.length - 1;
        if (j !== null) { e.preventDefault(); select(tabs[j], true); }
      });
    });
  }

  function showInputError(msg) { const e = $("#input-error"); e.textContent = msg; e.hidden = false; }
  function hideInputError() { $("#input-error").hidden = true; }

  // ------------------------------------------------------------------ upload
  const ACCEPT_RE = /^(image\/|audio\/|video\/webm|video\/ogg|application\/pdf)/;
  const EXT_RE = /\.(jpe?g|png|webp|gif|bmp|heic|pdf|mp3|wav|m4a|aac|ogg|oga|opus|webm|amr|flac|3gp)$/i;

  function initUpload() {
    const input = $("#file-input");
    const dz = $("#dropzone");
    input.addEventListener("change", () => { if (input.files && input.files[0]) pickFile(input.files[0]); });
    ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("is-drag"); }));
    ["dragleave", "dragend"].forEach((ev) => dz.addEventListener(ev, () => dz.classList.remove("is-drag")));
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      dz.classList.remove("is-drag");
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) pickFile(f);
    });
    // Allow dropping anywhere on the input card without the browser opening the file.
    window.addEventListener("dragover", (e) => e.preventDefault());
    window.addEventListener("drop", (e) => e.preventDefault());

    $("#fp-clear").addEventListener("click", () => { clearPending(); input.value = ""; input.click(); });
    $("#fp-check").addEventListener("click", () => {
      if (!S.pendingFile) return;
      const url = S.pendingUrl;
      S.pendingUrl = null; // ownership passes to the run
      startAnalysis({ file: S.pendingFile, mediaUrl: url, ownsUrl: true, label: S.pendingFile.name });
    });
  }

  function pickFile(file) {
    hideInputError();
    if (!(ACCEPT_RE.test(file.type || "") || EXT_RE.test(file.name || ""))) {
      showInputError("Please choose a photo, PDF, or audio recording.");
      return;
    }
    if (file.size > S.limits.max_upload_mb * 1024 * 1024) {
      showInputError(`That file is ${fmtBytes(file.size)}. The limit is ${S.limits.max_upload_mb} MB.`);
      return;
    }
    clearPending();
    S.pendingFile = file;
    S.pendingUrl = URL.createObjectURL(file);
    const media = $("#fp-media");
    media.replaceChildren();
    const type = file.type || "";
    if (type.startsWith("image/")) media.append(h("img", { src: S.pendingUrl, alt: "Preview of the chosen image" }));
    else if (type.startsWith("audio/") || type.startsWith("video/") || /\.(mp3|wav|m4a|aac|ogg|oga|opus|webm|amr|flac|3gp)$/i.test(file.name)) media.append(h("audio", { src: S.pendingUrl, controls: true, preload: "metadata" }));
    else media.append(h("div", { class: "fp-doc", text: "PDF" }));
    $("#fp-name").textContent = file.name || "Selected file";
    $("#fp-size").textContent = fmtBytes(file.size);
    $("#dropzone").hidden = true;
    $("#file-preview").hidden = false;
    $("#fp-check").focus();
  }

  function clearPending() {
    if (S.pendingUrl) URL.revokeObjectURL(S.pendingUrl);
    S.pendingUrl = null;
    S.pendingFile = null;
    $("#fp-media").replaceChildren();
    $("#file-preview").hidden = true;
    $("#dropzone").hidden = false;
  }

  // ------------------------------------------------------------------ recording (generic)
  function pickMime() {
    if (typeof MediaRecorder === "undefined") return null;
    const opts = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg", "audio/mp4"];
    for (const m of opts) { try { if (MediaRecorder.isTypeSupported(m)) return m; } catch { /* ignore */ } }
    return "";
  }
  function extFor(mime) {
    if (!mime) return "webm";
    if (mime.includes("ogg")) return "ogg";
    if (mime.includes("mp4")) return "m4a";
    return "webm";
  }

  /** Small recorder wrapper. onTick(seconds), onStop(blob|null, error?) */
  function createRecorder({ maxSeconds, onTick, onStop }) {
    let rec = null, stream = null, chunks = [], t0 = 0, iv = 0, stopTimer = 0;
    const cleanup = () => {
      clearInterval(iv); clearTimeout(stopTimer);
      if (stream) stream.getTracks().forEach((t) => t.stop());
      stream = null;
    };
    return {
      get active() { return !!rec && rec.state === "recording"; },
      async start() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
          throw new Error("Recording is not supported in this browser. Please upload a file instead.");
        }
        stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
        const mime = pickMime();
        rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        chunks = [];
        rec.addEventListener("dataavailable", (e) => { if (e.data && e.data.size) chunks.push(e.data); });
        rec.addEventListener("stop", () => {
          const type = rec.mimeType || mime || "audio/webm";
          const blob = chunks.length ? new Blob(chunks, { type }) : null;
          cleanup();
          onStop(blob, (Date.now() - t0) / 1000);
          rec = null;
        });
        rec.start(1000);
        t0 = Date.now();
        onTick(0);
        iv = setInterval(() => onTick((Date.now() - t0) / 1000), 250);
        stopTimer = setTimeout(() => this.stop(), maxSeconds * 1000);
      },
      stop() { if (rec && rec.state !== "inactive") rec.stop(); else cleanup(); },
      cancel() { if (rec && rec.state !== "inactive") { chunks = []; rec.stop(); } cleanup(); },
    };
  }

  const MAIN_REC_MAX = 300;
  let mainRec = null;
  let recBlob = null;
  let recUrl = null;

  function initRecorder() {
    const toggle = $("#rec-toggle");
    const label = $("#rec-label");
    const timer = $("#rec-timer");
    const status = $("#rec-status");
    const setTimer = (sec) => {
      timer.replaceChildren(fmtTime(sec) + " ", h("span", { class: "muted", text: `/ ${fmtTime(MAIN_REC_MAX)}` }));
    };
    mainRec = createRecorder({
      maxSeconds: MAIN_REC_MAX,
      onTick: setTimer,
      onStop: (blob, secs) => {
        toggle.classList.remove("is-recording");
        toggle.setAttribute("aria-pressed", "false");
        label.textContent = "Start recording";
        if (!blob || secs < 1) { status.textContent = "The recording was too short. Please try again."; return; }
        recBlob = blob;
        if (recUrl) URL.revokeObjectURL(recUrl);
        recUrl = URL.createObjectURL(blob);
        $("#rec-audio").src = recUrl;
        $("#rec-result").hidden = false;
        status.textContent = secs >= MAIN_REC_MAX - 1 ? "Stopped at the 5 minute limit." : "Recording ready. Listen back, then check it.";
        $("#rec-check").focus();
      },
    });
    toggle.addEventListener("click", async () => {
      hideInputError();
      if (mainRec.active) { mainRec.stop(); return; }
      try {
        $("#rec-result").hidden = true;
        status.textContent = "Starting microphone…";
        await mainRec.start();
        toggle.classList.add("is-recording");
        toggle.setAttribute("aria-pressed", "true");
        label.textContent = "Stop";
        status.textContent = "Recording… tap Stop when finished.";
      } catch (e) {
        status.textContent = "";
        showInputError(e && e.name === "NotAllowedError"
          ? "Microphone permission was blocked. Allow it in your browser settings, or upload a file instead."
          : (e && e.message) || "Could not start the microphone.");
      }
    });
    $("#rec-again").addEventListener("click", () => {
      $("#rec-result").hidden = true;
      setTimer(0);
      status.textContent = "";
      toggle.click();
    });
    $("#rec-check").addEventListener("click", () => {
      if (!recBlob) return;
      const file = new File([recBlob], `recording.${extFor(recBlob.type)}`, { type: recBlob.type || "audio/webm" });
      const url = URL.createObjectURL(recBlob);
      startAnalysis({ file, mediaUrl: url, ownsUrl: true, label: "Your recording" });
    });
  }

  // ------------------------------------------------------------------ text
  function initText() {
    const ta = $("#text-input");
    const count = $("#text-count");
    const upd = () => { count.textContent = `${ta.value.length} / ${ta.maxLength}`; };
    ta.addEventListener("input", upd);
    upd();
    $("#text-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const text = ta.value.trim();
      if (text.length < 8) { showInputError("Please paste the full message you received."); ta.focus(); return; }
      startAnalysis({ text, label: "Pasted message" });
    });
  }

  // ------------------------------------------------------------------ analysis run
  const STAGES = [
    { id: "read", label: "Reading the content" },
    { id: "check", label: "Checking for scam tricks" },
    { id: "explain", label: "Explaining in your language" },
    { id: "speak", label: "Preparing the voice" },
  ];

  function startAnalysis(input) {
    hideInputError();
    if (S.run) teardownRun(S.run);
    const run = newRun(input);
    S.run = run;
    resetResultView();
    $("#input-view").hidden = true;
    $("#result-view").hidden = false;
    window.scrollTo({ top: 0 });
    $("#main").focus({ preventScroll: true });
    buildStepper();
    run.timer = setInterval(() => {
      $("#elapsed").textContent = fmtTime((performance.now() - run.startedAt) / 1000);
      const sec = (performance.now() - run.startedAt) / 1000;
      if (!run.analysis && sec > 25) $("#progress-sub").textContent = "Still working — careful checks take a little longer. Please keep this page open.";
    }, 500);

    const fd = new FormData();
    if (input.file) fd.append("file", input.file, input.file.name || "upload");
    else if (input.sample) fd.append("sample", input.sample);
    else fd.append("text", input.text || "");
    fd.append("language", $("#language").value || "auto");

    streamAnalyze(run, fd).catch((err) => {
      if (run.controller.signal.aborted) return;
      failRun(run, (err && err.message) || "Connection lost. Please try again.");
    });
  }

  async function streamAnalyze(run, fd) {
    const res = await fetch("/api/analyze", { method: "POST", body: fd, signal: run.controller.signal, headers: { Accept: "application/x-ndjson" } });
    if (!res.ok) throw new Error(await errorFrom(res));
    if (!res.body || !res.body.getReader) {
      // Very old browsers: read whole body.
      const txt = await res.text();
      txt.split("\n").forEach((line) => handleLine(run, line));
    } else {
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, i);
          buf = buf.slice(i + 1);
          handleLine(run, line);
          if (S.run !== run) return;
        }
      }
      buf += dec.decode();
      if (buf.trim()) handleLine(run, buf);
    }
    if (S.run === run && !run.finished && !run.failed) {
      if (run.analysis) finishRun(run);
      else failRun(run, "The connection ended before the check finished. Please try again.");
    }
  }

  function handleLine(run, line) {
    line = line.trim();
    if (!line || S.run !== run) return;
    let ev;
    try { ev = JSON.parse(line); } catch { return; }
    try {
      switch (ev.type) {
        case "stage": onStage(ev); break;
        case "source": onSource(run, ev); break;
        case "analysis": onAnalysis(run, ev.analysis || {}); break;
        case "localized": onLocalized(run, ev.localized || {}); break;
        case "speech": onSpeech(run, b64ToUrl(ev.audio_b64, ev.mime)); break;
        case "notice": addNotice(ev.message); break;
        case "trace": run.trace = ev; renderTrace(run); break;
        case "done": finishRun(run); break;
        case "error": failRun(run, ev.message || "Something went wrong."); break;
        default: break;
      }
    } catch (e) {
      // Never let one bad event kill the stream.
      console.error("Kavach: failed to render event", ev && ev.type, e);
    }
  }

  function teardownRun(run) {
    try { run.controller.abort(); } catch { /* ignore */ }
    clearInterval(run.timer);
    [run.sourceAudio, run.speechAudio].forEach((a) => { if (a) { try { a.pause(); } catch { /* ignore */ } } });
    const sp = $("#speech-audio"); try { sp.pause(); } catch { /* ignore */ }
    if (run.ownsUrl && run.mediaUrl) URL.revokeObjectURL(run.mediaUrl);
  }

  // ------------------------------------------------------------------ progress
  function buildStepper() {
    const ol = $("#stepper");
    ol.replaceChildren();
    for (const st of STAGES) {
      ol.append(h("li", { class: "step", id: `step-${st.id}`, dataset: { status: "pending" } },
        h("span", { class: "step-icon" }),
        h("span", { class: "step-text" },
          h("span", { class: "step-label", text: st.label }),
          h("span", { class: "step-msg" }))));
    }
  }

  function onStage(ev) {
    const li = $(`#step-${CSS.escape(ev.id || "")}`);
    if (!li) return;
    li.dataset.status = ev.status || "active";
    if (ev.label) $(".step-label", li).textContent = ev.label;
    $(".step-msg", li).textContent = ev.message || "";
    const icon = $(".step-icon", li);
    icon.replaceChildren();
    if (ev.status === "done") icon.append(svg(ICON.check));
    else if (ev.status === "failed") icon.append(svg(ICON.cross));
    const verb = ev.status === "done" ? "Done" : ev.status === "failed" ? "Problem" : "Now";
    $("#progress-live").textContent = `${verb}: ${ev.label || ev.id}${ev.message ? ". " + ev.message : ""}`;
  }

  function addNotice(msg) {
    if (!msg) return;
    $("#notices").append(h("li", { text: msg }));
  }

  function finishRun(run) {
    if (run.finished) return;
    run.finished = true;
    clearInterval(run.timer);
    const card = $("#progress-card");
    card.classList.add("is-done");
    $("#progress-title").textContent = run.failed ? "Check stopped" : "Check complete";
    $("#progress-sub").textContent = `Finished in ${fmtTime((performance.now() - run.startedAt) / 1000)} min`;
    // Mark any still-active stage done (defensive).
    document.querySelectorAll('.step[data-status="active"]').forEach((li) => onStage({ id: li.id.slice(5), status: "done" }));
    document.querySelectorAll('.step[data-status="pending"]').forEach((li) => { li.dataset.status = "done"; $(".step-icon", li).replaceChildren(svg(ICON.check)); $(".step-msg", li).textContent = "Skipped"; });
    if (run.sessionId && run.analysis) enableAsk(true);
  }

  function failRun(run, message) {
    if (run.failed) return;
    run.failed = true;
    clearInterval(run.timer);
    $("#progress-card").classList.add("is-failed");
    document.querySelectorAll('.step[data-status="active"]').forEach((li) => onStage({ id: li.id.slice(5), status: "failed" }));
    if (run.analysis) {
      // Partial result is still useful: show error as a notice.
      addNotice(message);
      finishRun(run);
      return;
    }
    $("#progress-title").textContent = "Check could not finish";
    $("#progress-sub").textContent = "";
    $("#error-message").textContent = message;
    $("#error-card").hidden = false;
    $("#btn-error-reset").focus();
  }

  // ------------------------------------------------------------------ source / evidence
  function onSource(run, ev) {
    run.sessionId = ev.session_id || null;
    run.language = ev.language || null;
    run.source = ev.source || { segments: [] };
    $("#btn-delete").disabled = !run.sessionId;
    $("#footer-delete").disabled = !run.sessionId;
    renderEvidence(run);
  }

  function flaggedMap(run) {
    // segment id -> [{fi, start, end, quote}]
    const map = new Map();
    const findings = (run.analysis && run.analysis.findings) || [];
    findings.forEach((f, fi) => {
      const ev = f.evidence || {};
      if (!ev.segment_id) return;
      if (!map.has(ev.segment_id)) map.set(ev.segment_id, []);
      map.get(ev.segment_id).push({ fi, start: ev.start_char, end: ev.end_char, quote: ev.quote || "" });
    });
    return map;
  }

  /** Render text with <mark> spans for the flagged ranges. */
  function markedText(text, marks) {
    const frag = document.createDocumentFragment();
    text = String(text || "");
    const ranges = [];
    for (const m of marks || []) {
      let s = Number.isInteger(m.start) ? m.start : -1;
      let e = Number.isInteger(m.end) ? m.end : -1;
      if (!(s >= 0 && e > s && e <= text.length) && m.quote) {
        s = text.indexOf(m.quote);
        e = s >= 0 ? s + m.quote.length : -1;
      }
      if (s >= 0 && e > s) ranges.push({ s, e: Math.min(e, text.length), fi: m.fi });
    }
    ranges.sort((a, b) => a.s - b.s);
    const merged = [];
    for (const r of ranges) {
      const last = merged[merged.length - 1];
      if (last && r.s <= last.e) { last.e = Math.max(last.e, r.e); last.fis.push(r.fi); }
      else merged.push({ s: r.s, e: r.e, fis: [r.fi] });
    }
    let pos = 0;
    for (const r of merged) {
      if (r.s > pos) frag.append(text.slice(pos, r.s));
      const mk = h("mark", { class: "flag", dataset: { finding: String(r.fis[0]) }, title: "Red flag — tap to see why" }, text.slice(r.s, r.e));
      mk.addEventListener("click", (e) => { e.stopPropagation(); focusFinding(Number(mk.dataset.finding), { fromEvidence: true }); });
      frag.append(mk);
      pos = r.e;
    }
    if (pos < text.length) frag.append(text.slice(pos));
    return frag;
  }

  function renderEvidence(run) {
    const src = run.source;
    if (!src) return;
    const card = $("#evidence-card");
    const box = $("#evidence");
    card.hidden = false;
    box.replaceChildren();
    run.segEls = new Map();
    run.boxEls = new Map();
    const flagged = flaggedMap(run);
    const segs = Array.isArray(src.segments) ? src.segments : [];
    const lang = src.language || run.language || null;
    const modality = src.modality || "text";

    const kindText = { audio: "Recording", image: "Photo", pdf: "PDF", text: "Message" }[modality] || humanize(modality);
    $("#evidence-kind").textContent = kindText;
    const subBits = [];
    if (src.filename && !String(src.filename).startsWith("text:")) subBits.push(src.filename);
    if (src.duration) subBits.push(fmtTime(src.duration) + " min");
    if (src.pages) subBits.push(`${src.pages} page${src.pages > 1 ? "s" : ""}`);
    if (src.language) subBits.push(`Detected: ${langName(src.language)}${src.language_confidence ? ` (${Math.round(src.language_confidence * 100)}%)` : ""}`);
    $("#evidence-sub").textContent = subBits.join(" · ");

    if (modality === "audio") {
      const suspected = run.analysis ? run.analysis.suspected_caller : null;
      if (run.mediaUrl) {
        const audio = h("audio", { controls: true, preload: "metadata", src: run.mediaUrl, "aria-label": "Original recording" });
        if (run.sourceAudio) { try { run.sourceAudio.pause(); } catch { /* ignore */ } }
        run.sourceAudio = audio;
        audio.addEventListener("timeupdate", () => highlightPlaying(run, audio.currentTime));
        box.append(h("div", { class: "player-row" }, audio));
      }
      const speakers = [...new Set(segs.map((s) => s.speaker).filter(Boolean))];
      if (speakers.length > 1 || suspected) {
        box.append(h("div", { class: "speaker-legend" }, speakers.map((sp) =>
          h("span", { class: sp === suspected ? "badge badge-high" : "badge badge-neutral", text: sp === suspected ? `Speaker ${sp}: Suspected caller` : `Speaker ${sp}` }))));
      }
      const tr = h("div", { class: "transcript", lang: lang || null });
      const firstSpeaker = speakers[0];
      for (const seg of segs) {
        const isCaller = suspected && seg.speaker === suspected;
        const right = suspected ? !isCaller && !!seg.speaker : (seg.speaker && seg.speaker !== firstSpeaker);
        const marks = flagged.get(seg.id);
        const timeBtn = seg.start !== null && seg.start !== undefined
          ? h("button", { type: "button", class: "utt-time", "aria-label": `Play from ${fmtTime(seg.start)}`, text: fmtTime(seg.start) })
          : null;
        if (timeBtn) timeBtn.addEventListener("click", () => seekAudio(run, seg.start));
        const el = h("div", {
          class: `utt${right ? " lane-right" : ""}${isCaller ? " is-caller" : ""}${marks ? " is-flagged" : ""}`,
          id: `seg-${seg.id}`, dataset: { start: seg.start ?? "", end: seg.end ?? "" },
        },
          h("div", { class: "utt-meta" },
            h("span", { class: "utt-speaker", text: isCaller ? "Suspected caller" : seg.speaker ? `Speaker ${seg.speaker}` : "Speaker" }),
            timeBtn),
          h("div", { class: "utt-bubble" }, markedText(seg.text, marks)));
        run.segEls.set(seg.id, el);
        tr.append(el);
      }
      if (!segs.length) tr.append(h("p", { class: "muted", text: "No speech was found in this recording." }));
      box.append(tr);
      return;
    }

    if (modality === "image" && run.mediaUrl) {
      const view = h("div", { class: "doc-view" });
      const img = h("img", { src: run.mediaUrl, alt: "The document you shared, with red flags outlined" });
      view.append(img);
      for (const seg of segs) {
        if (!flagged.has(seg.id) || !Array.isArray(seg.bbox) || seg.bbox.length !== 4) continue;
        const [x1, y1, x2, y2] = seg.bbox.map(Number);
        if (![x1, y1, x2, y2].every(isFinite)) continue;
        const pct = (v) => `${Math.max(0, Math.min(100, v * 100))}%`;
        const fi = flagged.get(seg.id)[0].fi;
        const b = h("button", { type: "button", class: "bbox", "aria-label": "Red flag area — show details", dataset: { finding: String(fi), seg: seg.id } });
        Object.assign(b.style, { left: pct(x1), top: pct(y1), width: pct(Math.max(0.005, x2 - x1)), height: pct(Math.max(0.005, y2 - y1)) });
        b.addEventListener("click", () => focusFinding(fi, { fromEvidence: true }));
        view.append(b);
        if (!run.boxEls.has(seg.id)) run.boxEls.set(seg.id, []);
        run.boxEls.get(seg.id).push(b);
      }
      box.append(view);
      const det = h("details", { class: "segments-details" }, h("summary", { text: "Text Kavach read from the photo" }));
      det.append(segmentList(run, segs, flagged, lang, false));
      if (flagged.size) det.open = true;
      box.append(det);
      return;
    }

    // pdf / text / image-without-preview
    box.append(segmentList(run, segs, flagged, lang, modality === "pdf" || modality === "image"));
  }

  function segmentList(run, segs, flagged, lang, byPage) {
    const wrap = h("div", { class: `segments${byPage ? "" : " text-view"}`, lang: lang || null });
    let lastPage = null;
    for (const seg of segs) {
      if (byPage && seg.page !== null && seg.page !== undefined && seg.page !== lastPage) {
        lastPage = seg.page;
        wrap.append(h("p", { class: "page-head", text: `Page ${seg.page}` }));
      }
      const marks = flagged.get(seg.id);
      const el = h("p", { class: `seg${marks ? " is-flagged" : ""}`, id: `seg-${seg.id}` }, markedText(seg.text, marks));
      run.segEls.set(seg.id, el);
      wrap.append(el);
    }
    if (!segs.length) wrap.append(h("p", { class: "muted", text: "No readable text was found." }));
    return wrap;
  }

  function seekAudio(run, t) {
    const a = run.sourceAudio;
    if (!a || t === null || t === undefined) return;
    try {
      a.currentTime = Math.max(0, Number(t) - 0.2);
      const p = a.play();
      if (p && p.catch) p.catch(() => {});
    } catch { /* ignore */ }
  }

  let lastPlayingId = null;
  function highlightPlaying(run, t) {
    let cur = null;
    for (const [id, el] of run.segEls) {
      const s = parseFloat(el.dataset.start), e = parseFloat(el.dataset.end);
      if (isFinite(s) && isFinite(e) && t >= s && t < e) { cur = id; break; }
    }
    if (cur === lastPlayingId) return;
    if (lastPlayingId && run.segEls.get(lastPlayingId)) run.segEls.get(lastPlayingId).classList.remove("is-playing");
    if (cur) run.segEls.get(cur).classList.add("is-playing");
    lastPlayingId = cur;
  }

  // ------------------------------------------------------------------ analysis
  const VERDICT = {
    scam: { label: "Likely scam", icon: ICON.alert, meter: "High risk" },
    suspicious: { label: "Suspicious — be careful", icon: ICON.alert, meter: "Medium risk" },
    low_risk: { label: "Looks genuine · low risk", icon: ICON.shieldCheck, meter: "Low risk" },
  };

  function onAnalysis(run, a) {
    run.analysis = a;
    renderVerdict(run);
    renderFindings(run);
    renderFacts(run);
    renderEnglish(run);
    if (run.source) renderEvidence(run); // re-render with marks & caller label
    $("#report-card").hidden = a.verdict === "low_risk";
    $("#ask-card").hidden = false;
    if (!run.localized) renderExplainFallback(run);
    if (run.trace) renderTrace(run);
    $("#progress-sub").textContent = "Result ready — finishing the explanation and voice…";
  }

  function renderVerdict(run) {
    const a = run.analysis;
    const v = VERDICT[a.verdict] || VERDICT.suspicious;
    const sec = $("#verdict");
    sec.dataset.verdict = a.verdict || "suspicious";
    sec.hidden = false;
    $("#verdict-label").replaceChildren(svg(v.icon), v.label);
    const headline = $("#verdict-headline");
    if (!run.localized) {
      headline.textContent = a.verdict === "scam" ? "This looks like a scam. Do not pay or share any details."
        : a.verdict === "suspicious" ? "Some things here are worrying. Verify before you act."
        : "No scam signs found. Read the details below.";
      headline.removeAttribute("lang");
    }
    const meta = [];
    if (a.claimed_sender) meta.push(`Claims to be from: ${a.claimed_sender}`);
    if (a.document_kind) meta.push(humanize(a.document_kind));
    $("#verdict-meta").textContent = meta.join(" · ");
    const deg = $("#verdict-degraded");
    deg.hidden = !a.degraded;
    deg.textContent = a.degraded ? "Note: the AI check was partly unavailable, so this result relies more on fraud rules. Treat it with extra care." : "";
    renderGauge(Number(a.risk_score) || 0, v.meter);
  }

  function renderGauge(score, cap) {
    score = Math.max(0, Math.min(100, Math.round(score)));
    const g = $("#gauge");
    g.replaceChildren();
    g.setAttribute("aria-valuenow", String(score));
    g.setAttribute("aria-valuetext", `${score} out of 100, ${cap}`);
    const s = document.createElementNS(SVGNS, "svg");
    s.setAttribute("viewBox", "0 0 180 104");
    s.setAttribute("aria-hidden", "true");
    const d = "M 16 92 A 74 74 0 0 1 164 92";
    const track = document.createElementNS(SVGNS, "path");
    track.setAttribute("d", d); track.setAttribute("class", "gauge-track");
    const val = document.createElementNS(SVGNS, "path");
    val.setAttribute("d", d); val.setAttribute("class", "gauge-value");
    const len = Math.PI * 74;
    val.style.strokeDasharray = `${len}`;
    val.style.strokeDashoffset = `${len}`;
    s.append(track, val);
    g.append(s, h("div", { class: "gauge-num", text: String(score) }), h("div", { class: "gauge-cap", text: `Risk score · ${cap}` }));
    requestAnimationFrame(() => requestAnimationFrame(() => { val.style.strokeDashoffset = `${len * (1 - score / 100)}`; }));
  }

  function sourceBadge(f) {
    if (f.corroborated) return h("span", { class: "badge badge-corr", title: "Found by both the AI and Kavach's fraud rules", text: "AI + rules ✓" });
    if (f.source === "rule") return h("span", { class: "badge badge-rule", title: "Found by Kavach's fraud rules", text: "Rule" });
    return h("span", { class: "badge badge-ai", title: "Found by the AI and verified in the source", text: "AI" });
  }

  function renderFindings(run) {
    const a = run.analysis;
    const list = $("#findings");
    list.replaceChildren();
    const findings = Array.isArray(a.findings) ? a.findings : [];
    const card = $("#flags-card");
    card.hidden = false;
    $("#flags-count").textContent = findings.length ? String(findings.length) : "";
    $("#flags-title").firstChild.textContent = findings.length ? "Red flags found " : "Red flags ";
    if (!findings.length) list.append(h("li", { class: "no-flags", text: "No scam warning signs were found in this content." }));
    const lang = (run.source && run.source.language) || run.language || null;
    findings.forEach((f, i) => {
      const ev = f.evidence || {};
      const btn = h("button", { type: "button", class: "finding", dataset: { sev: f.severity || "low", index: String(i) }, "aria-describedby": null },
        h("span", { class: "finding-top" },
          h("span", { class: "finding-name", text: f.pattern_name || humanize(f.pattern_id) }),
          h("span", { class: "finding-badges" },
            h("span", { class: `badge badge-${f.severity || "low"}`, text: `${humanize(f.severity || "low")} risk` }),
            sourceBadge(f))),
        ev.quote ? h("span", { class: `finding-quote${ev.verified === false ? " unverified" : ""}`, lang: lang, style: { display: "block" }, text: `“${ev.quote}”` }) : null,
        f.explanation ? h("span", { class: "finding-expl", style: { display: "block" }, text: f.explanation }) : null,
        ev.segment_id ? h("span", { class: "finding-jump" }, svg(ICON.eye), "Show where") : null);
      btn.addEventListener("click", () => focusFinding(i));
      list.append(h("li", null, btn));
    });
    const legit = Array.isArray(a.legitimacy_indicators) ? a.legitimacy_indicators : [];
    $("#legit").hidden = !legit.length;
    $("#legit-list").replaceChildren(...legit.map((t) => h("li", { text: t })));
  }

  function focusFinding(i, opts = {}) {
    const run = S.run;
    if (!run || !run.analysis) return;
    const f = (run.analysis.findings || [])[i];
    if (!f) return;
    document.querySelectorAll(".finding.is-active").forEach((el) => el.classList.remove("is-active"));
    document.querySelectorAll(".is-focus").forEach((el) => el.classList.remove("is-focus"));
    document.querySelectorAll(".bbox.is-active").forEach((el) => el.classList.remove("is-active"));
    const card = document.querySelector(`.finding[data-index="${i}"]`);
    if (card) card.classList.add("is-active");
    const segId = f.evidence && f.evidence.segment_id;
    if (opts.fromEvidence) {
      if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    if (!segId) return;
    focusSegment(run, segId, !opts.fromEvidence);
  }

  function focusSegment(run, segId, scroll) {
    const segEl = run.segEls.get(segId);
    const boxes = run.boxEls.get(segId) || [];
    boxes.forEach((b) => { b.classList.remove("is-active"); void b.offsetWidth; b.classList.add("is-active"); });
    if (segEl) {
      segEl.classList.add("is-focus");
      const det = segEl.closest("details");
      if (det && !boxes.length) det.open = true;
    }
    const target = boxes[0] || segEl;
    if (scroll && target) target.scrollIntoView({ behavior: "smooth", block: "center" });
    if (run.source && run.source.modality === "audio" && segEl) {
      const start = parseFloat(segEl.dataset.start);
      if (isFinite(start)) seekAudio(run, start);
    }
  }

  const FACT_ICON = { amount: ICON.rupee, deadline: ICON.clock, contact: ICON.phone, account_or_upi: ICON.bank, link: ICON.link, reference_id: ICON.tag };
  function renderFacts(run) {
    const facts = Array.isArray(run.analysis.key_facts) ? run.analysis.key_facts : [];
    const card = $("#facts-card");
    card.hidden = !facts.length;
    const ul = $("#facts");
    ul.replaceChildren();
    for (const k of facts) {
      const clickable = !!(k.segment_id && run.segEls.has(k.segment_id));
      const li = h("li", { class: `fact${clickable ? " is-clickable" : ""}`, dataset: { kind: k.kind || "other" }, tabindex: clickable ? "0" : null, role: clickable ? "button" : null },
        h("span", { class: "fact-kind" }, svg(FACT_ICON[k.kind] || ICON.info), humanize(k.kind || "detail")),
        k.label ? h("span", { class: "fact-label", text: k.label }) : null,
        // Plain text on purpose — never a hyperlink.
        h("span", { class: "fact-value", text: String(k.value ?? "") }),
        k.kind === "link" ? h("span", { class: "fact-warn", text: "Do not open this link" }) : null);
      if (clickable) {
        const go = () => {
          document.querySelectorAll(".is-focus").forEach((el) => el.classList.remove("is-focus"));
          focusSegment(run, k.segment_id, true);
        };
        li.addEventListener("click", go);
        li.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
      }
      ul.append(li);
    }
  }

  function renderEnglish(run) {
    const a = run.analysis;
    $("#english-details").hidden = !(a.summary || (a.actions && a.actions.length));
    $("#english-summary").textContent = a.summary || "";
    const ul = $("#english-actions");
    ul.replaceChildren();
    for (const act of a.actions || []) {
      const text = typeof act === "string" ? act : act.text;
      const prio = typeof act === "string" ? null : act.priority;
      ul.append(h("li", null, prio ? h("span", { class: `prio prio-${prio}`, text: prio }) : null, text || ""));
    }
  }

  // ------------------------------------------------------------------ localized explanation + speech
  function renderExplainFallback(run) {
    const a = run.analysis;
    const card = $("#explain-card");
    card.hidden = false;
    const body = $("#explain-body");
    body.removeAttribute("lang");
    body.replaceChildren(h("p", { text: a.summary || "" }));
    renderChecklist((a.actions || []).map((x) => (typeof x === "string" ? { text: x } : x)), null);
    $("#explain-method").textContent = "Your-language explanation is on its way…";
  }

  function onLocalized(run, loc) {
    run.localized = loc;
    const card = $("#explain-card");
    card.hidden = false;
    const lang = loc.language || run.language || null;
    const lname = langName(lang);
    $("#explain-title").textContent = lname ? `What this means · ${lname}` : "What this means";
    const headline = $("#verdict-headline");
    if (loc.headline) {
      headline.textContent = loc.headline;
      if (lang) headline.lang = lang;
    }
    const body = $("#explain-body");
    if (lang) body.lang = lang; else body.removeAttribute("lang");
    const paras = String(loc.explanation || "").split(/\n{1,}/).map((p) => p.trim()).filter(Boolean);
    body.replaceChildren(...paras.map((p) => h("p", { text: p })));
    const acts = Array.isArray(loc.actions) ? loc.actions : [];
    const pri = ((run.analysis && run.analysis.actions) || []).map((x) => (x && x.priority) || null);
    renderChecklist(acts.map((t, i) => ({ text: typeof t === "string" ? t : t.text, priority: acts.length === pri.length ? pri[i] : null })), lang);
    const method = { llm: "Written in your language by Sarvam-105B", translated: "Translated with Sarvam AI", english: "Shown in English" }[loc.method] || "";
    $("#explain-method").textContent = method;
  }

  function renderChecklist(items, lang) {
    const block = $("#actions-block");
    const ul = $("#checklist");
    ul.replaceChildren();
    block.hidden = !items.length;
    items.forEach((it, i) => {
      const id = `act-${i}`;
      const prioLabel = { now: "Now", soon: "Soon", optional: "Optional" }[it.priority];
      ul.append(h("li", null, h("label", { for: id },
        h("input", { type: "checkbox", id }),
        h("span", { lang: lang || null }, prioLabel ? h("span", { class: `prio prio-${it.priority}`, lang: "en", text: prioLabel }) : null, it.text || ""))));
    });
  }

  // Audio arrives inline (base64) because the server is stateless; turn it into a blob: URL.
  const blobUrls = [];
  function b64ToUrl(b64, mime) {
    if (!b64) return null;
    try {
      const bin = atob(b64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const url = URL.createObjectURL(new Blob([bytes], { type: mime || "audio/wav" }));
      blobUrls.push(url);
      return url;
    } catch { return null; }
  }
  function revokeBlobUrls() { while (blobUrls.length) URL.revokeObjectURL(blobUrls.pop()); }

  function onSpeech(run, url) {
    if (!url || !String(url).startsWith("blob:")) return;
    const audio = $("#speech-audio");
    run.speechAudio = audio;
    audio.src = url;
    audio.hidden = false;
    $("#explain-card").hidden = false;
    $("#listen").hidden = false;
    const btn = $("#btn-listen");
    const p = audio.play();
    if (p && p.catch) {
      p.catch(() => {
        btn.classList.add("nudge");
        $("#listen-label").textContent = "Listen";
      });
    }
  }

  function initListen() {
    const audio = $("#speech-audio");
    const btn = $("#btn-listen");
    const lbl = $("#listen-label");
    btn.addEventListener("click", () => {
      btn.classList.remove("nudge");
      if (audio.paused) { const p = audio.play(); if (p && p.catch) p.catch(() => toast("Could not play audio on this device.")); }
      else audio.pause();
    });
    audio.addEventListener("play", () => { btn.setAttribute("aria-pressed", "true"); lbl.textContent = "Pause"; btn.classList.remove("nudge"); });
    audio.addEventListener("pause", () => { btn.setAttribute("aria-pressed", "false"); lbl.textContent = "Listen"; });
    audio.addEventListener("ended", () => { btn.setAttribute("aria-pressed", "false"); lbl.textContent = "Listen again"; });
  }

  // ------------------------------------------------------------------ trace
  function renderTrace(run) {
    const t = run.trace;
    if (!t) return;
    const det = $("#trace-details");
    det.hidden = false;
    $("#trace-total").textContent = t.total_ms ? `${(t.total_ms / 1000).toFixed(1)} s total` : "";
    const body = $("#trace-body");
    body.replaceChildren();

    body.append(h("div", { class: "trace-summary" },
      t.modality ? h("span", { class: "badge badge-neutral", text: `Input: ${humanize(t.modality)}` }) : null,
      t.request_id ? h("span", { class: "badge badge-neutral", text: `Request ${t.request_id}` }) : null,
      run.analysis && run.analysis.degraded ? h("span", { class: "badge badge-medium", text: "Degraded mode" }) : null));
    if (t.path) body.append(h("div", null, h("h3", { class: "trace-h", text: "Pipeline" }), h("p", { class: "trace-path", text: t.path })));

    const spans = Array.isArray(t.spans) ? t.spans : [];
    if (spans.length) {
      const total = Math.max(t.total_ms || 0, spans.reduce((m, s) => Math.max(m, s.ms || 0), 0), 1);
      const ol = h("ol", { class: "spans", "aria-label": "Sarvam API calls and timings" });
      for (const s of spans) {
        const row = h("li", { class: `span-row${s.ok === false ? " fail" : ""}` },
          h("span", { class: "span-name" },
            s.api ? h("span", { class: "api-tag", text: s.api }) : null,
            h("code", { text: s.name || "", title: s.detail || s.name || "" })),
          h("span", { class: "span-bar", "aria-hidden": "true" }, h("span", { class: "span-fill", style: { left: "0", width: `${Math.max(1, ((s.ms || 0) / total) * 100)}%` } })),
          h("span", { class: "span-ms", text: `${s.ms ?? 0} ms${s.ok === false ? " ✕" : ""}` }));
        ol.append(row);
      }
      body.append(h("div", null, h("h3", { class: "trace-h", text: "Sarvam API calls" }), ol));
    }

    const a = run.analysis;
    if (a && Array.isArray(a.score_breakdown) && a.score_breakdown.length) {
      const tbody = h("tbody", null, a.score_breakdown.map((r) => h("tr", null,
        h("td", { text: r.pattern || humanize(r.pattern_id) }),
        h("td", null, r.corroborated ? h("span", { class: "badge badge-corr", text: "AI + rules" }) : h("span", { class: `badge ${r.source === "rule" ? "badge-rule" : "badge-ai"}`, text: r.source === "rule" ? "Rule" : "AI" })),
        h("td", null, h("span", { class: `badge badge-${r.severity || "low"}`, text: humanize(r.severity || "") })),
        h("td", { class: "num", text: typeof r.weight === "number" ? `+${Math.round(r.weight * 10) / 10}` : String(r.weight ?? "") }))));
      body.append(h("div", null,
        h("h3", { class: "trace-h", text: `How the risk score (${a.risk_score ?? "–"}/100) was built` }),
        h("div", { class: "table-wrap" }, h("table", null,
          h("thead", null, h("tr", null, h("th", { text: "Pattern" }), h("th", { text: "Source" }), h("th", { text: "Severity" }), h("th", { text: "Weight", style: { textAlign: "right" } }))),
          tbody))));
    }
    if (a && Array.isArray(a.rejected_claims) && a.rejected_claims.length) {
      body.append(h("div", null,
        h("h3", { class: "trace-h", text: `Discarded: AI claims not found in the source (${a.rejected_claims.length})` }),
        h("p", { class: "muted small", text: "Kavach only reports red flags it can point to in the original. These AI claims could not be verified, so they were removed from the score." }),
        h("ul", { class: "rejected" }, a.rejected_claims.map((r) => h("li", null,
          h("strong", { text: r.pattern_name || humanize(r.pattern_id) }), " — ",
          r.evidence && r.evidence.quote ? h("span", { class: "rj-quote", text: `“${r.evidence.quote}”` }) : "no quote",
          r.explanation ? h("div", { text: r.explanation }) : null)))));
    }
  }

  // ------------------------------------------------------------------ ask
  let askRec = null;
  function enableAsk(on) {
    $("#ask-input").disabled = !on;
    $("#ask-send").disabled = !on;
    $("#ask-mic").disabled = !on || typeof MediaRecorder === "undefined";
    $("#ask-status").textContent = on ? "" : "You can ask questions once the check is finished.";
  }

  function addBubble(kind, text, lang) {
    const b = h("div", { class: `bubble ${kind}`, lang: lang || null }, text);
    $("#chat").append(b);
    b.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return b;
  }

  async function sendQuestion({ question, audioBlob }) {
    const run = S.run;
    if (!run || !run.sessionId) return;
    const fd = new FormData();
    run.qa = run.qa || [];
    fd.append("context", JSON.stringify({ source: run.source, analysis: run.analysis, history: run.qa.slice(-8) }));
    if (audioBlob) fd.append("audio", new File([audioBlob], `question.${extFor(audioBlob.type)}`, { type: audioBlob.type || "audio/webm" }));
    else fd.append("question", question);
    const langSel = $("#language").value;
    const lang = langSel && langSel !== "auto" ? langSel : (run.localized && run.localized.language) || run.language;
    if (lang) fd.append("language", lang);

    const qBubble = addBubble("q", audioBlob ? "Voice question…" : question);
    const pending = addBubble("a pending", h("span", { class: "typing", "aria-label": "Kavach is thinking" }, h("i"), h("i"), h("i")));
    enableAsk(false);
    $("#ask-status").textContent = "Kavach is thinking…";
    try {
      const res = await fetch("/api/ask", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await errorFrom(res));
      const j = await res.json();
      if (S.run !== run) return;
      qBubble.textContent = j.question || question || "";
      pending.classList.remove("pending");
      if (lang) pending.lang = lang;
      pending.replaceChildren(j.answer || "");
      if (j.question && j.answer) run.qa.push({ role: "user", content: j.question }, { role: "assistant", content: j.answer });
      const answerUrl = b64ToUrl(j.audio_b64, j.mime);
      if (answerUrl) {
        const a = h("audio", { controls: true, preload: "auto", src: answerUrl, "aria-label": "Listen to the answer" });
        pending.append(a);
        const speech = $("#speech-audio"); try { speech.pause(); } catch { /* ignore */ }
        const p = a.play(); if (p && p.catch) p.catch(() => {});
      }
      $("#ask-status").textContent = "";
    } catch (e) {
      pending.classList.remove("pending");
      pending.classList.add("err");
      pending.replaceChildren((e && e.message) || "Could not get an answer. Please try again.");
      if (audioBlob) qBubble.textContent = "Voice question";
    } finally {
      if (S.run === run) { enableAsk(true); $("#ask-input").focus(); }
    }
  }

  function initAsk() {
    const form = $("#ask-form");
    const input = $("#ask-input");
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) { input.focus(); return; }
      input.value = "";
      sendQuestion({ question: q });
    });
    const mic = $("#ask-mic");
    askRec = createRecorder({
      maxSeconds: 28,
      onTick: (s) => { $("#ask-status").textContent = `Listening… ${fmtTime(s)} — tap the mic again to send`; },
      onStop: (blob, secs) => {
        mic.setAttribute("aria-pressed", "false");
        mic.setAttribute("aria-label", "Ask by voice");
        $("#ask-status").textContent = "";
        if (!blob || secs < 0.8) { $("#ask-status").textContent = "That was too short — please try again."; return; }
        sendQuestion({ audioBlob: blob });
      },
    });
    mic.addEventListener("click", async () => {
      if (askRec.active) { askRec.stop(); return; }
      try {
        await askRec.start();
        mic.setAttribute("aria-pressed", "true");
        mic.setAttribute("aria-label", "Stop and send voice question");
      } catch (e) {
        $("#ask-status").textContent = e && e.name === "NotAllowedError" ? "Microphone permission was blocked." : (e && e.message) || "Could not start the microphone.";
      }
    });
  }

  // ------------------------------------------------------------------ complaint
  let complaintText = "";
  function initComplaint() {
    const dlg = $("#complaint-dialog");
    $("#btn-complaint").addEventListener("click", async () => {
      const run = S.run;
      if (!run || !run.sessionId) return;
      const btn = $("#btn-complaint");
      btn.disabled = true;
      const old = btn.textContent;
      btn.textContent = "Preparing…";
      try {
        const res = await fetch("/api/complaint", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: run.source, analysis: run.analysis }),
        });
        if (!res.ok) throw new Error(await errorFrom(res));
        complaintText = await res.text();
        $("#complaint-text").value = complaintText;
        if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
        $("#complaint-copy").focus();
      } catch (e) {
        toast((e && e.message) || "Could not prepare the complaint.");
      } finally {
        btn.disabled = false;
        btn.textContent = old;
      }
    });
    $("#complaint-close").addEventListener("click", () => dlg.close());
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
    $("#complaint-copy").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(complaintText);
        toast("Copied to clipboard");
      } catch {
        const ta = $("#complaint-text");
        ta.focus(); ta.select();
        try { document.execCommand("copy"); toast("Copied to clipboard"); } catch { toast("Select the text and copy it manually."); }
      }
    });
    $("#complaint-download").addEventListener("click", () => {
      const blob = new Blob([complaintText], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = h("a", { href: url, download: `kavach-complaint-${new Date().toISOString().slice(0, 10)}.txt` });
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    });
  }

  // ------------------------------------------------------------------ reset / delete
  function resetResultView() {
    $("#progress-card").classList.remove("is-done", "is-failed");
    $("#progress-title").textContent = "Checking it for you…";
    $("#progress-sub").textContent = "This usually takes 30–90 seconds.";
    $("#elapsed").textContent = "0:00";
    $("#notices").replaceChildren();
    $("#progress-live").textContent = "";
    ["#error-card", "#verdict", "#explain-card", "#flags-card", "#facts-card", "#evidence-card", "#english-details", "#report-card", "#ask-card", "#trace-details", "#listen"]
      .forEach((sel) => { $(sel).hidden = true; });
    $("#english-details").open = false;
    $("#trace-details").open = false;
    const sp = $("#speech-audio");
    try { sp.pause(); } catch { /* ignore */ }
    sp.removeAttribute("src");
    sp.hidden = true;
    $("#btn-listen").classList.remove("nudge");
    $("#btn-listen").setAttribute("aria-pressed", "false");
    $("#listen-label").textContent = "Listen";
    $("#explain-title").textContent = "What this means";
    $("#explain-body").replaceChildren();
    $("#explain-method").textContent = "";
    $("#verdict-headline").removeAttribute("lang");
    ["#findings", "#facts", "#evidence", "#chat", "#trace-body", "#checklist"].forEach((sel) => $(sel).replaceChildren());
    $("#ask-input").value = "";
    enableAsk(false);
    $("#btn-delete").disabled = true;
    $("#footer-delete").disabled = true;
    lastPlayingId = null;
  }

  function goHome() {
    if (askRec && askRec.active) askRec.cancel();
    if (S.run) { teardownRun(S.run); S.run = null; }
    resetResultView();
    $("#result-view").hidden = true;
    $("#input-view").hidden = false;
    clearPending();
    $("#file-input").value = "";
    window.scrollTo({ top: 0 });
    $("#main").focus({ preventScroll: true });
  }

  function deleteData() {
    // Kavach stores nothing server-side; the result only lives in this page. Clear it.
    revokeBlobUrls();
    goHome();
    toast("Cleared. Kavach keeps no copy of your content on its servers.");
  }

  // ------------------------------------------------------------------ boot
  function boot() {
    initTabs();
    initUpload();
    initRecorder();
    initText();
    initListen();
    initAsk();
    initComplaint();
    $("#btn-reset").addEventListener("click", goHome);
    $("#btn-error-reset").addEventListener("click", goHome);
    $("#btn-delete").addEventListener("click", deleteData);
    $("#footer-delete").addEventListener("click", deleteData);
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && mainRec && mainRec.active) mainRec.stop();
    });
    loadConfig();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

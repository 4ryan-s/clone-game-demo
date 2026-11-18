"use strict";
// Flow: consent -> record the fixed sentence -> clones are made -> listen and pick -> result.
const $ = (s) => document.querySelector(s);
const STEPS = ["consent", "record", "making", "game", "result"];
const TARGET_RATE = 16000;
const DEV = new URLSearchParams(location.search).get("dev") === "1";

let cfg = null, sid = null, retain = false;
let rec = null;            // active recorder
let recordedWav = null;    // Blob (16 kHz mono PCM16) waiting for "Use this recording"
let pollTimer = null;

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch (_) { /* not JSON */ }
  if (!r.ok) throw new Error((body && body.detail) || `Request failed (${r.status})`);
  return body;
}

function show(step) {
  document.querySelectorAll("section.step").forEach((s) => { s.hidden = s.id !== `step-${step}`; });
  const idx = STEPS.indexOf(step);
  document.querySelectorAll("#steps li").forEach((li) => {
    const i = STEPS.indexOf(li.dataset.step);
    li.classList.toggle("on", i === idx);
    li.classList.toggle("past", i < idx);
  });
  $("#steps").hidden = idx < 0;
  window.scrollTo(0, 0);
}

function setError(sel, msg) {
  const el = $(sel);
  el.textContent = msg || "";
  el.hidden = !msg;
}

// ---------------------------------------------------------------- consent
async function init() {
  try {
    cfg = await api("/api/config");
  } catch (e) {
    document.body.innerHTML = `<main><h1>The demo server is not responding</h1><p>${e.message}</p></main>`;
    return;
  }
  const c = cfg.consent;
  $("#consent-title").textContent = c.title;
  $("#consent-intro").textContent = c.intro;
  $("#consent-points").innerHTML = "";
  c.points.forEach((p) => { const li = document.createElement("li"); li.textContent = p; $("#consent-points").appendChild(li); });
  $("#agree-label").textContent = c.required.label;
  $("#retain-label").textContent = c.optional.label;
  $("#sentence").textContent = cfg.sentence;
  $("#agree").checked = false; $("#retain").checked = false; $("#consent-go").disabled = true;
  show("consent");
}

$("#agree").addEventListener("change", () => { $("#consent-go").disabled = !$("#agree").checked; });

$("#consent-go").addEventListener("click", async () => {
  setError("#consent-error", "");
  $("#consent-go").disabled = true;
  try {
    retain = $("#retain").checked;
    const r = await api("/api/sessions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agree: true, retain, version: cfg.consent.version }),
    });
    sid = r.session_id;
    resetRecordScreen();
    show("record");
  } catch (e) {
    setError("#consent-error", e.message);
    $("#consent-go").disabled = !$("#agree").checked;
  }
});

// ---------------------------------------------------------------- recording
function resetRecordScreen() {
  recordedWav = null;
  $("#review").hidden = true;
  $("#rec-btn").hidden = false;
  $("#rec-btn").textContent = "Start recording";
  $("#rec-btn").disabled = false;
  $("#record-hint").hidden = false;
  $("#meter-bar").style.width = "0";
  $("#timer").textContent = "0.0 s";
  setError("#record-error", "");
}

async function startRecording() {
  setError("#record-error", "");
  let stream;
  try {
    // Raw capture: browser noise suppression, echo cancellation and auto gain are off, so the clip is the real microphone signal.
    stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
  } catch (e) {
    setError("#record-error", "The microphone is blocked. Allow microphone access for this page, then try again.");
    return;
  }
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  await ctx.audioWorklet.addModule("recorder-worklet.js");
  const src = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, "recorder");
  const chunks = [];
  let samples = 0;
  const maxSamples = Math.floor(cfg.max_seconds * ctx.sampleRate);
  node.port.onmessage = (ev) => {
    const d = ev.data;
    chunks.push(d); samples += d.length;
    let peak = 0, sum = 0;
    for (let i = 0; i < d.length; i++) { const v = d[i]; sum += v * v; if (Math.abs(v) > peak) peak = Math.abs(v); }
    const rms = Math.sqrt(sum / d.length);
    const lvl = Math.min(1, Math.max(0, (20 * Math.log10(rms + 1e-9) + 60) / 60));
    $("#meter-bar").style.width = `${Math.round(lvl * 100)}%`;
    $("#meter-bar").classList.toggle("hot", peak > 0.98);
    $("#timer").textContent = `${(samples / ctx.sampleRate).toFixed(1)} s`;
    if (samples >= maxSamples) stopRecording();
  };
  src.connect(node);   // not connected to the speakers, so there is no echo
  rec = { stream, ctx, node, src, chunks, get samples() { return samples; } };
  $("#rec-btn").textContent = "Stop";
  $("#record-hint").hidden = true;
}

async function stopRecording() {
  if (!rec) return;
  const r = rec; rec = null;
  r.node.port.onmessage = null;
  r.src.disconnect(); r.stream.getTracks().forEach((t) => t.stop());
  const rate = r.ctx.sampleRate;
  await r.ctx.close();
  const data = new Float32Array(r.chunks.reduce((n, c) => n + c.length, 0));
  let o = 0; r.chunks.forEach((c) => { data.set(c, o); o += c.length; });
  const pcm = await resampleTo16k(data, rate);
  recordedWav = encodeWav(pcm, TARGET_RATE);
  $("#review-len").textContent = `${(data.length / rate).toFixed(1)} s`;   // no playback here: hearing the real take first would give it away
  $("#review").hidden = false;
  $("#rec-btn").hidden = true;
  $("#meter-bar").style.width = "0";
}

async function resampleTo16k(data, rate) {
  if (rate === TARGET_RATE) return data;
  const off = new OfflineAudioContext(1, Math.ceil((data.length * TARGET_RATE) / rate), TARGET_RATE);
  const buf = off.createBuffer(1, data.length, rate);
  buf.copyToChannel(data, 0);
  const s = off.createBufferSource();
  s.buffer = buf; s.connect(off.destination); s.start();
  return (await off.startRendering()).getChannelData(0);
}

function encodeWav(f32, rate) {
  const buf = new ArrayBuffer(44 + f32.length * 2), v = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); v.setUint32(4, 36 + f32.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, "data"); v.setUint32(40, f32.length * 2, true);
  for (let i = 0; i < f32.length; i++) { const s = Math.max(-1, Math.min(1, f32[i])); v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true); }
  return new Blob([buf], { type: "audio/wav" });
}

$("#rec-btn").addEventListener("click", () => { rec ? stopRecording() : startRecording(); });
$("#again-btn").addEventListener("click", resetRecordScreen);

$("#use-btn").addEventListener("click", async () => {
  setError("#record-error", "");
  $("#use-btn").disabled = true;
  try {
    const fd = new FormData();
    fd.append("file", recordedWav, "recording.wav");
    const verdict = await api(`/api/sessions/${sid}/recording`, { method: "POST", body: fd });
    if (!verdict.ok) { setError("#record-error", verdict.issues.join(" ")); return; }
    show("making");
    await startGeneration();
  } catch (e) {
    setError("#record-error", e.message);
  } finally {
    $("#use-btn").disabled = false;
  }
});

// ---------------------------------------------------------------- generation
function renderProgress(st) {
  const ul = $("#progress");
  ul.innerHTML = "";
  for (let i = 1; i <= st.total; i++) {
    const c = st.clones.find((x) => x.slot === `c${i}`);
    const status = c ? c.status : "running";
    const li = document.createElement("li");
    const label = status === "done" ? `Copy ${i} of ${st.total} is ready` : status === "error" ? `Copy ${i} of ${st.total} could not be made` : `Making copy ${i} of ${st.total}…`;
    li.innerHTML = `<span class="dot ${status === "running" ? "" : status}"></span><span></span>`;
    li.lastChild.textContent = label;
    ul.appendChild(li);
  }
}

async function startGeneration() {
  setError("#making-error", ""); $("#retry-btn").hidden = true;
  await api(`/api/sessions/${sid}/generate`, { method: "POST" });
  clearInterval(pollTimer);
  const tick = async () => {
    try {
      const st = await api(`/api/sessions/${sid}/status`);
      renderProgress(st);
      if (st.state === "done") { clearInterval(pollTimer); await showGame(); }
      else if (st.state === "error") {
        clearInterval(pollTimer);
        setError("#making-error", "Something went wrong while making the copies. Please try again.");
        $("#retry-btn").hidden = false;
      }
    } catch (e) { clearInterval(pollTimer); setError("#making-error", e.message); }
  };
  await tick();
  pollTimer = setInterval(tick, 700);
}
$("#retry-btn").addEventListener("click", startGeneration);

// ---------------------------------------------------------------- the game
const ICON_PLAY = '<svg class="i-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg><svg class="i-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';
const player = new Audio();
let playingCard = null, picked = null, cardIds = [];

function stopPlayback() {
  player.pause();
  document.querySelectorAll(".card.playing").forEach((c) => { c.classList.remove("playing"); const b = c.querySelector(".progressbar b"); if (b) b.style.width = "0"; });
  playingCard = null;
}
player.addEventListener("ended", stopPlayback);
player.addEventListener("timeupdate", () => {
  if (!playingCard || !player.duration) return;
  document.querySelectorAll(`.card[data-id="${playingCard}"] .progressbar b`).forEach((b) => { b.style.width = `${(100 * player.currentTime) / player.duration}%`; });
});

function togglePlay(id) {
  if (playingCard === id) { stopPlayback(); return; }
  stopPlayback();
  playingCard = id;
  player.src = `/api/sessions/${sid}/cards/${id}.wav`;
  player.play().then(() => {
    document.querySelectorAll(`.card[data-id="${id}"]`).forEach((c) => c.classList.add("playing"));
  }).catch(() => { playingCard = null; setError("#game-error", "The audio could not be played. Try again."); });
}

function cardShell(id, title) {
  const el = document.createElement("div");
  el.className = "card"; el.dataset.id = id;
  el.innerHTML = `<div class="name"></div>
    <button class="play" aria-label="Play">${ICON_PLAY}</button>
    <div class="wave" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
    <div class="progressbar" aria-hidden="true"><b></b></div>`;
  el.querySelector(".name").textContent = title;
  el.querySelector(".play").setAttribute("aria-label", `Play ${title}`);
  el.querySelector(".play").addEventListener("click", () => togglePlay(id));
  return el;
}

async function showGame() {
  setError("#game-error", "");
  const r = await api(`/api/sessions/${sid}/cards`);
  cardIds = r.cards; picked = null;
  $("#confirm-btn").disabled = true; $("#confirm-btn").textContent = "Choose a voice first";
  const wrap = $("#cards"); wrap.innerHTML = "";
  cardIds.forEach((id, i) => {
    const el = cardShell(id, `Voice ${String.fromCharCode(65 + i)}`);
    const pick = document.createElement("button");
    pick.className = "pickbtn"; pick.textContent = "This one is me";
    pick.addEventListener("click", () => {
      picked = id;
      wrap.querySelectorAll(".card").forEach((c) => { c.classList.toggle("selected", c.dataset.id === id); c.querySelector(".pickbtn").textContent = c.dataset.id === id ? "✓ Selected" : "This one is me"; });
      $("#confirm-btn").disabled = false; $("#confirm-btn").textContent = "Lock in my answer";
    });
    el.appendChild(pick); wrap.appendChild(el);
  });
  show("game");
}

$("#confirm-btn").addEventListener("click", async () => {
  if (!picked) return;
  $("#confirm-btn").disabled = true; $("#confirm-btn").textContent = "Checking…";
  setError("#game-error", "");
  try {
    stopPlayback();
    const res = await api(`/api/sessions/${sid}/pick`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ card: picked }) });
    showResult(res);
  } catch (e) {
    setError("#game-error", e.message);
    $("#confirm-btn").disabled = false; $("#confirm-btn").textContent = "Lock in my answer";
  }
});

function showResult(res) {
  const v = $("#verdict");
  v.className = `verdict ${res.won ? "won" : "lost"}`;
  $("#result-title").textContent = res.won ? "You spotted the real one" : "The AI fooled you";
  const clones = res.cards.filter((c) => !c.real), real = res.cards.find((c) => c.real);
  const caught = clones.filter((c) => c.says_clone).length;
  $("#result-text").textContent = res.won
    ? "Your ear was right. Here is what our clone check made of each voice."
    : "You picked a copy. Here is what our clone check made of each voice.";
  const wrap = $("#result-cards"); wrap.innerHTML = "";
  const lo = -15, hi = 30, pos = (m) => `${Math.max(0, Math.min(100, ((m - lo) / (hi - lo)) * 100))}%`;
  res.cards.forEach((c, i) => {
    const el = cardShell(c.card, `Voice ${String.fromCharCode(65 + cardIds.indexOf(c.card))}`);
    el.classList.add(c.real ? "chosen-real" : "chosen-clone");
    const you = c.card === res.picked ? "You picked this one" : "";
    el.insertAdjacentHTML("beforeend", `<span class="tag ${c.real ? "real" : "clone"}"></span><div class="picked"></div>
      <div class="score"><div class="num"></div><div class="call"></div>
        <div class="gauge" style="--cut:${pos(res.cutoff)}"><span class="cutmark"></span><span class="dot2" style="left:${pos(c.margin)}"></span></div>
        <div class="scale"><span>clone</span><span>real</span></div></div>`);
    el.querySelector(".tag").textContent = c.real ? "Your real voice" : "Clone";
    el.querySelector(".picked").textContent = you;
    el.querySelector(".num").textContent = (c.margin > 0 ? "+" : "") + c.margin.toFixed(1);
    el.querySelector(".call").textContent = c.says_clone ? "Called a clone" : "Passed as real";
    wrap.appendChild(el);
  });
  const realCall = real.says_clone ? " It wrongly doubted your real voice." : " It passed your real voice.";
  $("#result-note").textContent = `The score shows how strongly the detector thinks a voice is real. Below ${res.cutoff} it calls the voice a clone. It caught ${caught} of ${clones.length} clones.${realCall}`;
  $("#code").textContent = sid;
  $("#finish-note").textContent = retain
    ? "You agreed that we keep your recording and the copies without your name. Use the session code to ask for deletion later."
    : "You did not agree to keep your recording, so it is deleted when you press Finish.";
  show("result");
}

function bye(title, text) {
  stopPlayback();
  $("#bye-title").textContent = title; $("#bye-text").textContent = text;
  sid = null; show("bye"); $("#steps").hidden = true;
}
$("#finish-btn").addEventListener("click", async () => {
  try {
    const r = await api(`/api/sessions/${sid}/finish`, { method: "POST" });
    bye("Thank you", r.deleted ? "Your recording and the copies have been deleted." : "Your session is saved. Keep your code if you want it deleted later.");
  } catch (e) { bye("Thank you", e.message); }
});
$("#delete-btn").addEventListener("click", async () => {
  try { await api(`/api/sessions/${sid}`, { method: "DELETE" }); bye("Deleted", "Your recording and the copies have been deleted."); }
  catch (e) { bye("Could not delete", e.message); }
});
$("#restart-btn").addEventListener("click", init);

init();

import { useEffect, useRef, useState } from "react";
import { encodeWav, resampleTo16k } from "../lib/audio";
import { cx } from "../lib/cx";
import { Button, ErrorNote, StepHead } from "./ui";

export function RecordStep({ sentence, maxSeconds, onSubmit }) {
  const recRef = useRef(null);
  const [recording, setRecording] = useState(false);
  const [arming, setArming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState(0);
  const [hot, setHot] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [review, setReview] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => () => {
    const rec = recRef.current;
    if (!rec) return;
    rec.stopping = true;
    rec.node.port.onmessage = null;
    try { rec.src.disconnect(); } catch { /* already stopped */ }
    rec.stream.getTracks().forEach((track) => track.stop());
    rec.ctx.close();
    recRef.current = null;
  }, []);

  function reset() {
    setReview(null);
    setError("");
    setLevel(0);
    setHot(false);
    setSeconds(0);
  }

  async function stopRecording() {
    const rec = recRef.current;
    if (!rec || rec.stopping) return;
    rec.stopping = true;
    rec.node.port.onmessage = null;
    try { rec.src.disconnect(); } catch { /* already stopped */ }
    rec.stream.getTracks().forEach((track) => track.stop());
    const rate = rec.ctx.sampleRate;
    const chunks = rec.chunks;
    await rec.ctx.close();
    recRef.current = null;
    setRecording(false);
    const data = new Float32Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0));
    let offset = 0;
    chunks.forEach((chunk) => {
      data.set(chunk, offset);
      offset += chunk.length;
    });
    const pcm = await resampleTo16k(data, rate);
    setLevel(0);
    setHot(false);
    setReview({ seconds: data.length / rate, blob: encodeWav(pcm, 16000) });
  }

  async function startRecording() {
    setError("");
    setArming(true);
    let stream;
    let ctx;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
    } catch {
      setArming(false);
      setError("The microphone is blocked. Allow microphone access for this page, then try again.");
      return;
    }
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      await ctx.audioWorklet.addModule("/recorder-worklet.js");
      const src = ctx.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(ctx, "recorder");
      const rec = { stream, ctx, node, src, chunks: [], samples: 0, stopping: false };
      const maxSamples = Math.floor(maxSeconds * ctx.sampleRate);
      node.port.onmessage = (event) => {
        const live = recRef.current;
        if (!live || live.stopping) return;
        const chunk = event.data;
        live.chunks.push(chunk);
        live.samples += chunk.length;
        let peak = 0;
        let sum = 0;
        for (let i = 0; i < chunk.length; i++) {
          const value = chunk[i];
          sum += value * value;
          const abs = Math.abs(value);
          if (abs > peak) peak = abs;
        }
        const rms = Math.sqrt(sum / chunk.length);
        setLevel(Math.min(1, Math.max(0, (20 * Math.log10(rms + 1e-9) + 60) / 60)));
        setHot(peak > 0.98);
        setSeconds(live.samples / ctx.sampleRate);
        if (live.samples >= maxSamples) stopRecording();
      };
      src.connect(node);
      recRef.current = rec;
      setRecording(true);
    } catch (err) {
      stream.getTracks().forEach((track) => track.stop());
      if (ctx) ctx.close();
      setError(err.message || "The microphone could not be started.");
    } finally {
      setArming(false);
    }
  }

  async function useThis() {
    if (!review) return;
    setBusy(true);
    setError("");
    try {
      await onSubmit(review.blob);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-12 gap-8">
      <div className="col-span-7 flex min-h-0 flex-col">
        <StepHead
          kicker="Round 02 · Your line"
          title="Read this sentence out loud"
          lede="Hold the microphone close and speak at a normal pace. You will not hear the take back — that would give the real voice away."
        />
        <blockquote className="relative mt-8 flex flex-1 items-center rounded-[28px] border border-line bg-card px-10 py-12 shadow-[0_24px_50px_-36px_rgba(40,30,10,0.45)]">
          <span className="pointer-events-none absolute left-8 top-4 font-display text-8xl leading-none text-gold/35" aria-hidden="true">“</span>
          <p className="font-display text-[40px] leading-[1.25] text-balance">{sentence}</p>
        </blockquote>
      </div>

      <div className="col-span-5 min-h-0">
        <div className="flex h-full flex-col items-center justify-center rounded-[28px] border border-line bg-card px-8 py-10 text-center shadow-[0_24px_50px_-36px_rgba(40,30,10,0.45)]">
          <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-accent">The booth</p>
          <p className="mt-2 font-display text-3xl">Your microphone</p>

          {review ? (
            <div className="rise mt-8 flex flex-col items-center">
              <span className="pop grid h-20 w-20 place-items-center rounded-full bg-good text-3xl text-white">✓</span>
              <p className="mt-5 text-lg">Recording captured ({review.seconds.toFixed(1)} s)</p>
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <Button primary disabled={busy} onClick={useThis}>{busy ? "Checking…" : "Use this recording"}</Button>
                <Button disabled={busy} onClick={reset}>Record again</Button>
              </div>
            </div>
          ) : (
            <>
              <div className="relative mt-8 h-36 w-36">
                {recording && (
                  <>
                    <span className="pulse-ring absolute inset-0 rounded-full bg-accent/25" />
                    <span className="pulse-ring absolute inset-0 rounded-full bg-accent/20" style={{ animationDelay: "0.5s" }} />
                  </>
                )}
                <button
                  type="button"
                  className={cx(
                    "relative grid h-full w-full cursor-pointer place-items-center rounded-full text-white transition duration-150",
                    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent",
                    "disabled:cursor-not-allowed disabled:opacity-40",
                    recording ? "bg-bad hover:brightness-110" : "bg-accent hover:bg-accent-deep",
                  )}
                  disabled={arming}
                  onClick={() => (recording ? stopRecording() : startRecording())}
                  aria-label={recording ? "Stop recording" : "Start recording"}
                >
                  {recording ? <span className="h-8 w-8 rounded-md bg-white" /> : <MicIcon />}
                </button>
              </div>
              <p className="mt-6 text-lg font-semibold">{recording ? "Stop" : arming ? "Starting…" : "Start recording"}</p>
            </>
          )}

          <div className="mt-8 w-full">
            <div className="h-3 overflow-hidden rounded-full bg-mist" aria-hidden="true">
              <div className={cx("meter-bar h-full rounded-full", hot ? "bg-bad" : "bg-good")} style={{ width: `${Math.round(level * 100)}%` }} />
            </div>
            <p className="mt-3 text-2xl tabular-nums text-muted" aria-live="polite">{(review ? review.seconds : seconds).toFixed(1)} s</p>
          </div>

          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            {recording
              ? "Press stop when you finish the sentence."
              : `Stops automatically after ${maxSeconds} seconds. Press stop when you finish.`}
          </p>
          <div className="mt-3 min-h-5">
            <ErrorNote>{error}</ErrorNote>
          </div>
        </div>
      </div>
    </div>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-12 w-12" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M6 11a6 6 0 0 0 12 0M12 17v3.5M8.5 21h7" strokeLinecap="round" />
    </svg>
  );
}

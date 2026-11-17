import { useEffect, useRef, useState } from "react";
import { encodeWav, resampleTo16k } from "../lib/audio";
import { cx } from "../lib/cx";
import { Button, ErrorNote, StepHead } from "./ui";

const BARS = 48;
const quietWave = () => Array(BARS).fill(0.08);

export function RecordStep({ sentence, maxSeconds, onSubmit }) {
  const recRef = useRef(null);
  const waveRef = useRef(quietWave());
  const paintedAt = useRef(0);
  const [recording, setRecording] = useState(false);
  const [arming, setArming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [wave, setWave] = useState(quietWave);
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
    const quiet = quietWave();
    waveRef.current = quiet;
    setWave(quiet);
    setReview(null);
    setError("");
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
    setHot(false);
    const data = new Float32Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0));
    let offset = 0;
    chunks.forEach((chunk) => {
      data.set(chunk, offset);
      offset += chunk.length;
    });
    const pcm = await resampleTo16k(data, rate);
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
      const quiet = quietWave();
      waveRef.current = quiet;
      setWave(quiet);
      const rec = { stream, ctx, node, src, chunks: [], samples: 0, stopping: false, levelSum: 0, levelCount: 0, framePeak: 0 };
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
        live.levelSum += Math.sqrt(sum / chunk.length);
        live.levelCount += 1;
        if (peak > live.framePeak) live.framePeak = peak;
        setSeconds(live.samples / ctx.sampleRate);
        const now = performance.now();
        if (now - paintedAt.current > 45 && live.levelCount) {
          paintedAt.current = now;
          const rms = live.levelSum / live.levelCount;
          const loud = Math.min(1, Math.max(0, (20 * Math.log10(rms + 1e-9) + 52) / 52));
          const bars = waveRef.current;
          bars.push(loud);
          bars.shift();
          setWave(bars.slice());
          setHot(live.framePeak > 0.98);
          live.levelSum = 0;
          live.levelCount = 0;
          live.framePeak = 0;
        }
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
    <div className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col items-center justify-center text-center">
      <StepHead title="Read this aloud" />
      <blockquote className="mt-8 w-full rounded-[28px] border border-line bg-card px-10 py-12 shadow-[0_24px_50px_-36px_rgba(40,30,10,0.45)]">
        <p className="font-display text-4xl leading-snug text-balance">{sentence}</p>
      </blockquote>

      <div className="mt-10 w-full">
        <div className="flex h-44 w-full items-center gap-1.5" aria-hidden="true">
          {wave.map((value, index) => (
            <span
              key={index}
              className={cx("min-w-0 flex-1 rounded-full transition-[height] duration-75", hot ? "bg-bad" : "bg-accent")}
              style={{ height: `${Math.max(12, Math.round(value * 100))}%`, opacity: recording || review ? 0.5 + value * 0.5 : 0.35 }}
            />
          ))}
        </div>
        <p className="mt-4 text-2xl tabular-nums text-muted" aria-live="polite">
          {(review ? review.seconds : seconds).toFixed(1)} s
        </p>
      </div>

      <div className="mt-8 flex w-full max-w-md flex-col items-center">
        {review ? (
          <div className="rise flex flex-wrap justify-center gap-3">
            <Button primary disabled={busy} onClick={useThis}>{busy ? "Checking…" : "Use this"}</Button>
            <Button disabled={busy} onClick={reset}>Record again</Button>
          </div>
        ) : (
          <>
            <div className="relative h-28 w-28">
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
                {recording ? <span className="h-7 w-7 rounded-md bg-white" /> : <MicIcon />}
              </button>
            </div>
            <p className="mt-4 text-lg font-semibold">{recording ? "Stop" : arming ? "Starting…" : "Record"}</p>
          </>
        )}

        <div className="mt-3 min-h-5">
          <ErrorNote>{error}</ErrorNote>
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

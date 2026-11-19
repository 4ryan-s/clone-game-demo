import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Button, ErrorNote, StepHead } from "./ui";

export function MakingStep({ sid, onReady }) {
  const [error, setError] = useState("");
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const [pct, setPct] = useState(0);
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  const doneRef = useRef(0);
  const totalRef = useRef(0);
  const finishedRef = useRef(false);
  const startRef = useRef(Date.now());

  useEffect(() => {
    let timer = 0;
    let cancelled = false;
    let finished = false;
    let pending = false;

    async function tick() {
      if (finished || cancelled || pending) return;
      pending = true;
      try {
        const next = await api(`/api/sessions/${sid}/status`);
        if (finished || cancelled) return;
        doneRef.current = next.done || 0;
        totalRef.current = next.total || 0;
        if (next.state === "done") {
          finished = true;
          finishedRef.current = true;
          window.clearInterval(timer);
          try {
            await onReadyRef.current();
          } catch (err) {
            if (!cancelled) {
              setFailed(true);
              setError(err.message);
            }
          }
        } else if (next.state === "error") {
          finished = true;
          window.clearInterval(timer);
          if (!cancelled) {
            setFailed(true);
            setError("Something went wrong while preparing the voices. Please try again.");
          }
        }
      } catch (err) {
        finished = true;
        window.clearInterval(timer);
        if (!cancelled) setError(err.message);
      } finally {
        pending = false;
      }
    }

    tick();
    timer = window.setInterval(tick, 700);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [sid, attempt]);

  // Smoothly climbing percentage: eased toward real progress (done/total) with a
  // gentle time-based creep so the number keeps moving between engine completions.
  useEffect(() => {
    const id = window.setInterval(() => {
      setPct((current) => {
        const elapsed = (Date.now() - startRef.current) / 1000;
        const timeCreep = 90 * (1 - Math.exp(-elapsed / 18));
        const realFloor = totalRef.current ? (doneRef.current / totalRef.current) * 92 : 0;
        const target = finishedRef.current ? 100 : Math.min(96, Math.max(timeCreep, realFloor));
        const next = current + (target - current) * 0.12;
        return next > 99.5 ? 100 : next;
      });
    }, 120);
    return () => window.clearInterval(id);
  }, []);

  async function retry() {
    setRetrying(true);
    setError("");
    setFailed(false);
    finishedRef.current = false;
    doneRef.current = 0;
    startRef.current = Date.now();
    setPct(0);
    try {
      await api(`/api/sessions/${sid}/generate`, { method: "POST" });
      setAttempt((n) => n + 1);
    } catch (err) {
      setError(err.message);
      setFailed(true);
    } finally {
      setRetrying(false);
    }
  }

  const shown = Math.round(pct);

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col items-center text-center">
      {!failed && <span className="spinner spin h-16 w-16 rounded-full" aria-hidden="true" />}
      <div className={failed ? "" : "mt-8"}>
        <StepHead title={failed ? "Not ready yet" : "Hang on"} />
      </div>

      {!failed && (
        <div className="mt-6 w-full max-w-sm">
          <div className="flex items-end justify-center gap-1">
            <span className="font-display text-5xl leading-none tabular-nums text-accent">{shown}</span>
            <span className="pb-1 text-xl font-semibold text-accent">%</span>
          </div>
          <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-mist">
            <div className="meter-bar h-full rounded-full bg-accent" style={{ width: `${shown}%` }} />
          </div>
        </div>
      )}

      <p className="mt-5 max-w-md text-lg leading-relaxed text-muted">
        Next you will hear four voices. Play them, then pick the one that is your original voice.
      </p>
      <div className="mt-6 flex min-h-12 flex-col items-center gap-4">
        <ErrorNote>{error}</ErrorNote>
        {failed && (
          <Button primary disabled={retrying} onClick={retry}>{retrying ? "Trying again…" : "Try again"}</Button>
        )}
      </div>
    </div>
  );
}

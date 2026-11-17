import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import { Button, CheckIcon, ErrorNote, StepHead } from "./ui";

export function MakingStep({ sid, cloneCount, onReady }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

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
        setStatus(next);
        if (cancelled) return;
        if (next.state === "done") {
          finished = true;
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
            setError("Something went wrong while making the copies. Please try again.");
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

  async function retry() {
    setRetrying(true);
    setError("");
    setFailed(false);
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

  const clones = status?.clones || [];
  const total = status?.total || cloneCount || clones.length;
  const slots = Array.from({ length: Math.max(total, clones.length) }, (_, index) => {
    const slot = `c${index + 1}`;
    return clones.find((clone) => clone.slot === slot) || { slot, status: "running" };
  });
  const ready = slots.filter((slot) => slot.status === "done").length;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-end justify-between gap-6">
        <StepHead
          kicker="Round 03 · The copies"
          title="Making copies of your voice"
          lede="Each system is listening to your recording and saying the same sentence in your voice."
        />
        {total > 0 && (
          <p className="shrink-0 rounded-full bg-card px-4 py-2 text-sm font-semibold text-muted ring-1 ring-line">
            {ready} of {total} ready
          </p>
        )}
      </div>

      <div
        className="mt-8 grid min-h-0 flex-1 gap-5"
        style={{ gridTemplateColumns: `repeat(${Math.max(slots.length, 1)}, minmax(0, 1fr))` }}
      >
        {slots.length === 0 ? (
          <div className="grid place-items-center rounded-[28px] border border-line bg-card text-muted">Preparing the copies…</div>
        ) : slots.map((slot, index) => {
          const state = slot.status || "running";
          const label = state === "done"
            ? `Copy ${index + 1} of ${total} is ready`
            : state === "error"
              ? `Copy ${index + 1} of ${total} could not be made`
              : `Making copy ${index + 1} of ${total}…`;
          return (
            <article
              key={slot.slot}
              className="rise relative flex flex-col items-center justify-center overflow-hidden rounded-[28px] border border-line bg-card px-6 text-center shadow-[0_24px_50px_-36px_rgba(40,30,10,0.45)]"
              style={{ animationDelay: `${index * 80}ms` }}
            >
              <span className="pointer-events-none absolute right-6 top-4 font-display text-6xl text-mist">{String(index + 1).padStart(2, "0")}</span>
              {state === "running" && <span className="scan pointer-events-none absolute left-8 right-8 top-16 h-px bg-accent/70" />}
              <span className={cx(
                "grid h-20 w-20 place-items-center rounded-full",
                state === "running" && "spinner spin",
                state === "done" && "pop border-4 border-good bg-good text-white",
                state === "error" && "border-4 border-bad bg-bad text-white",
              )}>
                {state === "done" && <CheckIcon className="h-8 w-8" />}
                {state === "error" && <span className="text-3xl font-bold text-white">!</span>}
              </span>
              <h2 className="mt-6 font-display text-3xl">Copy {index + 1}</h2>
              <p className="mt-2 max-w-xs text-muted">{label}</p>
            </article>
          );
        })}
      </div>

      <div className="mt-5 flex min-h-12 items-center justify-between gap-4">
        <ErrorNote>{error}</ErrorNote>
        {failed && (
          <Button primary disabled={retrying} onClick={retry}>{retrying ? "Trying again…" : "Try again"}</Button>
        )}
      </div>
    </div>
  );
}

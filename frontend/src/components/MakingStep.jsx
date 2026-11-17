import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Button, ErrorNote, StepHead } from "./ui";

export function MakingStep({ sid, onReady }) {
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

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col items-center text-center">
      {!failed && <span className="spinner spin h-16 w-16 rounded-full" aria-hidden="true" />}
      <div className={failed ? "" : "mt-8"}>
        <StepHead title={failed ? "Not ready yet" : "Hang on"} />
      </div>
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

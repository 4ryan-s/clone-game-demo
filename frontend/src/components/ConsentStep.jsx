import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button, ErrorNote, StepHead } from "./ui";

const EMPTY_STATS = { guests: 0, identified: 0, missed: 0, voices: 0 };

export function ConsentStep({ consent, onAgree }) {
  const [agree, setAgree] = useState(false);
  const [retain, setRetain] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [stats, setStats] = useState(EMPTY_STATS);

  useEffect(() => {
    let cancelled = false;
    api("/api/stats")
      .then((next) => { if (!cancelled) setStats({ ...EMPTY_STATS, ...next }); })
      .catch(() => { if (!cancelled) setStats(EMPTY_STATS); });
    return () => { cancelled = true; };
  }, []);

  async function submit() {
    setBusy(true);
    setError("");
    try {
      await onAgree({ retain });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-xl">
      <StepHead title={consent.title} />
      <div className="mt-5 grid grid-cols-2 gap-2 sm:mt-6 sm:gap-3">
        <Stat label="Voices" value={stats.voices} note="Real and clones" />
        <Stat label="Guests" value={stats.guests} note="People who played" />
        <Stat label="Found it" value={stats.identified} note="Picked their voice" />
        <Stat label="Fooled" value={stats.missed} note="Picked a clone" />
      </div>
      <div className="mt-4 rounded-[28px] border border-line bg-card p-5 shadow-[0_24px_50px_-36px_rgba(40,30,10,0.55)] sm:mt-5 sm:p-6">
          <label className="flex cursor-pointer gap-3 rounded-2xl border border-line bg-paper/60 p-4 transition hover:border-accent/40">
            <input
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-[#0f6f5b]"
              checked={agree}
              onChange={(event) => setAgree(event.target.checked)}
            />
            <span className="text-[15px] leading-relaxed">{consent.required.label}</span>
          </label>

          <label className="mt-3 flex cursor-pointer gap-3 rounded-2xl border border-line bg-paper/60 p-4 transition hover:border-accent/40">
            <input
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-[#0f6f5b]"
              checked={retain}
              onChange={(event) => setRetain(event.target.checked)}
            />
            <span className="text-[15px] leading-relaxed">{consent.optional.label}</span>
          </label>

          {error ? (
            <div className="mt-4">
              <ErrorNote>{error}</ErrorNote>
            </div>
          ) : null}

          <Button primary className="mt-6 w-full" disabled={!agree || busy} onClick={submit}>
            {busy ? "Starting…" : "I agree"}
          </Button>
      </div>
    </div>
  );
}

function Stat({ label, value, note }) {
  return (
    <div className="rounded-2xl border border-line bg-card px-3 py-2.5 text-left">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">{label}</p>
      <p className="mt-1 font-display text-2xl leading-none tabular-nums sm:text-3xl">{value}</p>
      <p className="mt-1 text-xs text-muted">{note}</p>
    </div>
  );
}

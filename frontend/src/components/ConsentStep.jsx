import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button, ErrorNote, StepHead } from "./ui";
import { cx } from "../lib/cx";

const EMPTY_STATS = { guests: 0, identified: 0, missed: 0, voices: 0, recorded: 0, saved: 0 };

export function ConsentStep({ consent, onAgree }) {
  const [cloning, setCloning] = useState(false);
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
      await onAgree({ retain, cloning });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-xl">
      <StepHead title={consent.title} />
      <Scoreboard stats={stats} />
      <div className="mt-4 rounded-[28px] border border-line bg-card p-5 shadow-[0_24px_50px_-36px_rgba(40,30,10,0.55)] sm:mt-5 sm:p-6">
          <label className="flex cursor-pointer gap-3 rounded-2xl border border-line bg-paper/60 p-4 transition hover:border-accent/40">
            <input
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-[#0f6f5b]"
              checked={cloning}
              onChange={(event) => setCloning(event.target.checked)}
            />
            <span className="text-[15px] leading-relaxed">
              <span className="mr-2 inline-block rounded-full bg-bad/10 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-bad align-middle">Required</span>
              {consent.cloning.label}
            </span>
          </label>

          <label className="mt-3 flex cursor-pointer gap-3 rounded-2xl border border-line bg-paper/60 p-4 transition hover:border-accent/40">
            <input
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-[#0f6f5b]"
              checked={retain}
              onChange={(event) => setRetain(event.target.checked)}
            />
            <span className="text-[15px] leading-relaxed">
              <span className="mr-2 inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-accent align-middle">Optional</span>
              {consent.optional.label}
            </span>
          </label>

          {error ? (
            <div className="mt-4">
              <ErrorNote>{error}</ErrorNote>
            </div>
          ) : null}

          <Button primary className="mt-6 w-full" disabled={busy || !cloning} onClick={submit}>
            {busy ? "Starting…" : "Start"}
          </Button>
          {!cloning && (
            <p className="mt-2 text-center text-xs text-muted">Tick the required box above to begin.</p>
          )}
      </div>
    </div>
  );
}

function useCountUp(target, duration = 1100) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!target) {
      setValue(0);
      return undefined;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(target * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}

const GOOD = "#157a45";
const BAD = "#b4332a";
const GOLD = "#a67912";
const ACCENT = "#0f6f5b";

function Scoreboard({ stats }) {
  const total = stats.identified + stats.missed;
  const fooledRate = total ? Math.round((stats.missed / total) * 100) : 0;
  return (
    <section className="mt-5 sm:mt-6">
      <div className="mb-3 flex items-center justify-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-bad/60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-bad" />
        </span>
        <span className="text-xs font-bold uppercase tracking-[0.22em] text-muted">Live at the booth</span>
      </div>

      <div className="flex flex-col items-center gap-5 rounded-[28px] border border-line bg-card p-5 shadow-[0_24px_50px_-36px_rgba(40,30,10,0.55)] sm:flex-row sm:justify-center sm:gap-7 sm:p-6">
        <Donut identified={stats.identified} missed={stats.missed} />
        <div className="flex flex-col gap-3">
          <LegendRow color={GOOD} value={stats.identified} label="Spotted their voice" />
          <LegendRow color={BAD} value={stats.missed} label="Fooled by a clone" />
          <div className="h-px bg-line" />
          <LegendRow color={GOLD} value={stats.voices} label="Voices created" />
          <LegendRow color={ACCENT} value={stats.saved} label="Voices saved" />
        </div>
      </div>

      {total > 0 && (
        <div className="mt-3 overflow-hidden rounded-2xl bg-gradient-to-r from-accent via-[#1c8f6a] to-gold px-4 py-3 text-center text-white shadow-[0_18px_40px_-28px_rgba(15,111,91,0.9)]">
          <p className="text-sm font-semibold sm:text-base">
            <span className="font-display text-2xl tabular-nums sm:text-3xl">{fooledRate}%</span>{" "}
            were fooled by a clone. Can you beat them?
          </p>
        </div>
      )}
    </section>
  );
}

function Donut({ identified, missed }) {
  const [reveal, setReveal] = useState(false);
  const total = identified + missed;
  const players = useCountUp(total);
  const r = 68;
  const C = 2 * Math.PI * r;
  const idFrac = total ? identified / total : 0;
  const missFrac = total ? missed / total : 0;

  useEffect(() => {
    const t = window.setTimeout(() => setReveal(true), 120);
    return () => window.clearTimeout(t);
  }, [total]);

  const idLen = (reveal ? idFrac : 0) * C;
  const missLen = (reveal ? missFrac : 0) * C;

  return (
    <svg viewBox="0 0 180 180" className="h-44 w-44 shrink-0" role="img" aria-label={`${identified} spotted their voice, ${missed} were fooled`}>
      <circle cx="90" cy="90" r={r} fill="none" stroke="#e9e0d0" strokeWidth="24" />
      {total > 0 && (
        <>
          <circle
            cx="90" cy="90" r={r} fill="none" stroke={GOOD} strokeWidth="24"
            strokeDasharray={`${idLen} ${C - idLen}`}
            transform="rotate(-90 90 90)"
            style={{ transition: "stroke-dasharray 1s ease" }}
          />
          <circle
            cx="90" cy="90" r={r} fill="none" stroke={BAD} strokeWidth="24"
            strokeDasharray={`${missLen} ${C - missLen}`}
            transform={`rotate(${-90 + idFrac * 360} 90 90)`}
            style={{ transition: "stroke-dasharray 1s ease" }}
          />
        </>
      )}
      <text x="90" y="86" textAnchor="middle" fill="#1c1915" fontSize="44" style={{ fontFamily: "'Fraunces', Georgia, serif", fontWeight: 700 }}>{players}</text>
      <text x="90" y="110" textAnchor="middle" fill="#6f685f" fontSize="15" style={{ fontWeight: 600 }}>players</text>
    </svg>
  );
}

function LegendRow({ color, value, label }) {
  const shown = useCountUp(value);
  return (
    <div className="flex items-center gap-2.5">
      <span className="h-3.5 w-3.5 shrink-0 rounded-full" style={{ background: color }} />
      <span className="font-display text-2xl leading-none tabular-nums text-ink sm:text-3xl">{shown}</span>
      <span className="text-sm text-muted">{label}</span>
    </div>
  );
}

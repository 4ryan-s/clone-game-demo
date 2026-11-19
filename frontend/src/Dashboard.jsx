import { useEffect, useRef, useState } from "react";
import { api } from "./lib/api";

const EMPTY = { guests: 0, identified: 0, missed: 0, voices: 0, saved: 0 };
const GOOD = "#157a45";
const BAD = "#b4332a";
const GOLD = "#a67912";
const ACCENT = "#0f6f5b";
const POLL_MS = 1000;

export default function Dashboard() {
  const [stats, setStats] = useState(EMPTY);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    document.title = "Live at the booth";
    let cancelled = false;

    async function load() {
      try {
        const next = await api("/api/stats", { cache: "no-store" });
        if (!cancelled) {
          if (!next || typeof next.guests !== "number") {
            setOffline(true);
            return;
          }
          setStats({ ...EMPTY, ...next });
          setOffline(false);
        }
      } catch {
        if (!cancelled) setOffline(true);
      }
    }

    load();
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const total = stats.identified + stats.missed;
  const fooledRate = total ? Math.round((stats.missed / total) * 100) : 0;

  return (
    <main className="stage flex min-h-full flex-col items-center justify-center px-8 py-10">
      <div className="mb-8 flex items-center gap-3">
        <span className="relative flex h-4 w-4">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-bad/60" />
          <span className="relative inline-flex h-4 w-4 rounded-full bg-bad" />
        </span>
        <h1 className="font-display text-5xl text-ink xl:text-6xl">Live at the booth</h1>
      </div>

      <section className="flex w-full max-w-6xl flex-col items-center gap-12 rounded-[40px] border border-line bg-card px-10 py-12 shadow-[0_30px_80px_-40px_rgba(40,30,10,0.55)] xl:flex-row xl:justify-center xl:gap-20 xl:px-16">
        <Donut identified={stats.identified} missed={stats.missed} />
        <div className="flex flex-col gap-6">
          <LegendRow color={GOOD} value={stats.identified} label="Spotted their voice" />
          <LegendRow color={BAD} value={stats.missed} label="Fooled by a clone" />
          <div className="h-px bg-line" />
          <LegendRow color={GOLD} value={stats.voices} label="Voices created" />
          <LegendRow color={ACCENT} value={stats.saved} label="Voices saved" />
        </div>
      </section>

      {total > 0 && (
        <div className="mt-8 w-full max-w-6xl overflow-hidden rounded-[28px] bg-gradient-to-r from-accent via-[#1c8f6a] to-gold px-8 py-6 text-center text-white shadow-[0_18px_40px_-28px_rgba(15,111,91,0.9)]">
          <p className="text-3xl font-semibold xl:text-4xl">
            <span className="font-display text-6xl tabular-nums xl:text-7xl">{fooledRate}%</span>{" "}
            were fooled by a clone. Can you beat them?
          </p>
        </div>
      )}

      {offline && (
        <p className="mt-6 text-sm font-semibold uppercase tracking-[0.2em] text-muted">Reconnecting…</p>
      )}
    </main>
  );
}

function useCountTo(target, duration = 700) {
  const [value, setValue] = useState(0);
  const shown = useRef(0);
  useEffect(() => {
    const from = shown.current;
    const start = performance.now();
    let raf = 0;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = Math.round(from + (target - from) * eased);
      shown.current = next;
      setValue(next);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}

function Donut({ identified, missed }) {
  const total = identified + missed;
  const players = useCountTo(total);
  const r = 68;
  const C = 2 * Math.PI * r;
  const idFrac = total ? identified / total : 0;
  const missFrac = total ? missed / total : 0;

  return (
    <svg viewBox="0 0 180 180" className="h-80 w-80 shrink-0 xl:h-[26rem] xl:w-[26rem]" role="img" aria-label={`${identified} spotted their voice, ${missed} were fooled`}>
      <circle cx="90" cy="90" r={r} fill="none" stroke="#e9e0d0" strokeWidth="24" />
      {total > 0 && (
        <>
          <circle
            cx="90" cy="90" r={r} fill="none" stroke={GOOD} strokeWidth="24"
            strokeDasharray={`${idFrac * C} ${C - idFrac * C}`}
            transform="rotate(-90 90 90)"
            style={{ transition: "stroke-dasharray 700ms ease" }}
          />
          <circle
            cx="90" cy="90" r={r} fill="none" stroke={BAD} strokeWidth="24"
            strokeDasharray={`${missFrac * C} ${C - missFrac * C}`}
            transform={`rotate(${-90 + idFrac * 360} 90 90)`}
            style={{ transition: "stroke-dasharray 700ms ease" }}
          />
        </>
      )}
      <text x="90" y="84" textAnchor="middle" fill="#1c1915" fontSize="42" style={{ fontFamily: "'Fraunces', Georgia, serif", fontWeight: 700 }}>{players}</text>
      <text x="90" y="108" textAnchor="middle" fill="#6f685f" fontSize="14" style={{ fontWeight: 600 }}>players</text>
    </svg>
  );
}

function LegendRow({ color, value, label }) {
  const shown = useCountTo(value);
  return (
    <div className="flex items-center gap-5">
      <span className="h-6 w-6 shrink-0 rounded-full" style={{ background: color }} />
      <span className="font-display text-6xl leading-none tabular-nums text-ink xl:text-7xl">{shown}</span>
      <span className="text-2xl text-muted xl:text-3xl">{label}</span>
    </div>
  );
}

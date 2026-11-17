import { useEffect, useState } from "react";
import { cx } from "../lib/cx";
import { formatMargin, scorePercent } from "../lib/score";

export function VoiceCard({ letter, playing, progress, onPlay, selected, onPick, heard, reveal }) {
  const [slid, setSlid] = useState(false);
  useEffect(() => {
    if (!reveal) return undefined;
    const timer = window.setTimeout(() => setSlid(true), 80);
    return () => window.clearTimeout(timer);
  }, []);

  const border = reveal
    ? reveal.real ? "border-good" : "border-bad"
    : selected || playing ? "border-accent" : "border-line";
  const marginPct = reveal ? scorePercent(reveal.margin) : 0;
  const cutPct = reveal ? scorePercent(reveal.cutoff) : 0;

  return (
    <article className={cx(
      "flex min-h-0 flex-col overflow-hidden rounded-[28px] border-2 bg-card text-center shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)] transition duration-200",
      reveal ? "h-full px-3 py-3" : "h-auto px-4 py-4",
      border,
      !reveal && selected && "-translate-y-1 shadow-[0_0_0_6px_rgba(15,111,91,0.14)]",
      !reveal && !selected && "hover:-translate-y-1",
    )}>
      <div className={cx("flex items-center", reveal ? "justify-between text-left" : "flex-col")}>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">Voice</p>
          <h2 className={cx("font-display leading-none", reveal ? "text-2xl" : "text-4xl sm:text-5xl")}>{letter}</h2>
        </div>
        {reveal && (
          <PlayButton letter={letter} playing={playing} onPlay={onPlay} size="h-10 w-10" icon="h-4 w-4" />
        )}
      </div>

      {!reveal && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 py-4">
          <PlayButton letter={letter} playing={playing} onPlay={onPlay} size="h-16 w-16" icon="h-7 w-7" />
          <Wave playing={playing} />
          <Meter playing={playing} progress={progress} />
        </div>
      )}

      {reveal ? (
        <div className="mt-3 flex min-h-0 flex-1 flex-col">
          <Meter playing={playing} progress={progress} />
          <div className="mt-auto pt-3">
            <span className={cx(
              "inline-flex max-w-full rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white",
              reveal.real ? "bg-good" : "bg-bad",
            )}>
              {reveal.real ? "Your real voice" : `Clone: ${reveal.who}`}
            </span>
            <p className="mt-1.5 min-h-4 text-xs text-muted">{reveal.picked ? "You picked this one" : "\u00a0"}</p>
            <div className="mt-1 flex flex-wrap items-end justify-between gap-1">
              <p className="font-display text-2xl leading-none tabular-nums">{formatMargin(reveal.margin)}</p>
              <p className="pb-0.5 text-xs text-muted">{reveal.saysClone ? "Called a clone" : "Passed as real"}</p>
            </div>
            <div
              className="relative mt-2 h-2 rounded-full"
              style={{ background: `linear-gradient(90deg, #b4332a 0 ${cutPct}%, #157a45 ${cutPct}% 100%)` }}
            >
              <span className="absolute -bottom-1 -top-1 w-0.5 bg-ink" style={{ left: `${cutPct}%` }} />
              <span className="gauge-dot absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-ink" style={{ left: slid ? `${marginPct}%` : "0%" }} />
            </div>
            <div className="mt-2 flex justify-between text-[11px] font-semibold uppercase tracking-wider text-muted">
              <span>Clone</span>
              <span>Real</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-auto">
          <p className="mb-2 min-h-4 text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">{heard ? "Played" : ""}</p>
          <button
            type="button"
            onClick={onPick}
            disabled={!heard}
            className={cx(
              "w-full rounded-2xl border px-4 py-2.5 text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
              "disabled:cursor-not-allowed disabled:opacity-40",
              heard && "cursor-pointer",
              selected ? "border-accent bg-accent text-white" : "border-line bg-white text-ink hover:border-accent",
            )}
          >
            {selected ? "✓ Selected" : heard ? "This one is me" : "Play to choose"}
          </button>
        </div>
      )}
    </article>
  );
}

function PlayButton({ letter, playing, onPlay, size, icon }) {
  return (
    <button
      type="button"
      className={cx(
        "grid shrink-0 cursor-pointer place-items-center rounded-full bg-accent text-white shadow-[0_12px_24px_-12px_rgba(15,111,91,0.9)] transition hover:bg-accent-deep focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent",
        size,
      )}
      aria-label={`${playing ? "Pause" : "Play"} Voice ${letter}`}
      aria-pressed={playing}
      onClick={onPlay}
    >
      {playing ? <PauseIcon className={icon} /> : <PlayIcon className={icon} />}
    </button>
  );
}

function Wave({ playing }) {
  return (
    <div className="flex h-10 items-center gap-[3px]" aria-hidden="true">
      {Array.from({ length: 9 }, (_, index) => (
        <span
          key={index}
          className={cx("block w-1 rounded-full", playing ? "eq h-8 bg-accent" : "h-3 bg-[#d3c9b8]")}
          style={playing ? { animationDelay: `${(index % 5) * 0.12}s` } : undefined}
        />
      ))}
    </div>
  );
}

function Meter({ playing, progress }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-mist" aria-hidden="true">
      <div className="meter-bar h-full rounded-full bg-accent" style={{ width: `${(playing ? progress : 0) * 100}%` }} />
    </div>
  );
}

function PlayIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" className={cx("ml-0.5 fill-current", className)} aria-hidden="true">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function PauseIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" className={cx("fill-current", className)} aria-hidden="true">
      <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
    </svg>
  );
}

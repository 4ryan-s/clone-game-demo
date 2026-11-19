import { useCallback, useEffect, useRef, useState } from "react";
import WavesurferPlayer from "@wavesurfer/react";
import { cx } from "../lib/cx";
import { formatMargin, scorePercent } from "../lib/score";

export function VoiceCard({ letter, src, active, onStart, selected, onPick, heard, reveal }) {
  const [slid, setSlid] = useState(false);
  useEffect(() => {
    if (!reveal) return undefined;
    const timer = window.setTimeout(() => setSlid(true), 80);
    return () => window.clearTimeout(timer);
  }, []);

  const border = reveal
    ? reveal.real
      ? "border-4 border-good shadow-[0_0_0_5px_rgba(21,122,69,0.25)]"
      : "border-2 border-bad/70"
    : selected || active ? "border-2 border-accent" : "border-2 border-line";
  const fill = reveal
    ? reveal.real ? "bg-good-soft" : "bg-bad-soft"
    : "bg-card";
  const marginPct = reveal ? scorePercent(reveal.margin) : 0;
  const cutPct = reveal ? scorePercent(reveal.cutoff) : 0;

  return (
    <article className={cx(
      "flex min-h-0 flex-col overflow-hidden rounded-[28px] text-center shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)] transition duration-200",
      reveal ? "h-full px-2.5 py-2.5 sm:px-3 sm:py-3" : "h-auto px-2.5 py-3 sm:px-4 sm:py-4",
      border,
      fill,
      !reveal && selected && "-translate-y-1 shadow-[0_0_0_6px_rgba(15,111,91,0.14)]",
      !reveal && !selected && "hover:-translate-y-1",
    )}>
      <div className={cx("flex items-center", reveal ? "justify-between text-left" : "flex-col")}>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">Voice</p>
          <h2 className={cx("font-display leading-none", reveal ? "text-xl sm:text-2xl" : "text-3xl sm:text-5xl")}>{letter}</h2>
        </div>
        {reveal && reveal.picked && (
          <span className="rounded-full bg-ink px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white">
            Your pick
          </span>
        )}
      </div>

      {!reveal && (
        <div className="flex flex-1 flex-col items-center justify-center py-3 sm:py-4">
          <WavePlayer letter={letter} src={src} active={active} onStart={onStart} height={18} />
        </div>
      )}

      {reveal ? (
        <div className="mt-3 flex min-h-0 flex-1 flex-col">
          <WavePlayer letter={letter} src={src} active={active} onStart={onStart} height={16} />
          <div className="mt-auto pt-3">
            <span className={cx(
              "inline-flex max-w-full rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white",
              reveal.real ? "bg-good" : "bg-bad",
            )}>
              {reveal.real ? "Your real voice" : `Clone: ${reveal.who}`}
            </span>
            <p className={cx("mt-1.5 min-h-4 text-xs font-semibold", reveal.picked ? (reveal.real ? "text-good" : "text-bad") : "text-muted")}>
              {reveal.picked ? (reveal.real ? "You picked this \u2014 correct!" : "You picked this one") : "\u00a0"}
            </p>
            <div className="mt-1 flex flex-wrap items-end justify-between gap-1">
              <p className="font-display text-xl leading-none tabular-nums sm:text-2xl">{formatMargin(reveal.margin)}</p>
              <p className="pb-0.5 text-xs text-muted">{reveal.saysClone ? "Cloned voice" : "Passed as real"}</p>
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
              "w-full rounded-2xl border px-2 py-2 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:px-4 sm:py-2.5 sm:text-sm",
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

// Draw a flat rounded line instead of the waveform. wavesurfer sets fillStyle
// (wave colour, or progress colour on the clipped progress canvas) before it
// calls this, so the same line doubles as the progress fill.
function renderLine(channels, ctx) {
  const { width, height } = ctx.canvas;
  const thickness = Math.min(height, 8);
  const top = (height - thickness) / 2;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(0, top, width, thickness, thickness / 2);
  else ctx.rect(0, top, width, thickness);
  ctx.fill();
  ctx.closePath();
}

// Audio bar with click/drag seeking, powered by wavesurfer.js, rendered as a
// line (not a waveform). One "active" card plays at a time: when another card
// starts, this one pauses.
function WavePlayer({ letter, src, active, onStart, height }) {
  const wsRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!active && playing) wsRef.current?.pause();
  }, [active, playing]);

  const onReady = useCallback((ws) => {
    wsRef.current = ws;
    setReady(true);
  }, []);

  const toggle = useCallback(() => {
    wsRef.current?.playPause();
  }, []);

  return (
    <div className="flex w-full items-center gap-2.5">
      <button
        type="button"
        onClick={toggle}
        disabled={!ready}
        aria-label={`${playing ? "Pause" : "Play"} Voice ${letter}`}
        aria-pressed={playing}
        className="grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-full bg-accent text-white shadow-[0_12px_24px_-12px_rgba(15,111,91,0.9)] transition hover:bg-accent-deep focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent disabled:cursor-default disabled:opacity-50"
      >
        {playing ? <PauseIcon className="h-4 w-4" /> : <PlayIcon className="h-4 w-4" />}
      </button>
      <div className="min-w-0 flex-1">
        <WavesurferPlayer
          height={height}
          waveColor="#d3c9b8"
          progressColor="#0f6f5b"
          cursorColor="#0c5a4a"
          cursorWidth={2}
          dragToSeek
          renderFunction={renderLine}
          url={src}
          onReady={onReady}
          onPlay={() => { setPlaying(true); onStart?.(); }}
          onPause={() => setPlaying(false)}
          onFinish={() => setPlaying(false)}
        />
      </div>
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

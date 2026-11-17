import { useState } from "react";
import { Button, ErrorNote } from "./ui";
import { VoiceCard } from "./VoiceCard";
import { Confetti } from "./Confetti";
import { cx } from "../lib/cx";

export function ResultStep({ result, cardIds, player, retain, sid, onFinish, onDelete }) {
  const [closing, setClosing] = useState("");
  const [error, setError] = useState("");
  const won = result.won;
  const clones = result.cards.filter((card) => !card.real);
  const real = result.cards.find((card) => card.real);
  const caught = clones.filter((card) => card.says_clone).length;
  const ordered = (cardIds.length ? cardIds : result.cards.map((card) => card.card))
    .map((id, index) => {
      const card = result.cards.find((item) => item.card === id);
      return card ? { ...card, letter: String.fromCharCode(65 + index) } : null;
    })
    .filter(Boolean);

  const realCall = !real
    ? ""
    : real.says_clone
      ? " It wrongly doubted your real voice."
      : " It passed your real voice.";
  const note = `The score shows how strongly the detector thinks a voice is real. Below ${result.cutoff} it calls the voice a clone. It caught ${caught} of ${clones.length} clones.${realCall}`;
  const finishNote = retain
    ? "You agreed that we keep your recording and the copies without your name. Use the session code to ask for deletion later."
    : "You did not agree to keep your recording, so it is deleted when you press Finish.";

  async function run(kind) {
    setClosing(kind);
    setError("");
    try {
      await (kind === "delete" ? onDelete() : onFinish());
    } catch (err) {
      setError(err.message);
      setClosing("");
    }
  }

  async function play(id) {
    try {
      await player.toggle(id);
    } catch {
      setError("The audio could not be played. Try again.");
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5">
      <section className={cx(
        "relative shrink-0 overflow-hidden rounded-[28px] border-2 px-8 py-5",
        won ? "border-[#b7dfc8] bg-good-soft" : "border-[#e7c3bd] bg-bad-soft",
      )}>
        {won && <Confetti />}
        <span className="shine pointer-events-none absolute inset-y-0 left-0 w-1/4 bg-gradient-to-r from-transparent via-white/70 to-transparent" />
        <div className="relative flex items-center justify-between gap-8">
          <div>
            <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-accent">Round 05 · Reward</p>
            <Stars filled={won ? 3 : 1} />
            <h1 className="mt-2 font-display text-5xl leading-[1.05]">
              {won ? "You spotted the real one" : "The AI fooled you"}
            </h1>
            <p className="mt-3 max-w-2xl text-lg text-muted">
              {won
                ? "Your ear was right. Here is what our clone check made of each voice."
                : "You picked a copy. Here is what our clone check made of each voice."}
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Prize won={won} />
              <Stat label="Your pick" value={won ? "Real voice" : "A copy"} />
              <Stat label="Clones caught" value={`${caught} of ${clones.length}`} />
            </div>
          </div>
          {won ? <Medal /> : <ScorecardMark />}
        </div>
      </section>

      <div
        className="grid shrink-0 gap-4"
        style={{ gridTemplateColumns: `repeat(${Math.max(ordered.length, 1)}, minmax(0, 1fr))` }}
      >
        {ordered.map((card, index) => (
          <div key={card.card} className="rise min-h-0" style={{ animationDelay: `${120 + index * 80}ms` }}>
            <VoiceCard
              letter={card.letter}
              playing={player.playingId === card.card}
              progress={player.progress}
              onPlay={() => play(card.card)}
              reveal={{
                real: card.real,
                who: card.who,
                margin: card.margin,
                saysClone: card.says_clone,
                picked: card.card === result.picked,
                cutoff: result.cutoff,
              }}
            />
          </div>
        ))}
      </div>

      <footer className="mt-auto flex shrink-0 items-end justify-between gap-6 pt-1">
        <div className="max-w-3xl">
          <p className="text-sm leading-relaxed text-muted">{note}</p>
          <p className="mt-1 text-sm leading-relaxed text-muted">{finishNote}</p>
          <p className="mt-2 text-sm text-muted">
            Session code <strong className="ml-1 rounded-lg bg-card px-2 py-1 font-mono text-sm text-ink ring-1 ring-line">{sid}</strong>
          </p>
          <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>
        </div>
        <div className="flex shrink-0 gap-3">
          <Button disabled={!!closing} onClick={() => run("delete")}>{closing === "delete" ? "Deleting…" : "Delete my data"}</Button>
          <Button primary disabled={!!closing} onClick={() => run("finish")}>{closing === "finish" ? "Finishing…" : "Finish"}</Button>
        </div>
      </footer>
    </div>
  );
}

function Prize({ won }) {
  return (
    <div className="rounded-2xl bg-card px-4 py-3 ring-1 ring-line">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gold">Prize</p>
      <p className="font-display text-xl">{won ? "Sharp Ear" : "Detector's scorecard"}</p>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-2xl bg-card px-4 py-3 ring-1 ring-line">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">{label}</p>
      <p className="font-display text-xl">{value}</p>
    </div>
  );
}

function Stars({ filled }) {
  return (
    <div className="mt-3 flex gap-1" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <svg
          key={index}
          viewBox="0 0 24 24"
          className={cx("h-7 w-7 rise", index < filled ? "fill-gold" : "fill-line")}
          style={{ animationDelay: `${index * 120}ms` }}
        >
          <path d="M12 2.4 14.7 8.8l7 .6-5.3 4.6 1.7 6.8L12 17.4 5.9 20.8l1.7-6.8L2.3 9.4l7-.6z" />
        </svg>
      ))}
    </div>
  );
}

function Medal() {
  return (
    <svg viewBox="0 0 120 150" className="pop h-40 w-36 shrink-0" aria-hidden="true">
      <path d="M36 8h16l8 30H44z" fill="#c4493a" />
      <path d="M68 8h16l-8 30H60z" fill="#0f6f5b" />
      <path d="M46 34h28l-6 16H52z" fill="#a67912" />
      <circle cx="60" cy="94" r="40" fill="#f8e7b0" />
      <circle cx="60" cy="94" r="34" fill="none" stroke="#a67912" strokeWidth="4" className="draw" />
      <path fill="#a67912" d="M60 76.5 64.4 86l10.4 1-7.8 6.7 2.3 10.2L60 98.6l-9.3 5.3 2.3-10.2-7.8-6.7 10.4-1z" />
    </svg>
  );
}

function ScorecardMark() {
  return (
    <div className="pop grid h-36 w-36 shrink-0 place-items-center rounded-full bg-gold-soft text-gold" aria-hidden="true">
      <svg viewBox="0 0 48 48" className="h-16 w-16" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="12" y="8" width="24" height="32" rx="3" />
        <path d="M18 18h12M18 24h12M18 30h8" strokeLinecap="round" />
      </svg>
    </div>
  );
}

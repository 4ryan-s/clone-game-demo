import { useEffect, useState } from "react";
import { Button, ErrorNote } from "./ui";
import { VoiceCard } from "./VoiceCard";
import { CertificateCard } from "./CertificateCard";
import { Confetti } from "./Confetti";
import { cx } from "../lib/cx";

export function ResultStep({ result, cardIds, sid, retain, onFinish }) {
  const won = result.won;
  const [showScores, setShowScores] = useState(false);
  const [active, setActive] = useState(null);
  const [closing, setClosing] = useState("");
  const [error, setError] = useState("");
  const ordered = (cardIds.length ? cardIds : result.cards.map((card) => card.card))
    .map((id, index) => {
      const card = result.cards.find((item) => item.card === id);
      return card ? { ...card, letter: String.fromCharCode(65 + index) } : null;
    })
    .filter(Boolean);
  const real = ordered.find((card) => card.real);
  const shown = ordered;

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const timer = window.setTimeout(() => setShowScores(true), reduce ? 400 : 2800);
    return () => window.clearTimeout(timer);
  }, []);

  async function finish() {
    setClosing("finish");
    setError("");
    try {
      await onFinish();
    } catch (err) {
      setError(err.message);
      setClosing("");
    }
  }

  if (!showScores) {
    return (
      <div className="relative flex flex-col items-center overflow-hidden text-center">
        {won && <Confetti screen count={72} />}
        <div className={cx("relative flex flex-col items-center", won ? "pop" : "rise")}>
          {won ? <Stars filled={3} /> : <Stars filled={1} />}
          <h1 className="mt-4 font-display text-4xl leading-tight text-balance sm:text-5xl lg:text-6xl">
            {won ? "Woohoo! You got it right!" : "Oops! A cloned voice fooled you"}
          </h1>
          <p className="mt-3 text-lg text-muted">
            {won ? "That was your voice." : real ? `Voice ${real.letter} was yours.` : "That was a cloned voice."}
          </p>
          <div className="mt-8">{won ? <Medal /> : <ScorecardMark />}</div>
          <Button primary className="mt-8 w-full max-w-xs sm:mt-10 sm:w-auto sm:min-w-52" onClick={() => setShowScores(true)}>See the cloned voices</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div className="text-center">
        <h1 className="font-display text-3xl leading-tight text-balance sm:text-4xl">{won ? "Woohoo! You found your voice" : "Oops! A cloned voice fooled you"}</h1>
        {real && <p className="mt-2 text-muted">Voice {real.letter} was yours.</p>}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {shown.map((card, index) => (
          <div key={card.card} className="rise min-h-0 min-w-0" style={{ animationDelay: `${index * 80}ms` }}>
            <VoiceCard
              letter={card.letter}
              src={`/api/sessions/${sid}/cards/${card.card}.wav`}
              active={active === card.card}
              onStart={() => setActive(card.card)}
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

      <footer className="flex flex-col items-center gap-4 pt-1">
        {won && <CertificateCard sid={sid} />}
        {won && retain && (
          <p className="max-w-md text-center text-sm text-muted">
            Thank you for agreeing to let us save your voice to train future models!
          </p>
        )}
        <ErrorNote>{error}</ErrorNote>
        <Button primary disabled={!!closing} onClick={finish}>{closing ? "Finishing…" : "Finish"}</Button>
      </footer>
    </div>
  );
}

function Stars({ filled }) {
  return (
    <div className="flex justify-center gap-1" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <svg
          key={index}
          viewBox="0 0 24 24"
          className={cx("h-8 w-8 rise", index < filled ? "fill-gold" : "fill-line")}
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
    <svg viewBox="0 0 120 150" className="pop h-32 w-28 shrink-0 sm:h-44 sm:w-36" aria-hidden="true">
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

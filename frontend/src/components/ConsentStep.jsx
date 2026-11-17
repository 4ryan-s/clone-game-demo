import { useState } from "react";
import { Button, ErrorNote, StepHead } from "./ui";

export function ConsentStep({ consent, onAgree }) {
  const [agree, setAgree] = useState(false);
  const [retain, setRetain] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
    <div className="grid min-h-0 flex-1 grid-cols-12 gap-8">
      <div className="col-span-7 min-h-0 overflow-auto pr-2">
        <StepHead kicker="Round 01 · Briefing" title={consent.title} lede={consent.intro} />
        <ul className="mt-8 max-w-2xl space-y-3">
          {consent.points.map((point, index) => (
            <li
              key={point}
              className="rise flex gap-3 text-[17px] leading-relaxed"
              style={{ animationDelay: `${90 + index * 55}ms` }}
            >
              <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-good-soft text-xs font-bold text-good">
                {index + 1}
              </span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="col-span-5 min-h-0">
        <div className="flex h-full min-h-0 flex-col overflow-auto rounded-[28px] border border-line bg-card p-7 shadow-[0_24px_50px_-36px_rgba(40,30,10,0.55)]">
          <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-accent">Before you play</p>
          <h2 className="mt-2 font-display text-[32px] leading-tight">Your agreement</h2>
          <p className="mt-2 text-muted">The first choice is required. The second is optional and starts off.</p>

          <label className="mt-6 flex cursor-pointer gap-3 rounded-2xl border border-line bg-paper/60 p-4">
            <input
              type="checkbox"
              className="mt-1 h-5 w-5 shrink-0 accent-[#0f6f5b]"
              checked={agree}
              onChange={(event) => setAgree(event.target.checked)}
            />
            <span className="text-[15px] leading-relaxed">{consent.required.label}</span>
          </label>

          <label className="mt-3 flex cursor-pointer gap-3 rounded-2xl border border-line bg-paper/60 p-4">
            <input
              type="checkbox"
              className="mt-1 h-5 w-5 shrink-0 accent-[#0f6f5b]"
              checked={retain}
              onChange={(event) => setRetain(event.target.checked)}
            />
            <span className="text-[15px] leading-relaxed">{consent.optional.label}</span>
          </label>

          <div className="mt-4 min-h-5">
            <ErrorNote>{error}</ErrorNote>
          </div>

          <Button primary className="mt-auto w-full" disabled={!agree || busy} onClick={submit}>
            {busy ? "Starting…" : "I agree, continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}

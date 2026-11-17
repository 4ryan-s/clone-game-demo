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
    <div className="mx-auto w-full max-w-xl">
      <StepHead title={consent.title} />
      <div className="mt-6 rounded-[28px] border border-line bg-card p-5 shadow-[0_24px_50px_-36px_rgba(40,30,10,0.55)] sm:mt-7 sm:p-6">
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

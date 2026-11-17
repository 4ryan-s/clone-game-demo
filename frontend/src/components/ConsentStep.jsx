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
    <div className="mx-auto flex min-h-0 w-full max-w-xl flex-1 flex-col justify-center">
      <StepHead title={consent.title} />
      <div className="mt-8 rounded-[28px] border border-line bg-card p-6 shadow-[0_24px_50px_-36px_rgba(40,30,10,0.55)]">
          <label className="flex cursor-pointer gap-3 rounded-2xl border border-line bg-paper/60 p-4">
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

          <Button primary className="mt-6 w-full" disabled={!agree || busy} onClick={submit}>
            {busy ? "Starting…" : "I agree"}
          </Button>
      </div>
    </div>
  );
}

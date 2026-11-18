import { useState } from "react";
import { Button, ErrorNote } from "./ui";

export function StartStep({ onStart, sets }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function go() {
    setBusy(true);
    setError("");
    try {
      await onStart();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col items-center text-center">
      <h1 className="font-display text-4xl leading-tight text-balance sm:text-5xl">Can you tell a real voice from an AI clone?</h1>
      <p className="mt-4 max-w-md text-lg text-muted">
        You will hear four voices say the same words. One is a real person. The others are copies made by AI.
        Pick the real one, then see how our clone check scored each voice.
      </p>
      <ErrorNote>{error}</ErrorNote>
      <Button primary className="mt-8 w-full max-w-xs px-10 py-4 text-lg sm:w-auto sm:min-w-56" disabled={busy || sets === 0} onClick={go}>
        {busy ? "Picking a voice…" : "Start"}
      </Button>
      {sets === 0 ? <p className="mt-3 text-sm text-muted">No voices have been set up yet.</p> : null}
    </div>
  );
}

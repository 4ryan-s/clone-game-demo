import { useState } from "react";
import { Button, ErrorNote, StepHead } from "./ui";
import { VoiceCard } from "./VoiceCard";

export function GameStep({ sid, cardIds, onLock }) {
  const [picked, setPicked] = useState(null);
  const [heard, setHeard] = useState([]);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function start(id) {
    setActive(id);
    setHeard((current) => (current.includes(id) ? current : [...current, id]));
  }

  async function lock() {
    if (!picked) return;
    setBusy(true);
    setError("");
    try {
      await onLock(picked);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col">
      <StepHead title="Listen and find your voice" />

      <div className="mt-4 grid w-full grid-cols-2 gap-3 sm:mt-7 sm:gap-5">
        {cardIds.map((id, index) => (
          <div key={id} className="rise" style={{ animationDelay: `${index * 70}ms` }}>
            <VoiceCard
              letter={String.fromCharCode(65 + index)}
              src={`/api/sessions/${sid}/cards/${id}.wav`}
              active={active === id}
              onStart={() => start(id)}
              selected={picked === id}
              heard={heard.includes(id)}
              onPick={() => setPicked(id)}
            />
          </div>
        ))}
      </div>

      <footer className="mt-7 flex flex-col items-center gap-3">
        <ErrorNote>{error}</ErrorNote>
        <Button primary className="w-full max-w-xs sm:w-auto sm:min-w-52" disabled={!picked || busy} onClick={lock}>
          {busy ? "Checking…" : picked ? "Lock in" : "Pick a voice"}
        </Button>
      </footer>
    </div>
  );
}

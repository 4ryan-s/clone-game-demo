import { useState } from "react";
import { Button, ErrorNote, StepHead } from "./ui";
import { VoiceCard } from "./VoiceCard";

export function GameStep({ cardIds, player, onLock }) {
  const [picked, setPicked] = useState(null);
  const [heard, setHeard] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function play(id) {
    setError("");
    try {
      await player.toggle(id);
      setHeard((current) => (current.includes(id) ? current : [...current, id]));
    } catch {
      setError("The audio could not be played. Try again.");
    }
  }

  async function lock() {
    if (!picked) return;
    setBusy(true);
    setError("");
    player.stop();
    try {
      await onLock(picked);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col">
      <StepHead title="Which one is you?" />

      <div className="mt-7 grid w-full grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
        {cardIds.map((id, index) => (
          <div key={id} className="rise" style={{ animationDelay: `${index * 70}ms` }}>
            <VoiceCard
              letter={String.fromCharCode(65 + index)}
              playing={player.playingId === id}
              progress={player.progress}
              onPlay={() => play(id)}
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

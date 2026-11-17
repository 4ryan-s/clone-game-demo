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

  const voices = cardIds.length;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <StepHead
        kicker="Round 04 · The question"
        title="Which one is really you?"
        lede={voices
          ? `All ${voices} say the same sentence. One is your own recording, the others are copies made by AI voice systems. Listen to each, then pick the real one.`
          : "Listen to each voice, then pick the real one."}
      />

      <div
        className="mt-6 grid min-h-0 flex-1 gap-5"
        style={{ gridTemplateColumns: `repeat(${Math.max(voices, 1)}, minmax(0, 1fr))` }}
      >
        {cardIds.map((id, index) => (
          <div key={id} className="rise min-h-0" style={{ animationDelay: `${index * 70}ms` }}>
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

      <footer className="mt-5 flex items-center justify-between gap-6">
        <div>
          <ErrorNote>{error}</ErrorNote>
          <p className="text-sm text-muted">
            {heard.length} of {voices} {voices === 1 ? "voice" : "voices"} played
          </p>
        </div>
        <Button primary className="min-w-64" disabled={!picked || busy} onClick={lock}>
          {busy ? "Checking…" : picked ? "Lock in my answer" : "Choose a voice first"}
        </Button>
      </footer>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./lib/api";
import { usePlayer } from "./hooks/usePlayer";
import { Shell } from "./components/Shell";
import { Boot } from "./components/Boot";
import { StartStep } from "./components/StartStep";
import { ConsentStep } from "./components/ConsentStep";
import { RecordStep } from "./components/RecordStep";
import { MakingStep } from "./components/MakingStep";
import { GameStep } from "./components/GameStep";
import { ResultStep } from "./components/ResultStep";
import { ByeStep } from "./components/ByeStep";

// Two flows share the same cards, game and result screens:
//   static (cfg.static): Start -> Pick -> Reward. The voices and clones were made ahead of time; Start picks a random person.
//   live: consent -> record -> clones are made -> Pick -> Reward.
export default function App() {
  const [phase, setPhase] = useState("loading");
  const [bootError, setBootError] = useState("");
  const [cfg, setCfg] = useState(null);
  const [sid, setSid] = useState(null);
  const [round, setRound] = useState(null); // static flow: { id, name, text }
  const [retain, setRetain] = useState(false);
  const [cardIds, setCardIds] = useState([]);
  const [result, setResult] = useState(null);
  const [bye, setBye] = useState({ title: "", text: "" });
  const handedOff = useRef(false);
  const isStatic = !!(cfg && cfg.static);
  const player = usePlayer(isStatic ? (round ? `/api/rounds/${round.id}` : null) : sid ? `/api/sessions/${sid}` : null);

  const init = useCallback(async () => {
    setPhase("loading");
    setBootError("");
    try {
      const next = await api("/api/config");
      setCfg(next);
      setPhase(next.static ? "start" : "consent");
    } catch (err) {
      setBootError(err.message);
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    init();
  }, [init]);

  function restart() {
    player.stop();
    handedOff.current = false;
    setSid(null);
    setRound(null);
    setRetain(false);
    setCardIds([]);
    setResult(null);
    setBye({ title: "", text: "" });
    init();
  }

  // ---- static flow
  async function startRound() {
    const started = await api("/api/static/rounds", { method: "POST" });
    setRound({ id: started.round_id, name: started.name, text: started.text });
    setCardIds(started.cards);
    setResult(null);
    setPhase("game");
  }

  function playAgain() {
    player.stop();
    setRound(null);
    setCardIds([]);
    setResult(null);
    setPhase("start");
  }

  // ---- live flow
  async function agree({ retain: keep }) {
    const created = await api("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agree: true, retain: keep, version: cfg.consent.version }),
    });
    setRetain(keep);
    setSid(created.session_id);
    setPhase("record");
  }

  async function submitRecording(blob) {
    const body = new FormData();
    body.append("file", blob, "recording.wav");
    const verdict = await api(`/api/sessions/${sid}/recording`, { method: "POST", body });
    if (!verdict.ok) {
      throw new Error((verdict.issues || []).join(" ") || "That recording could not be used.");
    }
    await api(`/api/sessions/${sid}/generate`, { method: "POST" });
    handedOff.current = false;
    setPhase("making");
  }

  async function copiesReady() {
    if (handedOff.current) return;
    handedOff.current = true;
    try {
      const cards = await api(`/api/sessions/${sid}/cards`);
      setCardIds(cards.cards);
      setPhase("game");
    } catch (err) {
      handedOff.current = false;
      throw err;
    }
  }

  async function lock(card) {
    const path = isStatic ? `/api/rounds/${round.id}/pick` : `/api/sessions/${sid}/pick`;
    const reveal = await api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card }),
    });
    player.stop();
    setResult(reveal);
    setPhase("result");
  }

  async function finish() {
    player.stop();
    try {
      const done = await api(`/api/sessions/${sid}/finish`, { method: "POST" });
      setBye({
        title: "Thank you",
        text: done.deleted
          ? "Your recording and the copies have been deleted."
          : "Your recording is saved without your name. The copies have been deleted. Keep your session code if you want your recording deleted later.",
      });
    } catch (err) {
      setBye({ title: "Thank you", text: err.message });
    }
    setPhase("bye");
  }

  async function remove() {
    player.stop();
    try {
      await api(`/api/sessions/${sid}`, { method: "DELETE" });
      setBye({ title: "Deleted", text: "Your recording and the copies have been deleted." });
    } catch (err) {
      setBye({ title: "Could not delete", text: err.message });
    }
    setPhase("bye");
  }

  if (phase === "loading" || phase === "error") {
    return <Boot error={phase === "error" ? bootError : ""} onRetry={init} />;
  }
  if (phase === "bye") {
    return <ByeStep title={bye.title} text={bye.text} onRestart={restart} />;
  }

  return (
    <Shell phase={phase} isStatic={isStatic}>
      {phase === "start" && <StartStep onStart={startRound} sets={cfg.static_sets ?? 1} />}
      {phase === "consent" && <ConsentStep consent={cfg.consent} onAgree={agree} />}
      {phase === "record" && (
        <RecordStep sentence={cfg.sentence} maxSeconds={cfg.max_seconds} onSubmit={submitRecording} />
      )}
      {phase === "making" && (
        <MakingStep sid={sid} cloneCount={cfg.clone_count} onReady={copiesReady} />
      )}
      {phase === "game" && (
        <GameStep
          cardIds={cardIds}
          player={player}
          onLock={lock}
          title={isStatic ? `Which one is really ${round.name}?` : undefined}
          subtitle={isStatic ? `They all say: “${round.text}”` : ""}
          pickLabel={isStatic ? "This is the real voice" : undefined}
        />
      )}
      {phase === "result" && result && (
        <ResultStep
          result={result}
          cardIds={cardIds}
          player={player}
          retain={retain}
          sid={sid}
          onFinish={finish}
          onDelete={remove}
          name={isStatic ? result.name : ""}
          onAgain={isStatic ? playAgain : undefined}
        />
      )}
    </Shell>
  );
}

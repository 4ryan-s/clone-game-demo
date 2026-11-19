import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./lib/api";
import { Shell } from "./components/Shell";
import { Boot } from "./components/Boot";
import { ConsentStep } from "./components/ConsentStep";
import { RecordStep } from "./components/RecordStep";
import { MakingStep } from "./components/MakingStep";
import { GameStep } from "./components/GameStep";
import { ResultStep } from "./components/ResultStep";
import { ByeStep } from "./components/ByeStep";

export default function App() {
  const [phase, setPhase] = useState("loading");
  const [bootError, setBootError] = useState("");
  const [cfg, setCfg] = useState(null);
  const [sid, setSid] = useState(null);
  const [retain, setRetain] = useState(false);
  const [cardIds, setCardIds] = useState([]);
  const [result, setResult] = useState(null);
  const [bye, setBye] = useState({ title: "", text: "" });
  const handedOff = useRef(false);

  const init = useCallback(async () => {
    setPhase("loading");
    setBootError("");
    try {
      const next = await api("/api/config");
      setCfg(next);
      setPhase("consent");
    } catch (err) {
      setBootError(err.message);
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    init();
  }, [init]);

  function restart() {
    handedOff.current = false;
    setSid(null);
    setRetain(false);
    setCardIds([]);
    setResult(null);
    setBye({ title: "", text: "" });
    init();
  }

  async function agree({ retain: keep, cloning }) {
    const created = await api("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agree: cloning, cloning, retain: keep, version: cfg.consent.version }),
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
    const reveal = await api(`/api/sessions/${sid}/pick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card }),
    });
    setResult(reveal);
    setPhase("result");
  }

   async function finish() {
    try {
      const done = await api(`/api/sessions/${sid}/finish`, { method: "POST" });
      setBye({
        title: "Thank you",
        text: done.deleted
          ? "Your recording and the cloned voices have been deleted."
          : "Your recording is saved without your name. The cloned voices have been deleted.",
      });
    } catch (err) {
      setBye({ title: "Thank you", text: err.message });
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
    <Shell phase={phase}>
      {phase === "consent" && <ConsentStep consent={cfg.consent} onAgree={agree} />}
      {phase === "record" && (
        <RecordStep sentence={cfg.sentence} maxSeconds={cfg.max_seconds} onSubmit={submitRecording} />
      )}
      {phase === "making" && (
        <MakingStep sid={sid} cloneCount={cfg.clone_count} onReady={copiesReady} />
      )}
      {phase === "game" && <GameStep sid={sid} cardIds={cardIds} onLock={lock} />}
      {phase === "result" && result && (
        <ResultStep
          result={result}
          cardIds={cardIds}
          retain={retain}
          sid={sid}
          onFinish={finish}
        />
      )}
    </Shell>
  );
}

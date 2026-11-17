import { useCallback, useEffect, useRef, useState } from "react";

export function usePlayer(sid) {
  const audioRef = useRef(null);
  const playingRef = useRef(null);
  const [playingId, setPlayingId] = useState(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const audio = new Audio();
    audioRef.current = audio;
    const onEnded = () => {
      playingRef.current = null;
      setPlayingId(null);
      setProgress(0);
    };
    const onTime = () => {
      if (!audio.duration || !playingRef.current) return;
      setProgress(audio.currentTime / audio.duration);
    };
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("timeupdate", onTime);
    return () => {
      audio.pause();
      audio.src = "";
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("timeupdate", onTime);
    };
  }, []);

  const stop = useCallback(() => {
    const audio = audioRef.current;
    if (audio) audio.pause();
    playingRef.current = null;
    setPlayingId(null);
    setProgress(0);
  }, []);

  const toggle = useCallback((id) => {
    const audio = audioRef.current;
    if (!audio || !sid) return Promise.resolve();
    if (playingRef.current === id) {
      stop();
      return Promise.resolve();
    }
    audio.pause();
    setProgress(0);
    playingRef.current = id;
    setPlayingId(id);
    audio.src = `/api/sessions/${sid}/cards/${id}.wav`;
    return audio.play().catch((err) => {
      if (err && err.name === "AbortError") return;
      if (playingRef.current === id) {
        playingRef.current = null;
        setPlayingId(null);
        setProgress(0);
      }
      throw err;
    });
  }, [sid, stop]);

  return { playingId, progress, toggle, stop };
}

import { useMemo } from "react";

const COLORS = ["#0f6f5b", "#e8c36a", "#f4efe6", "#1c1915", "#e07a4c", "#8fd0b8"];

export function Confetti({ screen = false, count = 42 }) {
  const pieces = useMemo(() => Array.from({ length: count }, (_, id) => ({
    id,
    left: Math.random() * 100,
    delay: Math.random() * 0.35,
    duration: 1.8 + Math.random() * 1.2,
    drift: `${-70 + Math.random() * 140}px`,
    rot: `${240 + Math.random() * 480}deg`,
    color: COLORS[id % COLORS.length],
    w: 7 + Math.random() * 7,
    h: 9 + Math.random() * 8,
    radius: Math.random() > 0.7 ? "999px" : "2px",
  })), [count]);

  return (
    <div className={screen ? "confetti-screen pointer-events-none absolute inset-0 overflow-hidden" : "pointer-events-none absolute inset-0 overflow-hidden"} aria-hidden="true">
      {pieces.map((piece) => (
        <span
          key={piece.id}
          className="confetti-bit"
          style={{
            left: `${piece.left}%`,
            width: piece.w,
            height: piece.h,
            background: piece.color,
            borderRadius: piece.radius,
            animationDuration: `${piece.duration}s`,
            animationDelay: `${piece.delay}s`,
            "--drift": piece.drift,
            "--rot": piece.rot,
          }}
        />
      ))}
    </div>
  );
}

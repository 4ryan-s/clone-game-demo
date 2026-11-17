const LO = -15;
const HI = 30;

export function scorePercent(margin) {
  return Math.max(0, Math.min(100, ((margin - LO) / (HI - LO)) * 100));
}

export function formatMargin(margin) {
  const n = Number(margin);
  const text = n.toFixed(1);
  return n > 0 ? `+${text}` : text;
}

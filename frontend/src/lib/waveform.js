// The share image shows the player's own voice as a waveform, drawn from the real clip of this round.

// Loudness of `bars` equal slices of the clip, 0 to 1. The server already trims the silence off the clip and evens out its level.
export async function fetchWaveform(url, bars = 34) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("The audio could not be loaded");
  const data = await res.arrayBuffer();
  const Ctx = window.AudioContext || window.webkitAudioContext;
  const ctx = new Ctx();
  try {
    const audio = await ctx.decodeAudioData(data);
    const samples = audio.getChannelData(0);
    const size = Math.max(1, Math.floor(samples.length / bars));
    const out = [];
    for (let i = 0; i < bars; i += 1) {
      let sum = 0;
      for (let j = i * size; j < (i + 1) * size && j < samples.length; j += 1) sum += samples[j] * samples[j];
      out.push(Math.sqrt(sum / size));
    }
    const max = Math.max(...out) || 1;
    return out.map((v) => Math.pow(v / max, 0.7)); // lift the quiet parts a little so every bar is visible
  } finally {
    ctx.close();
  }
}

// Fallback when the clip cannot be read: a believable shape that is the same for the same code.
export function seededWaveform(seed, bars = 34) {
  let h = 2166136261;
  for (const ch of String(seed)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  const rand = () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  };
  return Array.from({ length: bars }, (_, i) => {
    const envelope = 0.35 + 0.65 * Math.sin((Math.PI * (i + 1)) / (bars + 1));
    return Math.min(1, Math.max(0.12, envelope * (0.45 + 0.55 * rand())));
  });
}

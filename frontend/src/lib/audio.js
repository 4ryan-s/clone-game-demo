export const TARGET_RATE = 16000;

export async function resampleTo16k(data, rate) {
  if (rate === TARGET_RATE) return data;
  const off = new OfflineAudioContext(1, Math.ceil((data.length * TARGET_RATE) / rate), TARGET_RATE);
  const buf = off.createBuffer(1, data.length, rate);
  buf.copyToChannel(data, 0);
  const source = off.createBufferSource();
  source.buffer = buf;
  source.connect(off.destination);
  source.start();
  return (await off.startRendering()).getChannelData(0);
}

export function encodeWav(samples, rate) {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buf);
  const write = (offset, text) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buf], { type: "audio/wav" });
}

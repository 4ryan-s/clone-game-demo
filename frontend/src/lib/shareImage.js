// Draws the share image: 1080 x 1920 (9:16, an Instagram story) PNG on a canvas, in the browser, so it is instant.
// A story-sized picture is what makes "Instagram Stories" show up in the phone share sheet.
// Flat colours, one typeface for the headlines, no glow, sparkles or frames. The waveform is the player's own voice.
import { SHARE_URL, SUPPORT_EMAIL } from "./shareConfig";

const W = 1080;
const H = 1920;
const LAYOUT_H = 1350;
const GOLD = "#d8a94a";
const CORAL = "#ee6a55";
const CREAM = "#f3e9d8";
const SOFT = "#c8b8a4";
const DARK = "#1a0a0d";
const SERIF = "'Fraunces', Georgia, serif";
const SANS = "'Outfit', system-ui, sans-serif";

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// Largest font size (up to `size`) at which `text` fits in `maxWidth`.
function fit(ctx, text, weight, size, family, maxWidth) {
  let s = size;
  ctx.font = `${weight} ${s}px ${family}`;
  while (ctx.measureText(text).width > maxWidth && s > 20) {
    s -= 2;
    ctx.font = `${weight} ${s}px ${family}`;
  }
  return s;
}

function wrap(ctx, text, maxWidth) {
  const lines = [];
  let line = "";
  for (const word of text.split(" ")) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function spaced(ctx, px) {
  if ("letterSpacing" in ctx) ctx.letterSpacing = `${px}px`;
}

// waveform: numbers 0..1 (one per bar). cloneCount: how many fake voices were in the round.
export async function buildShareImage({ waveform, cloneCount, code, logoSrc = "/josh-logo.png" }) {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  try {
    await Promise.all([
      document.fonts.load(`680 100px ${SERIF}`),
      document.fonts.load(`560 40px ${SERIF}`),
      document.fonts.load(`600 28px ${SANS}`),
      document.fonts.load(`400 30px ${SANS}`),
    ]);
  } catch {
    // the generic font families are used instead
  }

  // Background: dark wine, lighter at the top left. Nothing else behind the text.
  const bg = ctx.createLinearGradient(0, 0, W * 0.65, H);
  bg.addColorStop(0, "#5a1620");
  bg.addColorStop(0.55, "#2a0d12");
  bg.addColorStop(1, "#150709");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);
  ctx.save();
  ctx.translate(0, (H - LAYOUT_H) / 2);

  const maxText = W - 160;
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";

  // Label.
  ctx.strokeStyle = GOLD;
  ctx.lineWidth = 2;
  roundRect(ctx, (W - 480) / 2, 74, 480, 62, 31);
  ctx.stroke();
  ctx.fillStyle = GOLD;
  ctx.font = `600 27px ${SANS}`;
  spaced(ctx, 7);
  ctx.fillText("DEEPFAKE CHALLENGE", W / 2 + 3, 114);
  spaced(ctx, 0);

  // Headline.
  ctx.fillStyle = CREAM;
  ctx.font = `560 50px ${SERIF}`;
  ctx.fillText("I successfully identified my", W / 2, 222);

  ctx.fillStyle = GOLD;
  fit(ctx, "original voice", 680, 124, SERIF, maxText);
  ctx.fillText("original voice", W / 2, 346);

  ctx.fillStyle = CREAM;
  ctx.font = `560 36px ${SERIF}`;
  ctx.fillText("among", W / 2, 416);

  ctx.fillStyle = CORAL;
  const fakes = `${cloneCount} deep fake${cloneCount === 1 ? "" : "s"}!`;
  fit(ctx, fakes, 680, 124, SERIF, maxText);
  ctx.fillText(fakes, W / 2, 536);

  // The player's own voice.
  const bars = waveform.length;
  const barW = 14;
  const gap = 11;
  const total = bars * barW + (bars - 1) * gap;
  const x0 = (W - total) / 2;
  const mid = 668;
  ctx.fillStyle = GOLD;
  waveform.forEach((v, i) => {
    const h = 14 + v * 150;
    roundRect(ctx, x0 + i * (barW + gap), mid - h / 2, barW, h, barW / 2);
    ctx.fill();
  });

  // Invitation.
  ctx.fillStyle = CREAM;
  ctx.font = `400 33px ${SANS}`;
  ctx.fillText("Can you tell your voice from a clone? Try it yourself.", W / 2, 816);

  // Link.
  const pillW = 620;
  ctx.fillStyle = GOLD;
  roundRect(ctx, (W - pillW) / 2, 856, pillW, 76, 38);
  ctx.fill();
  ctx.fillStyle = DARK;
  ctx.font = `600 31px ${SANS}`;
  ctx.fillText(`${SHARE_URL}  →`, W / 2, 904);

  // Session code.
  if (code) {
    const boxW = 560;
    ctx.strokeStyle = "rgba(216,169,74,0.55)";
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 7]);
    roundRect(ctx, (W - boxW) / 2, 962, boxW, 58, 10);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.textAlign = "left";
    ctx.fillStyle = SOFT;
    ctx.font = `600 20px ${SANS}`;
    spaced(ctx, 3);
    const label = "CODE";
    const labelW = ctx.measureText(label).width;
    spaced(ctx, 0);
    ctx.font = `600 30px ${SANS}`;
    const codeW = ctx.measureText(code).width;
    const startX = (W - (labelW + 28 + codeW)) / 2;
    ctx.font = `600 20px ${SANS}`;
    spaced(ctx, 3);
    ctx.fillText(label, startX, 998);
    spaced(ctx, 0);
    ctx.fillStyle = CREAM;
    ctx.font = `600 30px ${SANS}`;
    ctx.fillText(code, startX + labelW + 28, 1000);
    ctx.textAlign = "center";
  }

  // Deletion contact.
  ctx.fillStyle = SOFT;
  ctx.font = `400 23px ${SANS}`;
  const note = `For any queries about your voice sample or its permanent deletion, contact ${SUPPORT_EMAIL} with the code in the subject.`;
  let y = 1066;
  for (const line of wrap(ctx, note, 800)) {
    ctx.fillText(line, W / 2, y);
    y += 33;
  }

  // Logo on a white plate: the company mark is dark on white. The file is a square with the mark in a band across the
  // middle (x 10-437, y 168-274 of 447 px), so only that band is drawn.
  try {
    const logo = await loadImage(logoSrc);
    const k = logo.width / 447;
    const [sx, sy, sw, sh] = [10 * k, 168 * k, 427 * k, 106 * k];
    const lh = 78;
    const lw = (sw * lh) / sh;
    const pw = lw + 72;
    const ph = lh + 44;
    ctx.fillStyle = "#ffffff";
    roundRect(ctx, (W - pw) / 2, 1158, pw, ph, 20);
    ctx.fill();
    ctx.drawImage(logo, sx, sy, sw, sh, (W - lw) / 2, 1158 + 22, lw, lh);
  } catch {
    // no logo available; carry on
  }
  ctx.restore();

  const dataUrl = canvas.toDataURL("image/png");
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  return { blob, dataUrl };
}

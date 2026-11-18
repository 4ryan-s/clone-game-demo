// Draws a shareable certificate PNG on a canvas. Everything is client-side so
// the participant gets the image instantly and can save or share it.
const LOGO_SRC = "/josh-logo.png";
const EVENT = "Real or Clone \u2014 The Voice Challenge";
const GOODIE = "Collect your goodie from the booth by showing this certificate.";

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(x, y, w, h, r);
  } else {
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
}

function wrapLines(ctx, text, maxWidth) {
  const words = text.split(" ");
  const lines = [];
  let line = "";
  for (const word of words) {
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

function drawStar(ctx, cx, cy, spikes, outer, inner, color) {
  let rot = (Math.PI / 2) * 3;
  const step = Math.PI / spikes;
  ctx.beginPath();
  ctx.moveTo(cx, cy - outer);
  for (let i = 0; i < spikes; i++) {
    ctx.lineTo(cx + Math.cos(rot) * outer, cy + Math.sin(rot) * outer);
    rot += step;
    ctx.lineTo(cx + Math.cos(rot) * inner, cy + Math.sin(rot) * inner);
    rot += step;
  }
  ctx.lineTo(cx, cy - outer);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

// Returns { blob, dataUrl }. `won` picks the accent colour and wording.
export async function buildCertificate({ won, name, code, date }) {
  const W = 1600;
  const H = 1000;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  try {
    await document.fonts.ready;
  } catch {
    // custom fonts just fall back to the generic family
  }

  const accent = won ? "#0f6f5b" : "#a67912";

  // Background and borders.
  ctx.fillStyle = "#faf7f0";
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = accent;
  ctx.lineWidth = 16;
  ctx.strokeRect(30, 30, W - 60, H - 60);
  ctx.strokeStyle = "#d9cfbd";
  ctx.lineWidth = 3;
  ctx.strokeRect(56, 56, W - 112, H - 112);

  // Logo.
  try {
    const logo = await loadImage(LOGO_SRC);
    const lw = 200;
    const lh = (logo.height * lw) / logo.width;
    ctx.drawImage(logo, (W - lw) / 2, 92, lw, lh);
  } catch {
    // no logo available; carry on
  }

  ctx.textAlign = "center";

  // Title.
  ctx.fillStyle = "#1c1915";
  ctx.font = "700 74px 'Fraunces', Georgia, serif";
  ctx.fillText("Certificate of Participation", W / 2, 360);

  // Event subtitle.
  ctx.fillStyle = "#6f685f";
  ctx.font = "600 30px 'Outfit', system-ui, sans-serif";
  ctx.fillText(EVENT, W / 2, 410);

  // Divider.
  ctx.strokeStyle = accent;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(W / 2 - 90, 440);
  ctx.lineTo(W / 2 + 90, 440);
  ctx.stroke();

  // "Awarded to".
  ctx.fillStyle = "#6f685f";
  ctx.font = "600 24px 'Outfit', system-ui, sans-serif";
  ctx.fillText("A W A R D E D   T O", W / 2, 500);

  // Name.
  ctx.fillStyle = accent;
  ctx.font = "700 58px 'Fraunces', Georgia, serif";
  ctx.fillText(name || "Valued Participant", W / 2, 566);

  // Result sentence.
  ctx.fillStyle = "#1c1915";
  ctx.font = "400 34px 'Outfit', system-ui, sans-serif";
  const sentence = won
    ? "For spotting their own real voice among lifelike AI voice clones."
    : "For taking on lifelike AI voice clones in the voice challenge.";
  const lines = wrapLines(ctx, sentence, W - 360);
  let y = 628;
  for (const line of lines) {
    ctx.fillText(line, W / 2, y);
    y += 46;
  }

  // Goodie message box.
  const boxW = 1120;
  const boxH = 104;
  const boxX = (W - boxW) / 2;
  const boxY = 724;
  ctx.fillStyle = won ? "#e4f5ea" : "#f6e7b6";
  roundRect(ctx, boxX, boxY, boxW, boxH, 24);
  ctx.fill();
  drawStar(ctx, boxX + 54, boxY + boxH / 2, 5, 22, 10, accent);
  drawStar(ctx, boxX + boxW - 54, boxY + boxH / 2, 5, 22, 10, accent);
  ctx.fillStyle = "#1c1915";
  ctx.font = "700 30px 'Outfit', system-ui, sans-serif";
  ctx.fillText(GOODIE, W / 2, boxY + boxH / 2 + 11);

  // Footer: code and date.
  ctx.fillStyle = "#6f685f";
  ctx.font = "600 26px 'Outfit', system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`Code  ${code}`, 140, 912);
  ctx.textAlign = "right";
  ctx.fillText(date, W - 140, 912);

  const dataUrl = canvas.toDataURL("image/png");
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  return { blob, dataUrl };
}

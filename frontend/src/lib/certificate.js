// Draws a shareable, Instagram-story-sized (1080x1920, 9:16) certificate PNG on
// a canvas. Everything is client-side so the participant gets it instantly.
const LOGO_SRC = "/josh-logo.png";
const EVENT = "Real or Clone \u2014 The Voice Challenge";
const BODY = "You identified your own original voice from the best AI-cloned model voices.";
const GOODIE = "Collect your goodie from the booth by showing this certificate.";

const INK = "#1c1915";
const MUTED = "#6f685f";
const ACCENT = "#0f6f5b";
const GOLD = "#a67912";

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
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

function drawBadge(ctx, cx, cy, r) {
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fillStyle = "#f8e7b0";
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx, cy, r - 14, 0, Math.PI * 2);
  ctx.lineWidth = 8;
  ctx.strokeStyle = GOLD;
  ctx.stroke();
  drawStar(ctx, cx, cy, 5, r * 0.55, r * 0.26, GOLD);
}

function confetti(ctx, W) {
  const colors = [ACCENT, GOLD, "#c4493a", "#157a45"];
  const dots = [
    [120, 300], [220, 210], [900, 250], [980, 360], [160, 470],
    [940, 500], [90, 1700], [980, 1680], [150, 1840], [930, 1860],
  ];
  dots.forEach(([x, y], i) => {
    ctx.beginPath();
    ctx.arc(Math.min(x, W - 40), y, 12, 0, Math.PI * 2);
    ctx.fillStyle = colors[i % colors.length];
    ctx.globalAlpha = 0.5;
    ctx.fill();
    ctx.globalAlpha = 1;
  });
}

// Returns { blob, dataUrl }.
export async function buildCertificate({ code, date }) {
  const W = 1080;
  const H = 1920;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  try {
    await document.fonts.ready;
  } catch {
    // custom fonts just fall back to the generic family
  }

  // Background and borders.
  ctx.fillStyle = "#faf7f0";
  ctx.fillRect(0, 0, W, H);
  confetti(ctx, W);
  ctx.strokeStyle = ACCENT;
  ctx.lineWidth = 18;
  ctx.strokeRect(36, 36, W - 72, H - 72);
  ctx.strokeStyle = "#d9cfbd";
  ctx.lineWidth = 3;
  ctx.strokeRect(66, 66, W - 132, H - 132);

  // Logo.
  try {
    const logo = await loadImage(LOGO_SRC);
    const lw = 300;
    const lh = (logo.height * lw) / logo.width;
    ctx.drawImage(logo, (W - lw) / 2, 150, lw, lh);
  } catch {
    // no logo available; carry on
  }

  ctx.textAlign = "center";

  // Label.
  ctx.fillStyle = MUTED;
  ctx.font = "600 30px 'Outfit', system-ui, sans-serif";
  ctx.fillText("C E R T I F I C A T E   O F   A C H I E V E M E N T", W / 2, 560);

  // Headline.
  ctx.fillStyle = ACCENT;
  ctx.font = "700 96px 'Fraunces', Georgia, serif";
  ctx.fillText("Congratulations!", W / 2, 680);

  // Divider.
  ctx.strokeStyle = GOLD;
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.moveTo(W / 2 - 90, 724);
  ctx.lineTo(W / 2 + 90, 724);
  ctx.stroke();

  // Body.
  ctx.fillStyle = INK;
  ctx.font = "400 46px 'Outfit', system-ui, sans-serif";
  const lines = wrapLines(ctx, BODY, W - 220);
  let y = 820;
  for (const line of lines) {
    ctx.fillText(line, W / 2, y);
    y += 62;
  }

  // Badge.
  drawBadge(ctx, W / 2, 1230, 170);

  // Goodie box.
  const boxW = W - 180;
  const boxH = 180;
  const boxX = 90;
  const boxY = 1470;
  ctx.fillStyle = "#e4f5ea";
  roundRect(ctx, boxX, boxY, boxW, boxH, 28);
  ctx.fill();
  ctx.fillStyle = INK;
  ctx.font = "700 38px 'Outfit', system-ui, sans-serif";
  const goodieLines = wrapLines(ctx, GOODIE, boxW - 100);
  let gy = boxY + boxH / 2 - (goodieLines.length - 1) * 26 + 12;
  for (const line of goodieLines) {
    ctx.fillText(line, W / 2, gy);
    gy += 52;
  }

  // Footer.
  ctx.fillStyle = MUTED;
  ctx.font = "600 32px 'Outfit', system-ui, sans-serif";
  ctx.fillText(EVENT, W / 2, 1744);
  ctx.font = "600 28px 'Outfit', system-ui, sans-serif";
  ctx.fillText(`Code ${code}   \u2022   ${date}`, W / 2, 1800);

  const dataUrl = canvas.toDataURL("image/png");
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  return { blob, dataUrl };
}

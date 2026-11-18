import { useRef, useState } from "react";
import { QRCodeCanvas } from "qrcode.react";
import { Button, ErrorNote } from "./ui";
import { api } from "../lib/api";
import { buildCertificate } from "../lib/certificate";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const FILE_NAME = "voice-challenge-certificate.png";

function triggerDownload(blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = FILE_NAME;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function CertificateCard({ sid, won }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [preview, setPreview] = useState("");
  const [certUrl, setCertUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const blobRef = useRef(null);

  async function create() {
    if (email.trim() && !EMAIL_RE.test(email.trim())) {
      setError("That email address doesn't look right.");
      return;
    }
    setError("");
    setNote("");
    setBusy(true);
    try {
      const { blob, dataUrl } = await buildCertificate({
        won,
        name: name.trim(),
        code: sid,
        date: new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }),
      });
      blobRef.current = blob;
      setPreview(dataUrl);
      const res = await api(`/api/sessions/${sid}/certificate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: dataUrl, email: email.trim(), name: name.trim(), won }),
      });
      setCertUrl(new URL(res.url, window.location.origin).href);
    } catch (err) {
      setError(err.message || "The certificate could not be created. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function onShare() {
    try {
      const blob = blobRef.current;
      if (!blob) return;
      const file = new File([blob], FILE_NAME, { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: "Real or Clone — The Voice Challenge",
          text: won
            ? "I spotted my own real voice among AI clones at the Voice Challenge!"
            : "I took on AI voice clones at the Voice Challenge!",
        });
      } else {
        triggerDownload(blob);
        setNote("Sharing isn't supported here, so we downloaded the image for you to post.");
      }
    } catch (err) {
      if (!(err && err.name === "AbortError")) setError("Sharing failed. Try Download instead.");
    }
  }

  return (
    <div className="w-full max-w-xl rounded-[28px] border-2 border-line bg-card p-5 text-center shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)] sm:p-7">
      <h2 className="font-display text-2xl leading-tight sm:text-3xl">Get your certificate</h2>

      {!certUrl ? (
        <>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
            Make your certificate, then scan the QR code to save it on your phone. {" "}
            <strong className="text-ink">Collect your goodie from the booth by showing it.</strong>
          </p>

          <div className="mt-5 flex flex-col gap-3 text-left">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted">Your name (optional)</span>
              <input
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Name on the certificate"
                maxLength={40}
                className="rounded-2xl border border-line bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-accent focus-visible:ring-2 focus-visible:ring-accent/30"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted">Email (optional)</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                className="rounded-2xl border border-line bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-accent focus-visible:ring-2 focus-visible:ring-accent/30"
              />
            </label>
          </div>

          <div className="mt-4 flex justify-center">
            <Button primary className="w-full sm:w-auto sm:min-w-56" disabled={busy} onClick={create}>
              {busy ? "Creating…" : "Create my certificate"}
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
            <strong className="text-ink">Scan this with your phone camera</strong> to open and save your certificate.
            Then collect your goodie from the booth by showing it.
          </p>

          <div className="mt-5 flex justify-center">
            <div className="rounded-2xl border border-line bg-white p-4">
              <QRCodeCanvas value={certUrl} size={208} includeMargin level="M" fgColor="#1c1915" />
            </div>
          </div>

          <p className="mt-3 break-all text-xs text-muted">{certUrl}</p>

          {preview && (
            <img
              src={preview}
              alt="Your certificate preview"
              className="mt-4 w-full rounded-2xl border border-line shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)]"
            />
          )}

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Button primary className="w-full sm:w-auto" onClick={() => blobRef.current && triggerDownload(blobRef.current)}>
              Download on this device
            </Button>
            <Button className="w-full sm:w-auto" onClick={onShare}>Share</Button>
          </div>
        </>
      )}

      <div className="mt-3 flex flex-col items-center gap-1">
        <ErrorNote>{error}</ErrorNote>
        {note && <p className="text-xs text-muted">{note}</p>}
      </div>
    </div>
  );
}

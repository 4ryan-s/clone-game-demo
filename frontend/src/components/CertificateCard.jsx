import { useEffect, useRef, useState } from "react";
import { QRCodeCanvas } from "qrcode.react";
import { Button, ErrorNote } from "./ui";
import { api } from "../lib/api";
import { buildCertificate } from "../lib/certificate";

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

export function CertificateCard({ sid }) {
  const [preview, setPreview] = useState("");
  const [certUrl, setCertUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const blobRef = useRef(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    (async () => {
      try {
        const { blob, dataUrl } = await buildCertificate({
          code: sid,
          date: new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }),
        });
        blobRef.current = blob;
        setPreview(dataUrl);
        const res = await api(`/api/sessions/${sid}/certificate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: dataUrl, won: true }),
        });
        setCertUrl(new URL(res.url, window.location.origin).href);
      } catch (err) {
        setError(err.message || "The certificate could not be created.");
      } finally {
        setLoading(false);
      }
    })();
  }, [sid]);

  async function onShare() {
    try {
      const blob = blobRef.current;
      if (!blob) return;
      const file = new File([blob], FILE_NAME, { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: "Real or Clone — The Voice Challenge",
          text: "I identified my own real voice among the best AI voice clones!",
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
    <div className="w-full max-w-md rounded-[28px] border-2 border-line bg-card p-5 text-center shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)] sm:p-7">
      <h2 className="font-display text-2xl leading-tight sm:text-3xl">Your certificate</h2>

      {loading ? (
        <p className="mt-3 text-sm text-muted">Preparing your certificate…</p>
      ) : (
        <>
          {certUrl && (
            <>
              <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
                <strong className="text-ink">Scan with your phone camera</strong> to save and share it.
                Collect your goodie from the booth by showing it.
              </p>
              <div className="mt-5 flex justify-center">
                <div className="rounded-2xl border border-line bg-white p-4">
                  <QRCodeCanvas value={certUrl} size={200} includeMargin level="M" fgColor="#1c1915" />
                </div>
              </div>
              <p className="mt-3 break-all text-xs text-muted">{certUrl}</p>
            </>
          )}

          {preview && (
            <img
              src={preview}
              alt="Your certificate"
              className="mx-auto mt-4 w-full max-w-[260px] rounded-2xl border border-line shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)]"
            />
          )}

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Button primary className="w-full sm:w-auto" onClick={() => blobRef.current && triggerDownload(blobRef.current)}>
              Download
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

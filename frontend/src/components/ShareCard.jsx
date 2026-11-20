import { useEffect, useRef, useState } from "react";
import { QRCodeCanvas } from "qrcode.react";
import { Button, ErrorNote } from "./ui";
import { api } from "../lib/api";
import { buildShareImage } from "../lib/shareImage";
import { fetchWaveform, seededWaveform } from "../lib/waveform";
import { SHARE_CAPTION, SHARE_FILE_NAME } from "../lib/shareConfig";

function triggerDownload(blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = SHARE_FILE_NAME;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// The picture the player posts. cloneCount: fake voices in the round. audioUrl: the player's own clip, drawn as the waveform.
// The picture is also kept on the server for a few days so a phone can open it from the QR code (no name or email is collected).
export function ShareCard({ sid, cloneCount, audioUrl }) {
  const [preview, setPreview] = useState("");
  const [phoneUrl, setPhoneUrl] = useState("");
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
        let waveform;
        try {
          waveform = audioUrl ? await fetchWaveform(audioUrl) : seededWaveform(sid);
        } catch {
          waveform = seededWaveform(sid); // the picture is still made if the clip cannot be read
        }
        const { blob, dataUrl } = await buildShareImage({ waveform, cloneCount, code: sid });
        blobRef.current = blob;
        setPreview(dataUrl);
        try {
          const res = await api(`/api/sessions/${sid}/share`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: dataUrl }),
          });
          setPhoneUrl(new URL(res.url, window.location.origin).href);
        } catch {
          setNote("The phone link could not be made. You can still share or download the image here.");
        }
      } catch (err) {
        setError(err.message || "The image could not be created.");
      } finally {
        setLoading(false);
      }
    })();
  }, [sid, cloneCount, audioUrl]);

  async function onShare() {
    setError("");
    try {
      const blob = blobRef.current;
      if (!blob) return;
      const file = new File([blob], SHARE_FILE_NAME, { type: "image/png" });
      const withCaption = { files: [file], text: SHARE_CAPTION };
      if (navigator.canShare && navigator.canShare(withCaption)) {
        await navigator.share(withCaption);
      } else if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file] });
      } else {
        triggerDownload(blob);
        setNote("Sharing is not available here, so the image was saved. You can post it from your files.");
      }
    } catch (err) {
      if (!(err && err.name === "AbortError")) setError("Sharing did not work. Try Download instead.");
    }
  }

  return (
    <div className="w-full max-w-md rounded-[28px] border-2 border-line bg-card p-5 text-center shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)] sm:p-7">
      {loading ? (
        <p className="text-sm text-muted">Getting your image ready…</p>
      ) : (
        <>
          {phoneUrl && (
            <div className="mb-5">
              <p className="mx-auto max-w-xs text-sm text-muted">
                <strong className="text-ink">Scan with your phone camera</strong> to save and share your image.
              </p>
              <div className="mt-3 flex justify-center">
                <div className="rounded-2xl border border-line bg-white p-3" data-testid="share-qr">
                  <QRCodeCanvas value={phoneUrl} size={180} includeMargin level="M" fgColor="#1c1915" />
                </div>
              </div>
            </div>
          )}
          {preview && (
            <img
              src={preview}
              alt="Your image to share"
              className="mx-auto w-full max-w-[300px] rounded-2xl border border-line shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)]"
            />
          )}
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Button primary className="w-full sm:w-auto" onClick={onShare}>Share</Button>
            <Button className="w-full sm:w-auto" onClick={() => blobRef.current && triggerDownload(blobRef.current)}>Download</Button>
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

import { useEffect, useRef, useState } from "react";
import { Button, ErrorNote } from "./ui";
import { buildShareImage } from "../lib/shareImage";
import { fetchWaveform, seededWaveform } from "../lib/waveform";
import { SHARE_FILE_NAME, SHARE_URL } from "../lib/shareConfig";

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
export function ShareCard({ sid, cloneCount, audioUrl }) {
  const [preview, setPreview] = useState("");
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
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: "Real or Clone",
          text: `I identified my original voice among ${cloneCount} deep fake${cloneCount === 1 ? "" : "s"}! Can you tell your voice from a clone? ${SHARE_URL}`,
        });
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
          {preview && (
            <div className="relative mx-auto w-full max-w-[300px]">
              <img
                src={preview}
                alt="Your image to share"
                className="w-full rounded-2xl border border-line shadow-[0_18px_40px_-32px_rgba(40,30,10,0.55)]"
              />
              <a
                href={`https://${SHARE_URL}`}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open ${SHARE_URL}`}
                title={SHARE_URL}
                className="absolute rounded-full"
                style={{ left: "20.4%", top: "62.8%", width: "59.3%", height: "6.8%" }}
              />
            </div>
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

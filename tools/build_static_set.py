"""Build the static demo set: for each real clip, make the clones ahead of time and score everything with the clone check.

    python tools/build_static_set.py                 build every original that has no finished set yet
    python tools/build_static_set.py --only aryan    just one person
    python tools/build_static_set.py --force         redo clones and scores even if they exist

Input, in data/static_sources/ (git-ignored: these are real people's voices):
    <person>/reference.wav        10 to 15 s of that person speaking. The clones copy this. (reference.txt = what they say; optional)
    <person>/originals/<clip>.wav the real clip shown in the game. It must NOT be part of reference.wav. (<clip>.txt = transcript; optional)
Without a .txt file the words are transcribed locally with Whisper. Every clone says the same words as the real clip.

Output, in data/static_set/<person>_<clip>/ : original.wav, sarvam.wav, sarvam2.wav, qwen3tts.wav (16 kHz mono) and set.json
with the words and the clone-check score of each file. The game server reads these folders; nothing is made at play time.

Needs: SARVAM_API_KEY in the environment, the Qwen3-TTS worker running (workers/qwen3tts_server.py), and the clone-check model.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import audio  # noqa: E402
import config  # noqa: E402
import engines  # noqa: E402
import scoring  # noqa: E402

ENGINE_ORDER = ["sarvam", "sarvam2", "qwen3tts"]


def transcribe(wav: Path) -> str:
    try:
        import whisper
    except ImportError:
        sys.exit(f"No transcript next to {wav.name} and Whisper is not installed. Put a {wav.stem}.txt next to it, or `pip install openai-whisper`.")
    model = whisper.load_model("small", download_root=str(config.MODELS_DIR / "whisper"))
    return model.transcribe(str(wav), fp16=False, task="transcribe", language="en")["text"].strip()


def words_for(wav: Path) -> str:
    txt = wav.with_suffix(".txt")
    if txt.exists():
        return txt.read_text(encoding="utf-8").strip()
    text = transcribe(wav)
    txt.write_text(text, encoding="utf-8")        # kept, so it can be corrected by hand and the next build uses it
    return text


def load16(path: Path):
    x, sr = audio.read_wav_bytes(path.read_bytes())
    return audio.to_16k(x, sr)


def build_one(person: str, original: Path, args) -> None:
    src = config.STATIC_SOURCES_DIR / person
    ref = src / "reference.wav"
    set_id = f"{person}_{original.stem}"
    out = config.STATIC_SET_DIR / set_id
    done = out / "set.json"
    if done.exists() and not args.force:
        print(f"[skip] {set_id} is already built")
        return
    out.mkdir(parents=True, exist_ok=True)

    ref_seconds = len(load16(ref)) / audio.SR
    if not 5 <= ref_seconds <= 15:
        sys.exit(f"{ref} is {ref_seconds:.1f} s. Sarvam accepts at most 15 s; use 10 to 15 s of speech.")
    ref_text = words_for(ref)
    text = words_for(original)
    print(f"[{set_id}] reference {ref_seconds:.1f} s; the words: {text!r}", flush=True)

    x = load16(original)
    audio.write_wav(out / "original.wav", x)
    files = {"original": {"file": "original.wav", "engine": None, "seconds": round(len(x) / audio.SR, 2)}}
    for name in args.engines.split(","):
        eng = engines.REGISTRY[name]()
        ok, why = eng.available()
        if not ok:
            sys.exit(f"{name} is not ready: {why}")
        raw = out / f"{name}.raw.wav"
        t0 = time.time()
        eng.clone(ref, ref_text, text, raw)
        y, sr = audio.read_wav_bytes(raw.read_bytes())
        y = audio.to_16k(y, sr)
        audio.write_wav(out / f"{name}.wav", y)
        raw.unlink()
        files[name] = {"file": f"{name}.wav", "engine": name, "seconds": round(len(y) / audio.SR, 2)}
        print(f"   {name:9s} {len(y) / audio.SR:5.1f} s of audio, made in {time.time() - t0:.0f} s", flush=True)

    for key, info in files.items():
        info["margin"] = round(scoring.margin(load16(out / info["file"])), 2)
        print(f"   score {key:9s} {info['margin']:6.1f}  {'clone' if info['margin'] < config.CUTOFF else 'real'}", flush=True)

    record = {"id": set_id, "person": person, "name": person.split("-")[0].capitalize(), "text": text,
              "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "original": files.pop("original"),
              "clones": [{**v} for v in files.values()]}
    tmp = out / "set.json.tmp"
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    tmp.replace(done)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--engines", default=",".join(ENGINE_ORDER))
    args = ap.parse_args()
    people = sorted(p for p in config.STATIC_SOURCES_DIR.iterdir() if p.is_dir() and (p / "reference.wav").exists())
    if args.only:
        people = [p for p in people if p.name == args.only]
    if not people:
        sys.exit(f"Nothing to build. Expected {config.STATIC_SOURCES_DIR}/<person>/reference.wav and <person>/originals/*.wav")
    scoring.warm_up()
    for p in people:
        for original in sorted((p / "originals").glob("*.wav")):
            build_one(p.name, original, args)
    print("done")


if __name__ == "__main__":
    main()

# Real or Clone? (demo)

A participant reads one fixed sentence. The demo makes copies of that voice, mixes them with the real recording, and asks the participant to spot the real one. The reward screen shows how the clone check scored each clip.

This is a standalone project. It does not use or modify the voice-banking repositories, except that the clone check reads the Spectra model from a folder you point at.

## Download

```bash
git clone git@github.com:4ryan-s/clone-game-demo.git
cd clone-game-demo
```

You need Python 3.11 or later, and Node.js 20 or later for the React quiz.

## Setup

### Quick path (any laptop)

```bash
python setup.py              # creates the environments and downloads Qwen3-TTS and CosyVoice 2 (about 20 GB)
python setup.py --check      # shows what is installed and what is missing
```

- No NVIDIA GPU: `python setup.py --cpu`. It works but is much slower.
- Mac: Apple Silicon only (PyTorch 2.11 has no Intel-Mac build). Use Python 3.11 or 3.12 (`brew install python@3.12`); the Mac's built-in `python3` is too old. CosyVoice also needs Python 3.10 and a compiler (`xcode-select --install`). Qwen3-TTS runs on the Apple GPU; CosyVoice runs on the CPU and will be slow. Sarvam needs no setup beyond its key, so on a Mac it is the fast path. **None of the Mac path has been run on a real Mac yet.**
- The models are downloaded, not stored in git: Qwen3-TTS from Hugging Face (`Qwen/Qwen3-TTS-12Hz-0.6B-Base`), CosyVoice 2 from Hugging Face (`FunAudioLLM/CosyVoice2-0.5B`), both into `models/`.
- The clone-check model (Spectra-AASIST3, 1.2 GB) is not public. Put it at `models/spectra_aasist3.onnx`, or run `python setup.py --spectra-from <file>`, or set `SPECTRA_URL` (and `SPECTRA_TOKEN` if the link needs one).
- Already have models or environments on this machine? Create `local_config.py` (git ignores it) and set the same names as in `config.py`, for example `HF_HOME`, `QWEN_PYTHON`, `COSYVOICE_PYTHON`, `SPECTRA_ONNX`.
- Start everything: `.\start_demo.ps1` (Windows) or `./start_demo.sh` (Mac/Linux).
- Memory: three engines plus the clone check need about 16 GB of RAM free-ish and 8 GB of video memory. Close browsers and other heavy apps before a live session.

The steps below are the same thing by hand.

### 1. Python API

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`.venv/` is gitignored. `requirements.txt` is the demo API only. The CosyVoice worker keeps its own environment (`config.COSYVOICE_PYTHON`).

Set the Sarvam key in the environment. It is never logged or stored.

```bash
export SARVAM_API_KEY=your-key     # Windows: setx SARVAM_API_KEY "your-key"
```

The clone check no longer needs the banking repo: `spectra_prep.py` holds the input preparation (checked identical to the backend's own, `tests/parity_prepare_wav.py`) and `assets/silero_vad.onnx` the speech detector. Only the Spectra model file is needed (`config.SPECTRA_ONNX`).

Paths in `config.py` default to folders inside the project (`models/`, `.venvs/`, `third_party/`). Local engine workers: CosyVoice at `http://127.0.0.1:8765`, Qwen3-TTS at `http://127.0.0.1:8766`.

`config.SENTENCE`, `config.CONTACT`, and the wording in `consent.py` are still placeholders.

### 2. React quiz (the demo page)

```bash
cd frontend
npm install
npm run build        # the API serves frontend/dist at http://localhost:8000
```

`python setup.py` does this for you. While changing the page, `npm run dev` gives hot reload at http://127.0.0.1:5173 (it proxies `/api` to the API on port 8000).

## Run

```
.\start_demo.ps1            # Windows: starts the engine workers, then the API and the quiz at http://localhost:8000
.\start_demo.ps1 -Debug     # same, plus the developer file fetch route
./start_demo.sh             # Mac/Linux
```

Open http://localhost:8000 . Use a browser on the same computer: browsers only allow the microphone on localhost or https.
The first plain-HTML page is still served at http://localhost:8000/classic as a fallback.

End-to-end API check, with the server already running:

```bash
python tests/smoke_api.py path/to/a-reference.wav
```

## What the quiz does

Consent, then record the sentence (raw, 16 kHz mono), then a quality check. Sarvam, CosyVoice 2 and Qwen3-TTS make copies at the same time. The cards are shuffled: play, pick, win or lose, then the clone-check score for each voice.

Cards = 1 real + one per engine. Three engines (Sarvam, CosyVoice 2, Qwen3-TTS), so 4 cards.

## Layout

- `config.py` sentence, limits, which engines run, URLs. Everything that changes on demo day.
- `consent.py` consent wording (DRAFT, needs sign-off) and its version, stored with every session.
- `server.py` API, the built React quiz at `/` and the original static page at `/classic`. `pipeline.py` runs the engines at the same time.
- `requirements.txt` Python packages for that API.
- `frontend/` React quiz (Vite, Tailwind). Light mode, full desktop.
- `engines/` one file per cloning engine. To add one: new file, add to `REGISTRY` in `engines/__init__.py`, add its name to `config.ENGINES`.
- `workers/cosyvoice_server.py` and `workers/qwen3tts_server.py` keep the local models loaded on the GPU, each in its own environment under `.venvs/`.
- `setup.py` one-command setup and download of the models. `local_config.py` (not in git) overrides paths on one machine.
- `static/` the original page (plain HTML, CSS and JS, no build step).
- `data/sessions/<id>/` per participant: `consent.json`, `original.wav`, `raw/` (engine output untouched), `clones/` (16 kHz), `meta.json`.

## Data and consent rules built in

- The required box is needed to start; keeping the data for training is a separate box, off by default.
- No retention consent: everything is deleted on Finish, or purged when the server starts if older than 24 h.
- Delete on request: `DELETE /api/sessions/<code>`.
- The browser only sees neutral slot ids (`c1`, `c2`). Which engine made which clip is in `meta.json` and is not sent before the pick.
- Placeholders to settle: the final sentence (`config.SENTENCE`), the contact for deletion (`config.CONTACT`), and sign-off on `consent.py`.

## Known limits

- One participant at a time on the GPU worker (a second queues).
- Raw capture turns the browser's noise suppression, echo cancellation and auto gain off, so a noisy room is audible in the clip.
- Not yet tried from a fresh machine: `setup.py` was checked with `--check` and `--dry-run` only. The CosyVoice install is the most fragile part (needs Python 3.10).

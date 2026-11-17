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

Before a real session, point these paths in `config.py` at this machine:

- `SPECTRA_BACKEND` — voice-banking backend folder that contains `model/spectra_aasist3.onnx` and `voiceprint.utils.pad_scorer`. The server only reads it.
- `COSYVOICE_PYTHON` — Python executable of the existing CosyVoice environment.
- `COSYVOICE_URL` — local worker, default `http://127.0.0.1:8765`.

`config.SENTENCE`, `config.CONTACT`, and the wording in `consent.py` are still placeholders.

### 2. React quiz

```bash
cd frontend
npm install
```

The dev server proxies `/api` to `http://127.0.0.1:8000`. The page cannot load the quiz until the API is running.

## Run

Two terminals.

```bash
# API, from the project root, with .venv active
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

```bash
# Quiz
cd frontend
npm run dev
```

Open http://127.0.0.1:5173 . Use a browser on the same computer: browsers only allow the microphone on localhost or https.

On the Windows demo machine, `start_demo.ps1` starts the CosyVoice worker and then the API:

```
.\start_demo.ps1            # http://localhost:8000
.\start_demo.ps1 -Debug     # same, plus ?dev=1 to fetch generated files
```

The API also serves the original page from `static/` at http://127.0.0.1:8000 . The React app is the full-desktop quiz.

End-to-end API check, with the server already running:

```bash
python tests/smoke_api.py path/to/a-reference.wav
```

## What the quiz does

Consent, then record the sentence (raw, 16 kHz mono), then a quality check. Sarvam and CosyVoice 2 make copies at the same time. The cards are shuffled: play, pick, win or lose, then the clone-check score for each voice.

Cards = 1 real + one per engine. Two engines now, so 3 cards. A third engine adds the 4th card.

## Layout

- `config.py` sentence, limits, which engines run, URLs. Everything that changes on demo day.
- `consent.py` consent wording (DRAFT, needs sign-off) and its version, stored with every session.
- `server.py` API and the original static page. `pipeline.py` runs the engines at the same time.
- `requirements.txt` Python packages for that API.
- `frontend/` React quiz (Vite, Tailwind). Light mode, full desktop.
- `engines/` one file per cloning engine. To add one: new file, add to `REGISTRY` in `engines/__init__.py`, add its name to `config.ENGINES`.
- `workers/cosyvoice_server.py` keeps CosyVoice loaded on the GPU. Runs in the existing CosyVoice venv.
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
- The clone check and CosyVoice paths in `config.py` are still the Windows demo-machine paths until you change them.

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
python setup.py              # creates the environments and downloads Qwen3-TTS and the clone-check model (about 8 GB)
python setup.py --check      # shows what is installed and what is missing
```

- No NVIDIA GPU: `python setup.py --cpu`. It works but is much slower.
- Mac: Apple Silicon only (PyTorch 2.11 has no Intel-Mac build). Python 3.11 or later is enough, including 3.14; Qwen3-TTS uses the same interpreter that runs `setup.py`. Qwen3-TTS runs on the Apple GPU. Sarvam needs no setup beyond its key, so on a Mac it is the fast path. **None of the Mac path has been run on a real Mac yet.**
- The models are downloaded, not stored in git: Qwen3-TTS from Hugging Face (`Qwen/Qwen3-TTS-12Hz-0.6B-Base`), the clone-check model from Hugging Face (below), both into `models/`.
- The clone-check model (Spectra-AASIST3, 1.2 GB, Apache-2.0) is downloaded from Hugging Face (`lab260/Spectra-AASIST3`) into `models/spectra_aasist3.onnx` and checked against its published checksum. Use `--spectra-from <file>` or `SPECTRA_URL` to supply your own copy.
- Already have models or environments on this machine? Create `local_config.py` (git ignores it) and set the same names as in `config.py`, for example `HF_HOME`, `QWEN_PYTHON`, `SPECTRA_ONNX`.
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

`.venv/` is gitignored. `requirements.txt` is the demo API only. The Qwen3-TTS worker keeps its own environment (`config.QWEN_PYTHON`).

Set the Sarvam key in the environment. It is never logged or stored.

```bash
export SARVAM_API_KEY=your-key     # Windows: setx SARVAM_API_KEY "your-key"
```

The clone check no longer needs the banking repo: `spectra_prep.py` holds the input preparation (checked identical to the backend's own, `tests/parity_prepare_wav.py`) and `assets/silero_vad.onnx` the speech detector. Only the Spectra model file is needed (`config.SPECTRA_ONNX`).

Paths in `config.py` default to folders inside the project (`models/`, `.venvs/`). The Qwen3-TTS worker listens at `http://127.0.0.1:8766`.

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

Consent, then record the sentence (raw, 16 kHz mono), then a quality check. Sarvam (twice, with different settings) and Qwen3-TTS make copies at the same time. The cards are shuffled: play, pick, win or lose, then the clone-check score for each voice.

Cards = 1 real + one per engine. Three engines (Sarvam, Sarvam with other settings, Qwen3-TTS), so 4 cards.

## Layout

- `config.py` sentence, limits, which engines run, URLs. Everything that changes on demo day.
- `consent.py` consent wording (DRAFT, needs sign-off) and its version, stored with every session.
- `server.py` API, the built React quiz at `/` and the original static page at `/classic`. `pipeline.py` runs the engines at the same time.
- `requirements.txt` Python packages for that API.
- `frontend/` React quiz (Vite, Tailwind). Light mode, full desktop.
- `engines/` one file per cloning engine. To add one: new file, add to `REGISTRY` in `engines/__init__.py`, add its name to `config.ENGINES`.
- `workers/qwen3tts_server.py` keeps Qwen3-TTS loaded on the GPU, in its own environment under `.venvs/qwen`.
- `setup.py` one-command setup and download of the models. `local_config.py` (not in git) overrides paths on one machine.
- `static/` the original page (plain HTML, CSS and JS, no build step).
- `data/sessions/<id>/` working data of one play-through: `consent.json`, `original.wav`, `raw/`, `clones/` (16 kHz), `meta.json`. Always deleted when the session ends.
- `data/voice_samples/` the recordings kept with consent: `000000.wav`, `000001.wav`, ... and `index.csv` (see `voicebank.py`). Inside the repo folder, but `data/` is git-ignored, so recordings are never committed or pushed.

## Data and consent rules built in

- The required box is needed to start; keeping the recording for training is a separate box, off by default.
- Keep-my-recording ticked: as soon as the recording passes the quality check it is copied to `data/voice_samples/` under the next number (starting at 0). `index.csv` holds the number, session code, times, consent wording version, length and checksum. Recording again replaces the file under the same number. Only the original recording is kept: the clones are not.
- Not ticked: nothing is copied anywhere. The working recording is deleted on Finish.
- Unfinished sessions (tab closed): the working folder is removed when the server starts if older than 24 h. A consenting participant's recording is already in the voice bank by then.
- Delete on request: `DELETE /api/sessions/<code>` (works after Finish too) removes the saved recording and marks its index row `deleted`; the number is never reused. For the host: `python voicebank.py delete <code>` and `python voicebank.py list`.
- The browser only sees neutral slot ids (`c1`, `c2`). Which engine made which clip is in `meta.json` and is not sent before the pick.
- Placeholders to settle: the final sentence (`config.SENTENCE`), the contact for deletion (`config.CONTACT`), and sign-off on `consent.py`.

## Concurrency and batching

Several people can generate clones at the same time. Sarvam is a cloud service and takes them in parallel. The local Qwen3-TTS worker runs **one model on one GPU** and serves them by **micro-batching** (`workers/batcher.py`):

1. Every request waits in a queue.
2. The first request opens a short window (`QWEN_BATCH_WINDOW_S`, default 2 s). Requests arriving inside the window join it, up to `QWEN_MAX_BATCH` (default 4).
3. The whole batch goes through the model in one call. On a GPU, generating one clip leaves most of the card idle, so four clips in one batch take about as long as one. Each person gets back their own clip, made from their own voice.
4. A request that arrives while a batch is running waits for it to finish and goes into the next batch.

Measured on an RTX 4060 laptop (on battery, so slow): four different voices at once took 40 s for all four, the same as one clip; one at a time they would have taken about 140 s. Six at once ran as a batch of four and a batch of two (77 s). A batch of four used about 3.9 GB of video memory on top of the 2.7 GB model. `/health` always answers, also while generating (it reports the batching counters).

Trade-offs: a lone person waits up to the window longer; a longer window catches people who finish a few seconds apart but delays everyone a little more. A batch is not extended once it has started (true continuous batching, for example with vLLM, would remove that wait). Raise `QWEN_MAX_BATCH` only if the GPU has the memory. The server no longer holds a per-engine lock, since that would stop people sharing a batch.

Checks: `python tests/test_batcher.py` (no GPU, fake model) and `python tests/qwen_worker_live.py` (needs the running worker and a GPU).

## Known limits

- Qwen3-TTS batches people who finish recording close together (see Concurrency). Someone who arrives just after a batch has started waits for it to finish, then runs in the next one, so their wait can be about twice as long.
- Raw capture turns the browser's noise suppression, echo cancellation and auto gain off, so a noisy room is audible in the clip.
- Not yet tried from a fresh machine: `setup.py` was checked with `--check` and `--dry-run` only.

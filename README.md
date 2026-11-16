# Real or Clone? (demo)

A participant reads one fixed sentence. We make copies of their voice with several cloning systems, mix them with
their real recording, and (next phase) they try to spot the real one, then see how our clone check scores each clip.

This is a standalone project. It does not use or modify the voice-banking repositories.

## Built so far
consent page -> record the sentence (raw, 16 kHz mono) -> quality check -> clones from Sarvam and CosyVoice 2 in parallel -> shuffled cards (play, pick) -> win or lose -> reveal with the clone-check score per voice.

Cards = 1 real + one per engine. Two engines now, so 3 cards. A third engine adds the 4th card.
Not done yet: final sentence, third engine, consent sign-off, browser test.

The clone check (`scoring.py`) reads the Spectra model and `prepare_wav` from the voice-banking backend folder by path (`config.SPECTRA_BACKEND`). Nothing from it is copied into this repo.

## Run
```
.\start_demo.ps1            # starts the CosyVoice worker window, then the server at http://localhost:8000
.\start_demo.ps1 -Debug     # same, plus ?dev=1 to listen to the generated files
python tests\smoke_api.py D:\clone_detection_tests\data\refs\aryan_app.wav     # end-to-end API check, server must be running
```
`SARVAM_API_KEY` must be set in the environment or in the Windows user variables. It is never logged or stored.
Use a browser on the same computer (`localhost`): browsers only allow the microphone on localhost or https.

## Layout
- `config.py` sentence, limits, which engines run, URLs. Everything that changes on demo day.
- `consent.py` consent wording (DRAFT, needs sign-off) and its version, stored with every session.
- `server.py` API and static page. `pipeline.py` runs the engines at the same time.
- `engines/` one file per cloning engine. To add one: new file, add to `REGISTRY` in `engines/__init__.py`, add its name to `config.ENGINES`.
- `workers/cosyvoice_server.py` keeps CosyVoice loaded on the GPU. Runs in the existing cosyvoice venv.
- `static/` the page (plain HTML, CSS and JS, no build step).
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

"""The static game: rounds built from sets that were made ahead of time (tools/build_static_set.py).

A set is one real clip plus its clones, all saying the same words, with a clone-check score for each file. A round picks a
random set, shuffles its clips into cards with random ids, and keeps the answer on the server until the participant picks.
Nothing is generated or scored at play time, so the server needs no GPU, no cloning engine and no clone-check model.
Rounds live in memory only; a restart simply starts new ones."""
import json
import random
import secrets
import threading
import time

import config
import game

_lock = threading.Lock()
_rounds: dict[str, dict] = {}
_last_set: str | None = None
ROUND_TTL_S = 3 * 3600


def load_sets() -> list[dict]:
    """Every finished set folder. Read each time a round starts, so a new set built while the server runs shows up."""
    out = []
    root = config.STATIC_SET_DIR
    if not root.is_dir():
        return out
    for f in sorted(root.glob("*/set.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
            rec["dir"] = f.parent
            out.append(rec)
        except (OSError, ValueError):
            continue
    return out


def summary() -> dict:
    sets = load_sets()
    return {"sets": len(sets), "people": sorted({s["name"] for s in sets})}


def _purge() -> None:
    cutoff = time.time() - ROUND_TTL_S
    for rid in [k for k, v in _rounds.items() if v["at"] < cutoff]:
        del _rounds[rid]


def start_round() -> dict:
    """Pick a random set (not the same one twice in a row when there is a choice) and shuffle its clips into cards."""
    global _last_set
    sets = load_sets()
    if not sets:
        raise LookupError("No voices have been built yet. Run tools/build_static_set.py first.")
    with _lock:
        pool = [s for s in sets if s["id"] != _last_set] or sets
        chosen = random.SystemRandom().choice(pool)
        _last_set = chosen["id"]
        cards = [{"id": secrets.token_urlsafe(6), "real": True, "who": chosen["name"], "file": chosen["dir"] / chosen["original"]["file"],
                  "margin": chosen["original"]["margin"], "seconds": chosen["original"]["seconds"]}]
        for c in chosen["clones"]:
            cards.append({"id": secrets.token_urlsafe(6), "real": False, "who": config.ENGINE_LABELS.get(c["engine"], c["engine"]),
                          "file": chosen["dir"] / c["file"], "margin": c["margin"], "seconds": c["seconds"]})
        random.SystemRandom().shuffle(cards)
        rid = secrets.token_urlsafe(9)
        _purge()
        _rounds[rid] = {"at": time.time(), "set": chosen["id"], "name": chosen["name"], "text": chosen["text"], "cards": cards, "pick": None}
    return {"round_id": rid, "cards": [c["id"] for c in cards], "name": chosen["name"], "text": chosen["text"]}


def find_card(rid: str, card_id: str) -> dict | None:
    r = _rounds.get(rid)
    return next((c for c in r["cards"] if c["id"] == card_id), None) if r else None


def playback_wav(rid: str, card_id: str) -> bytes | None:
    c = find_card(rid, card_id)
    return game.playback_from_file(c["file"]) if c else None


def pick(rid: str, card_id: str) -> dict | None:
    """Record the pick (the first one stands) and reveal every card with its clone-check score. None if the round or card is unknown."""
    with _lock:
        r = _rounds.get(rid)
        if not r or not find_card(rid, card_id):
            return None
        if r["pick"] is None:
            r["pick"] = card_id
        picked = r["pick"]
    cards = [{"card": c["id"], "real": c["real"], "who": c["who"], "margin": round(c["margin"], 1),
              "says_clone": c["margin"] < config.CUTOFF, "seconds": c["seconds"]} for c in r["cards"]]
    return {"won": next(c for c in cards if c["card"] == picked)["real"], "picked": picked, "cutoff": config.CUTOFF,
            "name": r["name"], "text": r["text"], "cards": cards}

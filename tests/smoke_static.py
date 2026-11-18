"""End-to-end check of the static game against a running server (STATIC_MODE on, at least one set built).
    python tests/smoke_static.py [base_url]"""
import io
import sys

import requests
import soundfile as sf

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


cfg = requests.get(base + "/api/config").json()
check(cfg["static"] and cfg["static_sets"] >= 1, f"static mode on, {cfg['static_sets']} set(s) built")
health = requests.get(base + "/api/health").json()["static_set"]
check(health["ready"], f"health: {health['sets']} sets for {health['people']}")

seen_people, won = set(), 0
for i in range(12):
    r = requests.post(base + "/api/static/rounds")
    rd = r.json()
    cards = rd["cards"]
    if i == 0:
        check(r.status_code == 200, "round started")
        check(len(cards) == 4 and len(set(cards)) == 4, "four distinct card ids")
        check(set(rd) == {"round_id", "cards", "name", "text"}, "round response shows only name, words and neutral card ids")
        text = str(rd).lower()
        check(not any(w in text for w in ("sarvam", "qwen", "clone", "real")), "nothing in the round response says which card is real")
        lens = []
        for c in cards:
            a = requests.get(f"{base}/api/rounds/{rd['round_id']}/cards/{c}.wav")
            y, sr = sf.read(io.BytesIO(a.content), dtype="float32")
            lens.append((a.status_code, sr, round(len(y) / sr, 1)))
        check(all(s == 200 and sr == 16000 for s, sr, _ in lens), f"all four cards play as 16 kHz wav, lengths {[l for _, _, l in lens]}")
        check(requests.get(f"{base}/api/rounds/{rd['round_id']}/cards/nope.wav").status_code == 404, "unknown card is 404")
        check(requests.post(f"{base}/api/rounds/nope/pick", json={"card": cards[0]}).status_code == 404, "unknown round is 404")
    res = requests.post(f"{base}/api/rounds/{rd['round_id']}/pick", json={"card": cards[0]}).json()
    if i == 0:
        check(sum(c["real"] for c in res["cards"]) == 1 and len(res["cards"]) == 4, "reveal: exactly one real card of four")
        who = sorted(c["who"] for c in res["cards"] if not c["real"])
        check(len(who) == 3, f"reveal names the clones: {who}")
        check(all("margin" in c and "says_clone" in c for c in res["cards"]), "every card has a clone-check score")
        again = requests.post(f"{base}/api/rounds/{rd['round_id']}/pick", json={"card": cards[1]}).json()
        check(again["picked"] == res["picked"], "the first pick stands")
    seen_people.add(rd["name"])
    won += res["won"]
print(f"12 rounds: people seen {sorted(seen_people)}, won {won} (picking card 1 each time)")
check(len(seen_people) >= min(2, cfg["static_sets"]) or cfg["static_sets"] == 1, "random choice reaches more than one person")
print("ALL PASSED")

"""Generalised scorebug goal detection from OCR raw text (see 12_metrics.moments_2022).
Usage: python goals_gen.py <tag> <HOME> <AWAY>   -> prints goals and writes evidence/audit/<tag>_moments.csv"""
import csv, json, re, sys
from common import EVIDENCE
tag, H, A = sys.argv[1:4]
o = json.load(open(EVIDENCE / f"ocr_{tag}.json"))
W, Hh = o["frame_size"]
rx = re.compile(rf"{H}\W{{0,3}}(\d)\W{{0,4}}(\d)\W{{0,3}}{A}")
obs = {}
for t, raws in o["raw"].items():
    seen = [r for r in raws if r[2][1] < 0.12 * Hh and r[2][0] < 0.6 * W and r[3] == "full"]
    seen.sort(key=lambda r: r[2][0])
    txt = " ".join(r[0] for r in seen).upper().replace("O", "0").replace("0K", "0 K")
    m = rx.search(txt.replace("0R", "OR"))  # tolerate KOR -> K0R
    if m:
        obs[int(t)] = (int(m.group(1)), int(m.group(2)))
ts = sorted(obs)
goals, cur, run = [], (0, 0), []
for t in ts:
    s = obs[t]
    if s == cur:
        run = []
        continue
    if run and run[-1][1] == s:
        run.append((t, s))
    else:
        run = [(t, s)]
    if len(run) >= 3 and sum(s) == sum(cur) + 1 and s[0] >= cur[0] and s[1] >= cur[1]:
        goals.append((run[0][0], s))
        cur = s
        run = []
print(tag, "score observations", len(obs), "goals", goals)
rows = [{"label": f"Goal {a}-{b}", "start": max(0, t - 15), "end": t + 30, "t_first_seen": t} for t, (a, b) in goals]
print(rows)
json.dump(rows, open(EVIDENCE / f"goals_{tag}.json", "w"), indent=1)

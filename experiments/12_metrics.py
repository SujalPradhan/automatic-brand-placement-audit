"""Exposure metrics for one video from audited, fused per-second presence.

Usage: python 12_metrics.py <tag>

Definitions (1 frame sampled per second, so every duration is +/- 1 s per appearance boundary):
  visible_s        seconds in which the brand was detected (and survived the audit)
  appearances      runs of detected seconds; gaps of <= 1 missed sample are merged
  legible_s        seconds where the brand's largest detected mark is at least LEGIBLE_H of frame height
  mean_area_pct    mean share of the frame covered by the brand's detected marks, over its visible seconds
  key_moment_s     visible seconds inside goal windows: evidence/audit/<tag>_moments.csv if present, else (2022
                   final) derived from the score graphic, plus the shootout
  share_*_pct      the brand's seconds as a share of all sponsors' seconds (brand-seconds), so shares sum to 100
"""
import csv
import json
import re
import sys

from common import BRAND_INFO, EVIDENCE
from presence import VIDEO, presence, runs

TAG = sys.argv[1]
LEGIBLE_H = 0.025  # ~27 px at 1080p, ~18 px at 720p: wordmark readable at broadcast size
dur = VIDEO[TAG]["duration"]
ocr = json.loads((EVIDENCE / f"ocr_{TAG}.json").read_text())


def texts(t):
    return [x[0] for x in ocr["raw"].get(str(t), [])]


def moments_2022():
    """Goal = score graphic changes (ARG a-b FRA); window = 15 s before to 30 s after (goal, celebration, replays)."""
    seen, prev, changes = {}, None, []
    for t in range(dur):
        for s in texts(t):
            m = re.search(r"ARG\W*(\d)\W+(\d)\W*FRA", s.upper().replace("O", "0"))
            if m:
                seen[t] = (int(m.group(1)), int(m.group(2)))
    for t, s in sorted(seen.items()):
        if prev and s != prev and sum(s) == sum(prev) + 1:
            changes.append((t, s))
        if not prev or sum(s) >= sum(prev):
            prev = s
    ms = [{"label": f"Goal {a}-{b}", "start": max(0, t - 15), "end": t + 30} for t, (a, b) in changes]
    shoot = [t for t in range(dur) if any("PENALTY" in s.upper() and "SH" in s.upper() for s in texts(t))]
    if shoot:
        ms.append({"label": "Penalty shootout", "start": min(shoot) - 5, "end": dur})
    return ms


def moments_csv():
    """Hand-marked from the footage: evidence/audit/<tag>_moments.csv (label,start,end)."""
    return [{"label": r["label"], "start": int(r["start"]), "end": int(r["end"])}
            for r in csv.DictReader((EVIDENCE / "audit" / f"{TAG}_moments.csv").open())]


# Hand-marked windows whenever the CSV exists; otherwise the 2022 final's score-graphic detection.
moments = moments_csv() if (EVIDENCE / "audit" / f"{TAG}_moments.csv").exists() else moments_2022()
for a, b in zip(moments, moments[1:]):
    a["end"] = min(a["end"], b["start"])
in_moment = {t for m in moments for t in range(m["start"], m["end"])}

P = presence(TAG)
brands = {}
for b, d in P.items():
    ts = sorted(t for t in d if t < dur)
    if not ts:
        continue
    r = runs(ts)
    brands[b] = {
        "name": BRAND_INFO[b][0], "country": BRAND_INFO[b][1],
        "visible_s": len(ts), "appearances": len(r),
        "legible_s": sum(1 for t in ts if d[t]["h"] >= LEGIBLE_H),
        "mean_area_pct": round(100 * sum(d[t]["area"] for t in ts) / len(ts), 3),
        "key_moment_s": sum(1 for t in ts if t in in_moment),
        "timeline": [[t, int(d[t]["h"] >= LEGIBLE_H)] for t in ts],
    }
tot = sum(v["visible_s"] for v in brands.values())
tot_leg = sum(v["legible_s"] for v in brands.values())
tot_km = sum(v["key_moment_s"] for v in brands.values())
for v in brands.values():
    v["share_visible_pct"] = round(100 * v["visible_s"] / tot, 1)
    v["share_legible_pct"] = round(100 * v["legible_s"] / tot_leg, 1) if tot_leg else 0
    v["share_key_moment_pct"] = round(100 * v["key_moment_s"] / tot_km, 1) if tot_km else 0
    v["legible_ratio"] = round(v["legible_s"] / v["visible_s"], 2)

seconds_with_any = len({t for d in P.values() for t in d if t < dur})
out = {"tag": TAG, **VIDEO[TAG], "moments": moments, "key_moment_seconds": len(in_moment),
       "seconds_with_any_sponsor": seconds_with_any, "brand_seconds": tot, "legible_h": LEGIBLE_H,
       "brands": dict(sorted(brands.items(), key=lambda x: -x[1]["visible_s"]))}
(EVIDENCE / f"metrics_{TAG}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(TAG, "moments:", [(m["label"], m["start"], m["end"]) for m in moments])
print(f"seconds with any sponsor {seconds_with_any}/{dur}, brand-seconds {tot}")
for b, v in out["brands"].items():
    print(f'{v["name"]:18s} {v["country"]:12s} vis={v["visible_s"]:4d} app={v["appearances"]:3d} '
          f'leg={v["legible_s"]:4d} ({v["legible_ratio"]:.2f}) share={v["share_visible_pct"]:5.1f}% '
          f'km={v["key_moment_s"]:3d} ({v["share_key_moment_pct"]:5.1f}%)')

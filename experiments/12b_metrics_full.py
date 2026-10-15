"""Full-match exposure metrics (same definitions as 12_metrics.py), restricted to live play.
Usage: python 12b_metrics_full.py <tag>      writes evidence/metrics_<tag>.json
Live play = segments of kind live_play in evidence/audit/<tag>_segments.csv (replays sit inside them).
Goal windows: evidence/goals_<tag>.json (score-bug OCR; 15 s before to 30 s after the first frame showing the new score).
"""
import csv, json, sys
from common import BRAND_INFO, EVIDENCE, TIERS, TIER_SET
from presence import FULL, presence, runs

TAG = sys.argv[1]
LEGIBLE_H = 0.025
segs = list(csv.DictReader((EVIDENCE / "audit" / f"{TAG}_segments.csv").open()))
live = {t for s in segs if s["kind"] == "live_play" for t in range(int(s["start_s"]), int(s["end_s"]))}
goals = json.loads((EVIDENCE / f"goals_{TAG}.json").read_text())
moments = [{"label": g["label"], "start": g["start"], "end": g["end"]} for g in goals]
for a, b in zip(moments, moments[1:]):
    a["end"] = min(a["end"], b["start"])
in_moment = {t for m in moments for t in range(m["start"], m["end"])} & live
tiers = TIERS[TIER_SET[TAG]]
tier = lambda b: next((k for k, v in tiers.items() if b in v), "Other")
P = presence(TAG)
allp = presence(TAG, audited=False)
brands = {}
for b, d in P.items():
    ts_all = sorted(d)
    ts = [t for t in ts_all if t in live]
    if not ts and not ts_all:
        continue
    info = BRAND_INFO.get(b, (b, "?"))
    brands[b] = {"name": info[0], "country": info[1], "tier": tier(b), "visible_s_all": len(ts_all),
                 "visible_s": len(ts), "appearances": len(runs(ts)),
                 "legible_s": sum(1 for t in ts if d[t]["h"] >= LEGIBLE_H),
                 "key_moment_s": sum(1 for t in ts if t in in_moment),
                 "mean_area_pct": round(100 * sum(d[t]["area"] for t in ts) / len(ts), 3) if ts else 0}
tot = sum(v["visible_s"] for v in brands.values())
tkm = sum(v["key_moment_s"] for v in brands.values())
tiersum = {}
for v in brands.values():
    v["share_visible_pct"] = round(100 * v["visible_s"] / tot, 1) if tot else 0
    v["share_key_moment_pct"] = round(100 * v["key_moment_s"] / tkm, 1) if tkm else 0
    x = tiersum.setdefault(v["tier"], [0, 0]); x[0] += v["visible_s"]; x[1] += v["key_moment_s"]
seg_s = {}
for s in segs:
    seg_s[s["kind"]] = seg_s.get(s["kind"], 0) + int(s["end_s"]) - int(s["start_s"])
out = {"tag": TAG, **FULL[TAG], "segment_seconds": seg_s, "live_play_s": len(live), "moments": moments,
       "key_moment_live_s": len(in_moment), "brand_seconds_live": tot,
       "seconds_with_any_sponsor_live": len({t for d in P.values() for t in d if t in live}),
       "seconds_with_any_sponsor_nonlive": len({t for d in P.values() for t in d if t not in live}),
       "tier_share": {k: {"live_s": v[0], "share_pct": round(100 * v[0] / tot, 1) if tot else 0,
                          "goal_window_s": v[1], "goal_share_pct": round(100 * v[1] / tkm, 1) if tkm else 0}
                      for k, v in tiersum.items()},
       "brands": dict(sorted(brands.items(), key=lambda x: -x[1]["visible_s"]))}
(EVIDENCE / f"metrics_{TAG}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(TAG, "live_s", len(live), "any-sponsor live s", out["seconds_with_any_sponsor_live"], "brand-seconds", tot, "goal-window brand-s", tkm)
print({k: (v["live_s"], v["share_pct"], v["goal_share_pct"]) for k, v in out["tier_share"].items()})
for b, v in list(out["brands"].items())[:14]:
    print(f'{v["name"]:16s} {v["tier"]:9s} live_s={v["visible_s"]:5d} app={v["appearances"]:4d} leg={v["legible_s"]:5d} km={v["key_moment_s"]:4d} share={v["share_visible_pct"]}')

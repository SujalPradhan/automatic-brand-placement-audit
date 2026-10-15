"""Write the site's data files from the evidence (every number on the pages comes from these).

story/benchmark.json      accuracy, cost, speed, cross-game tier and origin shares (landing page)
story/game-<tag>.json     per-game metrics, tiers, goal windows with per-brand seconds, timelines
"""
import json

from common import EVIDENCE, ROOT, tier_of
from presence import VIDEO

STORY = ROOT / "story"
scores = json.loads((EVIDENCE / "scores.json").read_text())
ee = json.loads((EVIDENCE / "ee_scores.json").read_text())
usage = json.loads((EVIDENCE / "gcp_usage.json").read_text())

games = {}
for tag in VIDEO:
    m = json.loads((EVIDENCE / f"metrics_{tag}.json").read_text())
    B = m["brands"]
    for b, v in B.items():
        v["tier"] = tier_of(tag, b)
    for mo in m["moments"]:
        rng = set(range(mo["start"], mo["end"]))
        mo["brands"] = sorted([[v["name"], v["tier"], len(rng & {t for t, _ in v["timeline"]})] for v in B.values()
                               if rng & {t for t, _ in v["timeline"]}], key=lambda x: -x[2])
    tot = sum(v["visible_s"] for v in B.values())
    tkm = sum(v["key_moment_s"] for v in B.values())
    tiers = {}
    for v in B.values():
        a = tiers.setdefault(v["tier"], {"brands": 0, "visible_s": 0, "key_moment_s": 0})
        a["brands"] += 1
        a["visible_s"] += v["visible_s"]
        a["key_moment_s"] += v["key_moment_s"]
    for a in tiers.values():
        a["share_visible_pct"] = round(100 * a["visible_s"] / tot, 1)
        a["share_key_moment_pct"] = round(100 * a["key_moment_s"] / tkm, 1)
    cn = [v for v in B.values() if v["country"] == "China"]
    m["tiers"] = tiers
    m["china"] = {"brands": [v["name"] for v in cn],
                  "share_visible_pct": round(100 * sum(v["visible_s"] for v in cn) / tot, 1),
                  "share_key_moment_pct": round(100 * sum(v["key_moment_s"] for v in cn) / tkm, 1)}
    m["key_moment_brand_seconds"] = tkm
    m["ocr_sec_per_frame"] = json.loads((EVIDENCE / f"ocr_{tag}.json").read_text())["sec_per_frame_mean"]
    m["accuracy"] = scores.get(tag)
    games[tag] = m
    (STORY / f"game-{tag}.json").write_text(json.dumps(m, ensure_ascii=False))

loc = ee["class_agnostic"]
for tag in scores:
    scores[tag]["short"] = VIDEO[tag]["short"]  # labels for the accuracy table
bench = {
    "scores": scores, "gcp_usage": usage,
    "games": {tag: {"label": g["label"], "short": g["short"], "duration": g["duration"], "tiers": g["tiers"],
                    "china": g["china"], "brand_seconds": g["brand_seconds"],
                    "seconds_with_any_sponsor": g["seconds_with_any_sponsor"],
                    "ocr_sec_per_frame": g["ocr_sec_per_frame"], "n_brands": len(g["brands"])}
              for tag, g in games.items()},
    "dropped": {"cloud_vision_recall": loc["cloud_vision"]["iou50"]["recall"],
                "owlv2_recall": loc["owlv2"]["iou50"]["recall"], "owlv2_precision": loc["owlv2"]["iou50"]["precision"],
                "ee_gt_boxes": ee["gt_boxes"]},
}
(STORY / "benchmark.json").write_text(json.dumps(bench, ensure_ascii=False, indent=1))
for tag, g in games.items():
    print(tag, {k: (v["share_visible_pct"], v["share_key_moment_pct"]) for k, v in g["tiers"].items()}, g["china"])

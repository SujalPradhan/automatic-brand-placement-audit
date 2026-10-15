"""Exposure metrics for the WC final from per-second detections.

Usage: python 12_wc_metrics.py <source>   (source: ocr | vi | fused = union of both)

Definitions (sampling = 1 frame per second, so every figure is +/- 1 s per appearance boundary):
  visible_s        seconds in which the brand is detected
  appearances      runs of detected seconds, merging gaps of <= MERGE_GAP missed samples; min length 1 sample
  share_visible    mean fraction of the frame covered by the brand's boxes, over seconds where visible
  share_seconds    sum over seconds of covered fraction (prominence-weighted exposure, "full-screen seconds")
  key_moment_s     visible seconds inside goal / shootout windows
"""
import json
import re
import sys

from common import EVIDENCE, VI_ALIASES, norm_brand

SRC = sys.argv[1] if len(sys.argv) > 1 else "ocr"
MERGE_GAP = 1
FRAME_AREA = 1920 * 1080
DURATION = 716

ocr = json.loads((EVIDENCE / "wc_ocr.json").read_text())


# ---- key moments from the on-screen score bug (read by OCR) ----
def score_of(text):
    t = text.upper().replace("O", "0")
    m = re.search(r"ARG\W*(\d)\W+(\d)\W*FRA", t)
    return (int(m.group(1)), int(m.group(2))) if m else None


scores = {}
for t, items in ocr["raw"].items():
    for text, _, _ in items:
        s = score_of(text)
        if s:
            scores[int(t)] = s
timeline = sorted(scores.items())
changes, prev = [], None
for t, s in timeline:
    if prev and s != prev and sum(s) == sum(prev) + 1:
        changes.append((t, s))
    if not prev or sum(s) >= sum(prev):
        prev = s
# The score bug updates a few seconds after the ball goes in; highlight edits then show celebrations and replays.
# Checked by eye on the 3-2 goal: shot ~546 s, bug updates 558 s, replays until ~588 s.
# So a goal window = [change - 15 s, change + 30 s], cut short where the next window starts.
moments = [{"label": f"Goal {s[0]}-{s[1]}", "start": max(0, t - 15), "end": t + 30} for t, s in changes]
shoot = [int(t) for t, items in ocr["raw"].items() if any("PENALTY" in x[0].upper() and "SH" in x[0].upper() for x in items)]
if shoot:
    moments.append({"label": "Penalty shootout", "start": min(shoot) - 5, "end": DURATION})
for a, b in zip(moments, moments[1:]):
    a["end"] = min(a["end"], b["start"])
in_moment = {t for m in moments for t in range(m["start"], m["end"])}

# ---- per-second brand presence and covered area ----
pres = {}  # brand -> {t: area_fraction}


def add(b, t, a):
    pres.setdefault(b, {})[t] = max(pres.get(b, {}).get(t, 0), min(a, 1.0))


if SRC in ("ocr", "fused"):
    for t, d in ocr["per_second"].items():
        for b, boxes in d.items():
            add(b, int(t), sum((x[2] - x[0]) * (x[3] - x[1]) for x in boxes) / FRAME_AREA)
if SRC in ("vi", "fused"):
    vi = json.loads((EVIDENCE / "vi_wc_final.json").read_text())
    for l in vi["logos"]:
        b = VI_ALIASES.get(norm_brand(l["entity"]))
        if not b:  # unmapped catalogue labels (e.g. 'Musixmatch' on Crypto.com boards) are not trusted
            continue
        per_t = {}
        for tr in l["tracks"]:
            for ts, x1, y1, x2, y2 in tr["boxes"]:
                t = round(ts)
                per_t.setdefault(t, []).append((x2 - x1) * (y2 - y1))
        for t, areas in per_t.items():
            add(b, t, max(areas))  # VI samples several boxes per second; keep the largest


def runs(ts):
    out = []
    for t in sorted(ts):
        if out and t - out[-1][1] <= MERGE_GAP + 1:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


metrics = {}
for b, d in pres.items():
    ts = sorted(d)
    r = runs(ts)
    metrics[b] = {
        "visible_s": len(ts),
        "appearances": len(r),
        "median_appearance_s": sorted(e - s + 1 for s, e in r)[len(r) // 2] if r else 0,
        "share_visible_pct": round(100 * sum(d.values()) / len(ts), 3) if ts else 0,
        "share_seconds": round(sum(d.values()), 3),
        "key_moment_s": sum(1 for t in ts if t in in_moment),
        "timeline": ts,
    }
total_visible = sum(m["visible_s"] for m in metrics.values())
total_km = sum(m["key_moment_s"] for m in metrics.values())
for m in metrics.values():
    m["share_of_exposure_pct"] = round(100 * m["visible_s"] / max(total_visible, 1), 1)
    m["share_of_key_moments_pct"] = round(100 * m["key_moment_s"] / max(total_km, 1), 1)

out = {"source": SRC, "duration_s": DURATION, "sampling_fps": 1, "merge_gap_samples": MERGE_GAP,
       "score_timeline": timeline, "moments": moments, "key_moment_seconds": len(in_moment),
       "brands": dict(sorted(metrics.items(), key=lambda x: -x[1]["visible_s"]))}
(EVIDENCE / f"wc_metrics_{SRC}.json").write_text(json.dumps(out, indent=1))
print("moments:", moments)
for b, m in out["brands"].items():
    print(f'{b:16s} vis={m["visible_s"]:4d}s app={m["appearances"]:3d} share%vis={m["share_visible_pct"]:6.2f} '
          f'fullscreen-s={m["share_seconds"]:6.2f} keymoment={m["key_moment_s"]:3d}s '
          f'({m["share_of_exposure_pct"]}% of exposure, {m["share_of_key_moments_pct"]}% of key moments)')

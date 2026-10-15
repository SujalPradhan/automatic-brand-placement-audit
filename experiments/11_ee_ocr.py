"""OCR brand identification on the ExposureEngine benchmark test half (same frames/brands as 05_score_ee).

Puma and Volkswagen are symbol logos with no text, included on purpose to show OCR's blind spot.
"""
import json
from pathlib import Path

import cv2
from ocrmac import ocrmac
from common import EVIDENCE, load_obb_labels, text_matches

split = json.loads((EVIDENCE / "ee_split.json").read_text())
test = [Path(p) for p in split["bench"]][1::2]
LEX = {600: ["unibet"], 443: ["puma"], 274: ["intersport"], 621: ["volkswagen"],
       157: ["elkedjan"], 395: ["nordicwellness"]}
names = json.loads((EVIDENCE / "ee_brand_names.json").read_text())


def hit(text, words):
    return text_matches(text, words) > 0


res = {c: {"tp": 0, "fp": 0, "fn": 0} for c in LEX}
for p in test:
    h, w = cv2.imread(str(p)).shape[:2]
    present = {c for c, _, _ in load_obb_labels(p.parent.parent / "labels" / f"{p.stem}.txt", w, h)}
    texts = [r[0] for r in ocrmac.OCR(str(p), recognition_level="accurate").recognize()]
    for c, words in LEX.items():
        pred = any(hit(t, words) for t in texts)
        r = res[c]
        r["tp"] += pred and c in present
        r["fp"] += pred and c not in present
        r["fn"] += (not pred) and c in present
out = {}
for c, r in res.items():
    P = r["tp"] / max(r["tp"] + r["fp"], 1)
    R = r["tp"] / max(r["tp"] + r["fn"], 1)
    out[names[str(c)]] = {"frame_precision": round(P, 3), "frame_recall": round(R, 3),
                          "frame_f1": round(2 * P * R / max(P + R, 1e-9), 3), "frames_with_brand": r["tp"] + r["fn"]}
scores = json.loads((EVIDENCE / "ee_scores.json").read_text())
scores["brand_identification"]["ocr_apple_vision"] = out
(EVIDENCE / "ee_scores.json").write_text(json.dumps(scores, indent=1))
print(json.dumps(out, indent=1))

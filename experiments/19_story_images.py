"""Annotated evidence frames for the story pages: detected boards outlined and labelled."""
import json

import cv2

from common import BRAND_INFO, DATA, EVIDENCE, ROOT
from presence import presence

OUT = ROOT / "story" / "img"
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = [("wc_final", 1, "open_0001"), ("wc_final", 516, "byjus_0836"), ("wc_final", 546, "messi_winner"),
         ("wc_final", 645, "mengniu_0645"), ("wc_final", 676, "shootout_visa"),
         ("wc2026", 262, "vinicius_goal"), ("wc2026", 146, "saibari_goal"), ("wc2026", 476, "lenovo_board"),
         ("wc2026_final", 64, "final26_hisense"), ("wc2026_final", 69, "final26_goal"),
         ("wc2026_final", 40, "final26_partners")]
for tag, t, name in SHOTS:
    P = presence(tag)
    ocr = json.loads((EVIDENCE / f"ocr_{tag}.json").read_text())["per_second"].get(str(t), {})
    im = cv2.imread(str(DATA / tag / "frames_1fps" / f"f_{t + 1:04d}.jpg"))
    k = im.shape[1] / 1920
    placed = []
    for b, d in sorted(P.items(), key=lambda x: x[1].get(t, {}).get("box", [0])[0]):
        if t not in d:
            continue
        x1, y1, x2, y2 = d[t]["box"]
        for o in ocr.get(b, []):  # every board OCR read for this brand, not only the largest
            cv2.rectangle(im, (round(o[0]) - 4, round(o[1]) - 4), (round(o[2]) + 4, round(o[3]) + 4), (40, 220, 255), max(2, int(4 * k)))
        cv2.rectangle(im, (x1 - 4, y1 - 4), (x2 + 4, y2 + 4), (40, 220, 255), max(2, int(4 * k)))
        lab = BRAND_INFO[b][0]
        fs = 0.9 * k + 0.2
        (tw, th), _ = cv2.getTextSize(lab, cv2.FONT_HERSHEY_SIMPLEX, fs, 2)
        y = max(th + 8, y1 - 10)
        step = 0
        lx = min(max(8, x1), im.shape[1] - tw - 8)  # keep labels of boards cut by the frame edge readable
        while any(not (lx + tw + 4 < a or lx - 4 > c or y < bb - 2 or y - th - 6 > dd + 2) for a, bb, c, dd in placed):
            step += 1
            y = (y2 + th + 14) + (step - 1) * (th + 12) if step > 0 else y
        placed.append((lx - 4, y - th - 6, lx + tw + 4, y + 4))
        cv2.rectangle(im, (lx - 4, y - th - 6), (lx + tw + 4, y + 4), (40, 220, 255), -1)
        cv2.putText(im, lab, (lx, y), cv2.FONT_HERSHEY_SIMPLEX, fs, (20, 20, 20), 2)
    cv2.imwrite(str(OUT / f"{name}.jpg"), cv2.resize(im, (960, 540)), [cv2.IMWRITE_JPEG_QUALITY, 74])
    print(name, sorted(b for b, d in P.items() if t in d))

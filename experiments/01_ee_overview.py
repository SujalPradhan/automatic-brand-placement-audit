"""Dataset overview: class frequencies, box sizes, and a GT-annotated contact sheet."""
import collections
import json
import random

import cv2
import numpy as np

from common import EVIDENCE, ee_pairs, load_obb_labels

random.seed(0)
stats = {}
cls_count = collections.Counter()
cls_frames = collections.defaultdict(set)
areas = []
for split in ["train", "val", "test"]:
    pairs = ee_pairs(split)
    stats[split] = len(pairs)
    for img, lab in pairs:
        h, w = cv2.imread(str(img)).shape[:2]
        for c, box, _ in load_obb_labels(lab, w, h):
            cls_count[c] += 1
            cls_frames[c].add((split, img.stem))
            areas.append((box[2] - box[0]) * (box[3] - box[1]) / (w * h))

areas = np.array(areas)
summary = {
    "matched_pairs": stats,
    "boxes": int(len(areas)),
    "classes": len(cls_count),
    "top_classes": [(c, n, len(cls_frames[c])) for c, n in cls_count.most_common(15)],
    "box_area_pct_quantiles": {q: round(float(np.quantile(areas, q)) * 100, 3) for q in [0.1, 0.25, 0.5, 0.75, 0.9]},
}
print(json.dumps(summary, indent=1))
(EVIDENCE / "ee_overview.json").write_text(json.dumps(summary, indent=1))

# Contact sheet of 12 frames with GT boxes drawn
sample = random.sample(ee_pairs("test") + ee_pairs("val"), 12)
tiles = []
for img, lab in sample:
    im = cv2.imread(str(img))
    h, w = im.shape[:2]
    for c, box, poly in load_obb_labels(lab, w, h):
        cv2.polylines(im, [poly.astype(np.int32)], True, (0, 255, 0), 3)
        cv2.putText(im, str(c), (int(box[0]), int(box[1]) - 4), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    tiles.append(cv2.resize(im, (640, 360)))
rows = [np.hstack(tiles[i:i + 3]) for i in range(0, 12, 3)]
cv2.imwrite(str(EVIDENCE / "ee_gt_contact_sheet.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])

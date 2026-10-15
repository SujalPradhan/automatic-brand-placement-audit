"""Fix the benchmark/reference split and render a crop gallery of the most frequent classes.

Benchmark = all val+test pairs + 91 random train pairs (150 frames).
Reference pool = remaining train pairs (used only for one-shot query crops).
"""
import collections
import json
import random

import cv2
import numpy as np

from common import EVIDENCE, ee_pairs, load_obb_labels

random.seed(42)
train = ee_pairs("train")
random.shuffle(train)
bench = ee_pairs("val") + ee_pairs("test") + train[:91]
ref = train[91:]
split = {"bench": [str(p[0]) for p in bench], "ref": [str(p[0]) for p in ref]}
(EVIDENCE / "ee_split.json").write_text(json.dumps(split, indent=1))

crops = collections.defaultdict(list)
for img, lab in ref:
    im = cv2.imread(str(img))
    h, w = im.shape[:2]
    for c, box, _ in load_obb_labels(lab, w, h):
        x1, y1, x2, y2 = map(int, box)
        if (x2 - x1) * (y2 - y1) > 2500:  # skip tiny crops for naming
            crops[c].append(im[max(0, y1):y2, max(0, x1):x2])

counts = collections.Counter({c: len(v) for c, v in crops.items()})
top = [c for c, _ in counts.most_common(24)]
rows = []
for c in top:
    tiles = [cv2.resize(x, (200, 80)) for x in crops[c][:5]]
    tiles += [np.zeros((80, 200, 3), np.uint8)] * (5 - len(tiles))
    label = np.zeros((80, 90, 3), np.uint8)
    cv2.putText(label, str(c), (5, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    rows.append(np.hstack([label] + tiles))
cv2.imwrite(str(EVIDENCE / "ee_class_gallery.jpg"), np.vstack(rows))
print("bench", len(bench), "ref", len(ref), "top classes", top)

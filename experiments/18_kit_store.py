"""Kit/jersey logo detections, kept out of the board analysis but saved for later use.

Writes evidence/kit_<tag>.json: {brand: [seconds]} plus the hand-labelled kit marks from the recall frames.
"""
import csv
import json

from common import EVIDENCE
from presence import VIDEO, presence

for tag in VIDEO:
    P = presence(tag, kit=True)
    labels = []
    for r in csv.DictReader((EVIDENCE / "audit" / f"{tag}_gt.csv").open()):
        for x in r["labels"].split(";"):
            if x and x.split(":")[2] != "board":
                labels.append([int(r["t"])] + x.split(":"))
    out = {"note": "Kit/jersey and on-screen-graphic marks. Not part of the board exposure analysis.",
           "detected_seconds": {b: sorted(d) for b, d in P.items()}, "hand_labels": labels}
    (EVIDENCE / f"kit_{tag}.json").write_text(json.dumps(out, indent=1))
    print(tag, {b: len(d) for b, d in P.items()}, "labels", len(labels))

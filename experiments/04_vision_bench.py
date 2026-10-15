"""Google Cloud Vision LOGO_DETECTION on the ExposureEngine benchmark frames.

150 images -> inside the 1,000 free units/month. Results are cached; re-running does not re-bill.
"""
import json
import time
from pathlib import Path

from google.cloud import vision

from common import EVIDENCE, charge, gcp_client_options, gcp_credentials

OUT = EVIDENCE / "ee_gcv.json"
split = json.loads((EVIDENCE / "ee_split.json").read_text())
cache = json.loads(OUT.read_text())["detections"] if OUT.exists() else {}
todo = [p for p in split["bench"] if Path(p).name not in cache]

client = vision.ImageAnnotatorClient(credentials=gcp_credentials(), client_options=gcp_client_options())
times = []
for i in range(0, len(todo), 16):  # batch_annotate_images accepts up to 16 images
    batch = todo[i:i + 16]
    charge("vision_images", len(batch))
    reqs = [vision.AnnotateImageRequest(
        image=vision.Image(content=Path(p).read_bytes()),
        features=[vision.Feature(type_=vision.Feature.Type.LOGO_DETECTION, max_results=50)],
    ) for p in batch]
    t0 = time.perf_counter()
    resp = client.batch_annotate_images(requests=reqs)
    times.append((time.perf_counter() - t0) / len(batch))
    for p, r in zip(batch, resp.responses):
        if r.error.message:
            print("error", p, r.error.message)
            continue
        dets = []
        for a in r.logo_annotations:
            xs = [v.x for v in a.bounding_poly.vertices]
            ys = [v.y for v in a.bounding_poly.vertices]
            dets.append([min(xs), min(ys), max(xs), max(ys), round(a.score, 4), a.description])
        cache[Path(p).name] = dets
    print(f"{i + len(batch)}/{len(todo)}")

prev = json.loads(OUT.read_text()) if OUT.exists() else {}
OUT.write_text(json.dumps({
    "api": "vision.LOGO_DETECTION",
    "sec_per_frame_mean": round(sum(times) / len(times), 3) if times else prev.get("sec_per_frame_mean"),
    "detections": cache,
}))
names = sorted({d[5] for v in cache.values() for d in v})
print("frames", len(cache), "brands returned:", names)

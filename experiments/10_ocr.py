"""On-device OCR (Apple Vision via ocrmac) over every 1 fps frame of a video, full frame + tiled & upscaled.

The tiled pass exists because distant perimeter boards are only ~8-12 px tall: a 3x2 grid of overlapping tiles,
each upscaled (2x at 1080p, 3x at 720p), lets the OCR read them. Raw text is saved so brand matching can be
re-run with --rematch without re-reading the frames.

A third, Chinese-first full-frame pass (--add-zh) reads Chinese-only boards (Mengniu, Wanda), which the
English-first passes return nothing for.

Usage: python 10_ocr.py <tag> [--rematch | --add-zh]      tag: wc_final (2022) | wc2026 | wc2026_final
Output: evidence/ocr_<tag>.json  per_second[t] = {brand: [[x1,y1,x2,y2,score,text,src], ...]}
"""
import json
import sys
import time

from PIL import Image

from common import DATA, EVIDENCE, LEXICON, iou, text_matches

TAG = sys.argv[1]
ADD_ZH = "--add-zh" in sys.argv
REMATCH = "--rematch" in sys.argv or ADD_ZH
FR = DATA / TAG / "frames_1fps"
OUT = EVIDENCE / f"ocr_{TAG}.json"
COLS, ROWS, OVERLAP = 3, 2, 0.15


def tiles(w, h):
    tw, th = w / (COLS - (COLS - 1) * OVERLAP), h / (ROWS - (ROWS - 1) * OVERLAP)
    for r in range(ROWS):
        for c in range(COLS):
            x0, y0 = c * tw * (1 - OVERLAP), r * th * (1 - OVERLAP)
            yield int(x0), int(y0), int(min(w, x0 + tw)), int(min(h, y0 + th))


def read(img, x0=0, y0=0, scale=1.0, langs=("en-US", "zh-Hans")):
    """OCR an image; return [text, conf, [x1,y1,x2,y2]] in full-frame pixel coordinates."""
    out = []
    w, h = img.size
    for text, conf, (x, y, bw, bh) in ocrmac.OCR(img, recognition_level="accurate",
                                                 language_preference=list(langs)).recognize():
        box = [x * w, (1 - y - bh) * h, (x + bw) * w, (1 - y) * h]  # Vision uses a bottom-left origin
        out.append([text, round(conf, 3), [round(x0 + v / scale, 1) if i % 2 == 0 else round(y0 + v / scale, 1)
                                           for i, v in enumerate(box)]])
    return out


def match(raw):
    """Brand hits per frame, de-duplicated across the full-frame and tile passes."""
    hits = {}
    for text, conf, box, src in raw:
        for brand, words in LEXICON.items():
            s = text_matches(text, words)
            if not s:
                continue
            lst = hits.setdefault(brand, [])
            dup = next((h for h in lst if iou(h[:4], box) > 0.3), None)
            if dup is None:
                lst.append(box + [round(s / 100 * conf, 3), text, src])
            elif (box[2] - box[0]) * (box[3] - box[1]) > (dup[2] - dup[0]) * (dup[3] - dup[1]):
                dup[:4] = box
    return hits


if not REMATCH or ADD_ZH:
    from ocrmac import ocrmac

prev = json.loads(OUT.read_text()) if REMATCH else None
per_second, raw_all, times = {}, {}, []
for p in sorted(FR.glob("f_*.jpg")):
    t = int(p.stem[2:]) - 1
    if REMATCH:
        raw = [r for r in prev["raw"][str(t)] if not (ADD_ZH and r[3] == "zh")]
        if ADD_ZH:
            raw += [r + ["zh"] for r in read(Image.open(p).convert("RGB"), langs=("zh-Hans",))]
    else:
        t0 = time.perf_counter()
        img = Image.open(p).convert("RGB")
        scale = 2.0 if img.height >= 1000 else 3.0
        raw = [r + ["full"] for r in read(img)]
        for x0, y0, x1, y1 in tiles(*img.size):
            tile = img.crop((x0, y0, x1, y1))
            tile = tile.resize((int(tile.width * scale), int(tile.height * scale)), Image.LANCZOS)
            raw += [r + ["tile"] for r in read(tile, x0, y0, scale)]
        times.append(time.perf_counter() - t0)
    raw_all[t] = raw
    per_second[t] = match(raw)
    if not REMATCH and len(times) % 100 == 0:
        print(len(times), f"{sum(times) / len(times):.2f}s/frame", flush=True)

spf = prev["sec_per_frame_mean"] if REMATCH else round(sum(times) / len(times), 3)
W, H = Image.open(next(FR.glob("f_*.jpg"))).size
OUT.write_text(json.dumps({"tag": TAG, "frame_size": [W, H], "engine": "Apple Vision (ocrmac, accurate), full + 3x2 tiles",
                           "sec_per_frame_mean": spf, "per_second": per_second, "raw": raw_all}, ensure_ascii=False))
counts = {}
for d in per_second.values():
    for b in d:
        counts[b] = counts.get(b, 0) + 1
print(TAG, "s/frame", spf, sorted(counts.items(), key=lambda x: -x[1]))

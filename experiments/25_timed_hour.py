"""Timed end-to-end run of the Apple Vision pipeline on one hour of video, from the video file.
Stages: ffmpeg frame extraction (1 fps) -> OCR (full frame + 3x2 upscaled tiles + Chinese pass, 4 workers) ->
brand matching -> per-brand seconds. Writes evidence/timing_hour_run.json. Frames stay under data/timing_run/.
Usage: python 25_timed_hour.py <video.mp4> [workers=4] [seconds=3600]
"""
import json, subprocess, sys, time
from multiprocessing import get_context
from pathlib import Path

from common import DATA, EVIDENCE, LEXICON, ffmpeg_exe, iou, text_matches

VIDEO, WORKERS, SECONDS = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 4, int(sys.argv[3]) if len(sys.argv) > 3 else 3600
RUN = DATA / "timing_run"
FR = RUN / "frames_1fps"
HOST_USD_PER_HOUR = 1.23   # EC2 mac-m4 dedicated host, evidence/pricing.json
COLS, ROWS, OVERLAP = 3, 2, 0.15


def tiles(w, h):
    tw, th = w / (COLS - (COLS - 1) * OVERLAP), h / (ROWS - (ROWS - 1) * OVERLAP)
    for r in range(ROWS):
        for c in range(COLS):
            x0, y0 = c * tw * (1 - OVERLAP), r * th * (1 - OVERLAP)
            yield int(x0), int(y0), int(min(w, x0 + tw)), int(min(h, y0 + th))


def read(ocr, img, x0=0, y0=0, scale=1.0, langs=("en-US", "zh-Hans")):
    out = []
    w, h = img.size
    for text, conf, (x, y, bw, bh) in ocr.OCR(img, recognition_level="accurate", language_preference=list(langs)).recognize():
        box = [x * w, (1 - y - bh) * h, (x + bw) * w, (1 - y) * h]
        out.append([text, round(conf, 3), [x0 + box[0] / scale, y0 + box[1] / scale, x0 + box[2] / scale, y0 + box[3] / scale]])
    return out


def match(raw):
    hits = {}
    for text, conf, box in raw:
        for brand, words in LEXICON.items():
            s = text_matches(text, words)
            if not s:
                continue
            lst = hits.setdefault(brand, [])
            if not any(iou(h, box) > 0.3 for h in lst):
                lst.append(box)
    return hits


def work(path):
    from ocrmac import ocrmac
    from PIL import Image
    t0 = time.perf_counter()
    img = Image.open(path).convert("RGB")
    scale = 2.0 if img.height >= 1000 else 3.0
    raw = read(ocrmac, img)
    for x0, y0, x1, y1 in tiles(*img.size):
        tile = img.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * scale), int((y1 - y0) * scale)), Image.LANCZOS)
        raw += read(ocrmac, tile, x0, y0, scale)
    raw += read(ocrmac, img, langs=("zh-Hans",))
    hits = match(raw)
    return int(Path(path).stem[2:]) - 1, sorted(hits), time.perf_counter() - t0


if __name__ == "__main__":
    FR.mkdir(parents=True, exist_ok=True)
    for old in FR.glob("f_*.jpg"):
        old.unlink()
    res = {"video": VIDEO.name, "seconds": SECONDS, "workers": WORKERS, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    T0 = time.perf_counter()
    t = time.perf_counter()
    subprocess.run([ffmpeg_exe(), "-v", "error", "-t", str(SECONDS), "-i", str(VIDEO), "-vf", "fps=1", "-q:v", "2",
                    str(FR / "f_%04d.jpg")], check=True)
    res["extract_s"] = round(time.perf_counter() - t, 1)
    frames = sorted(FR.glob("f_*.jpg"))
    res["frames"] = len(frames)
    print("extracted", len(frames), res["extract_s"], "s", flush=True)

    t = time.perf_counter()
    per_sec, lat, done_at = {}, [], []
    with get_context("spawn").Pool(WORKERS) as pool:
        for i, (sec, brands, dt) in enumerate(pool.imap_unordered(work, [str(p) for p in frames], chunksize=4)):
            per_sec[sec] = brands
            lat.append(dt)
            done_at.append(time.perf_counter() - t)
            if (i + 1) % 300 == 0:
                print(i + 1, f"{(i + 1) / done_at[-1]:.2f} frames/s", flush=True)
    res["ocr_s"] = round(time.perf_counter() - t, 1)

    t = time.perf_counter()
    secs = {}
    for sec, brands in per_sec.items():
        for b in brands:
            secs[b] = secs.get(b, 0) + 1
    res["aggregate_s"] = round(time.perf_counter() - t, 3)
    res["brands_found"] = len(secs)
    res["seconds_with_any_brand"] = sum(1 for b in per_sec.values() if b)
    res["top_brands"] = sorted(secs.items(), key=lambda x: -x[1])[:8]
    res["total_s"] = round(time.perf_counter() - T0, 1)
    res["mean_latency_s"] = round(sum(lat) / len(lat), 2)
    blocks = []
    for k in range(0, len(done_at), 600):
        chunk = done_at[k:k + 600]
        prev = done_at[k - 1] if k else 0
        blocks.append(round(len(chunk) / (chunk[-1] - prev), 2))
    res["frames_per_s_by_600_frame_block"] = blocks
    res["video_seconds"] = res["frames"]
    res["cost_usd_host_prorata"] = round(res["total_s"] / 3600 * HOST_USD_PER_HOUR, 3)
    res["total_s_per_video_hour"] = round(res["total_s"] / res["frames"] * 3600, 1)
    res["cost_usd_per_video_hour"] = round(res["total_s_per_video_hour"] / 3600 * HOST_USD_PER_HOUR, 3)
    res["cost_usd_extract"] = round(res["extract_s"] / 3600 * HOST_USD_PER_HOUR, 3)
    res["cost_usd_ocr"] = round(res["ocr_s"] / 3600 * HOST_USD_PER_HOUR, 3)
    (EVIDENCE / (f"timing_{sys.argv[4]}_{WORKERS}w.json" if len(sys.argv) > 4 else "timing_hour_run.json" if WORKERS == 4 else f"timing_hour_run_{WORKERS}w.json")).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))

"""Benchmark alternative sponsor-board readers against Apple Vision OCR on the 156 hand-labelled frames.

Usage: python 21_engine_bench.py <engine> [--rescore] | --sheets
  engines: apple_baseline apple_fullframe_only apple_no_zh apple_parallel paddleocr tesseract cloud_vision_text
           gemini_flash
Output: evidence/engines/<engine>.json (metrics + per-frame hits), evidence/engines/raw_<engine>.json (raw reads).
Precision: a hit (brand, frame) is verified automatically when it is a labelled board mark or already survived the
v2/v3 appearance audit; the rest are looked at by eye and logged in evidence/engines/verdicts.csv
(tag,t,brand,verdict[true|false|kit],note). `--sheets` writes contact sheets of the unresolved hits.
"""
import base64
import csv
import io
import json
import math
import multiprocessing as mp
import sys
import time

from PIL import Image

from common import DATA, EVIDENCE, GCP_PROJECT, LEXICON, VI_ALIASES, charge, gcp_credentials, iou, norm_brand, text_matches
from presence import KIT_ONLY, VIDEO, kit_marks, presence, rejects

OUTDIR = EVIDENCE / "engines"
TAGS = ["wc_final", "wc2026", "wc2026_final"]
COLS, ROWS, OVERLAP = 3, 2, 0.15


# ---------------------------------------------------------------- ground truth and scoring
def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def gt(tag):
    rows = []
    for r in csv.DictReader((EVIDENCE / "audit" / f"{tag}_gt.csv").open()):
        rows.append((int(r["t"]), [x.split(":") for x in r["labels"].split(";") if x]))
    return rows


def frame_path(tag, t):
    return DATA / tag / "frames_1fps" / f"f_{t + 1:04d}.jpg"  # frame N = second N-1


def labelled_frames():
    return [(tag, t) for tag in TAGS for t, _ in gt(tag)]


def tiles(w, h):
    tw, th = w / (COLS - (COLS - 1) * OVERLAP), h / (ROWS - (ROWS - 1) * OVERLAP)
    for r in range(ROWS):
        for c in range(COLS):
            x0, y0 = c * tw * (1 - OVERLAP), r * th * (1 - OVERLAP)
            yield int(x0), int(y0), int(min(w, x0 + tw)), int(min(h, y0 + th))


def match(raw):
    """Same matcher as 10_ocr.match: brand hits per frame from [text, conf, box, src] reads."""
    hits = {}
    for text, conf, box, src in raw:
        for brand, words in LEXICON.items():
            s = text_matches(text, words)
            if not s:
                continue
            lst = hits.setdefault(brand, [])
            dup = next((h for h in lst if iou(h[:4], box) > 0.3), None)
            if dup is None:
                lst.append(list(box) + [round(s / 100 * conf, 3), text, src])
    return hits


def recall(hits):
    """hits[tag][t] = {brand: ...}. Board-only recall as 16_score.py: found/of for all, L and S, per game + pooled."""
    res, pooled = {}, {}
    for tag in TAGS:
        cnt = {}
        for t, labs in gt(tag):
            for b, size, kind in labs:
                if kind != "board":
                    continue
                for key in ("all", size):
                    c = cnt.setdefault(key, [0, 0])
                    c[1] += 1
                    c[0] += int(b in hits.get(tag, {}).get(str(t), {}))
        for k, v in cnt.items():
            p = pooled.setdefault(k, [0, 0])
            p[0] += v[0]
            p[1] += v[1]
        res[tag] = {("large" if k == "L" else "small" if k == "S" else k): fmt(v) for k, v in cnt.items()}
    names = {"all": "all", "L": "large", "S": "small"}
    return {"pooled": {names[k]: fmt(v) for k, v in pooled.items()}, "per_game": res}


def fmt(v):
    return {"found": v[0], "of": v[1], "recall": round(v[0] / v[1], 3) if v[1] else None, "ci95": wilson(*v)}


def board_hits(hits):
    """set of (tag, t, brand) GT board marks found."""
    out = set()
    for tag in TAGS:
        for t, labs in gt(tag):
            for b, size, kind in labs:
                if kind == "board" and b in hits.get(tag, {}).get(str(t), {}):
                    out.add((tag, t, b))
    return out


# ---------------------------------------------------------------- precision audit
def verdicts():
    p = OUTDIR / "verdicts.csv"
    v = {}
    if p.exists():
        for r in csv.DictReader(p.open()):
            v[(r["tag"], int(r["t"]), r["brand"])] = r["verdict"]
    return v


_known = {}


def known(tag, t, brand):
    """true / false / kit / None (needs eye audit) from existing labels + the v2/v3 audit."""
    if tag not in _known:
        G = {t_: labs for t_, labs in gt(tag)}
        pres = presence(tag, ("ocr", "vi"), audited=True)
        _known[tag] = (G, pres, rejects(tag), kit_marks(tag))
    G, pres, bad, kit = _known[tag]
    labs = G.get(t, [])
    if any(b == brand and k == "board" for b, s, k in labs):
        return "true"
    if (brand, t) in bad:
        return "false"
    if brand in KIT_ONLY or (brand, t) in kit or any(b == brand and k != "board" for b, s, k in labs):
        return "kit"
    if t in pres.get(brand, {}):
        return "true"
    return None


def precision(hits):
    V = verdicts()
    ver = det = 0
    pending, false, per = [], [], {}
    for tag in TAGS:
        pv = pd = 0
        for t, d in hits.get(tag, {}).items():
            for b in d:
                v = known(tag, int(t), b) or V.get((tag, int(t), b))
                if v == "kit":
                    continue
                if v is None:
                    pending.append([tag, int(t), b])
                    continue
                pd += 1
                pv += v == "true"
                if v == "false":
                    false.append([tag, int(t), b])
        per[tag] = {"verified": pv, "detected": pd}
        ver += pv
        det += pd
    return {"verified": ver, "detected": det, "precision": round(ver / det, 3) if det else None, "ci95": wilson(ver, det),
            "per_game": per, "false_hits": false, "unaudited_pending": len(pending), "pending": pending}


# ---------------------------------------------------------------- engines
_ocr = None


def apple_read(img, x0=0, y0=0, scale=1.0, langs=("en-US", "zh-Hans")):
    global _ocr
    if _ocr is None:
        from ocrmac import ocrmac as _ocr
    out = []
    w, h = img.size
    for text, conf, (x, y, bw, bh) in _ocr.OCR(img, recognition_level="accurate",
                                                language_preference=list(langs)).recognize():
        box = [x * w, (1 - y - bh) * h, (x + bw) * w, (1 - y) * h]
        out.append([text, round(conf, 3), [round(x0 + v / scale, 1) if i % 2 == 0 else round(y0 + v / scale, 1)
                                           for i, v in enumerate(box)]])
    return out


def apple_frame(path, tiled=True, zh=True):
    img = Image.open(path).convert("RGB")
    scale = 2.0 if img.height >= 1000 else 3.0
    raw = [r + ["full"] for r in apple_read(img)]
    if tiled:
        for x0, y0, x1, y1 in tiles(*img.size):
            tile = img.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * scale), int((y1 - y0) * scale)), Image.LANCZOS)
            raw += [r + ["tile"] for r in apple_read(tile, x0, y0, scale)]
    if zh:
        raw += [r + ["zh"] for r in apple_read(img, langs=("zh-Hans",))]
    return raw


def _apple_worker(args):
    path, tiled, zh = args
    t0 = time.perf_counter()
    apple_frame(path, tiled, zh)
    return time.perf_counter() - t0


_paddle = None


def paddle_read(img, x0=0, y0=0, scale=1.0):
    import numpy as np
    global _paddle
    if _paddle is None:
        from paddleocr import PaddleOCR
        _paddle = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                            use_textline_orientation=False)
    out = []
    for res in _paddle.predict(np.array(img)[:, :, ::-1].copy()):
        r = res if isinstance(res, dict) else res.json["res"]
        for txt, sc, poly in zip(r["rec_texts"], r["rec_scores"], r["rec_polys"]):
            p = np.array(poly)
            box = [x0 + p[:, 0].min() / scale, y0 + p[:, 1].min() / scale, x0 + p[:, 0].max() / scale,
                   y0 + p[:, 1].max() / scale]
            out.append([txt, round(float(sc), 3), [round(float(v), 1) for v in box]])
    return out


def tess_read(img, x0=0, y0=0, scale=1.0):
    import pytesseract
    d = pytesseract.image_to_data(img, lang="eng", config="--psm 11", output_type=pytesseract.Output.DICT)
    words = [(d["text"][i], d["conf"][i], d["left"][i], d["top"][i], d["width"][i], d["height"][i],
              (d["block_num"][i], d["par_num"][i], d["line_num"][i])) for i in range(len(d["text"]))
             if d["text"][i].strip() and float(d["conf"][i]) >= 0]
    out = []

    def add(txt, conf, l, t_, r, b):
        out.append([txt, round(conf / 100, 3), [round(x0 + l / scale, 1), round(y0 + t_ / scale, 1),
                                                round(x0 + r / scale, 1), round(y0 + b / scale, 1)]])
    lines = {}
    for w in words:
        add(w[0], float(w[1]), w[2], w[3], w[2] + w[4], w[3] + w[5])
        lines.setdefault(w[6], []).append(w)
    for ws in lines.values():  # also whole lines, so "QATAR AIRWAYS" can match a one-word lexicon entry
        if len(ws) > 1:
            add(" ".join(w[0] for w in ws), sum(float(w[1]) for w in ws) / len(ws), min(w[2] for w in ws),
                min(w[3] for w in ws), max(w[2] + w[4] for w in ws), max(w[3] + w[5] for w in ws))
    return out


def generic_frame(path, reader, tiled=True):
    img = Image.open(path).convert("RGB")
    scale = 2.0 if img.height >= 1000 else 3.0
    raw = [r + ["full"] for r in reader(img)]
    if tiled:
        for x0, y0, x1, y1 in tiles(*img.size):
            tile = img.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * scale), int((y1 - y0) * scale)), Image.LANCZOS)
            raw += [r + ["tile"] for r in reader(tile, x0, y0, scale)]
    return raw


def cloud_vision_frame(client, path):
    from google.cloud import vision
    data = path.read_bytes()
    resp = client.text_detection(image=vision.Image(content=data))
    if resp.error.message:
        raise RuntimeError(resp.error.message)
    out = []
    ann = resp.full_text_annotation

    def bb(poly):
        xs = [v.x for v in poly.vertices]
        ys = [v.y for v in poly.vertices]
        return [min(xs), min(ys), max(xs), max(ys)]
    for page in ann.pages:
        for blk in page.blocks:
            for par in blk.paragraphs:
                ws = [("".join(s.text for s in w.symbols), w) for w in par.words]
                for txt, w in ws:
                    out.append([txt, round(w.confidence, 3), bb(w.bounding_box), "word"])
                if len(ws) > 1:
                    out.append([" ".join(t for t, _ in ws), round(par.confidence, 3), bb(par.bounding_box), "para"])
    return out


GEMINI_MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash"]  # (gemini-3.5-flash was tried first: ~$1.2 for ~half the frames, run lost to a hang)  # first that answers is used
# USD per 1M tokens (input incl. image, output incl. thinking); filled from the model's published price below
GEMINI_PRICE = {"gemini-3.5-flash": (1.50, 9.00),  # third-party trackers, not verified on Google's page
                "gemini-3.1-flash-lite": (0.25, 1.50), "gemini-2.5-flash": (0.30, 2.50), "gemini-2.5-flash-lite": (0.10, 0.40)}
PROMPT = ("This is a frame from a football (soccer) TV broadcast. List every sponsor / advertiser brand whose name or "
          "logo is legible on the pitch-side perimeter advertising boards, LED boards or stadium signage. Do not "
          "list kit manufacturers or shirt sponsors, broadcaster graphics or scoreboard graphics. For each give the "
          "brand name as printed, a tight bounding box box_2d=[ymin,xmin,ymax,xmax] normalised to 0-1000, and "
          "size 'large' if a viewer can read it easily at normal broadcast size or 'small' if it is tiny or far "
          "away. Return only a JSON list like [{\"brand\":\"Visa\",\"box_2d\":[..],\"size\":\"large\"}]; "
          "return [] if there are none.")


def gemini_call(model, path, token):
    import requests
    body = {"contents": [{"role": "user", "parts": [
        {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(path.read_bytes()).decode()}},
        {"text": PROMPT}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    url = (f"https://aiplatform.googleapis.com/v1/projects/{GCP_PROJECT}/locations/global/"
           f"publishers/google/models/{model}:generateContent")
    for attempt in range(4):
        r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 503):
            time.sleep(3 * (attempt + 1))
            continue
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    raise RuntimeError("retries exhausted")


def map_brand(name):
    n = norm_brand(name)
    if n in VI_ALIASES:
        return VI_ALIASES[n]
    for b, words in LEXICON.items():
        if text_matches(name, words) >= 85 or norm_brand(b) == n:
            return b
    return None


# ---------------------------------------------------------------- runners
def run_text_engine(name, frames, fn, warmup=None, budget_s=None):
    """Resumable: per-frame reads + timings are checkpointed in evidence/engines/partial_<name>.json."""
    ck = OUTDIR / f"partial_{name}.json"
    OUTDIR.mkdir(parents=True, exist_ok=True)
    done = json.loads(ck.read_text()) if ck.exists() else {}
    if warmup:
        warmup()
    start = time.time()
    for tag, t in frames:
        key = f"{tag}:{t}"
        if key in done:
            continue
        if budget_s and time.time() - start > budget_s:
            print(f"partial: {len(done)}/{len(frames)} frames done; rerun to continue")
            raise SystemExit(3)
        t0 = time.perf_counter()
        r = fn(frame_path(tag, t))
        done[key] = {"raw": r, "lat": time.perf_counter() - t0}
        ck.write_text(json.dumps(done, ensure_ascii=False))
    raw, hits, times = {}, {}, []
    for tag, t in frames:
        d = done[f"{tag}:{t}"]
        raw.setdefault(tag, {})[str(t)] = d["raw"]
        hits.setdefault(tag, {})[str(t)] = match(d["raw"])
        times.append(d["lat"])
    return raw, hits, times


def _record(j, tag, t, a, b, raw, hits, unmapped):
    try:
        items = json.loads(j["candidates"][0]["content"]["parts"][-1]["text"])
    except Exception:
        items = []
    raw.setdefault(tag, {})[str(t)] = {"items": items, "tokens_in": a, "tokens_out": b}
    W, H = Image.open(frame_path(tag, t)).size
    d = {}
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        br = map_brand(str(it.get("brand", "")))
        bx = it.get("box_2d") or [0, 0, 0, 0]
        box = [bx[1] / 1000 * W, bx[0] / 1000 * H, bx[3] / 1000 * W, bx[2] / 1000 * H]
        if br is None:
            unmapped[str(it.get("brand"))] = unmapped.get(str(it.get("brand")), 0) + 1
            continue
        d.setdefault(br, []).append([round(v, 1) for v in box] + [1.0, it.get("brand"), "gemini"])
    hits.setdefault(tag, {})[str(t)] = d


def run_gemini(frames):
    from google.auth.transport.requests import Request
    cred = gcp_credentials()
    model = None
    for m in GEMINI_MODELS:
        try:
            gemini_call(m, frame_path(*frames[0]), cred.token)
            model = m
            break
        except Exception as e:
            print("model", m, "unavailable:", str(e)[:120])
    if model is None:
        raise SystemExit("no Gemini model answered")
    pin, pout = GEMINI_PRICE[model]
    raw, hits, times, tin, tout, spend, unmapped = {}, {}, [], 0, 0, 0.0, {}
    stopped = None
    ck = OUTDIR / f"partial_gemini_{model}.json"
    done = json.loads(ck.read_text()) if ck.exists() else {}
    t_tok = T0 = time.time()
    for i, (tag, t) in enumerate(frames):
        if time.time() - t_tok > 1500:
            cred = gcp_credentials()
            t_tok = time.time()
        key = f"{tag}:{t}"
        if key not in done and time.time() - T0 > 480:
            print("partial; rerun to continue"); raise SystemExit(3)
        if key in done:
            j, lat = done[key]["j"], done[key]["lat"]
            u = j.get("usageMetadata", {})
            a, b = u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
            cost = (a * pin + b * pout) / 1e6
            times.append(lat)
            tin += a
            tout += b
            spend += cost
            _record(j, tag, t, a, b, raw, hits, unmapped)
            continue
        p = frame_path(tag, t)
        t0 = time.perf_counter()
        try:
            j = gemini_call(model, p, cred.token)
        except Exception as e:
            print("error", tag, t, str(e)[:200])
            raw.setdefault(tag, {})[str(t)] = {"error": str(e)[:200]}
            continue
        lat = time.perf_counter() - t0
        times.append(lat)
        done[key] = {"j": j, "lat": lat}
        ck.write_text(json.dumps(done))
        u = j.get("usageMetadata", {})
        a, b = u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
        cost = (a * pin + b * pout) / 1e6
        try:
            charge("gemini_usd", round(cost, 6))
        except RuntimeError as e:
            stopped = str(e)
            print(stopped)
            break
        tin += a
        tout += b
        spend += cost
        _record(j, tag, t, a, b, raw, hits, unmapped)
    return raw, hits, times, dict(model=model, tokens_in=tin, tokens_out=tout, usd=round(spend, 4), unmapped=unmapped,
                                  stopped=stopped)


def finish(name, raw, hits, times, extra, notes):
    res = {"engine": name, "frames": sum(len(v) for v in hits.values()),
           "sec_per_frame": round(sum(times) / len(times), 3) if times else None,
           "sec_per_frame_note": "wall time per frame, single process, includes image load + all passes + API latency",
           "recall": recall(hits), "precision": precision(hits), "notes": notes, **extra}
    base = OUTDIR / "apple_baseline.json"
    if name != "apple_baseline" and base.exists():
        bh = json.loads(base.read_text())["hits"]
        mine, theirs = board_hits(hits), board_hits(bh)
        res["vs_apple_baseline"] = {"extra_gt_boards_found": sorted(mine - theirs), "n_extra": len(mine - theirs),
                                    "gt_boards_apple_only": len(theirs - mine)}
    res["hits"] = {tag: {t: {b: [h[:4] + [h[4]] for h in v] for b, v in d.items()} for t, d in td.items() if d}
                   for tag, td in hits.items()}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / f"{name}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    if raw is not None:
        (OUTDIR / f"raw_{name}.json").write_text(json.dumps(raw, ensure_ascii=False))
    r = res["recall"]["pooled"]
    p = res["precision"]
    print(name, "s/frame", res["sec_per_frame"], {k: f"{v['found']}/{v['of']}" for k, v in r.items()},
          f"precision {p['verified']}/{p['detected']} pending {p['unaudited_pending']}")
    return res


def sheets():
    """Contact sheets of hits that are neither labelled nor previously audited (all engines, deduplicated)."""
    from PIL import ImageDraw
    V = verdicts()
    todo = {}
    for f in sorted(OUTDIR.glob("*.json")):
        if f.name.startswith("raw_") or f.name == "verdicts.json":
            continue
        d = json.loads(f.read_text())
        if "hits" not in d:
            continue
        for tag, td in d["hits"].items():
            for t, bd in td.items():
                for b, boxes in bd.items():
                    k = (tag, int(t), b)
                    if known(*k) is None and k not in V:
                        cur = todo.setdefault(k, {"engines": set(), "box": boxes[0][:4]})
                        cur["engines"].add(d["engine"])
                        if (boxes[0][2] - boxes[0][0]) > (cur["box"][2] - cur["box"][0]):
                            cur["box"] = boxes[0][:4]
    items = sorted(todo.items())
    (OUTDIR / "sheets").mkdir(exist_ok=True)
    per = 12
    for s in range(0, len(items), per):
        sheet = Image.new("RGB", (4 * 480, 3 * 300), "white")
        dr = ImageDraw.Draw(sheet)
        for i, ((tag, t, b), v) in enumerate(items[s:s + per]):
            img = Image.open(frame_path(tag, t)).convert("RGB")
            x1, y1, x2, y2 = v["box"]
            mx, my = max(60, (x2 - x1) * 0.6), max(40, (y2 - y1) * 1.5)
            c = img.crop((int(max(0, x1 - mx)), int(max(0, y1 - my)), int(min(img.width, x2 + mx)),
                          int(min(img.height, y2 + my))))
            c.thumbnail((470, 270))
            ox, oy = (i % 4) * 480, (i // 4) * 300
            sheet.paste(c, (ox + 5, oy + 25))
            dr.text((ox + 5, oy + 5), f"#{s + i} {tag} t={t} {b}", fill="black")
        sheet.save(OUTDIR / "sheets" / f"unresolved_{s // per:02d}.jpg", quality=88)
    (OUTDIR / "sheets" / "index.json").write_text(json.dumps([[i, *k, sorted(v["engines"])] for i, (k, v) in
                                                              enumerate(items)], indent=0))
    print(len(items), "unresolved hits ->", (len(items) + per - 1) // per, "sheets")


def main():
    eng = sys.argv[1]
    if eng == "--sheets":
        return sheets()
    frames = labelled_frames()
    rescore = "--rescore" in sys.argv
    if rescore:
        old = json.loads((OUTDIR / f"{eng}.json").read_text())
        raw = json.loads((OUTDIR / f"raw_{eng}.json").read_text()) if (OUTDIR / f"raw_{eng}.json").exists() else None
        hits = {tag: {t: {b: [h + ["", ""] if len(h) == 5 else h for h in v] for b, v in d.items()} for t, d in td.items()}
                for tag, td in old["hits"].items()}
        for tag in TAGS:
            hits.setdefault(tag, {})
        times = [old["sec_per_frame"]] if old["sec_per_frame"] else []
        extra = {k: old[k] for k in ("api_units", "tokens", "spend_usd", "model") if k in old}
        return finish(eng, raw, hits, times, extra, old["notes"])
    if eng in ("apple_baseline", "apple_fullframe_only", "apple_no_zh"):
        cfg = {"apple_baseline": (True, True), "apple_fullframe_only": (False, False), "apple_no_zh": (True, False)}[eng]
        raw, hits, times = run_text_engine(eng, frames, lambda p: apple_frame(p, *cfg))
        notes = {"apple_baseline": "full frame + 3x2 upscaled tiles + Chinese-first full-frame pass (current pipeline)",
                 "apple_fullframe_only": "full-frame pass only (en+zh language preference), no tiles, no zh pass",
                 "apple_no_zh": "full frame + 3x2 upscaled tiles, no separate Chinese-first pass"}[eng]
        return finish(eng, raw, hits, times, {}, notes)
    if eng == "apple_parallel":
        fl = sorted((DATA / "wc_final" / "frames_1fps").glob("f_*.jpg"))[:320]
        res = {}
        for n in (1, 2, 4, 8):
            runs = []
            for rep in (1, 2):
                args = [(p, True, True) for p in fl]
                t0 = time.perf_counter()
                if n == 1:
                    ts = [_apple_worker(a) for a in args]
                else:
                    with mp.get_context("spawn").Pool(n) as pool:
                        ts = pool.map(_apple_worker, args, chunksize=4)
                wall = time.perf_counter() - t0
                runs.append({"wall_s": round(wall, 1), "frames_per_sec": round(len(fl) / wall, 3),
                             "mean_frame_latency_s": round(sum(ts) / len(ts), 3)})
                print(n, rep, runs[-1], flush=True)
            res[str(n)] = runs
        out = {"engine": "apple_parallel", "frames": len(fl), "tag": "wc_final", "first_frame": fl[0].name,
               "last_frame": fl[-1].name, "pipeline": "full + 3x2 tiles + zh (baseline)", "settings": res,
               "notes": "spawn Pool(n).map over frames; each setting run twice back to back; cpu_count=" +
                        str(mp.cpu_count())}
        OUTDIR.mkdir(parents=True, exist_ok=True)
        (OUTDIR / "apple_parallel.json").write_text(json.dumps(out, indent=1))
        return
    if eng in ("paddleocr", "tesseract"):
        reader = paddle_read if eng == "paddleocr" else tess_read
        warm = (lambda: reader(Image.new("RGB", (200, 80), "white"))) if eng == "paddleocr" else None
        raw, hits, times = run_text_engine(eng, frames, lambda p: generic_frame(p, reader), warm, budget_s=480)
        notes = ("PaddleOCR PP-OCRv5 (default multilingual zh/en models, CPU), full frame + 3x2 tiles upscaled 2x/3x"
                 if eng == "paddleocr" else
                 "Tesseract 5.5.2, eng traineddata only (no Chinese pack installed), --psm 11, full frame + 3x2 tiles "
                 "upscaled 2x/3x")
        return finish(eng, raw, hits, times, {}, notes)
    if eng == "cloud_vision_text":
        from google.cloud import vision
        client = vision.ImageAnnotatorClient(credentials=gcp_credentials())
        raw, hits, times = {}, {}, []
        charge("vision_images", len(frames))
        for tag, t in frames:
            t0 = time.perf_counter()
            r = cloud_vision_frame(client, frame_path(tag, t))
            times.append(time.perf_counter() - t0)
            raw.setdefault(tag, {})[str(t)] = r
            hits.setdefault(tag, {})[str(t)] = match(r)
        return finish(eng, raw, hits, times, {"api_units": {"vision_images": len(frames)}, "spend_usd": 0.0},
                      "Cloud Vision TEXT_DETECTION, one call per full 1080p/720p frame, words and paragraphs matched; "
                      "free tier (<=1000 units/month)")
    if eng == "gemini_flash":
        raw, hits, times, g = run_gemini(frames)
        n = max(1, len(times))
        return finish(eng, raw, hits, times,
                      {"model": g["model"], "tokens": {"in": g["tokens_in"], "out_incl_thinking": g["tokens_out"],
                                                       "in_per_frame": round(g["tokens_in"] / n),
                                                       "out_per_frame": round(g["tokens_out"] / n)},
                       "spend_usd": g["usd"], "unmapped_brand_names": g["unmapped"], "stopped": g["stopped"],
                       "price_usd_per_1M": {"in": GEMINI_PRICE[g["model"]][0], "out": GEMINI_PRICE[g["model"]][1]}},
                      f"{g['model']} via Vertex AI (global), image + prompt asking for sponsor board brand names + boxes")
    raise SystemExit("unknown engine " + eng)


if __name__ == "__main__":
    main()

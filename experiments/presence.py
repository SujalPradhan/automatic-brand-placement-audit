"""Per-second brand presence for a video, fused from OCR and Video Intelligence, minus audited rejects.

presence(tag) -> {brand: {t: {"area": frac, "h": box_height_frac, "box": [x1,y1,x2,y2] px, "src": "ocr|vi|both"}}}
"""
import csv
import json

from common import EVIDENCE, VI_ALIASES, norm_brand

VIDEO = {
    "wc_final": {"label": "2022 final · Argentina v France", "short": "2022 final", "duration": 716, "size": (1920, 1080)},
    "wc2026": {"label": "2026 group stage · Brazil v Morocco", "short": "2026 group game", "duration": 600, "size": (1280, 720)},
    "wc2026_final": {"label": "2026 final · Spain v Argentina", "short": "2026 final", "duration": 117, "size": (1920, 1080)},
}
# Full-match runs (kept out of VIDEO so that 16_score.py, which iterates VIDEO, is unaffected)
FULL = {
    "full_bra": {"label": "2022 round of 16 · Brazil v South Korea (full match)", "short": "Brazil v Korea", "duration": 6246, "size": (1920, 1080)},
    "full_por": {"label": "2018 group B · Portugal v Spain (full match)", "short": "Portugal v Spain", "duration": 6005, "size": (1920, 1080)},
}


def _ocr(tag):
    o = json.loads((EVIDENCE / f"ocr_{tag}.json").read_text())
    W, H = o["frame_size"]
    out = {}
    for t, d in o["per_second"].items():
        for b, boxes in d.items():
            big = max(boxes, key=lambda x: (x[2] - x[0]) * (x[3] - x[1]))
            area = sum((x[2] - x[0]) * (x[3] - x[1]) for x in boxes) / (W * H)
            out.setdefault(b, {})[int(t)] = {"area": min(area, 1.0), "h": (big[3] - big[1]) / H,
                                             "box": [round(v) for v in big[:4]], "src": "ocr"}
    return out


def _vi(tag):
    p = EVIDENCE / f"vi_{tag}.json"
    if not p.exists():
        return {}
    W, H = {**VIDEO, **FULL}[tag]["size"]
    vi = json.loads(p.read_text())
    out = {}
    for l in vi["logos"]:
        b = VI_ALIASES.get(norm_brand(l["entity"]))
        if not b:
            continue  # unmapped catalogue labels (e.g. 'Musixmatch' on Crypto.com boards) are not trusted
        for tr in l["tracks"]:
            for ts, x1, y1, x2, y2 in tr["boxes"]:
                t = round(ts)
                a = (x2 - x1) * (y2 - y1)
                cur = out.setdefault(b, {}).get(t)
                if cur is None or a > cur["area"]:
                    out[b][t] = {"area": min(a, 1.0), "h": y2 - y1,
                                 "box": [round(x1 * W), round(y1 * H), round(x2 * W), round(y2 * H)], "src": "vi"}
    return out


def rejects(tag):
    """Audited false detections: rows of brand,start,end (inclusive seconds)."""
    p = EVIDENCE / "audit" / f"{tag}_rejects.csv"
    bad = set()
    if p.exists():
        for r in csv.DictReader(p.open()):
            for t in range(int(r["start"]), int(r["end"]) + 1):
                bad.add((r["brand"], t))
    return bad


KIT_ONLY = {"Nike", "Puma"}  # brands that appear only on kits in these videos


def kit_marks(tag):
    """Audited kit appearances of brands that also have boards (evidence/audit/<tag>_kit.csv)."""
    p = EVIDENCE / "audit" / f"{tag}_kit.csv"
    kit = set()
    if p.exists():
        for r in csv.DictReader(p.open()):
            for t in range(int(r["start"]), int(r["end"]) + 1):
                kit.add((r["brand"], t))
    return kit


def presence(tag, sources=("ocr", "vi"), audited=True, kit=False):
    """Board/perimeter presence by default; kit=True returns only the kit marks (kept out of the analysis)."""
    parts = [f(tag) for s, f in (("ocr", _ocr), ("vi", _vi)) if s in sources]
    bad = rejects(tag) if audited else set()
    kits = kit_marks(tag)
    out = {}
    for part in parts:
        for b, d in part.items():
            for t, v in d.items():
                if (b, t) in bad:
                    continue
                is_kit = b in KIT_ONLY or (b, t) in kits
                if is_kit != kit:
                    continue
                cur = out.setdefault(b, {}).get(t)
                if cur is None:
                    out[b][t] = dict(v)
                else:
                    if v["area"] > cur["area"]:
                        cur.update(area=v["area"], h=v["h"], box=v["box"])
                    if v["src"] != cur["src"]:
                        cur["src"] = "both"
    return out


def runs(ts, gap=1):
    """Group sorted seconds into appearances, merging gaps of <= gap missed samples."""
    out = []
    for t in sorted(ts):
        if out and t - out[-1][1] <= gap + 1:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out

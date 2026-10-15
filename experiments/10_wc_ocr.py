"""Local OCR (Apple Vision via ocrmac) over every 1 fps frame of the WC final + fuzzy brand lexicon.

Most perimeter-board sponsors are wordmarks, so reading the text is a cheap brand identifier.
Output evidence/wc_ocr.json: per_second[t] = {brand: [[x1,y1,x2,y2,score,text], ...]} (pixel boxes, 1920x1080)
"""
import json
import sys
import time

from ocrmac import ocrmac
from common import DATA, EVIDENCE, text_matches

FR = DATA / "wc_final" / "frames_1fps"
W, H = 1920, 1080
# brand -> lexicon of wordmarks / board taglines seen on the boards
LEX = {
    "QatarAirways": ["qatarairways", "worldsbestairline", "flythroughdoha"],
    "Hyundai": ["hyundai", "ioniq", "goalofthecentury"],
    "Wanda": ["wanda", "万达文旅", "万达"],
    "Visa": ["visa"],
    "Vivo": ["vivo"],
    "Budweiser": ["budweiser", "bringhomethebud"],
    "CryptoCom": ["cryptocom"],
    "CocaCola": ["cocacola", "believingismagic"],
    "McDonalds": ["mcdonalds", "wedeliver"],
    "QatarEnergy": ["qatarenergy"],
    "Nubank": ["nubank"],
    "Claro": ["claro"],
    "UPL": ["upl", "reimaginingsustainability"],
    "InterRapidisimo": ["interrapidisimo", "rapidisimo"],
    "Mengniu": ["mengniu", "蒙牛"],
    "Hisense": ["hisense"],
    "BYJUS": ["byjus"],
    "Adidas": ["adidas"],
}


def match(text):
    return [(b, sc / 100) for b, words in LEX.items() if (sc := text_matches(text, words))]


OUT = EVIDENCE / "wc_ocr.json"
REMATCH = "--rematch" in sys.argv  # re-run only the lexicon matching on saved OCR text
prev = json.loads(OUT.read_text()) if REMATCH else None
per_second, raw, times = {}, {}, []
for p in sorted(FR.glob("f_*.jpg")):
    t = int(p.stem[2:]) - 1
    if REMATCH:
        res = [(x[0], x[1], x[2]) for x in prev["raw"][str(t)]]
    else:
        t0 = time.perf_counter()
        res = ocrmac.OCR(str(p), recognition_level="accurate", language_preference=["en-US", "zh-Hans"]).recognize()
        times.append(time.perf_counter() - t0)
    raw[t] = [[r[0], round(r[1], 3), [round(v, 4) for v in r[2]]] for r in res]
    per_second[t] = {}
    for text, conf, (x, y, w, h) in res:
        for brand, s in match(text):
            box = [x * W, (1 - y - h) * H, (x + w) * W, (1 - y) * H]  # Vision uses bottom-left origin
            per_second[t].setdefault(brand, []).append([round(v, 1) for v in box] + [round(s * conf, 3), text])

spf = prev["sec_per_frame_mean"] if REMATCH else round(sum(times) / len(times), 3)
OUT.write_text(json.dumps({
    "engine": "Apple Vision (ocrmac, accurate)", "sec_per_frame_mean": spf,
    "lexicon": LEX, "per_second": per_second, "raw": raw}, ensure_ascii=False))
counts = {}
for d in per_second.values():
    for b in d:
        counts[b] = counts.get(b, 0) + 1
print("s/frame", spf, "seconds with brand:", sorted(counts.items(), key=lambda x: -x[1]))

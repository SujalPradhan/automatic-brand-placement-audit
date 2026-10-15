"""Shared helpers for the feasibility experiments."""
import json
import os
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EVIDENCE = ROOT / "evidence"
EE = DATA / "exposureengine"

GCP_PROJECT = os.environ.get("GCP_PROJECT", "")  # your GCP project id (only needed for the Google engines)
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")    # bucket for Video Intelligence uploads
USAGE_FILE = EVIDENCE / "gcp_usage.json"
CAPS = {"vision_images": 900, "video_minutes": 250, "gemini_usd": 2.0}  # stay inside monthly free tiers


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def ee_pairs(split):
    """(image_path, label_path) for ExposureEngine frames that have both files."""
    out = []
    for img in sorted((EE / split / "images").glob("*.jpg")):
        lab = EE / split / "labels" / f"{img.stem}.txt"
        if lab.exists():
            out.append((img, lab))
    return out


def load_obb_labels(label_path, w, h):
    """YOLO-OBB lines -> list of (class_id, aabb [x1,y1,x2,y2] in pixels, polygon Nx2)."""
    boxes = []
    for line in Path(label_path).read_text().splitlines():
        parts = line.split()
        if len(parts) != 9:
            continue
        pts = np.array(parts[1:], dtype=float).reshape(4, 2) * [w, h]
        x1, y1 = pts.min(0)
        x2, y2 = pts.max(0)
        boxes.append((int(parts[0]), [x1, y1, x2, y2], pts))
    return boxes


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def match(preds, gts, thr):
    """Greedy one-to-one matching by IoU. Returns (tp, fp, fn, matched_pairs)."""
    pairs = sorted(((iou(p, g), i, j) for i, p in enumerate(preds) for j, g in enumerate(gts)), reverse=True)
    used_p, used_g, matched = set(), set(), []
    for v, i, j in pairs:
        if v < thr:
            break
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        matched.append((i, j, v))
    tp = len(matched)
    return tp, len(preds) - tp, len(gts) - tp, matched


def charge(kind, amount):
    """Record GCP usage and refuse to exceed the free-tier caps."""
    EVIDENCE.mkdir(exist_ok=True)
    usage = json.loads(USAGE_FILE.read_text()) if USAGE_FILE.exists() else {}
    used = usage.get(kind, 0)
    if used + amount > CAPS[kind]:
        raise RuntimeError(f"GCP cap hit for {kind}: {used}+{amount} > {CAPS[kind]}")
    usage[kind] = used + amount
    USAGE_FILE.write_text(json.dumps(usage, indent=2))


GCP_ACCOUNT = os.environ.get("GCP_ACCOUNT", "")  # account that owns GCP_PROJECT; token comes from `gcloud auth print-access-token`


def _need_gcp():
    if not GCP_PROJECT or not GCP_ACCOUNT:
        raise SystemExit("Set GCP_PROJECT and GCP_ACCOUNT (see .env.example) to use the Google engines.")


def gcp_client_options():
    _need_gcp()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", GCP_PROJECT)
    return {"quota_project_id": GCP_PROJECT}


def gcp_credentials():
    """Short-lived user token for GCP_ACCOUNT from the gcloud CLI (valid ~1h)."""
    import subprocess

    from google.oauth2.credentials import Credentials
    _need_gcp()
    token = subprocess.check_output(
        ["gcloud", "auth", "print-access-token", f"--account={GCP_ACCOUNT}"], text=True).strip()
    return Credentials(token=token, quota_project_id=GCP_PROJECT)


def norm_brand(s):
    return re.sub(r"[^a-z]", "", s.lower())


# Video Intelligence entity description -> brand key used in GT and metrics
VI_ALIASES = {
    "mcdonalds": "McDonalds", "vivo": "Vivo", "hyundai": "Hyundai", "hyundaimotorcompany": "Hyundai",
    "cocacola": "CocaCola", "wanda": "Wanda", "wandagroup": "Wanda", "dalianwanda": "Wanda",
    "budweiser": "Budweiser", "cryptocom": "CryptoCom", "qatarairways": "QatarAirways",
    "qatarenergy": "QatarEnergy", "visa": "Visa", "visainc": "Visa", "nike": "Nike", "valvolineinstantoilchange": "Valvoline", "verizonwireless": "Verizon", "hyundaimotorgroup": "Hyundai", "puma": "Puma", "lays": "Lays", "fritolay": "Lays", "mengniu": "Mengniu", "mengniudairy": "Mengniu",
    "nubank": "Nubank", "claro": "Claro", "upl": "UPL", "interrapidisimo": "InterRapidisimo", "adidas": "Adidas", "hisense": "Hisense", "lenovo": "Lenovo", "saudiaramco": "Aramco", "aramco": "Aramco", "verizon": "Verizon", "verizoncommunications": "Verizon", "bankofamerica": "BankOfAmerica", "michelobultra": "MichelobUltra", "kraken": "Kraken", "betano": "Betano", "dove": "Dove", "valvoline": "Valvoline", "globant": "Globant", "marriottbonvoy": "MarriottBonvoy", "marriottinternational": "MarriottBonvoy", "unileverdove": "Dove", "mcdonaldscorporation": "McDonalds", "thecocacolacompany": "CocaCola", "visainc": "Visa", "nike": "Nike", "valvolineinstantoilchange": "Valvoline", "verizonwireless": "Verizon", "hyundaimotorgroup": "Hyundai", "puma": "Puma", "lays": "Lays", "fritolay": "Lays",
    "powerade": "Powerade", "fanatics": "Fanatics", "fanaticsinc": "Fanatics", "doordash": "DoorDash",
    "mercadolibre": "MercadoLibre", "mercadolivre": "MercadoLibre",
}


def norm_text(s):
    return re.sub(r"[^0-9a-z一-鿿]", "", s.lower())


def text_matches(text, words):
    """Best fuzzy score (0-100) of an OCR string against a brand's lexicon words.

    A fragment shorter than the word must cover >= 55% of it (so 'ENTE' or 'VISA' can't match inside a long
    tagline); short words (<= 5 chars) must match a whole token.
    """
    from rapidfuzz import fuzz
    t = norm_text(text)
    toks = [norm_text(x) for x in re.split(r"[\s|/•·,]+", text) if norm_text(x)]
    best = 0
    for w in words:
        if len(w) <= 5:
            s = max((fuzz.ratio(x, w) for x in toks), default=0)
            s = s if s >= 80 else 0
        elif len(t) >= len(w):
            s = fuzz.partial_ratio(w, t)
            s = s if s >= 80 else 0
        elif len(t) >= 0.55 * len(w):
            s = fuzz.partial_ratio(t, w)
            s = s if s >= 88 else 0
        else:
            s = 0
        best = max(best, s)
    return best


# Sponsor wordmarks and board taglines seen on the perimeter boards of the two videos (lower-case, no spaces).
# Taglines count only when they are unique to one brand (e.g. "We Deliver" = McDonald's, "Step in with Visa").
LEXICON = {
    "QatarAirways": ["qatarairways", "worldsbestairline", "flythroughdoha"],
    "Hyundai": ["hyundai", "ioniq", "goalofthecentury"],
    "Wanda": ["wanda", "万达文旅", "万达", "达文旅"],
    "Visa": ["visa", "stepinwithvisa"],
    "Vivo": ["vivo"],
    "Budweiser": ["budweiser", "bringhomethebud", "bud"],
    "MichelobUltra": ["michelobultra", "michelob", "superiorlightbeer"],
    "CryptoCom": ["cryptocom"],
    "Kraken": ["kraken", "investtradeown"],
    "CocaCola": ["cocacola", "believingismagic"],
    "McDonalds": ["mcdonalds", "wedeliver", "mcdelivery"],
    "QatarEnergy": ["qatarenergy"],
    "Aramco": ["aramco", "globalenergypartner"],
    "Lenovo": ["lenovo", "联想"],
    "Hisense": ["hisense", "海信"],
    "Mengniu": ["mengniu", "蒙牛", "自然力量", "天生要强", "今晚彻底不慌了", "赛场硬实力", "营养软吸收", "试试软牛奶", "软牛奶"],
    "BYJUS": ["byjus"],
    "Adidas": ["adidas"],
    "ADIPredictstreet": ["adipredictstreet", "predictstreet"],  # v3: was wrongly folded into Adidas in v2
    "Nubank": ["nubank"],
    "Claro": ["claro"],
    "UPL": ["upl", "reimaginingsustainability"],
    "InterRapidisimo": ["interrapidisimo", "rapidisimo"],
    "Betano": ["betano"],
    "Verizon": ["verizon"],
    "BankOfAmerica": ["bankofamerica"],
    "Dove": ["dove"],
    "Valvoline": ["valvoline"],
    "Globant": ["globant"],
    "MarriottBonvoy": ["marriottbonvoy", "marriott"],
    "SavvyGames": ["savvygamesgroup", "savvygames"],
    "Lays": ["lays"],
    "Powerade": ["powerade"],
    "Fanatics": ["fanatics"],
    "DoorDash": ["doordash"],
    "MercadoLibre": ["mercadolibre", "mercadolivre"],
    # added after the full-match runs (2022 round of 16 boards seen in frames; tiers not set because unconfirmed)
    "BossZhipin": ["boss", "boss直聘", "bosszhipin"],
    "Ooredoo": ["ooredoo"],
    "QNB": ["qnb"],
    "FuzeTea": ["fuzetea"],
    "Smartwater": ["smartwater"],
    "MinuteMaid": ["minutemaid"],
    "CostaCoffee": ["costacoffee"],
    # added after the 2018 full-match run (Russia 2018 boards)
    "Gazprom": ["gazprom"],
    "Alrosa": ["alrosa"],
    "AlfaBank": ["alfabank", "альфабанк"],
}

# Display name and home country (company headquarters) for each brand key.
BRAND_INFO = {
    "QatarAirways": ("Qatar Airways", "Qatar"), "Hyundai": ("Hyundai", "South Korea"),
    "Wanda": ("Wanda", "China"), "Visa": ("Visa", "USA"), "Vivo": ("Vivo", "China"),
    "Budweiser": ("Budweiser", "Belgium/USA"), "MichelobUltra": ("Michelob Ultra", "Belgium/USA"),
    "CryptoCom": ("Crypto.com", "Singapore"), "Kraken": ("Kraken", "USA"), "CocaCola": ("Coca-Cola", "USA"),
    "McDonalds": ("McDonald's", "USA"), "QatarEnergy": ("QatarEnergy", "Qatar"), "Aramco": ("Aramco", "Saudi Arabia"),
    "Lenovo": ("Lenovo", "China"), "Hisense": ("Hisense", "China"), "Mengniu": ("Mengniu", "China"),
    "BYJUS": ("BYJU'S", "India"), "Adidas": ("Adidas", "Germany"), "Nubank": ("Nubank", "Brazil"),
    "Claro": ("Claro", "Mexico"), "UPL": ("UPL", "India"), "InterRapidisimo": ("Inter Rapidísimo", "Colombia"),
    "Betano": ("Betano", "Greece"), "Verizon": ("Verizon", "USA"), "BankOfAmerica": ("Bank of America", "USA"),
    "Dove": ("Dove", "UK"), "Valvoline": ("Valvoline", "USA"), "Globant": ("Globant", "Argentina"),
    "MarriottBonvoy": ("Marriott Bonvoy", "USA"), "SavvyGames": ("Savvy Games Group", "Saudi Arabia"),
    "Lays": ("Lay's", "USA"), "Nike": ("Nike", "USA"), "Puma": ("Puma", "Germany"),
    "ADIPredictstreet": ("ADI Predictstreet", "UAE"), "Powerade": ("Powerade", "USA"), "Fanatics": ("Fanatics", "USA"),
    "DoorDash": ("DoorDash", "USA"), "MercadoLibre": ("Mercado Libre", "Argentina"),
    "BossZhipin": ("BOSS Zhipin", "China"), "Ooredoo": ("Ooredoo", "Qatar"), "QNB": ("QNB", "Qatar"),
    "FuzeTea": ("Fuze Tea", "USA"), "Smartwater": ("Smartwater", "USA"), "MinuteMaid": ("Minute Maid", "USA"),
    "CostaCoffee": ("Costa Coffee", "UK"), "Gazprom": ("Gazprom", "Russia"), "Alrosa": ("Alrosa", "Russia"),
    "AlfaBank": ("Alfa-Bank", "Russia"),
}


# FIFA sponsor tier per tournament (Partner > World Cup Sponsor > Regional/Tournament Supporter).
# Sources: FIFA media releases and Sportcal/SportBusiness/Inside World Football coverage (see story/index.html).
TIERS = {
    "wc_final": {
        "Partner": ["Adidas", "CocaCola", "Hyundai", "QatarAirways", "QatarEnergy", "Visa", "Wanda",
                    "Powerade"],  # Powerade: Coca-Cola Company brand on its partner inventory (inferred)
        "Sponsor": ["Budweiser", "BYJUS", "CryptoCom", "Hisense", "McDonalds", "Mengniu", "Vivo"],
        "Supporter": ["Nubank", "Claro", "UPL", "InterRapidisimo"],
    },
    "wc2026": {
        "Partner": ["Adidas", "CocaCola", "Hyundai", "QatarAirways", "Aramco", "Visa", "Lenovo",
                    "ADIPredictstreet",  # FIFA release 2 Apr 2026: "FIFA Partner", prediction-market category
                    "Powerade"],  # Coca-Cola Company brand on its partner inventory (inferred)
        "Sponsor": ["BankOfAmerica", "Verizon", "Hisense", "Mengniu", "Budweiser", "MichelobUltra", "McDonalds",
                    "Lays", "Dove"],
        "Supporter": ["Betano", "Globant", "InterRapidisimo", "Kraken", "MarriottBonvoy", "Valvoline",
                      "SavvyGames",  # Savvy Games Group: PIF-owned; PIF is a listed supporter (unconfirmed)
                      "DoorDash",  # FIFA, 18 Nov 2025: Official Tournament Supporter
                      "MercadoLibre",  # Latin America e-commerce supporter (secondary source only; unconfirmed)
                      "Fanatics"],  # FIFA on-site retail licensee, not a named sponsor tier; grouped here (inferred)
    },
}


TIERS["wc2018"] = {  # Russia 2018 (FIFA Partners / World Cup Sponsors / Russia 2018 supporters; Powerade inferred as in 2022)
    "Partner": ["Adidas", "CocaCola", "Gazprom", "Hyundai", "QatarAirways", "Visa", "Wanda", "Powerade"],
    "Sponsor": ["Budweiser", "Hisense", "McDonalds", "Mengniu", "Vivo"],
    "Supporter": ["Alrosa", "AlfaBank"],
}

TIER_SET = {"wc_final": "wc_final", "wc2026": "wc2026", "wc2026_final": "wc2026", "full_bra": "wc_final", "full_por": "wc2018"}  # clip tag -> tournament


def tier_of(tag, brand):
    return next((t for t, bs in TIERS[TIER_SET.get(tag, tag)].items() if brand in bs), "Other")

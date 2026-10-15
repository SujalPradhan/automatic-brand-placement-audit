"""Cost of auditing 100,000 hours of video (Anand's scale), per option, from measured speeds and confirmed prices.

Inputs: evidence/pricing.json (every rate with source), evidence/engines/*.json (measured speed/tokens/recall),
evidence/full_bra_scores.json (full-match throughput is recorded in BENCHMARKS.md v4).
Output: evidence/cost_model.json. Every figure on story/cost.html is generated from that file.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
price = {i["id"]: i for i in json.loads((EV / "pricing.json").read_text())["items"]}


def p(i):
    it = price[i]
    assert it["confirmed"] and it["price_usd"] is not None, f"price {i} is not confirmed"
    return it["price_usd"]


HOURS = 100_000
SECONDS = HOURS * 3600           # 1 fps sampling -> one frame per second
FRAMES = SECONDS
MINUTES = HOURS * 60
assert FRAMES == 360_000_000 and MINUTES == 6_000_000

eng = {n: json.loads((EV / "engines" / f"{n}.json").read_text()) for n in
       ("apple_baseline", "apple_fullframe_only", "paddleocr", "tesseract", "cloud_vision_text", "gemini_flash")}


def recall(n):
    r = eng[n]["recall"]["pooled"]
    return {"all": r["all"]["recall"], "small": r["small"]["recall"], "large": r["large"]["found"] / r["large"]["of"],
            "found": r["all"]["found"], "of": r["all"]["of"]}


# ---- measured throughput of Apple Vision (frames per second, whole machine) --------------------------------------
# Full matches (BRA 6,246 frames in ~2,260 s; POR 6,005 in ~2,310 s), baseline pipeline, 4 workers (BENCHMARKS.md v4).
FPS_4W = (6246 + 6005) / (2260 + 2310)
# 300-frame scaling test, 8 workers (same pipeline), mean of the two timed runs of the full-match agent: 4.35 fps.
FPS_8W = 4.35
# Full-frame-only pass: single process, 0.139 s/frame (evidence/engines/apple_fullframe_only.json).
FPS_FF_1W = 1 / eng["apple_fullframe_only"]["sec_per_frame"]

HOST = p("ec2_mac_m4")  # $/host-hour, dedicated host, 24 h minimum


def apple(fps):
    host_hours = FRAMES / fps / 3600
    return {"host_hours": round(host_hours), "usd": round(host_hours * HOST), "fps": round(fps, 2)}


opts = []


def add(id, name, usd_low, usd_high, rec, basis, measured, note=""):
    o = {"id": id, "name": name, "usd_low": round(usd_low), "usd_high": round(usd_high),
         "usd_per_video_hour_low": round(usd_low / HOURS, 2), "usd_per_video_hour_high": round(usd_high / HOURS, 2),
         "recall_all": rec.get("all") if rec else None, "recall_small": rec.get("small") if rec else None,
         "recall_large": rec.get("large") if rec else None,
         "basis": basis, "accuracy_measured": measured, "note": note}
    assert usd_low <= usd_high
    opts.append(o)


# End-to-end seconds per video hour, extraction included. Low = the timed one-hour run on an otherwise idle Mac
# (evidence/timing_hour_run.json); high = full-match OCR speed (shared Mac) + the slower measured extraction.
T = json.loads((EV / "timing_hour_run.json").read_text())
T8 = json.loads((EV / "timing_hour_run_8w.json").read_text())
H22 = json.loads((EV / "timing_hl2022_8w.json").read_text())
H26 = json.loads((EV / "timing_hl2026_8w.json").read_text())
per_hour = lambda r: r["total_s"] / r["frames"] * 3600       # end-to-end seconds per video hour
runs8 = {"full-match hour, 1080p30": per_hour(T8), "2022 final highlights, 1080p50": per_hour(H22),
         "2026 group highlights, 720p60": per_hour(H26)}
assert T8["workers"] == H22["workers"] == H26["workers"] == 8
assert T["seconds"] == 3600 and T["frames"] == 3600
EXTRACT_LO = T["extract_s"]                       # 54.3 s per video hour (idle Mac)
EXTRACT_HI = 141 / 6005 * 3600                    # Portugal full match: 141 s for 6,005 s of video
OCR_LO = T["ocr_s"]                               # 1,185.8 s, 4 workers
OCR_HI = 3600 / FPS_4W                            # full matches, 4 workers
SEC_4W = (T["total_s"], OCR_HI + EXTRACT_HI)
SEC_8W = (min(runs8.values()), max(runs8.values()))
SEC_FF = (3600 / FPS_FF_1W + EXTRACT_LO, 3600 / FPS_FF_1W + EXTRACT_HI)
usd_h = lambda sec: sec / 3600 * HOST * HOURS      # cost for 100,000 hours
A4_LO, A4_HI = usd_h(SEC_4W[0]), usd_h(SEC_4W[1])
A8_LO, A8_HI = usd_h(SEC_8W[0]), usd_h(SEC_8W[1])
HH4 = HOURS * SEC_4W[1] / 3600                     # host-hours at the conservative speed
HH8 = HOURS * SEC_8W[1] / 3600

add("apple_4w", "Apple Vision OCR on EC2 Mac, 4 workers, start to finish", A4_LO, A4_HI, recall("apple_baseline"),
    f"{SEC_4W[0] / 60:.1f} to {SEC_4W[1] / 60:.1f} min per video hour x ${HOST}/h; frame extraction included", True,
    "low: timed one-hour run on an idle Mac; high: full-match speed on a shared Mac")
add("apple_8w", "Apple Vision OCR on EC2 Mac, 8 workers, start to finish", A8_LO, A8_HI, recall("apple_baseline"),
    f"{SEC_8W[0] / 60:.1f} to {SEC_8W[1] / 60:.1f} min per video hour x ${HOST}/h; frame extraction included", True,
    "three timed runs on an idle Mac (full-match hour, two highlight clips); the EC2 host's own speed is not measured")
add("apple_fullframe", "Apple Vision, full frame only (1 worker)", usd_h(SEC_FF[0]), usd_h(SEC_FF[1]), recall("apple_fullframe_only"),
    f"{SEC_FF[0] / 60:.1f} to {SEC_FF[1] / 60:.1f} min per video hour x ${HOST}/h; frame extraction included", True,
    "single process; more workers would be cheaper, not measured")

# Gemini Flash-Lite: measured tokens per frame, two confirmed rates (standard / batch) of the 3.5 Flash-Lite listing.
g = eng["gemini_flash"]["tokens"]
tin, tout = g["in_per_frame"], g["out_per_frame"]
std = (tin * p("gemini_3_5_flash_lite_input_per_1m") + tout * p("gemini_3_5_flash_lite_output_per_1m")) / 1e6
bat = (tin * p("gemini_3_5_flash_lite_batch_input_per_1m") + tout * p("gemini_3_5_flash_lite_batch_output_per_1m")) / 1e6
add("gemini", "Gemini Flash-Lite reading every frame", bat * FRAMES, std * FRAMES, recall("gemini_flash"),
    f"{tin} in + {tout} out tokens per frame (measured); ${bat:.5f} (batch) to ${std:.5f} (standard) per frame", True,
    "tokens were measured on gemini-3.1-flash-lite; priced at the confirmed 3.5 Flash-Lite rates")

# Cloud Vision text detection per frame: $1.50/1000 for units 1,001-5M a month, $0.60/1000 beyond (first 1,000 free ignored).
cv_rate1, cv_rate2 = p("vision_text_detection_per_1000") / 1000, 0.60 / 1000
one_month = 5_000_000 * cv_rate1 + (FRAMES - 5_000_000) * cv_rate2
per_month = FRAMES / 12
twelve = 12 * (5_000_000 * cv_rate1 + (per_month - 5_000_000) * cv_rate2)
add("cloud_vision", "Google Cloud Vision text detection per frame", one_month, twelve, recall("cloud_vision_text"),
    "one call per frame; low = all in one month, high = spread over 12 months", True)

# Video Intelligence logo detection: $0.15/min after 1,000 free; lower tiers are $0.135 and $0.12 (boundaries not stated).
vi_hi = (MINUTES - 1000) * p("vi_logo_per_min")
vi_lo = (MINUTES - 1000) * 0.12
_sc = json.loads((EV / "scores.json").read_text())  # v3 per-game VI counts on the same 156 frames
_vi = lambda k: sum(_sc[g]["vi"][k]["found"] for g in _sc if "vi" in _sc[g]) / sum(_sc[g]["vi"][k]["of"] for g in _sc if "vi" in _sc[g])
vi_rec = {"all": _vi("board_all"), "small": _vi("board_S"), "large": _vi("board_L")}
assert abs(vi_rec["large"] - 66 / 130) < 1e-9 and abs(vi_rec["small"] - 13 / 46) < 1e-9
add("vi", "Google Video Intelligence logo detection", vi_lo, vi_hi, vi_rec,
    "6,000,000 minutes x $0.12-$0.15", True, "$0.15 is the list price; $0.135 and $0.12 are the 1-year and 3-year savings-plan commitment rates")

# Rekognition DetectText per frame: per-image tiers 0.001 (to 1M), 0.0008 (to 5M), 0.0006 (to 35M), 0.00025 beyond, per month.
def rek_text(images):
    t = [(1_000_000, 0.001), (5_000_000, 0.0008), (35_000_000, 0.0006), (float("inf"), 0.00025)]
    cost, lo = 0.0, 0
    for hi, r in t:
        n = max(0, min(images, hi) - lo)
        cost += n * r
        lo = hi
    return cost
rt_one, rt_year = rek_text(FRAMES), 12 * rek_text(FRAMES / 12)
assert round(rt_one) == 103_450
add("rekognition_text", "AWS Rekognition text detection per frame", rt_one, rt_year, None,
    "per-image tiers from the AWS price file; low = all in one month, high = spread over 12 months", False,
    "price only: accuracy not measured")

# Rekognition: priced only. Rate is for stored video; mapping to text detection not stated in the price file.
rek = MINUTES * p("rekognition_video_archived_per_min")
add("rekognition", "AWS Rekognition Video, stored video (text detection is on this rate)", rek, rek, None, "6,000,000 minutes x $0.10", False,
    "price only: accuracy not measured, and the price file does not say which operation this rate covers")

# Not costed: PaddleOCR (25.6 s/frame on one CPU process; instance parallelism not measured), Tesseract (recall 0.18).
not_costed = [
    {"name": "PaddleOCR", "why": "accurate (recall 0.73) but 25.6 s/frame on one CPU process; per-instance parallelism not measured",
     "recall_all": recall("paddleocr")["all"]},
    {"name": "Tesseract", "why": "recall 0.18 and precision 0.41 on our frames",
     "recall_all": recall("tesseract")["all"]},
]

# ---- wall-clock for the Apple options with N hosts ------------------------------------------------------------------
def wall(host_hours, n):
    return host_hours / n

speed = [{"hosts": n, "apple_4w_days": round(wall(HH4, n) / 24, 1),
          "apple_8w_days": round(wall(HH8, n) / 24, 1)} for n in (1, 10, 100, 1000)]

# ---- processing time for one hour of video, per option (minutes of wall-clock, one stream) -------------------------
VI_MIN = (95 + 10) / 104 * 60   # full match: ~95 min Google processing + ~10 min upload for a 104-min video
mins = {
    "apple_4w": SEC_4W[1] / 60, "apple_8w": SEC_8W[1] / 60, "apple_fullframe": SEC_FF[1] / 60,
    "gemini": 3600 * eng["gemini_flash"]["sec_per_frame"] / 60,
    "cloud_vision": 3600 * eng["cloud_vision_text"]["sec_per_frame"] / 60,
    "vi": VI_MIN, "rekognition": None, "rekognition_text": None,
}
notes = {
    "apple_4w": "one Mac host, 4 workers, measured on two full matches",
    "apple_8w": "one Mac host, 8 workers, measured on 300 frames",
    "apple_fullframe": "one process, measured per frame",
    "gemini": "one request at a time at the measured 2.6 s per frame; parallel requests would cut this, not measured",
    "cloud_vision": "one request at a time at the measured 0.83 s per frame; parallel requests would cut this, not measured",
    "vi": "upload plus Google processing, measured on one 104-minute match; our short clips ran slower per minute",
    "rekognition": "not measured", "rekognition_text": "not measured",
}
for o in opts:
    mm = mins[o["id"]]
    o["minutes_per_video_hour"] = None if mm is None else round(mm, 1)
    o["time_note"] = notes[o["id"]]
    lo = {"apple_4w": SEC_4W[0], "apple_8w": SEC_8W[0], "apple_fullframe": SEC_FF[0]}.get(o["id"])
    o["minutes_per_video_hour_low"] = None if lo is None else round(lo / 60, 1)

head = next(o for o in opts if o["id"] == "apple_8w")
out = {
    "scale": {"hours": HOURS, "frames": FRAMES, "minutes": MINUTES, "sampling": "1 frame per second"},
    "headline": {"apple_usd": head["usd_low"], "apple_usd_high": head["usd_high"],
                 "per_video_hour": head["usd_per_video_hour_low"], "per_video_hour_high": head["usd_per_video_hour_high"],
                 "per_100_min_match": round(head["usd_per_video_hour_low"] * 100 / 60, 2),
                 "per_100_min_match_high": round(head["usd_per_video_hour_high"] * 100 / 60, 2),
                 "minutes_per_hour": [round(SEC_8W[0] / 60, 1), round(SEC_8W[1] / 60, 1)],
                 "minutes_per_hour_4w": [round(SEC_4W[0] / 60, 1), round(SEC_4W[1] / 60, 1)],
                 "cheapest_cloud_usd": min(o["usd_low"] for o in opts if o["id"] in ("gemini", "cloud_vision", "vi", "rekognition", "rekognition_text")),
                 "vi_usd_low": round(vi_lo), "vi_usd_high": round(vi_hi)},
    "throughput": {"apple_4w_fps": round(FPS_4W, 2), "apple_8w_fps": FPS_8W, "apple_fullframe_1w_fps": round(FPS_FF_1W, 2),
                   "host_usd_per_hour": HOST, "gemini_tokens_per_frame": [tin, tout]},
    "bands": {"good_max_usd": 50_000, "fair_max_usd": 300_000, "applies_to": "the high end of each price range"},
    "options": opts, "not_costed": not_costed, "speed": speed,
    "assumptions": [
        "1 frame per second, as measured. Sampling every 2 s would halve every figure here and cost recall on short appearances (not measured).",
        "Apple options assume an EC2 Mac M4 host matches the speed of the machine we measured on. That is not tested.",
        "Hosts are on-demand at $1.23 per host-hour with a 24-hour minimum, so small batches pay for a full day per host.",
        "Recall is pooled over 156 hand-labelled frames (176 boards) from three highlight edits. Full matches have more wide shots.",
        "Cloud-API figures are list prices with no volume discount or committed-use deal.",
    ],
}


# ---- whole pipeline, stage by stage, per video hour (Apple-only pipeline plus the optional parts) -------------------
rate_min = HOST / 60
runs_all = [T8, H22, H26]
ex = [r["extract_s"] / r["frames"] * 3600 for r in runs_all]
oc = [r["ocr_s"] / r["frames"] * 3600 for r in runs_all]
EX_LO, EX_HI, OC_LO, OC_HI = min(ex), max(ex), min(oc), max(oc)
pipeline = [
    {"stage": "Break the video into frames (ffmpeg, 1 per second)", "min_low": EX_LO / 60, "min_high": EX_HI / 60,
     "usd_low": EX_LO / 3600 * HOST, "usd_high": EX_HI / 3600 * HOST, "measured": "yes, three timed runs"},
    {"stage": "Read every frame: full frame, 6 zoomed tiles, Chinese pass (Apple Vision, 8 workers)", "min_low": OC_LO / 60, "min_high": OC_HI / 60,
     "usd_low": OC_LO / 3600 * HOST, "usd_high": OC_HI / 3600 * HOST, "measured": "yes, three timed runs"},
    {"stage": "Match text to brands and total the seconds", "min_low": 0.0, "min_high": 0.0, "usd_low": 0.0, "usd_high": 0.0,
     "measured": "yes, under 1 second"},
]
tot_lo, tot_hi = SEC_8W[0] / 60, SEC_8W[1] / 60
out["pipeline"] = {"stages": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in x.items()} for x in pipeline],
                   "total_min": [round(tot_lo, 1), round(tot_hi, 1)],
                   "total_usd": [round(SEC_8W[0] / 3600 * HOST, 3), round(SEC_8W[1] / 3600 * HOST, 3)],
                   "runs": {k: round(v / 60, 1) for k, v in runs8.items()},
                   "optional": [
                       {"stage": "Google Video Intelligence logo recognition (optional, runs in Google's cloud)",
                        "min": round(VI_MIN, 0), "usd_low": 0.12 * 60, "usd_high": 0.15 * 60,
                        "note": "about 6 min upload plus about 55 min processing, measured on one 104-minute match"}],
                   "not_included": ["Human review of detections (precision audit, recall labels): not timed, not costed",
                                    "Moving the video into AWS and storing it: not priced",
                                    "A 24-hour minimum applies to every EC2 Mac host, so a host must stay busy for the per-hour figures to hold"]}

# ---- quality composite for the scatter: mean of all-board recall and small-board recall (measured options only) ------
for o in opts:
    ra, rs = o["recall_all"], o["recall_small"]
    o["quality"] = None if ra is None or rs is None else round((ra + rs) / 2, 3)
out["quality_definition"] = "mean of the share of all boards found and the share of small boards found, on the 156 labelled frames"

# ---- two-pass plan: Apple Vision (8 workers) on every hour, then Gemini Flash-Lite on a share of high-priority hours ----
g = by_id = {o["id"]: o for o in opts}
two = []
for share in (0.05, 0.10, 0.25):
    lo = g["apple_8w"]["usd_low"] + share * g["gemini"]["usd_low"]
    hi = g["apple_8w"]["usd_high"] + share * g["gemini"]["usd_high"]
    two.append({"share_rechecked": share, "hours_rechecked": int(HOURS * share), "usd_low": round(lo), "usd_high": round(hi),
                "vs_gemini_everywhere_low": round(g["gemini"]["usd_low"]), "vs_gemini_everywhere_high": round(g["gemini"]["usd_high"])})
out["two_pass"] = two

# ---- arithmetic checks ----------------------------------------------------------------------------------------------
assert abs(out["headline"]["apple_usd"] - min(runs8.values()) / 3600 * HOST * HOURS) < 1
assert abs(vi_hi - 5_999_000 * 0.15) < 1
by = {o["id"]: o for o in opts}
assert "apple_vi" not in by
assert by["apple_8w"]["usd_high"] < by["apple_4w"]["usd_high"] and by["apple_8w"]["usd_low"] < by["apple_4w"]["usd_low"]
(EV / "cost_model.json").write_text(json.dumps(out, indent=1))
for o in opts:
    print(f"{o['id']:16s} ${o['usd_low']:>9,} - ${o['usd_high']:>9,}  recall {o['recall_all']}")
print(out["headline"], out["throughput"])

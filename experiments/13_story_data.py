"""Assemble story/data.json from the evidence files (every number on the page comes from here)."""
import json

from common import EVIDENCE, ROOT

ee = json.loads((EVIDENCE / "ee_scores.json").read_text())
wc = json.loads((EVIDENCE / "wc_scores.json").read_text())
ocr_m = json.loads((EVIDENCE / "wc_metrics_ocr.json").read_text())
vi_m = json.loads((EVIDENCE / "wc_metrics_vi.json").read_text())
fused_m = json.loads((EVIDENCE / "wc_metrics_fused.json").read_text())
usage = json.loads((EVIDENCE / "gcp_usage.json").read_text())
ocr_raw = json.loads((EVIDENCE / "wc_ocr.json").read_text())

LABEL = {"QatarAirways": "Qatar Airways", "CryptoCom": "Crypto.com", "CocaCola": "Coca-Cola",
         "McDonalds": "McDonald's", "QatarEnergy": "QatarEnergy", "InterRapidisimo": "Inter Rapidísimo",
         "BYJUS": "BYJU'S"}


def brands(m, min_s=8):
    out = []
    for k, v in m["brands"].items():
        if v["visible_s"] < min_s:
            continue
        out.append({"key": k, "name": LABEL.get(k, k), **{x: v[x] for x in (
            "visible_s", "appearances", "median_appearance_s", "share_visible_pct", "share_seconds",
            "key_moment_s", "share_of_exposure_pct", "share_of_key_moments_pct", "timeline")}})
    return out


agn = ee["class_agnostic"]
bid = ee["brand_identification"]
data = {
    "video": {"title": "2022 FIFA World Cup Final, Argentina v France (extended highlights)", "duration_s": 716,
              "resolution": "1920x1080, 50 fps", "sampling_fps": 1},
    "moments": [m | {"brands": sorted(
        [[LABEL.get(b, b), len(set(range(m["start"], m["end"])) & set(v["timeline"]))] for b, v in fused_m["brands"].items()
         if set(range(m["start"], m["end"])) & set(v["timeline"])], key=lambda x: -x[1])} for m in fused_m["moments"]],
    "key_moment_seconds": fused_m["key_moment_seconds"],
    "measure": {"primary": brands(fused_m), "ocr": brands(ocr_m, 1), "vi": brands(vi_m, 1)},
    "wc_accuracy": {k: {x: v[x] for x in ("micro_precision", "micro_recall", "tp", "fp", "fn")} | {
        "per_brand": v["per_brand"]} for k, v in wc.items() if isinstance(v, dict) and "per_brand" in v},
    "ee": {
        "frames": ee["benchmark_frames"], "test_frames": ee["test_frames"], "gt_boxes": ee["gt_boxes"],
        "localisation": {k: {"precision": round(v["iou50"]["precision"], 3), "recall": round(v["iou50"]["recall"], 3),
                             "recall_by_size": v["iou50"]["recall_by_size"], "sec_per_frame": v["sec_per_frame"]}
                         for k, v in agn.items()},
        "brand_id": {m: {b: {x: r[x] for x in ("frame_precision", "frame_recall", "frame_f1", "frames_with_brand")}
                         for b, r in res.items()} for m, res in bid.items()},
        "cloud_vision_top_labels": list(ee["cloud_vision_descriptions"].items())[:8],
    },
    "cost": {"gcp_usage": usage, "ocr_sec_per_frame": ocr_raw["sec_per_frame_mean"]},
    "vi_unverified_labels": sorted(wc["vi_unmapped_entities"].items(), key=lambda x: -x[1])[:10],
    "vi_entities_total": len(json.loads((EVIDENCE / "vi_wc_final.json").read_text())["logos"]),
}
out = ROOT / "story" / "data.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
print("wrote", out, round(out.stat().st_size / 1024, 1), "KB")

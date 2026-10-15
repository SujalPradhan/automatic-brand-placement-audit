"""GCP Video Intelligence LOGO_RECOGNITION on a whole clip (uploaded to GCS).

Usage: python 06_vi_logo.py <video.mp4> <out_tag>
Free tier: first 1,000 min/month. Clip minutes are charged against the local cap before submitting.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

from google.cloud import storage, videointelligence

from common import EVIDENCE, GCP_PROJECT, GCS_BUCKET, charge, ffmpeg_exe, gcp_client_options, gcp_credentials

BUCKET = GCS_BUCKET
if not BUCKET:
    sys.exit("Set GCS_BUCKET (see .env.example).")
video, tag = Path(sys.argv[1]), sys.argv[2]
out = EVIDENCE / f"vi_{tag}.json"
if out.exists():
    sys.exit(f"{out} exists; not re-billing")

probe = subprocess.run([ffmpeg_exe(), "-i", str(video)], capture_output=True, text=True).stderr
h, m, s = probe.split("Duration: ")[1].split(",")[0].split(":")
minutes = math.ceil((int(h) * 3600 + int(m) * 60 + float(s)) / 60)
charge("video_minutes", minutes)

creds = gcp_credentials()
gcs = storage.Client(project=GCP_PROJECT, credentials=creds)
bucket = gcs.bucket(BUCKET)
blob = bucket.blob(f"{tag}.mp4")
if not blob.exists():
    blob.upload_from_filename(str(video), timeout=1800)
uri = f"gs://{BUCKET}/{tag}.mp4"

client = videointelligence.VideoIntelligenceServiceClient(credentials=creds, client_options=gcp_client_options())
op = client.annotate_video(request={"input_uri": uri, "features": [videointelligence.Feature.LOGO_RECOGNITION]})
print("submitted", uri, minutes, "min; waiting...")
res = op.result(timeout=3600).annotation_results[0]


def ts(d):
    return d.seconds + d.microseconds / 1e6


logos = []
for ann in res.logo_recognition_annotations:
    tracks = []
    for t in ann.tracks:
        tracks.append({
            "start": ts(t.segment.start_time_offset), "end": ts(t.segment.end_time_offset),
            "confidence": round(t.confidence, 4),
            "boxes": [[round(ts(o.time_offset), 3), round(o.normalized_bounding_box.left, 4),
                       round(o.normalized_bounding_box.top, 4), round(o.normalized_bounding_box.right, 4),
                       round(o.normalized_bounding_box.bottom, 4)] for o in t.timestamped_objects],
        })
    logos.append({"entity": ann.entity.description, "entity_id": ann.entity.entity_id,
                  "segments": [[ts(sg.start_time_offset), ts(sg.end_time_offset)] for sg in ann.segments],
                  "tracks": tracks})
out.write_text(json.dumps({"uri": uri, "minutes_billed": minutes, "logos": logos}))
for l in sorted(logos, key=lambda l: -sum(t["end"] - t["start"] for t in l["tracks"])):
    print(f'{l["entity"]:30s} tracks={len(l["tracks"]):4d} track_sec={sum(t["end"] - t["start"] for t in l["tracks"]):7.1f}')

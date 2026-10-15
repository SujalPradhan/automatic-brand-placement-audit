# Automatic Brand Placement Audit

Measure which sponsor boards appear in football broadcast video, for how long, and how much of that falls around the
goals. It runs on a Mac with Apple Vision OCR, and on one hour of 1080p video it takes about 14 minutes and costs about
$0.26 to $0.31 of Mac host time (measured on an idle 10-core Mac, 8 workers).

This repository holds the pipeline, the hand labels used to score it, the benchmarks and the data-story site. It does
**not** hold the match footage, extracted frames or raw OCR output (large, and broadcast material).

## What is here

| Path | What |
|---|---|
| `experiments/` | the pipeline and the benchmark scripts (see run order below) |
| `evidence/audit/` | hand labels: `*_gt.csv` (boards per sampled frame), `*_rejects.csv` (audited false detections), `*_kit.csv`, `*_moments.csv`, `*_segments.csv` |
| `evidence/*.json` | scores, metrics, cost model, prices with source URLs, competitor research |
| `story/` | the data-story site (HTML, CSS, JS, JSON). Images are left out, so image slots are empty |
| `BENCHMARKS.md` | every benchmark run, v1 to v4d, never edited after the fact |
| `COSTS.md`, `API_DESIGN.md` | cost model arithmetic; how to turn the pipeline into an API |

## Set up (macOS only)

Apple Vision is reached through `ocrmac`, so the OCR stage needs macOS.

```bash
python3 -m venv .venv && source .venv/bin/activate    # Python 3.11
pip install -r requirements.txt
```

The Google engines are optional. Copy `.env.example` to `.env` and fill it in only if you use them (they need the
`gcloud` CLI logged in to the account that owns the project).

## Run it on a video

One command, from the video file, with timings per stage (the same script used for the cost figures):

```bash
cd experiments
python 25_timed_hour.py /path/to/match.mp4 8 3600      # video, workers, seconds of video to process
```

It extracts one frame per second, reads each frame with Apple Vision (full frame, six 2x tiles, and a Chinese-language
pass), matches the text to the brand list in `common.LEXICON`, and writes `evidence/timing_*.json`.

For the full analysis, in order:

1. `ffmpeg -i video.mp4 -vf fps=1 -q:v 2 data/<tag>/frames_1fps/f_%04d.jpg` extract frames (add the tag to `presence.VIDEO`)
2. `python 10_ocr.py <tag> [--add-zh]` read frames and match brands, writes `evidence/ocr_<tag>.json`
3. `python 06_vi_logo.py <video> <tag>` optional Google Video Intelligence logos (needs `.env`)
4. `python 15_audit_sheets.py <tag>` crop sheets for checking detections by eye, then record false ones in `evidence/audit/<tag>_rejects.csv`
5. `python 16_score.py` recall and precision against `evidence/audit/<tag>_gt.csv`
6. `python 12_metrics.py <tag>` per-brand seconds, tier shares and goal windows (`12b_metrics_full.py` for full matches)
7. `python 17_story_data.py` then `23_build_cost_page.py` and `24_build_match_pages.py` to rebuild the site data

Scripts `01` to `09`, `11` and `13` are the first-iteration method comparison (see `BENCHMARKS.md` v1).

## Live demo with in-page video

The match owners block their YouTube uploads from playing inside other sites, so the public site opens YouTube at the
right second instead. To give a demo where the video plays in the page and every click on the timeline seeks it:

1. Put the match files in `data/World-Cup/` with the names listed in `experiments/youtube.py` (`VIDEO_FILES`).
2. `python experiments/serve_demo.py`
3. Open http://127.0.0.1:8000/ and pick a game page.

Each game page has one player. Clicking a tick, a brand's row, a goal window, a goal button under the player or a
"▶ Play at m:ss" button jumps it to that second, and a line on the chart follows the playing position. The server only
listens on this machine and nothing is uploaded. A page whose file is missing falls back to YouTube links.

## What to expect

- Apple Vision finds about 69% of the sponsor boards a person could identify on our labelled frames (84% of large boards,
  28% of small, distant ones), with about 93% precision. Gemini Flash-Lite found 85% on the same frames.
- Detection is not the whole job: every number on the story pages came from checking detections by eye, which is not
  included in the time or cost figures.
- Sponsor tiers for 2018 and 2022 additions are partly inferred; see the footers on the story pages.

## Footage and licence

The code is MIT licensed. The match footage belongs to its rights holders and was used for internal measurement only; do
not redistribute it.

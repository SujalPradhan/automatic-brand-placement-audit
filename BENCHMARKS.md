# Benchmarks

One dated section per iteration. Older sections are never edited or deleted; each new run is appended below.
Raw numbers for v2 are frozen in `evidence/history/v2/`.

---

## v1 (2026-10-13): method selection

### ExposureEngine dataset (sports-broadcast logo boxes)
Source: `evidence/ee_scores.json`. 150 frames (75 calibration, 75 test), 2,469 ground-truth logo boxes.
Class-agnostic logo localisation at IoU 0.5 on the test frames:

| Method | Recall | Precision | Notes |
|---|---|---|---|
| OWLv2 (threshold 0.10) | 0.47 (625 of 1,343) | 0.26 | 0.75 s/frame; small logos (<0.1% of frame) recall 0.24 |
| OWLv2, tiled (threshold 0.15) | 0.31 | 0.33 | 1.45 s/frame |
| Google Cloud Vision logo detection | 0.006 (8 of 1,343) | 0.53 | found 0.6% of the logos |

Outcome: open-vocabulary detection was too imprecise and Cloud Vision too blind; both dropped.

### 2022 final, first 180 s (brand-seconds with a clearly visible board)
Source: `evidence/wc_scores.json`. 174 labelled brand-seconds.

| Method | Recall | Precision | TP / FN / FP |
|---|---|---|---|
| Apple Vision OCR | 0.649 | 1.000 | 113 / 61 / 0 |
| Google Video Intelligence logos | 0.420 | 0.859 | 73 / 101 / 12 |
| OCR + VI fused | 0.770 | 0.918 | 134 / 40 / 12 |

Outcome: OCR + Video Intelligence fusion adopted for iteration 2.

---

## v2 (2026-10-13): two games, boards only, audited

Source: `evidence/scores.json`, `story/benchmark.json` (frozen copies in `evidence/history/v2/`).
Recall is board-only, from hand-labelled frames every 10 s; 95% Wilson intervals. "Large" and "small" are the
labeller's judgement of whether the board is readable at broadcast size. Precision is from an audit of every
detected appearance, in brand-seconds.

### 2022 final · Argentina v France (716 s; 72 frames, 75 board marks)

| Method | Recall, all boards | Large | Small | Precision |
|---|---|---|---|---|
| OCR | 0.640 (48/75) [0.527, 0.739] | 0.754 (46/61) [0.633, 0.845] | 0.143 (2/14) [0.040, 0.399] | 0.966 (519/537) [0.948, 0.979] |
| VI | 0.453 (34/75) [0.346, 0.566] | 0.492 (30/61) [0.371, 0.614] | 0.286 (4/14) [0.117, 0.546] | 0.969 (413/426) [0.948, 0.982] |
| Fused | 0.747 (56/75) [0.638, 0.831] | 0.820 (50/61) [0.705, 0.896] | 0.429 (6/14) [0.214, 0.674] | 0.954 (636/667) [0.935, 0.967] |

### 2026 group stage · Brazil v Morocco (600 s; 60 frames, 65 board marks)

| Method | Recall, all boards | Large | Small | Precision |
|---|---|---|---|---|
| OCR | 0.754 (49/65) [0.637, 0.842] | 0.905 (38/42) [0.779, 0.962] | 0.478 (11/23) [0.292, 0.670] | 0.890 (403/453) [0.857, 0.915] |
| VI | 0.431 (28/65) [0.318, 0.552] | 0.476 (20/42) [0.334, 0.623] | 0.348 (8/23) [0.188, 0.551] | 0.986 (286/290) [0.965, 0.995] |
| Fused | 0.831 (54/65) [0.722, 0.903] | 0.952 (40/42) [0.842, 0.987] | 0.609 (14/23) [0.408, 0.778] | 0.901 (489/543) [0.872, 0.923] |

### Tier shares and coverage (fused, audited)

| Game | Brands | Brand-seconds | Seconds with any sponsor | Partner share (all / goal windows) | Sponsor | Supporter | Chinese brands |
|---|---|---|---|---|---|---|---|
| 2022 final | 18 | 636 | 388 of 716 | 52.7% / 51.0% | 40.3% / 49.0% | 7.1% / 0.0% | 24.4% / 19.6% |
| 2026 group game | 22 | 489 | 285 of 600 | 50.1% / 28.2% | 19.8% / 0.0% | 30.1% / 71.8% | 12.3% / 0.0% |

OCR speed: 0.946 s/frame (2022 final), 0.795 s/frame (2026 group game).

---

## v3 (2026-10-14): three games, re-validated

Source: `evidence/scores.json`, `story/benchmark.json`. New clip: the 2026 final, Spain 1–0 Argentina (117 s, 1080p).
Recall frames for the new clip are every **5 s** (24 frames), because a 10 s grid would give only 12. Other
conventions as in v2. Ratios are computed from the counts.

### 2026 final · Spain v Argentina (117 s; 24 frames, 34 board marks)

| Method | Recall, all boards | Large | Small | Precision |
|---|---|---|---|---|
| OCR | 0.706 (24/34) [0.538, 0.832] | 0.923 (24/26) [0.759, 0.979] | 0.000 (0/8) [0.000, 0.324] | 0.982 (108/110) [0.936, 0.995] |
| VI | 0.471 (16/34) [0.315, 0.633] | 0.577 (15/26) [0.389, 0.745] | 0.125 (1/8) [0.022, 0.471] | 0.819 (77/94) [0.729, 0.884] |
| Fused | 0.735 (25/34) [0.569, 0.854] | 0.923 (24/26) [0.759, 0.979] | 0.125 (1/8) [0.022, 0.471] | 0.860 (117/136) [0.792, 0.909] |

VI's lower precision here: all 17 of its false seconds are boxes on shots where the brand is not visible, often a
track running one second past a cut or onto the end-card transition. The fast edit has many cuts. All 19 false brand-seconds are listed in `evidence/audit/wc2026_final_rejects.csv`.

### 2022 final (re-run)

| Method | Recall, all boards | Large | Small | Precision |
|---|---|---|---|---|
| OCR | 0.645 (49/76) [0.533, 0.743] | 0.758 (47/62) [0.638, 0.848] | 0.143 (2/14) [0.040, 0.399] | 0.967 (521/539) [0.948, 0.979] |
| VI | 0.461 (35/76) [0.353, 0.572] | 0.500 (31/62) [0.379, 0.621] | 0.286 (4/14) [0.117, 0.546] | 0.967 (415/429) [0.946, 0.980] |
| Fused | 0.750 (57/76) [0.642, 0.834] | 0.823 (51/62) [0.710, 0.898] | 0.429 (6/14) [0.214, 0.674] | 0.952 (638/670) [0.933, 0.966] |

### 2026 group stage · Brazil v Morocco (re-run)

| Method | Recall, all boards | Large | Small | Precision |
|---|---|---|---|---|
| OCR | 0.742 (49/66) [0.626, 0.833] | 0.905 (38/42) [0.779, 0.962] | 0.458 (11/24) [0.279, 0.649] | 0.870 (403/463) [0.837, 0.898] |
| VI | 0.424 (28/66) [0.312, 0.544] | 0.476 (20/42) [0.334, 0.623] | 0.333 (8/24) [0.180, 0.533] | 0.986 (286/290) [0.965, 0.995] |
| Fused | 0.818 (54/66) [0.709, 0.893] | 0.952 (40/42) [0.842, 0.987] | 0.583 (14/24) [0.388, 0.755] | 0.885 (491/555) [0.855, 0.909] |

### Tier shares and coverage (fused, audited)

| Game | Brands | Brand-seconds | Seconds with any sponsor | Partner share (all / goal windows) | Sponsor | Supporter | Chinese brands |
|---|---|---|---|---|---|---|---|
| 2022 final | 19 | 638 | 388 of 716 | 52.8% / 51.0% | 40.1% / 49.0% | 7.1% / 0.0% | 24.3% / 19.6% |
| 2026 group game | 23 | 491 | 285 of 600 | 50.3% / 28.2% | 19.8% / 0.0% | 29.9% / 71.8% | 12.2% / 0.0% |
| 2026 final | 16 | 117 | 68 of 117 | 66.7% / 60.0% | 9.4% / 40.0% | 23.9% / 0.0% | 18.8% / 30.0% |

The 2026 final's goal window holds only 10 detected brand-seconds (Aramco 6, Hisense 3, Michelob Ultra 1).
OCR speed: 0.839 s/frame on the new clip. GCP usage after v3: 25 of 60 local-cap video minutes, 150 of 900 Vision images.

### What changed in the two older games, and why

Every change traces to the v3 lexicon:

1. **ADI Predictstreet split from Adidas.** v2's lexicon mapped "predictstreet" to Adidas. ADI Predictstreet is a
   separate FIFA Partner (prediction markets; FIFA release, 2 Apr 2026). In the group game, 14 brand-seconds
   (222–226, 524–530, 534–535) moved from Adidas to ADI Predictstreet; 536–537 stay Adidas (VI found the real pink
   Adidas board) and are also ADI Predictstreet (OCR), so brand-seconds rose 489 → 491. Adidas 37 → 23 s. Both brands
   are Partners, so tier shares change only by rounding. The group-game recall labels at t=225, 525 and 535 were
   relabelled to ADI Predictstreet, and a small pink Adidas board seen at t=535 was added (65 → 66 marks; recall
   0.831 → 0.818).
2. **Powerade added** (Coca-Cola Company brand on Coca-Cola's board inventory; tier inferred as Partner).
   2022 final: +2 real board seconds (84–85); recall label added at t=85 (75 → 76 marks); one VI second (86) rejected.
   Group game: every OCR hit was audited and none was a board: "Powered by" on the Lenovo AI graphic (245–248,
   453–456) and "Trade" on Kraken's board (308–309) are rejected, which lowers OCR precision 0.890 → 0.870; drinks
   coolers (212–214, 577–583) go to the kit/other file.
3. **New lexicon entries with no hits in the old games:** Fanatics, DoorDash, Mercado Libre, and Michelob Ultra's
   "Superior Light Beer" tagline.

Page correction found during the number check: v2's landing card said Kraken, Betano and Inter Rapidísimo had
"30% of screen time". 30% was the whole supporter tier (seven brands); the three had 16%.

Known gap (unchanged, now documented): the 2022 final's Coca-Cola boards also rotate through Fuze Tea, Smartwater,
Minute Maid and Costa Coffee. These are not in the lexicon, so they are not counted.

---

## v4 (2026-10-14/15): engine comparison, full matches, cost at scale

Sources: `evidence/engines/*.json`, `evidence/audit/full_*_scores.json`, `evidence/metrics_full_*.json`,
`evidence/cost_model.json`. The v1–v3 sections above are unchanged.

### Engine comparison on the 156 labelled frames (176 board marks: 130 large, 46 small)

Recall is board-only. Precision is verified / detected unique (brand, frame) hits; hits that matched a labelled mark or
had survived the v2/v3 audit were auto-verified, and 61 remaining hits were audited by eye (`engines/verdicts.csv`).
The 10-random-misses spot-check in the plan was **not** done.

| Engine | Recall, all | Large | Small | Precision | Seconds / frame | Cost |
|---|---|---|---|---|---|---|
| Apple Vision, full + tiles + zh (current) | 122/176 = 0.693 | 109/130 = 0.838 | 13/46 = 0.283 | 125/134 = 0.933 | 1.005 (1 process) | free |
| Apple Vision, no zh pass | 117/176 = 0.665 | 104/130 | 13/46 | 120/129 = 0.930 | 0.867 | free |
| Apple Vision, full frame only | 108/176 = 0.614 | 98/130 | 10/46 | 111/119 = 0.933 | 0.139 | free |
| PaddleOCR PP-OCRv5, CPU | 129/176 = 0.733 | 111/130 | 18/46 | 131/138 = 0.949 | 25.6 | free |
| Tesseract 5.5.2 (English only) | 31/176 = 0.176 | 29/130 | 2/46 | 32/78 = 0.410 | 2.08 | free |
| Google Cloud Vision text detection | 133/176 = 0.756 | 112/130 | 21/46 | 136/149 = 0.913 | 0.83 | free tier; $1.50 / 1,000 images |
| Gemini Flash-Lite (3.1) | 150/176 = 0.852 | 122/130 | 28/46 | 155/165 = 0.939 | 2.60 | 1,249 in + 178 out tokens per frame; $0.090 for the run |

Apple Vision parallel scaling (320 consecutive 2022-final frames, two runs each, agreeing within 7%):
1 worker 0.93 frames/s, 2 workers 1.80, 4 workers 2.6, 8 workers 3.2.

### Full matches (live play only; both without commercials)

| Match | Frames | Method | Recall, all | Large | Small | Precision (150-detection sample) |
|---|---|---|---|---|---|---|
| Brazil 4–1 Korea, 2022 R16 (1:44:06) | 30 labelled, 26 boards | Apple Vision | 20/26 = 0.77 [0.58, 0.89] | 18/22 | 2/4 | 120/130 = 0.923 (detections) |
| | | Video Intelligence | 16/26 = 0.62 [0.43, 0.78] | 15/22 | 1/4 | 72/84 = 0.857 |
| | | Both | 22/26 = 0.85 [0.67, 0.94] | 19/22 | 3/4 | 131/150 = 0.873 [0.81, 0.92] |
| Portugal 3–3 Spain, 2018 (1:40:05) | 30 labelled, 29 boards | Apple Vision | 25/29 = 0.86 [0.69, 0.95] | 24/28 | 1/1 | 144/150 = 0.96 [0.915, 0.98] |

Throughput (baseline pipeline, 4 workers): about 2,260 s for Brazil and 2,310 s for Portugal, roughly 22 minutes per
video hour, 1.44–1.52 s per-frame latency. Speed fell 20–25% over the last 10-minute blocks. Video Intelligence on
Brazil: about 10 minutes upload plus about 95 minutes of Google processing for a 104-minute video.
Segments: Brazil live play 5,985 s, Portugal 5,821 s; no commercials in either.

Goals found from the scoreboard and checked on frames: Brazil 5, Portugal 6.
Live-play tier shares: Brazil Partner 50.0% (51.9% in goal windows), Sponsor 38.5%, Supporter 2.6%, other 8.9%;
Portugal Partner 61.6% (66.1%), Sponsor 35.7%, Supporter 0.9%, other 1.8% (2018 tiers are inferred).

Caveats: samples of 26 and 29 boards give wide intervals, and Portugal's small-board recall rests on one board. The
Brazil precision sample was drawn before the lexicon additions below. Replays were not separated from live play.

Lexicon additions made during these runs (`experiments/common.py`): BossZhipin, Ooredoo, QNB, FuzeTea, Smartwater,
MinuteMaid, CostaCoffee, Gazprom, Alrosa, AlfaBank; Mengniu, McDonald's and Budweiser terms extended ("bud" lifted
Portugal's recall from 20 to 25 of 29 and has not been spot-checked for false positives). The older games' stored
results were **not** re-matched against this lexicon.

### Cost at 100,000 hours of one-hour video (360 million frames at 1 per second)

Prices and sources: `evidence/pricing.json`. Model: `experiments/22_cost_model.py`.

| Option | Cost | Per video hour | Recall, all (156 frames) |
|---|---|---|---|
| Apple Vision, EC2 Mac M4, 4 workers (measured on full matches) | $45,883 | $0.46 | 0.69 |
| Apple Vision, 8 workers | $28,276 | $0.28 | 0.69 |
| Apple Vision, full frame only (1 worker) | $17,097 | $0.17 | 0.61 |
| Gemini Flash-Lite, every frame (batch to standard rates) | $147,546 to $295,092 | $1.48 to $2.95 | 0.85 |
| Cloud Vision text (one month to spread over 12) | $220,500 to $270,000 | $2.21 to $2.70 | 0.76 |
| AWS Rekognition Video (price only; accuracy not measured) | $600,000 | $6.00 | n/a |
| Video Intelligence logos ($0.12 to $0.15 per minute) | $719,880 to $899,850 | $7.20 to $9.00 | 0.45 |
| Apple Vision + Video Intelligence (the v3 pipeline) | $765,763 to $945,733 | $7.66 to $9.46 | 0.77 |

Assumed: an EC2 Mac M4 host matches the machine we measured on (not tested); on-demand $1.23 per host-hour.
Unconfirmed prices (not used): Mac mini M4 retail price; the Gemini model priced at the third-party rate.
Cloud project changes made by the benchmark agent: Vertex AI API enabled on the personal GCP project; Gemini
spend $1.31 of the $2.00 cap (including $1.18 on a run that hung and returned nothing).

### v4b (2026-10-15): one timed hour, start to finish (Apple Vision only)

Source: `evidence/timing_hour_run.json`, `experiments/25_timed_hour.py`. First 3,600 s of the Brazil v Korea full match,
from the video file, 4 workers, one run, an otherwise idle Mac.

| Stage | Time | Cost at $1.23 per host-hour |
|---|---|---|
| ffmpeg frame extraction, 3,600 frames | 54.3 s | $0.019 |
| OCR: full frame, 6 upscaled tiles, Chinese pass | 1,185.8 s (3.04 frames/s; 3.25 down to 2.86 over the hour) | $0.405 |
| Matching and per-brand seconds | under 1 s | about $0 |
| **Total** | **1,240.2 s = 20.7 min** | **$0.424** |

Against the first-round figures (extraction 1.0 to 1.4 min, OCR 22 to 23 min, total about 24 min, $0.48): faster by
about 3 minutes and $0.06, which is the idle machine against the shared one. 37 brands, 2,056 of 3,600 seconds with a
sponsor board; top four Visa, Hisense, Wanda, Hyundai (raw, unreviewed). One run only; the two-run agreement check was
not done. Cost model after this run: $0.42 to $0.49 per video hour, $42,374 to $48,771 per 100,000 hours.

### v4c (2026-10-15): the same hour with 8 workers

Source: `evidence/timing_hour_run_8w.json`. Same video, same script, one run, idle Mac (10 cores, 4 performance).

| | 4 workers | 8 workers |
|---|---|---|
| Frame extraction | 54.3 s | 53.9 s |
| OCR | 1185.8 s (3.04 frames/s) | 797.9 s (4.51 frames/s) |
| Total | 1240.2 s = 20.7 min | 851.8 s = 14.2 min |
| Cost at $1.23 per host-hour | $0.424 | $0.291 |
| Speed, first to last 600 frames | 3.25 to 2.86 frames/s | 4.59 to 4.3 frames/s |
| Mean per-frame latency | 1.31 s | 1.77 s |
| Brands found / seconds with a brand | 37 / 2056 | 37 / 2056 |

One run each; the two-run agreement check is not done. Earlier 300-frame tests of 8 workers gave 3.2 and 4.35 frames/s.

### v4d (2026-10-15): 8 workers on all three videos

Sources: `evidence/timing_hour_run_8w.json`, `timing_hl2022_8w.json`, `timing_hl2026_8w.json`. One run each, idle Mac,
run one after another, same script (`experiments/25_timed_hour.py`). Per-video-hour figures scale each run's total.

| Video | Frames | Extraction | OCR | Total | Frames/s (OCR) | Per video hour | Cost per video hour |
|---|---|---|---|---|---|---|---|
| Brazil v Korea full match, first hour, 1080p30 | 3,600 | 53.9 s | 797.9 s | 851.8 s | 4.51 | 14.2 min | $0.291 |
| 2022 final highlights, 1080p50 | 716 | 18.5 s | 161.1 s | 179.6 s | 4.44 | 15.1 min | $0.309 |
| 2026 Brazil v Morocco highlights, 720p60 | 600 | 9.4 s | 115.3 s | 124.7 s | 5.20 | 12.5 min | $0.256 |

Across the three: 12.5 to 15.1 minutes and $0.256 to $0.309 per video hour; the 720p clip is fastest because its frames
are smaller. The full-match hour and the 1080p highlight differ by 6%. Cost model after this: $25,564 to $30,853 per
100,000 hours (4 workers: $42,374 to $48,771). One run each, so run-to-run repeatability is still unmeasured.

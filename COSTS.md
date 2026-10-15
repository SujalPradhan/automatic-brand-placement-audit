# Cost model: auditing 100,000 hours of video

Scale (Anand's brief): 100,000 videos of one hour each, sampled at 1 frame per second = 360,000,000 frames,
6,000,000 minutes. Result table and measured accuracy: [BENCHMARKS.md](BENCHMARKS.md) v4. Code:
`experiments/22_cost_model.py` (arithmetic is asserted). Output: `evidence/cost_model.json`.

## Method
- **Apple Vision on EC2 Mac:** frames ÷ measured frames per second ÷ 3,600 = host-hours; × $1.23 per
  host-hour (EC2 mac-m4 dedicated host, AWS Price List file published 2026-10-12, 24 h minimum).
  Speed: 2.68 frames/s with 4 workers (both full matches, 12,251 frames in 4,570 s); 4.35 frames/s with 8 workers
  (300-frame test); 7.19 frames/s for the full-frame-only pass in one process.
- **Gemini Flash-Lite:** measured 1,249 input and 178 output tokens per 1080p frame × the confirmed Flash-Lite rates,
  standard and batch.
- **Cloud Vision:** $1.50 per 1,000 images for units 1,001 to 5 M a month, $0.60 beyond; low = all in one month,
  high = spread evenly over 12 months.
- **Video Intelligence:** $0.15 per minute after 1,000 free minutes; tiers of $0.135 and $0.12 exist but their
  boundaries are not on the pricing page, so the low figure uses $0.12.
- **Rekognition:** $0.10 per minute of archived video. Price only.

## Hand check of two lines
- Apple, 4 workers: 360,000,000 ÷ 2.68 ÷ 3,600 = 37,313 host-hours × $1.23 = $45,895 (the model uses the unrounded speed:
  $45,883).
- Gemini, batch: (1,249 × $0.15 + 178 × $1.25) ÷ 1,000,000 = $0.000410 per frame × 360,000,000 = $147,546.

## What is not known
- Speed on an actual EC2 Mac host (all speeds are from one local machine, which degraded 20–25% over 100 minutes).
- Full-frame-only Apple Vision with parallel workers.
- Accuracy on sampling below 1 frame per second.
- Rekognition's accuracy, and which operation its per-minute rate covers.
- PaddleOCR on a GPU, and Mac mini M4 retail price (not confirmed).

## Update 2026-10-15: end-to-end figures
Apple options now include frame extraction (54 s per video hour on an idle Mac, 85 s on the Portugal full match) and
show a range: low = the timed one-hour run (20.7 min, $0.424); high = full-match OCR speed on a shared Mac plus the
slower extraction (23.8 min, $0.488). 100,000 hours: $42,374 to $48,771. Hand check: 1,240.2 s / 3,600 x $1.23 x
100,000 = $42,374; (1,343 + 85) s / 3,600 x $1.23 x 100,000 = $48,771. Human review and data transfer are not included.

## Update 2026-10-15 (later): 8 workers is the headline configuration
Three timed 8-worker runs (BENCHMARKS.md v4d) give 748 to 903 s per video hour end to end: $0.256 to $0.309, or
$25,564 to $30,853 for 100,000 hours. Hand check: 748.2 s / 3,600 x $1.23 x 100,000 = $25,564; 903.0 s / 3,600 x
$1.23 x 100,000 = $30,853. 4 workers stays in the table as the more conservative configuration.

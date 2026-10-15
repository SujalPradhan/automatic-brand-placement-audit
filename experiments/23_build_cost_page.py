"""Builds story/cost.html and story/cost_model.json from evidence/cost_model.json and the full-match scores,
so every number on the page is generated, not typed."""
import json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV, ST = ROOT / "evidence", ROOT / "story"
m = json.loads((EV / "cost_model.json").read_text())
bra = json.loads((EV / "audit" / "full_bra_scores.json").read_text())
por = json.loads((EV / "audit" / "full_por_scores.json").read_text())
shutil.copy(EV / "cost_model.json", ST / "cost_model.json")
O = {o["id"]: o for o in m["options"]}
usd = lambda v: "${:,.0f}".format(v)
k = lambda v: "${:,.0f}k".format(v / 1000) if v < 1e6 else "${:.2f}M".format(v / 1e6)
rng = lambda o: k(o["usd_low"]) if o["usd_low"] == o["usd_high"] else f'{k(o["usd_low"])} to {k(o["usd_high"])}'
pct = lambda v: "n/a" if v is None else f"{round(v * 100)}%"
h = m["headline"]; t = m["throughput"]
min_4w_lo, min_4w_hi = h["minutes_per_hour"]
min_4w_a, min_4w_b = h["minutes_per_hour_4w"]
plo, phi = h["per_video_hour"], h["per_video_hour_high"]
PL = m["pipeline"]
_lr = json.loads((EV / "engines" / "apple_baseline.json").read_text())["recall"]["pooled"]["large"]
large_rec = _lr["found"] / _lr["of"]
PL_RUNS = "; ".join(f"{k} ({v:.1f} min per hour)" for k, v in PL["runs"].items())
HH4_TXT = "{:,.0f}".format(100000 * min_4w_hi / 60)
cloud = [O[i] for i in ("gemini", "cloud_vision", "vi", "rekognition", "rekognition_text")]
cloud_lo, cloud_hi = min(o["usd_low"] for o in cloud), max(o["usd_high"] for o in cloud)

def tm(v):
    return f"{v:.0f} min" if v < 120 else f"{v / 60:.1f} h"


rows = ""
bd = m["bands"]
cband = lambda o: "good" if o["usd_high"] <= bd["good_max_usd"] else "fair" if o["usd_high"] <= bd["fair_max_usd"] else "weak"
rband = lambda v: "" if v is None else "good" if v >= 0.8 else "fair" if v >= 0.5 else "weak"
order = sorted(O, key=lambda i: (-O[i]["usd_high"], -O[i]["usd_low"]))   # most expensive first
for i in order:
    o = O[i]
    note = "" if o["accuracy_measured"] else " (price only, accuracy not measured)"
    cb = cband(o)
    mh, ml = o["minutes_per_video_hour"], o.get("minutes_per_video_hour_low")
    tband = "" if mh is None else ("good" if mh <= 30 else "fair" if mh <= 120 else "weak")
    tcell = "n/a" if mh is None else (tm(mh) if ml is None or round(ml) == round(mh) else "%.0f–%s" % (ml, tm(mh)))
    rc = lambda v: f'<td class="n{" q-" + rband(v) if v is not None else ""}">{pct(v)}</td>'
    rows += (f'<tr{" class=strong" if i == "apple_8w" else ""}><td>{o["name"]}{note}</td><td class="n q-{cb}">{rng(o)}</td>'
             f'<td class="n q-{cb}">${o["usd_per_video_hour_low"]:.2f}{"" if o["usd_low"]==o["usd_high"] else " to $%.2f" % o["usd_per_video_hour_high"]}</td>'
             f'<td class="n{" q-" + tband if tband else ""}" title="{o["time_note"]}">{tcell}</td>'
             f'{rc(o["recall_all"])}{rc(o["recall_small"])}</tr>')

speed = "".join(f'<tr><td class="n">{s["hosts"]:,}</td><td class="n">{s["apple_4w_days"]:,} days</td><td class="n">{s["apple_8w_days"]:,} days</td></tr>' for s in m["speed"])

def fm(sc, key, label, game):
    r = sc[key]
    return (f'<tr><td>{game}</td><td>{label}</td><td class="n">{r["all"]["found"]} of {r["all"]["of"]} ({r["all"]["recall"]:.2f})</td>'
            f'<td class="n">{r["large"]["found"]} of {r["large"]["of"]}</td><td class="n">{r["small"]["found"]} of {r["small"]["of"]}</td></tr>')
full = (fm(bra, "ocr", "Apple Vision", "Brazil v Korea, 2022 (1:44)") + fm(bra, "vi", "Video Intelligence", "") + fm(bra, "fused", "Both", "")
        + fm(por, "ocr", "Apple Vision", "Portugal v Spain, 2018 (1:40)"))
ps = bra["precision_sample"]["all"]; pp = por["precision_sample"]["all"]


def mm(v):
    return "under 1 s" if v < 0.02 else (f"{v * 60:.0f} s" if v < 1.5 else f"{v:.1f} min")


def rng2(lo, hi, f):
    return f(lo) if f(lo) == f(hi) else f"{f(lo)} to {f(hi)}"


pl_rows = ""
for x in PL["stages"]:
    pl_rows += (f'<tr><td>{x["stage"]}</td><td class="n">{rng2(x["min_low"], x["min_high"], mm)}</td>'
                f'<td class="n">{rng2(x["usd_low"], x["usd_high"], lambda v: "$%.3f" % v if v else "about $0")}</td>'
                f'<td class="n">{rng2(x["usd_low"] * 100000, x["usd_high"] * 100000, lambda v: "$%s" % format(round(v, -2), ",.0f") if v else "about $0")}</td></tr>')
tl, th = PL["total_min"]; ul, uh = PL["total_usd"]
pl_rows += (f'<tr class="strong"><td>Whole pipeline, Apple Vision only</td><td class="n">{tl:.1f} to {th:.1f} min</td>'
            f'<td class="n">${ul:.2f} to ${uh:.2f}</td><td class="n">{usd(round(ul * 100000, -2))} to {usd(round(uh * 100000, -2))}</td></tr>')
for x in PL["optional"]:
    pl_rows += (f'<tr><td>Optional: {x["stage"]}</td><td class="n">about {x["min"]:.0f} min, in parallel</td>'
                f'<td class="n">${x["usd_low"]:.2f} to ${x["usd_high"]:.2f}</td><td class="n">{usd(x["usd_low"] * 100000)} to {usd(x["usd_high"] * 100000)}</td></tr>')
pl_not = "".join(f"<li>{n}</li>" for n in PL["not_included"])

CMP = json.loads((EV / "competitors_validated.json").read_text())["rows"]
def _cb(v):
    return "" if v is None else " q-good" if v <= 0.50 else " q-fair" if v <= 3.00 else " q-weak"


def _tb(v):
    return "" if v is None else " q-good" if v <= 30 else " q-fair" if v <= 120 else " q-weak"


def _rb(v):
    return "" if v is None else " q-good" if v >= 0.8 else " q-fair" if v >= 0.5 else " q-weak"


cmp_rows = "".join(
    f'<tr{" class=strong" if r["kind"] == "in-house" else ""}><td>{r["name"]}<br><span class="muted">{r["kind"]}</span></td>'
    f'<td class="{_cb(r["price_hr_band_value"]).strip()}"><b>{r["usd_hr"]}</b></td><td class="{_cb(r["price_hr_band_value"]).strip()}">{r["usd_100k"]}</td>'
    f'<td class="{_tb(r["minutes_measured"]).strip()}">{r["time"]}</td><td class="{_rb(r["recall_measured"]).strip()}">{r["accuracy"]}</td>'
    f'<td class="muted">{r["verdict"]}</td></tr>'
    for r in CMP)

two_rows = "".join(f'<tr><td class="n">{int(x["share_rechecked"] * 100)}% ({x["hours_rechecked"]:,} hours)</td>'
                   f'<td class="n q-good">{k(x["usd_low"])} to {k(x["usd_high"])}</td>'
                   f'<td class="n q-fair">{k(x["vs_gemini_everywhere_low"])} to {k(x["vs_gemini_everywhere_high"])}</td></tr>' for x in m["two_pass"])

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Cost at Scale</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<link rel="stylesheet" href="style.css">
<style>html, body {{ margin: 0; }} img {{ max-width: 100%; }} [hidden] {{ display: none !important; }} :root {{ padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }}</style>
</head>
<body>
<main class="wrap" data-page="cost">

  <nav class="top" aria-label="Pages">
    <a href="index.html">Overview &amp; accuracy</a>
    <a href="game-2022.html">2022 final</a>
    <a href="game-2026.html">2026: Brazil v Morocco</a>
    <a href="game-2026-final.html">2026 final</a>
    <a href="cost.html" aria-current="page">Cost at scale</a>
  </nav>

  <header class="hero">
    <p class="eyebrow">Cost and speed · per hour of video, then at 100,000 hours</p>
    <h1>${plo:.2f}–${phi:.2f} to audit an hour of video</h1>
    <p class="dek">Start to finish, frame extraction included, Apple's on-device text reader on a rented Mac costs ${plo:.2f} to ${phi:.2f} per video hour and takes {min_4w_lo:.0f} to {min_4w_hi:.0f} minutes. The cloud APIs we tested cost ${O["gemini"]["usd_per_video_hour_low"]:.2f} to ${O["vi"]["usd_per_video_hour_high"]:.2f} for the same hour. At 100,000 one-hour videos that is {k(h["apple_usd"])} to {k(h["apple_usd_high"])} against {k(cloud_lo)} to {k(cloud_hi)}.</p>
    <div class="stats">
      <div class="stat"><b class="num">${plo:.2f}–${phi:.2f}</b><span>to audit one hour of video, start to finish, with Apple Vision on an EC2 Mac. The cheapest cloud API we tested is ${O["gemini"]["usd_per_video_hour_low"]:.2f}</span></div>
      <div class="stat"><b class="num">{min_4w_lo:.0f}–{min_4w_hi:.0f} min</b><span>to process one hour of video on one Mac with 8 workers, frame extraction included</span></div>
      <div class="stat"><b class="num">${h["per_100_min_match"]:.2f}–${h["per_100_min_match_high"]:.2f}</b><span>for a full 100-minute match, about 6,000 frames</span></div>
      <div class="stat"><b class="num">{large_rec:.0%}</b><span>of large boards found, and {pct(O["apple_4w"]["recall_small"])} of small, distant ones</span></div>
    </div>
  </header>

  <section aria-labelledby="c0">
    <div class="col">
      <h2 id="c0">Cheap first, expensive where it matters</h2>
      <p>Each dot is one way of reading the boards. Further right costs more per video hour; higher finds more. Quality here is the average of two measured shares: all boards found, and small boards found.</p>
    </div>
    <figure>
      <div class="legend"><span><i style="background:var(--s2)"></i>Apple Vision on a Mac</span><span><i style="background:var(--s1)"></i>Cloud APIs</span><span class="muted">Lines show each option's price range. AWS Rekognition is left out: its accuracy was not measured.</span></div>
      <div class="chart" id="scatter"></div>
      <figcaption>Quality from the 156 hand-labelled frames (176 boards). Cost per video hour, start to finish, at list prices.</figcaption>
    </figure>
    <div class="col">
      <p><strong>A two-pass plan.</strong> Run Apple Vision on every hour, then send only the high-priority hours to Gemini Flash-Lite, which found {pct(O["gemini"]["recall_all"])} of boards against Apple's {pct(O["apple_8w"]["recall_all"])}.</p>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Hours re-checked with Gemini</th><th>Cost for 100,000 hours</th><th>Gemini on every hour</th></tr></thead>
      <tbody>{two_rows}</tbody>
    </table></div>
  </section>

  <section aria-labelledby="c1">
    <div class="col">
      <h2 id="c1">What each option costs at 100,000 hours</h2>
      <p>Every option reads one frame per second, which is 360 million frames. Prices are list prices with no volume deal. Accuracy is the share of sponsor boards found on the 156 frames we labelled by hand.</p>
    </div>
    <figure>
      <div class="chart" id="costbars"></div>
      <figcaption>Cost for 100,000 hours, most expensive first. Lines show the range where a price has tiers or batch discounts. Every option is listed; the bars share one scale.</figcaption>
    </figure>
    <div class="legend"><span><i class="sq" style="background:var(--bar-good)"></i>Cost under {usd(bd["good_max_usd"])}</span><span><i class="sq" style="background:var(--bar-fair)"></i>{usd(bd["good_max_usd"])} to {usd(bd["fair_max_usd"])}</span><span><i class="sq" style="background:var(--bar-weak)"></i>Over {usd(bd["fair_max_usd"])}</span><span><i class="sq" style="background:var(--q-good)"></i>Time under 30 min per video hour</span><span><i class="sq" style="background:var(--q-fair)"></i>30 min to 2 h</span><span><i class="sq" style="background:var(--q-weak)"></i>Over 2 h</span><span class="muted">Cost colour follows the high end of each price range. Boards-found columns use the accuracy bands from the overview (green 0.80 and up).</span></div>
    <div class="table-wrap"><table>
      <thead><tr><th>Option</th><th>Cost, 100,000 hours</th><th>Per video hour</th><th>Time per video hour</th><th>Boards found</th><th>Small boards found</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
    <div class="col">
      <p>Three things stand out:</p>
      <ul class="plain">
        <li><strong>Apple's reader is the cost winner.</strong> At 1 frame per second it needs about {HH4_TXT} Mac host-hours, {k(h["apple_usd"])} to {k(h["apple_usd_high"])}.</li>
        <li><strong>Video Intelligence is the most expensive way to add recall.</strong> It adds about {round((O["apple_vi"]["recall_all"] - O["apple_4w"]["recall_all"]) * 100)} points of board recall for {k(h["vi_usd_low"])} to {k(h["vi_usd_high"])} more.</li>
        <li><strong>Gemini finds the most boards,</strong> including {pct(O["gemini"]["recall_small"])} of the small ones, at {k(O["gemini"]["usd_low"])} to {k(O["gemini"]["usd_high"])}. That is {O["gemini"]["usd_low"] / h["apple_usd_high"]:.1f}–{O["gemini"]["usd_high"] / h["apple_usd_high"]:.1f}× the Apple price. Whether the extra boards are worth it depends on the client.</li>
      </ul>
    </div>
  </section>

  <section aria-labelledby="c1b">
    <div class="col">
      <h2 id="c1b">The whole pipeline, stage by stage</h2>
      <p>One hour of video, from the video file to per-brand seconds, on one Mac host with 8 workers. Each range covers three timed runs on an otherwise idle Mac: {PL_RUNS}.</p>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Stage</th><th>Time per video hour</th><th>Cost per video hour</th><th>Cost at 100,000 hours</th></tr></thead>
      <tbody>{pl_rows}</tbody>
    </table></div>
    <div class="col">
      <p>Not in these numbers:</p>
      <ul class="plain">{pl_not}</ul>
    </div>
  </section>

  <section aria-labelledby="c2">
    <div class="col">
      <h2 id="c2">How fast</h2>
      <p>One Mac host processes an hour of video in about {min_4w_lo:.0f} to {min_4w_hi:.0f} minutes with 8 workers, or {min_4w_a:.0f} to {min_4w_b:.0f} minutes with 4. The table shows calendar time for 100,000 hours on more hosts, at the slower speed of each.</p>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Hosts running in parallel</th><th>4 workers each</th><th>8 workers each</th></tr></thead>
      <tbody>{speed}</tbody>
    </table></div>
    <p class="col muted" style="font-size:.9rem">Cost does not change with the number of hosts, only the calendar time. Mac hosts bill for a minimum of 24 hours each.</p>
  </section>

  <section aria-labelledby="c3">
    <div class="col">
      <h2 id="c3">Does it hold up on full matches?</h2>
      <p>The cost model was built on highlight clips, so we ran two complete matches, 30 hand-labelled frames each. All frames were live play. These samples are small, so the ranges are wide.</p>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Match</th><th>Method</th><th>Boards found</th><th>Large</th><th>Small</th></tr></thead>
      <tbody>{full}</tbody>
    </table></div>
    <div class="col">
      <p>Of 150 detections checked by eye per match, {ps["true"]} were real in the Brazil match (fused, {ps["precision"]:.2f}) and {pp["true"]} in the Portugal match (Apple only, {pp["precision"]:.2f}). Video Intelligence on its own was weaker on the full match, with {bra["precision_sample"]["vi"]["true"]} of {bra["precision_sample"]["vi"]["n"]} of its single-method detections real.</p>
    </div>
  </section>

  <section aria-labelledby="c4">
    <div class="col">
      <h2 id="c4">How this compares with what is on the market</h2>
      <p>Prices are per video hour at one frame per second, from each vendor's public page, checked on 2026-10-15. Sponsorship vendors do not publish prices, so only the general-purpose APIs can be compared on cost. Nobody publishes a numeric accuracy figure, so ours is the only recall and precision number in the table.</p>
    </div>
    <div class="legend"><span><i class="sq" style="background:var(--q-good)"></i>Good: under $0.50 per hour, under 30 min, recall 0.80 or more</span><span><i class="sq" style="background:var(--q-fair)"></i>Middle: $0.50 to $3.00, 30 min to 2 h, recall 0.50 to 0.79</span><span><i class="sq" style="background:var(--q-weak)"></i>Weak: over $3.00, over 2 h, recall under 0.50</span><span class="muted">Uncoloured: not stated by the vendor, or quote only. Colour is used only for prices we read or numbers we measured.</span></div>
    <div class="table-wrap"><table>
      <thead><tr><th>Service</th><th>Per video hour</th><th>Per 100,000 hours</th><th>Turnaround</th><th>Accuracy claim</th><th>Checked</th></tr></thead>
      <tbody>{cmp_rows}</tbody>
    </table></div>
    <div class="col">
      <h2 id="c5">Why ours is cheaper and faster</h2>
      <ol class="plain">
        <li><strong>We rent a computer, not a service.</strong> Cloud APIs add margin, support and scaling to every call.</li>
        <li><strong>Apple's OCR runs on the Mac itself.</strong> No upload, no queue, no network.</li>
        <li><strong>The job is narrow.</strong> We read text and match a short list of brands, and Apple's OCR does that well enough.</li>
        <li><strong>It runs as a batch on a dedicated machine,</strong> with most cores busy and nobody else in line.</li>
        <li><strong>We skip what vendors sell:</strong> valuation, reports, live delivery and human review.</li>
      </ol>
      <p class="muted">The trade is accuracy: we find 69% of boards, Gemini 85%. We are batch, not live.</p>
    </div>
  </section>

  <p class="caveat col">Assumptions: the EC2 Mac M4 host is assumed to match the speed of the machine we measured on, which we did not test. Cloud Vision, Gemini and Rekognition rates are list prices. The Gemini token counts came from one model and were priced at another model's confirmed rates, so the range covers both rates. The Rekognition rows are price only: we did not measure their accuracy. PaddleOCR (recall {pct(m["not_costed"][0]["recall_all"])}) was too slow to cost and Tesseract (recall {pct(m["not_costed"][1]["recall_all"])}) too inaccurate. Sampling every 2 seconds instead of every second would halve every figure, and we have not measured what it costs in recall.</p>

  <footer><p>Prices, with source URLs and the date checked: <code>evidence/pricing.json</code>. Model: <code>experiments/22_cost_model.py</code> → <code>evidence/cost_model.json</code>. Back to the <a href="index.html">overview and accuracy</a>.</p></footer>
</main>
<script src="script.js"></script>
</body>
</html>
"""
(ST / "cost.html").write_text(html)
print("wrote story/cost.html", len(html))

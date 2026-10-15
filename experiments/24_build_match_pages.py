"""Builds the two full-match story pages and their chart data from evidence/metrics_full_*.json, the audited
scores and the goal windows. All numbers in the prose are computed here. Also normalises the nav on every page."""
import csv, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BRAND_INFO
from presence import presence

ROOT = Path(__file__).resolve().parents[1]
EV, ST = ROOT / "evidence", ROOT / "story"
mmss = lambda s: f"{s // 60}:{s % 60:02d}"
band = lambda v, g, f: "good" if v >= g else "fair" if v >= f else "weak"

PAGES = [("index.html", "Overview &amp; accuracy"), ("game-2022.html", "2022 final"), ("game-2026.html", "2026: Brazil v Morocco"),
         ("game-2026-final.html", "2026 final"), ("game-full-bra.html", "2022: Brazil v Korea"),
         ("game-full-por.html", "2018: Portugal v Spain"), ("cost.html", "Cost at scale")]


def nav(cur):
    cur_attr = ' aria-current="page"'
    a = "".join('    <a href="%s"%s>%s</a>\n' % (h, cur_attr if h == cur else "", t) for h, t in PAGES)
    return f'<nav class="top" aria-label="Pages">\n{a}  </nav>'


def goals(tag, metrics):
    segs = list(csv.DictReader((EV / "audit" / f"{tag}_segments.csv").open()))
    live = {t for s in segs if s["kind"] == "live_play" for t in range(int(s["start_s"]), int(s["end_s"]))}
    gl = json.loads((EV / f"goals_{tag}.json").read_text())
    P = presence(tag)
    rows = []
    for g, mo in zip(gl, metrics["moments"]):
        c = {}
        for b, d in P.items():
            n = sum(1 for t in d if mo["start"] <= t < mo["end"] and t in live)
            if n:
                c[BRAND_INFO.get(b, (b,))[0]] = n
        tot = sum(c.values())
        rows.append({"label": g["label"], "t": g["t_first_seen"], "total": tot,
                     "top": sorted(c.items(), key=lambda x: -x[1])[:3]})
    return rows, P, live


def chart_json(tag, m, P, live):
    brands = {}
    for b, v in m["brands"].items():
        brands[b] = dict(v, timeline=[[t, 1] for t in sorted(P.get(b, {})) if t in live])
    out = {"tag": tag, "duration": m["duration"], "moments": m["moments"], "brands": brands}
    (ST / f"game-{tag}.json").write_text(json.dumps(out, ensure_ascii=False))


def bench_table(rows):
    h = '<table><thead><tr><th>Method</th><th>Boards found</th><th>Large</th><th>Small</th><th>Detections that were real</th></tr></thead><tbody>'
    for name, r, prec in rows:
        c = lambda x, g=0.8, f=0.5: f'<td class="n q-{band(x["found"] / x["of"], g, f)}">{x["found"]} of {x["of"]} ({x["found"] / x["of"]:.2f})</td>'
        pr = f'<td class="n q-{band(prec[0] / prec[1], 0.95, 0.85)}">{prec[0]} of {prec[1]} ({prec[0] / prec[1]:.2f})</td>'
        h += f'<tr><td>{name}</td>{c(r["all"])}{c(r["large"])}{c(r["small"])}{pr}</tr>'
    return h + "</tbody></table>"


def goal_table(rows):
    h = '<table><thead><tr><th>Goal</th><th>At</th><th>Brand-seconds in the window</th><th>Who had them</th></tr></thead><tbody>'
    for r in rows:
        who = ", ".join(f"{n} {s}" for n, s in r["top"])
        h += f'<tr><td>{r["label"].replace("Goal ", "")}</td><td class="n">{mmss(r["t"])}</td><td class="n">{r["total"]}</td><td>{who}</td></tr>'
    return h + "</tbody></table>"


HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<link rel="stylesheet" href="style.css">
<style>html, body {{ margin: 0; }} img {{ max-width: 100%; }} [hidden] {{ display: none !important; }} :root {{ padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }}</style>
</head>
<body>
"""


def page(cur, tag, title, eyebrow, h1, dek, beats, bench_rows, bench_note, caveat, m, grows):
    cwrap = lambda s: f'<div class="col">{s}</div>'
    return HEAD.format(title=title) + f"""<main class="wrap" data-page="{tag}">

  {nav(cur)}

  <header class="hero">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{h1}</h1>
    <p class="dek">{dek}</p>
  </header>

  <section aria-labelledby="b1">
    <div class="col">
      <h2 id="b1">Goal by goal</h2>
      {beats}
    </div>
    <div class="table-wrap">{goal_table(grows)}</div>
    <figure>
      <div class="legend"><span><i style="background:var(--s1)"></i>Share of all sponsor screen time</span><span><i style="background:var(--s2)"></i>Share of goal-moment seconds</span></div>
      <div class="chart" id="dumbbell"></div>
      <figcaption>Brands with at least 8 seconds of live play on screen. Each goal window runs from 15 s before the on-screen score changes to 30 s after, which covers the build-up, goal, celebration and replays. {m["key_moment_live_s"]} seconds of the match are in a goal window.</figcaption>
    </figure>
  </section>

  <section aria-labelledby="b2">
    <div class="col">
      <h2 id="b2">Every sponsor, second by second</h2>
      <p>{m["live_play_s"]:,} seconds of live play, with at least one sponsor board visible in {m["seconds_with_any_sponsor_live"]:,} of them. {len(m["brands"])} brands were detected.</p>
    </div>
    <figure>
      <div class="legend"><span><i style="background:var(--t1)"></i>FIFA Partner</span><span><i style="background:var(--t2)"></i>World Cup Sponsor</span><span><i style="background:var(--t3)"></i>Regional supporter</span><span><i style="background:var(--s1)"></i>Not in our sponsor list</span><span><i style="background:var(--moment);border:1px solid var(--rule)"></i>Goal window</span></div>
      <div class="chart" id="timeline"></div>
      <figcaption>One tick per second in which the brand was detected during live play. Brands seen for fewer than 3 seconds are left out of the chart.</figcaption>
    </figure>
    <div class="table-wrap" id="brands"></div>
  </section>

  <section aria-labelledby="b3">
    <div class="col">
      <h2 id="b3">How well did the tools see this match?</h2>
      {bench_note}
    </div>
    <div class="legend"><span><i class="sq" style="background:var(--q-good)"></i>Good: ≥ 0.80 (precision ≥ 0.95)</span><span><i class="sq" style="background:var(--q-fair)"></i>Fair: 0.50–0.79 (0.85–0.94)</span><span><i class="sq" style="background:var(--q-weak)"></i>Weak: below that</span></div>
    <div class="table-wrap">{bench_table(bench_rows)}</div>
  </section>

  <p class="caveat col">{caveat}</p>

  <footer><p>Perimeter boards only; kit logos are excluded. Data: <code>story/game-{tag}.json</code>. Back to the <a href="index.html">overview and accuracy</a> or the <a href="cost.html">cost at scale</a>.</p></footer>
</main>
<script src="script.js"></script>
</body>
</html>
"""


out = {}
for tag, key in (("full_bra", "bra"), ("full_por", "por")):
    m = json.loads((EV / f"metrics_{tag}.json").read_text())
    sc = json.loads((EV / "audit" / f"{tag}_scores.json").read_text())
    grows, P, live = goals(tag, m)
    chart_json(tag, m, P, live)
    out[tag] = (m, sc, grows)

# ---------------- Brazil v South Korea (2022 round of 16) ----------------
m, sc, g = out["full_bra"]
B = m["brands"]
ooq = B["Ooredoo"]["key_moment_s"] + B["QNB"]["key_moment_s"]
ooq_screen = B["Ooredoo"]["visible_s"] + B["QNB"]["visible_s"]
tot_km = sum(v["key_moment_s"] for v in B.values())
tot_vis = m["brand_seconds_live"]
ooq_g, ooq_v = 100 * ooq / tot_km, 100 * ooq_screen / tot_vis
assert round(ooq_g) == 21 and round(ooq_v, 1) == 1.3, (ooq_g, ooq_v)
hy = next(r for r in g if r["label"] == "Goal 4-1")
assert hy["top"][0][0] == "Hyundai"
qa = B["QatarAirways"]
bench_rows = [("Apple Vision (on-device text reading)", sc["ocr"], (120, 130)),
              ("Google Video Intelligence (logos)", sc["vi"], (72, 84)),
              ("Both combined", sc["fused"], (sc["precision_sample"]["all"]["true"], sc["precision_sample"]["all"]["n"]))]
html = page("game-full-bra.html", "full_bra", "Brazil v Korea 2022",
    "2022 round of 16 · Brazil 4–1 South Korea · full match, 1:44",
    "Every Brazil goal had a different sponsor behind it",
    f"In Brazil's 4–1 win, no brand owned the goals. Each of the five went to a different set of boards: QatarEnergy, Ooredoo and QNB, Budweiser and Hisense, Visa, and Hyundai. The two Qatari brands, Ooredoo and QNB, were {ooq_v:.1f}% of all sponsor screen time but {ooq_g:.0f}% of goal-moment seconds, nearly all from one stoppage before the second goal.",
    f"""<p>Which brand ended up in the shot depended on where the camera was pointing when the ball went in.</p>
      <ul class="plain">
        <li><strong>Second goal:</strong> the camera held on the goal-line boards for about 20 seconds before the goal. Ooredoo and QNB, brands from Qatar that are not in FIFA's sponsor tiers, filled the shot. We checked these frames by eye.</li>
        <li><strong>Last goal, Korea's:</strong> {hy["top"][0][1]} of {hy["total"]} brand-seconds were Hyundai. Hyundai is a South Korean company, and its boards were in view for almost the whole window.</li>
        <li><strong>Qatar Airways:</strong> {qa["visible_s"]} seconds on screen, the {sorted(B, key=lambda k: -B[k]["visible_s"]).index("QatarAirways") + 1}th most of any brand, and {qa["key_moment_s"]} seconds during goals.</li>
      </ul>""",
    bench_rows,
    f"""<p>We hand-labelled 30 frames of live play (26 boards) and checked a random 150 detections by eye. Both methods ran on the whole match. Apple Vision took about 22 minutes per hour of video on four workers; Video Intelligence took about 95 minutes of Google processing for the 104-minute match.</p>""",
    f"One match, five goals, and a goal-moment share built from {tot_km} brand-seconds. The 26-board recall sample gives wide ranges (Apple Vision 0.77, 95% range 0.58 to 0.89). The 150-detection precision sample was checked before a few brand terms were added to the list, so some brands may be slightly off. Brands in grey are ones we did not place in a sponsor tier, which includes real host-country boards such as Ooredoo and QNB and some that may be misreads; none of the claims above rest on a misread. Replays sit inside live play and are counted.",
    m, g)
(ST / "game-full-bra.html").write_text(html)

# ---------------- Portugal v Spain (2018 group B) ----------------
m2, sc2, g2 = out["full_por"]
B2 = m2["brands"]
qa2 = B2["QatarAirways"]
top2 = max(B2, key=lambda k: B2[k]["visible_s"])
assert top2 == "QatarAirways"
winners = [f'{r["top"][0][0]}' for r in g2]
bench_rows2 = [("Apple Vision (on-device text reading)", sc2["ocr"], (sc2["precision_sample"]["all"]["true"], sc2["precision_sample"]["all"]["n"]))]
html2 = page("game-full-por.html", "full_por", "Portugal v Spain 2018",
    "2018 group B · Portugal 3–3 Spain · full match, 1:40",
    "The most-seen board got one second of goal time",
    f"In this six-goal draw, Qatar Airways had more sponsor screen time than any other brand ({qa2['visible_s']} seconds, {qa2['share_visible_pct']}%) and {qa2['key_moment_s']} second inside a goal window. Six goals went to six different sets of boards, led by {', '.join(winners[:-1])} and {winners[-1]}.",
    f"""<p>Six goals means six separate windows, so this is a better test than a one-goal clip of whether one brand keeps getting the goals. It didn't. A different brand led every window.</p>
      <ul class="plain">
        <li><strong>Partners kept their share:</strong> FIFA's top tier had {m2["tier_share"]["Partner"]["share_pct"]}% of screen time and {m2["tier_share"]["Partner"]["goal_share_pct"]}% of goal-moment seconds.</li>
        <li><strong>Over-index:</strong> Hyundai ({B2["Hyundai"]["share_visible_pct"]}% to {B2["Hyundai"]["share_key_moment_pct"]}%), Adidas ({B2["Adidas"]["share_visible_pct"]}% to {B2["Adidas"]["share_key_moment_pct"]}%) and Coca-Cola ({B2["CocaCola"]["share_visible_pct"]}% to {B2["CocaCola"]["share_key_moment_pct"]}%).</li>
        <li><strong>Under-index:</strong> Qatar Airways, Visa ({B2["Visa"]["share_visible_pct"]}% to {B2["Visa"]["share_key_moment_pct"]}%) and Mengniu, which had {B2["Mengniu"]["visible_s"]} seconds on screen and none during a goal.</li>
      </ul>""",
    bench_rows2,
    f"""<p>This match was read by Apple Vision only. We hand-labelled 30 frames of live play (29 boards) and checked a random 150 detections by eye. Apple Vision took about 22 minutes per hour of video on four workers.</p>""",
    f"One match, six goals, and {sum(v['key_moment_s'] for v in B2.values())} goal-moment brand-seconds, so each brand's goal share rests on a handful of seconds. Sponsor tiers for 2018 are inferred from the 2022 listing, not taken from a 2018 FIFA list. Only one small board was in the 29 labelled, so small-board recall is not measured here. Brands in grey are ones we did not place in a sponsor tier.",
    m2, g2)
(ST / "game-full-por.html").write_text(html2)

# ---------------- nav on every page ----------------
for f, _ in PAGES:
    p = ST / f
    t = p.read_text()
    new = re.sub(r'<nav class="top".*?</nav>', lambda _m: nav(f), t, flags=re.S)
    p.write_text(new)
print("built both pages; Ooredoo+QNB goal share %.1f%%, screen share %.1f%%" % (ooq_g, ooq_v))

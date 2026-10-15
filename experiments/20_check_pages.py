"""Assert every number in the story pages' prose against the regenerated JSON.

Each CLAIM is (page, text that must appear, value from the data). The text is built from the value, so a stale
number on a page fails. Afterwards every number left in the visible prose that no claim covers is listed, so new
prose can't add an unchecked number silently.

Usage: python 20_check_pages.py      (exit code 1 on any mismatch)
"""
import json
import re
import sys

from common import ROOT

S = ROOT / "story"
bench = json.loads((S / "benchmark.json").read_text())
G = {t: json.loads((S / f"game-{t}.json").read_text()) for t in bench["games"]}
SC = bench["scores"]
f22, g26, f26 = G["wc_final"], G["wc2026"], G["wc2026_final"]


def pct(x):
    return f"{round(x)}%"


def b(g, k):
    return g["brands"][k]


def tier(g, t, k="share_key_moment_pct"):
    return g["tiers"][t][k]


def mom(g, i, name):
    return next(x[2] for x in g["moments"][i]["brands"] if x[0] == name)


def mmss(t):
    return f"{t // 60}:{t % 60:02d}"


def rec(tag, key="board_all"):
    r = SC[tag]["fused"][key]
    return f"{r['found'] / r['of']:.2f}"  # from the counts, not the 3-decimal rounding in scores.json


def words(n):
    return {16: "Sixteen", 19: "Nineteen", 23: "Twenty-three"}[n]


three = ("Kraken", "Betano", "InterRapidisimo")
CLAIMS = [
    # landing
    ("index.html", f"held {pct(tier(f22, 'Partner'))} of the seconds around the goals in 2022 and {pct(tier(f26, 'Partner'))} in 2026"),
    ("index.html", f"held {pct(tier(g26, 'Supporter', 'share_visible_pct'))} of screen time, and three of them took {pct(sum(b(g26, k)['key_moment_s'] for k in three) / g26['key_moment_brand_seconds'] * 100)} of goal-moment seconds"),
    ("index.html", f'<b class="num">{pct(tier(f26, "Partner"))}</b><span>of the 2026 final'),
    ("index.html", f'<b class="num">{pct(tier(g26, "Supporter"))}</b><span>of Brazil v Morocco'),
    ("index.html", f"{pct(tier(f22, 'Partner'))} in the 2022 final, {pct(tier(g26, 'Partner'))} in the group game, {pct(tier(f26, 'Partner'))} in the 2026 final"),
    ("index.html", f"2022 final: {f22['brand_seconds']} brand-seconds, {f22['key_moment_brand_seconds']} of them in goal windows. 2026 group game: {g26['brand_seconds']} and {g26['key_moment_brand_seconds']}. 2026 final: {f26['brand_seconds']} and {f26['key_moment_brand_seconds']}."),
    ("index.html", f"framed for {g26['moments'][1]['end'] - g26['moments'][1]['start']} seconds of build-up"),
    ("index.html", f"{pct(f22['china']['share_visible_pct'])} in the 2022 final (Wanda, Vivo, Hisense, Mengniu), {pct(g26['china']['share_visible_pct'])} in the group game (Lenovo, Hisense, Mengniu) and {pct(f26['china']['share_visible_pct'])} in the 2026 final (Lenovo, Hisense)"),
    ("index.html", f"its goal window holds only {f26['key_moment_brand_seconds']} detected brand-seconds"),
    ("index.html", f"Budweiser: {pct(b(f22, 'Budweiser')['share_visible_pct'])} of screen time, {pct(b(f22, 'Budweiser')['share_key_moment_pct'])} of goal-moment seconds"),
    ("index.html", f"Kraken, Betano and Inter Rapidísimo: {pct(sum(b(g26, k)['visible_s'] for k in three) / g26['brand_seconds'] * 100)} of screen time, {pct(tier(g26, 'Supporter'))} of goal moments"),
    ("index.html", f"Aramco: {pct(b(f26, 'Aramco')['share_visible_pct'])} of screen time, {pct(b(f26, 'Aramco')['share_key_moment_pct'])} of goal-moment seconds"),
    ("index.html", f"{SC['wc_final']['frames_labelled']} frames with {SC['wc_final']['board_marks_labelled']} boards in the 2022 final, {SC['wc2026']['frames_labelled']} frames with {SC['wc2026']['board_marks_labelled']} boards in the group game, and {SC['wc2026_final']['frames_labelled']} frames with {SC['wc2026_final']['board_marks_labelled']} boards in the 2026 final"),
    ("index.html", f"about {round(SC['wc_final']['fused']['board_S']['recall'] * 10)} in 10 in the 2022 final, {round(SC['wc2026']['fused']['board_S']['recall'] * 10)} in 10 in the group game, and {SC['wc2026_final']['fused']['board_S']['found']} of {SC['wc2026_final']['fused']['board_S']['of']} in the 2026 final"),
    ("index.html", f"recall {bench['dropped']['owlv2_recall']:.2f}, precision {bench['dropped']['owlv2_precision']:.2f}"),
    ("index.html", f"found {bench['dropped']['cloud_vision_recall'] * 100:.1f}% of {bench['dropped']['ee_gt_boxes']:,} labelled logos"),
    # 2022 final
    ("game-2022.html", f"Budweiser still spent more time on screen around the goals than any other brand: {b(f22, 'Budweiser')['key_moment_s']} seconds. That's {pct(b(f22, 'Budweiser')['share_key_moment_pct'])} of goal-moment time, from {pct(b(f22, 'Budweiser')['share_visible_pct'])}"),
    ("game-2022.html", f"gave Budweiser {mom(f22, 4, 'Budweiser')} seconds and Crypto.com {mom(f22, 4, 'Crypto.com')}"),
    ("game-2022.html", f"<p>{words(len(f22['brands']))} sponsors appear on the boards."),
    ("game-2022.html", f"Hisense and QatarEnergy: {b(f22, 'Hisense')['visible_s'] + b(f22, 'QatarEnergy')['visible_s']} seconds between them"),
    ("game-2022.html", f"Board recall in this video is {rec('wc_final')}"),
    ("game-2022.html", f"{f22['seconds_with_any_sponsor']} of the {f22['duration']} seconds"),
    # 2026 group game
    ("game-2026.html", f"they took {pct(tier(g26, 'Supporter'))} of goal-moment seconds"),
    ("game-2026.html", f"Saibari's opener for Morocco went to Hyundai ({mom(g26, 0, 'Hyundai')} seconds)"),
    ("game-2026.html", f"Kraken, a crypto exchange ({mom(g26, 1, 'Kraken')} s), Betano, a betting brand ({mom(g26, 1, 'Betano')} s), and Inter Rapidísimo, a Colombian courier ({mom(g26, 1, 'Inter Rapidísimo')} s). Visa got {mom(g26, 1, 'Visa')}."),
    ("game-2026.html", f"were on screen for {sum(b(g26, k)['visible_s'] for k in ('Aramco', 'Lenovo', 'Adidas'))} seconds between them"),
    ("game-2026.html", f"Saibari {mmss(g26['moments'][0]['start'])}–{mmss(g26['moments'][0]['end'])}, Vinícius {mmss(g26['moments'][1]['start'])}–{mmss(g26['moments'][1]['end'])}"),
    ("game-2026.html", f"{b(g26, 'Lenovo')['visible_s']} seconds on screen, none during a goal"),
    ("game-2026.html", f"<p>{words(len(g26['brands']))} sponsors appear in ten minutes"),
    ("game-2026.html", f"Michelob Ultra, for {b(g26, 'MichelobUltra')['visible_s']} seconds"),
    ("game-2026.html", f"held {pct(g26['china']['share_visible_pct'])} of screen time, half their 2022 share"),
    ("game-2026.html", f"{g26['seconds_with_any_sponsor']} of the {g26['duration']} seconds"),
    ("game-2026.html", f"Board recall in this video is {rec('wc2026')}"),
    ("game-2026.html", f"The {pct(tier(g26, 'Supporter'))} figure"),
    # 2026 final
    ("game-2026-final.html", f"Aramco ended with {b(f26, 'Aramco')['key_moment_s']} of the {f26['key_moment_brand_seconds']} brand-seconds we detected around the goal: {pct(b(f26, 'Aramco')['share_key_moment_pct'])} of goal-moment time, from {pct(b(f26, 'Aramco')['share_visible_pct'])}"),
    ("game-2026-final.html", f"from the start of the move at {mmss(f26['moments'][0]['start'])} to the restart at {mmss(f26['moments'][0]['end'])}"),
    ("game-2026-final.html", f"Hisense held the boards for the first {mom(f26, 0, 'Hisense')} seconds"),
    ("game-2026-final.html", f"Michelob Ultra got {['', 'one'][mom(f26, 0, 'Michelob Ultra')]} second at the end"),
    ("game-2026-final.html", f"Lenovo had more screen time than any other brand, {b(f26, 'Lenovo')['visible_s']} seconds"),
    ("game-2026-final.html", f"({mmss(f26['moments'][0]['start'])}–{mmss(f26['moments'][0]['end'])}). It holds only {f26['key_moment_brand_seconds']} detected brand-seconds, so each second moves a brand's share by {round(100 / f26['key_moment_brand_seconds'])} points"),
    ("game-2026-final.html", f"<p>{words(len(f26['brands']))} sponsors appear in under two minutes. FIFA's top-tier partners had {pct(tier(f26, 'Partner', 'share_visible_pct'))}"),
    ("game-2026-final.html", f"Lenovo and Hisense held {pct(f26['china']['share_visible_pct'])} of screen time and {pct(f26['china']['share_key_moment_pct'])} of goal time"),
    ("game-2026-final.html", f"Michelob Ultra, for {b(f26, 'MichelobUltra')['visible_s']} seconds"),
    ("game-2026-final.html", f"{f26['seconds_with_any_sponsor']} of the {f26['duration']} seconds"),
    ("game-2026-final.html", f"Board recall in this video is {rec('wc2026_final')}, and only {SC['wc2026_final']['fused']['board_S']['found']} of {SC['wc2026_final']['fused']['board_S']['of']} small"),
]

# Logical checks that are not a single number: ordering and "more than either other game".
LOGIC = [
    ("Budweiser has the most goal-moment seconds in the 2022 final",
     max(f22["brands"].values(), key=lambda v: v["key_moment_s"])["name"] == "Budweiser"),
    ("Lenovo has the most screen time in the 2026 final",
     max(f26["brands"].values(), key=lambda v: v["visible_s"])["name"] == "Lenovo"),
    ("2026 final partner screen share exceeds the other games",
     tier(f26, "Partner", "share_visible_pct") > max(tier(f22, "Partner", "share_visible_pct"), tier(g26, "Partner", "share_visible_pct"))),
    ("Every supporter goal second in the group game belongs to the three named brands",
     sum(b(g26, k)["key_moment_s"] for k in three) == g26["tiers"]["Supporter"]["key_moment_s"]),
    ("Lenovo, Visa and Hyundai have no goal time in the 2026 final",
     all(b(f26, k)["key_moment_s"] == 0 for k in ("Lenovo", "Visa", "Hyundai"))),
    ("Group game: Kraken, Betano, Inter Rapidísimo each ~5% of screen time and over 20% of goal time",
     all(4.5 <= b(g26, k)["share_visible_pct"] < 6.5 and b(g26, k)["share_key_moment_pct"] > 20 for k in three)),
]


def prose(html):
    html = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", "", html)
    return re.sub(r"\s+", " ", html)


fail = 0
covered = {}
for page, text in CLAIMS:
    raw = (S / page).read_text()
    ok = text in raw or text in prose(raw)
    covered.setdefault(page, []).append(text)
    if not ok:
        fail += 1
        print(f"MISMATCH {page}: expected text not found:\n    {text}")
for name, ok in LOGIC:
    if not ok:
        fail += 1
        print("LOGIC FAIL:", name)

# Numbers in prose not covered by any claim (years, clock times, fixed method facts are listed for a human look).
for page in ("index.html", "game-2022.html", "game-2026.html", "game-2026-final.html"):
    txt = prose((S / page).read_text())
    for t in covered.get(page, []):
        txt = txt.replace(prose(t), " ")
    left = sorted(set(re.findall(r"\d[\d,.:]*%?", txt)))
    print(f"{page}: unchecked numbers (context, dates, clock times): {' '.join(left)}")

print(f"{len(CLAIMS)} claims, {len(LOGIC)} logic checks, {fail} failures")
sys.exit(1 if fail else 0)

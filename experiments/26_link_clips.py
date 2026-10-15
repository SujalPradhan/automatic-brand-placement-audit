"""Adds YouTube timestamps to every evidence image on the hand-written story pages (idempotent):
the figure gets data-yt/data-t and a link: '▶ Play at m:ss' (seeks the page's one player) on game pages, 'Watch on YouTube' elsewhere."""
import re
from pathlib import Path

from youtube import PLAYER, SHOTS, YT, link

PAGE_TAG = {"game-2022.html": "wc_final", "game-2026.html": "wc2026", "game-2026-final.html": "wc2026_final"}
ST = Path(__file__).resolve().parents[1] / "story"
for f in ("index.html", "game-2022.html", "game-2026.html", "game-2026-final.html"):
    p = ST / f
    s = p.read_text()

    def fix(m):
        fig = m.group(0)
        name = re.search(r'src="img/([a-z0-9_]+)\.jpg"', fig).group(1)
        tag, t = SHOTS[name]
        fig = re.sub(r"<figure[^>]*>", f'<figure data-yt="{YT[tag]}" data-t="{t}">', fig, count=1)
        fig = re.sub(r'\s*<a class="yt"[^>]*>[^<]*</a>', "", fig)
        return fig.replace("</figcaption>", f" {link(tag, t, here=PAGE_TAG.get(f) == tag)}</figcaption>")

    s2 = re.sub(r'<figure[^>]*><img src="img/[^"]+"[^>]*>.*?</figure>', fix, s, flags=re.S)
    tag = PAGE_TAG.get(f)
    if tag:
        s2 = re.sub(r'<main class="wrap" data-page="([^"]+)"[^>]*>', lambda m: f'<main class="wrap" data-page="{m.group(1)}" data-yt="{YT[tag]}">', s2, count=1)
        s2 = re.sub(r'\s*<div class="player">.*?</p></div>', "", s2, flags=re.S)
        s2 = re.sub(r'(\n\s*<figure>\s*<div class="legend">(?:(?!</figure>).)*?id="timeline")', "\n    " + PLAYER + r"\1", s2, count=1, flags=re.S)
    p.write_text(s2)
    print(f, s2.count("data-yt="), "clips")

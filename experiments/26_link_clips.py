"""Adds YouTube timestamps to every evidence image on the hand-written story pages (idempotent):
the figure gets data-yt/data-t (the Pages build swaps the still for an embedded player) and a 'Watch on YouTube' link."""
import re
from pathlib import Path

from youtube import SHOTS, YT, link

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
        return fig.replace("</figcaption>", f" {link(tag, t)}</figcaption>")

    s2 = re.sub(r'<figure[^>]*><img src="img/[^"]+"[^>]*>.*?</figure>', fix, s, flags=re.S)
    p.write_text(s2)
    print(f, s2.count("data-yt="), "clips")

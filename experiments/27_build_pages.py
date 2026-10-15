"""Builds the GitHub Pages copy of the site in docs/ from story/.
- every figure with data-yt gets an embedded YouTube player at its timestamp in place of the still or link card
- index.html (a fragment for the artifact host) is wrapped in a full HTML document
Images are not copied: the public repo carries no broadcast stills."""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ST, OUT = ROOT / "story", ROOT / "docs"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
for f in ST.iterdir():
    if f.suffix in (".css", ".js", ".json"):
        shutil.copy(f, OUT / f.name)


def embed(m):
    fig = m.group(0)
    vid, t = re.search(r'data-yt="([^"]+)" data-t="(\d+)"', fig).groups()
    player = (f'<div class="yt-embed"><iframe src="https://www.youtube-nocookie.com/embed/{vid}?start={t}&rel=0" '
              f'title="Match footage at {t} seconds" loading="lazy" '
              f'allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>')
    fig = re.sub(r"<img [^>]*>", player, fig, count=1)
    fig = re.sub(r'<a class="clip-card".*?</a>', player, fig, count=1, flags=re.S)
    return fig


HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')
n = 0
for f in ST.glob("*.html"):
    s = f.read_text()
    s, k = re.subn(r"<figure[^>]*data-yt=.*?</figure>", embed, s, flags=re.S)
    n += k
    if not s.lstrip().lower().startswith("<!doctype"):
        title_end = s.index("</title>") + len("</title>")
        main_at = s.index("<main")
        s = (HEAD + s[:main_at].strip() + "\n<style>html, body { margin: 0; } img { max-width: 100%; } [hidden] { display: none !important; }</style>\n"
             "</head>\n<body>\n" + s[main_at:].strip() + "\n</body>\n</html>\n")
    (OUT / f.name).write_text(s)
(OUT / ".nojekyll").write_text("")
print("docs/ built:", len(list(OUT.glob("*.html"))), "pages,", n, "embedded clips")

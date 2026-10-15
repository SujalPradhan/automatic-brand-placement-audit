"""Builds the GitHub Pages copy of the site in docs/ from story/.
- every figure with data-yt loses its still and keeps its caption and play button (one player per page)
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
    """The public site carries no stills (FIFA footage), and each page has a single player, so an evidence figure keeps
    its caption and its '▶ Play at m:ss' button only."""
    fig = re.sub(r"<img [^>]*>", "", m.group(0), count=1)
    return re.sub(r'<a class="clip-card" .*?</a>', "", fig, count=1, flags=re.S)


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
print("docs/ built:", len(list(OUT.glob("*.html"))), "pages,", n, "evidence figures without stills")

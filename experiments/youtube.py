"""YouTube sources for each analysed video. Lengths match our downloaded files to the second, so a timestamp in our
data is the same moment on YouTube."""
YT = {"wc_final": "agrGb25mJzs", "wc2026": "GmzcVuAAWR4", "wc2026_final": "6HaHNYjnghE",
      "full_bra": "JIQnnYy7qYk", "full_por": "EGjiKT12JR8"}

# our own copies in data/World-Cup/ (never published); serve_demo.py streams them to the in-page player
VIDEO_FILES = {"wc_final": "The Greatest World Cup FINAL Ever _1080p50.mp4",
               "wc2026": "Vini Jr and Saibari Star In Brazil v Morocco Deadlock _ 2026 World Cup EXTENDED HIGHLIGHTS_720p60.mp4",
               "wc2026_final": "Highlights _ Spain 1-0 Argentina _ FIFA World Cup 2026™ FINAL_1080p.mp4",
               "full_bra": "FULL-MATCH-Brazil-SnapYT.App.mp4", "full_por": "FULL-MATCH-Portugal-SnapYT.App.mp4"}

# evidence images on the story pages -> (video tag, second)
SHOTS = {"open_0001": ("wc_final", 1), "byjus_0836": ("wc_final", 516), "messi_winner": ("wc_final", 546),
         "mengniu_0645": ("wc_final", 645), "shootout_visa": ("wc_final", 676), "vinicius_goal": ("wc2026", 262),
         "saibari_goal": ("wc2026", 146), "lenovo_board": ("wc2026", 476), "final26_hisense": ("wc2026_final", 64),
         "final26_goal": ("wc2026_final", 69), "final26_partners": ("wc2026_final", 40)}


def mmss(s):
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def watch(tag, t):
    return f"https://www.youtube.com/watch?v={YT[tag]}&t={t}s"


def link(tag, t, here=True):
    """here: the page's own player is above, and script.js turns this into a seek (it opens YouTube where nothing plays)."""
    text = f"▶ Play at {mmss(t)}" if here else f"Watch on YouTube at {mmss(t)} ↗"
    return f'<a class="yt{" play-at" if here else ""}" href="{watch(tag, t)}" target="_blank" rel="noopener">{text}</a>'


def clip(tag, t, caption):
    """A key moment with a button that plays it in the page's one player (no second player or thumbnail)."""
    return f'<figure class="clip" data-yt="{YT[tag]}" data-t="{t}"><figcaption>{caption} {link(tag, t)}</figcaption></figure>'


PLAYER = ('<div class="player"><div class="player-frame"><div id="yt-player"></div></div>'
          '<p class="player-status">Click any tick, row or goal window in the chart below to jump the video to that second.</p></div>')

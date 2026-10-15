"""YouTube sources for each analysed video. Lengths match our downloaded files to the second, so a timestamp in our
data is the same moment on YouTube."""
YT = {"wc_final": "agrGb25mJzs", "wc2026": "GmzcVuAAWR4", "wc2026_final": "6HaHNYjnghE",
      "full_bra": "JIQnnYy7qYk", "full_por": "EGjiKT12JR8"}

# evidence images on the story pages -> (video tag, second)
SHOTS = {"open_0001": ("wc_final", 1), "byjus_0836": ("wc_final", 516), "messi_winner": ("wc_final", 546),
         "mengniu_0645": ("wc_final", 645), "shootout_visa": ("wc_final", 676), "vinicius_goal": ("wc2026", 262),
         "saibari_goal": ("wc2026", 146), "lenovo_board": ("wc2026", 476), "final26_hisense": ("wc2026_final", 64),
         "final26_goal": ("wc2026_final", 69), "final26_partners": ("wc2026_final", 40)}


def mmss(s):
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def watch(tag, t):
    return f"https://www.youtube.com/watch?v={YT[tag]}&t={t}s"


def link(tag, t):
    return f'<a class="yt" href="{watch(tag, t)}" target="_blank" rel="noopener">Watch on YouTube at {mmss(t)} ↗</a>'


def clip(tag, t, caption):
    """A figure the Pages build turns into an embedded player; in the artifact it is a link card."""
    return (f'<figure class="clip" data-yt="{YT[tag]}" data-t="{t}"><a class="clip-card" href="{watch(tag, t)}" target="_blank" rel="noopener">'
            f'<span>▶ Watch at {mmss(t)}</span></a><figcaption>{caption} {link(tag, t)}</figcaption></figure>')


PLAYER = ('<div class="player"><div class="player-frame"><div id="yt-player"></div></div>'
          '<p class="player-status">Click any tick, row or goal window in the chart below to jump the video to that second.</p></div>')

"""Local demo server: the story site plus our own match videos, so the one player on each game page plays in the page
and the timeline seeks it to the exact second we measured. Binds to this machine only; nothing is published.

    python experiments/serve_demo.py [port]      then open http://127.0.0.1:8000/

The site asks for video/<tag>.mp4; this maps each tag to its file in data/World-Cup/ (see youtube.VIDEO_FILES) and
answers HTTP Range requests, which browsers need to seek inside a multi-GB file. Python's built-in server does not."""
import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from youtube import VIDEO_FILES

ROOT = Path(__file__).resolve().parent.parent
STORY, VIDEOS = ROOT / "story", ROOT / "data" / "World-Cup"
CHUNK = 1 << 20


class Handler(SimpleHTTPRequestHandler):
    def _video(self, head):
        m = re.fullmatch(r"/video/(\w+)\.mp4", self.path.split("?")[0])
        if not m:
            return False
        name = VIDEO_FILES.get(m.group(1))                 # only mapped files, so no path tricks
        path = VIDEOS / name if name else None
        if not path or not path.is_file():
            self.send_error(404, "Video not found: put the file in data/World-Cup/")
            return True
        size = path.stat().st_size
        start, end = 0, size - 1
        r = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
        if r and (r.group(1) or r.group(2)):
            if r.group(1):
                start, end = int(r.group(1)), int(r.group(2)) if r.group(2) else size - 1
            else:                                          # bytes=-N: the last N bytes
                start = max(0, size - int(r.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return True
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        if head:
            return True
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    buf = f.read(min(CHUNK, left))
                    if not buf:
                        break
                    self.wfile.write(buf)
                    left -= len(buf)
            except (BrokenPipeError, ConnectionResetError):  # the browser cancels requests whenever you seek
                pass
        return True

    def do_GET(self):
        if not self._video(head=False):
            super().do_GET()

    def do_HEAD(self):
        if not self._video(head=True):
            super().do_HEAD()

    def log_message(self, fmt, *args):
        if not self.path.startswith("/video/"):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    missing = [t for t, n in VIDEO_FILES.items() if not (VIDEOS / n).is_file()]
    if missing:
        print("No local file for", ", ".join(missing), "- those pages fall back to YouTube links")
    print(f"Serving the story site with local video at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(STORY))).serve_forever()

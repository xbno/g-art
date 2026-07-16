"""CLI:
    python -m review build [section ...]     regenerate the site
    python -m review serve [--port 8787]     build + serve with auto-reload
    python -m review collect-stars --port N  one-shot server on a gallery's
                                             historical port: opening
                                             http://localhost:N captures that
                                             origin's starred ids and exits
    python -m review import-stars            raw captures + gallery manifests
                                             -> review/stars.json (committed)
"""

import argparse
import json
import logging
import threading
from functools import partial
from http.server import (BaseHTTPRequestHandler, SimpleHTTPRequestHandler,
                         ThreadingHTTPServer)
from pathlib import Path

from .build import OUT, SECTIONS, build, import_stars


class _NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


_COLLECT_PAGE = b"""<!doctype html><html><body style="font:15px monospace;
background:#181614;color:#eee;padding:48px">
<h2 id="s">capturing stars from this origin\xe2\x80\xa6</h2><script>
fetch('/save',{method:'POST',body:localStorage.getItem('stars')||'[]'})
 .then(r=>r.text()).then(t=>{document.getElementById('s').textContent=
 'captured '+t+' starred ids \xe2\x80\x94 done, you can close this tab.'});
</script></body></html>"""


class _StarCollector(BaseHTTPRequestHandler):
    outfile: Path

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_COLLECT_PAGE)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        ids = json.loads(self.rfile.read(n) or b"[]")
        self.outfile.write_text(json.dumps(ids, indent=1))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(str(len(ids)).encode())
        print(f"captured {len(ids)} starred ids -> {self.outfile}")
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, fmt, *args):
        pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="review")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build")
    b.add_argument("sections", nargs="*", choices=SECTIONS)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8787)
    s.add_argument("--no-build", action="store_true")
    c = sub.add_parser("collect-stars")
    c.add_argument("--port", type=int, required=True)
    sub.add_parser("import-stars")
    args = ap.parse_args()

    if args.cmd == "serve":
        if not args.no_build:
            build()
        handler = partial(_NoCache, directory=str(OUT))
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"review UI: http://127.0.0.1:{args.port}")
        srv.serve_forever()
    elif args.cmd == "collect-stars":
        OUT.mkdir(parents=True, exist_ok=True)
        handler = type("H", (_StarCollector,), {
            "outfile": OUT / f"stars_raw_{args.port}.json"})
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"open http://localhost:{args.port} to capture this "
              f"origin's stars (server exits after capture)")
        srv.serve_forever()
    elif args.cmd == "import-stars":
        import_stars()
    else:
        build(tuple(args.sections) if getattr(args, "sections", None)
              else SECTIONS)


if __name__ == "__main__":
    main()

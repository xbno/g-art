"""CLI: python -m review [build [section ...]] | serve [--port N] [--no-build]"""

import argparse
import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .build import OUT, SECTIONS, build


class _NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

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
    args = ap.parse_args()

    if args.cmd == "serve":
        if not args.no_build:
            build()
        handler = partial(_NoCache, directory=str(OUT))
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"review UI: http://127.0.0.1:{args.port}")
        srv.serve_forever()
    else:
        build(tuple(args.sections) if getattr(args, "sections", None)
              else SECTIONS)


if __name__ == "__main__":
    main()

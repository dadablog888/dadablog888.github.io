#!/usr/bin/env python3
"""Preview the actual single-repository Pages layout without rewriting paths."""
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PREFIX = urlsplit(json.loads((ROOT / 'content/site.json').read_text())['url']).path


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/':
            super().do_GET()
        elif path not in ['/robots.txt', '/.nojekyll'] and not path.startswith(PREFIX):
            self.send_error(404)
        else:
            super().do_GET()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(ROOT)))
    print(f'Local: http://127.0.0.1:{args.port}{PREFIX}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

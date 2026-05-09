#!/usr/bin/env python3
"""Tiny dev server: serves web/ as root, /data/ from data/, SPA fallback."""
import http.server
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "web"
DATA = ROOT / "data"

class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        from urllib.parse import urlparse
        clean = urlparse(path).path
        if clean.startswith('/data/'):
            return str(DATA / clean[6:])
        rel = clean.lstrip('/')
        candidate = WEB / rel
        if candidate.is_file():
            return str(candidate)
        return str(WEB / "index.html")

    def end_headers(self):
        if self.path.startswith('/data/'):
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == '__main__':
    os.chdir(str(WEB))
    s = http.server.HTTPServer(('', 8089), Handler)
    print(f"Dev server: http://localhost:8089/")
    s.serve_forever()

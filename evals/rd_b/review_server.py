"""Local-only human rating forms; stdlib only so Windows needs no model DLLs."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from evals.rd_b.review_data import digest, validate_rating

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / 'evals/reviews/b4'
RATINGS = ROOT / '.local-models/b4-reviews'


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type='application/json'):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {'/', '/calibration', '/panel'}:
            self.send(200, (PACKS / 'review.html').read_text(encoding='utf-8'), 'text/html; charset=utf-8')
        elif path in {'/pack/calibration', '/pack/panel'}:
            target = PACKS / (path.rsplit('/', 1)[-1] + '.json')
            if not target.exists():
                self.send(409, {'detail': 'This pack is awaiting enough completed matched evaluation cases.'})
            else:
                pack = json.loads(target.read_text())
                self.send(200, {'pack': pack, 'pack_sha256': digest(pack)})
        else:
            self.send(404, {'detail': 'Not found'})

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {'/ratings/calibration', '/ratings/panel'}:
            self.send(404, {'detail': 'Not found'})
            return
        origin = self.headers.get('Origin')
        allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
        if origin and origin not in allowed:
            self.send(403, {'detail': 'Use the local review page'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100_000:
                raise ValueError('Invalid ratings size')
            kind = path.rsplit('/', 1)[-1]
            pack = json.loads((PACKS / (kind + '.json')).read_text())
            payload = validate_rating(json.loads(self.rfile.read(length)), pack)
            payload['submitted_at'] = datetime.now(UTC).isoformat()
            RATINGS.mkdir(parents=True, exist_ok=True)
            name = kind + '-' + digest(payload['reviewer'].casefold())[:20] + '.json'
            (RATINGS / name).write_text(json.dumps(payload, indent=2))
            self.send(200, {'saved': True, 'items': len(payload['labels'])})
        except (ValueError, KeyError, FileNotFoundError) as error:
            self.send(422, {'detail': str(error)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8804)
    args = parser.parse_args()
    print(f'Author: http://127.0.0.1:{args.port}/calibration; classmates: /panel', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

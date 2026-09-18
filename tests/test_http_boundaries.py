"""Real loopback HTTP, synthetic bytes only; production URL checks stay enabled."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from PyPDF2 import PdfWriter

from ez.acquisition import Retriever
from ez.process import run
from ez.state import read_json


@contextmanager
def server(handler):
    service = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    service.daemon_threads = True
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{service.server_port}'
    finally:
        service.shutdown()
        service.server_close()
        thread.join(timeout=2)


class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass


class HttpBoundaryTests(unittest.TestCase):
    def test_real_404_then_alternative_pdf_preserves_diagnostics(self):
        buffer = BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=72, height=72); writer.write(buffer)
        payload = buffer.getvalue()

        class Handler(QuietHandler):
            def do_GET(self):
                if self.path == '/missing':
                    self.send_response(404); self.end_headers(); return
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers(); self.wfile.write(payload)

        with tempfile.TemporaryDirectory() as folder, server(Handler) as url:
            retriever = Retriever(folder, 's1', seconds=5, attempts=1, check_url=lambda _: None)
            result = retriever.acquire({'source_id': 's1'}, candidates=[(url + '/missing', 'direct'), (url + '/pdf', 'repository')])
            self.assertEqual(result['validation_status'], 'valid')
            self.assertEqual(result['identity_status'], 'needs_review')
            self.assertEqual(Path(result['pdf_path']).read_bytes(), payload)
            self.assertEqual(result['attempts'][0]['failure_code'], 'not_found')
            self.assertEqual(result['pdf_source'], 'repository')

    def test_trickle_stream_cannot_outlive_supervised_deadline(self):
        received = threading.Event()

        class Handler(QuietHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); received.set()
                try:
                    for _ in range(1500):
                        self.wfile.write(b'x'); self.wfile.flush(); time.sleep(.01)
                except (ConnectionError, OSError):
                    pass

        with tempfile.TemporaryDirectory() as folder, server(Handler) as url:
            # A read inactivity timeout cannot stop this stream. The parent must.
            code = ('from ez.acquisition import Retriever; '
                    f'Retriever({folder!r}, "s1", seconds=30, attempts=1, check_url=lambda u: None).request({url!r}, "fixture")')
            started = time.monotonic()
            # Include cold interpreter/import startup in the five-second budget;
            # the server would otherwise keep streaming for fifteen seconds.
            result = run([sys.executable, '-c', code], timeout=5)
            self.assertTrue(received.is_set(), 'The test must reach a real HTTP stream: ' + result.stderr)
            self.assertEqual(result.reason, 'deadline_exceeded')
            self.assertLess(time.monotonic() - started, 10)
            self.assertEqual(read_json(Path(folder) / 'attempts.json')[0]['result'], 'started')

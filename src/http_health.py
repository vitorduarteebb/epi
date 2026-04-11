"""Servidor HTTP mínimo (stdlib) para health check e página simples no browser."""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

log = logging.getLogger(__name__)

_HTML = """<!DOCTYPE html>
<html lang="pt">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor EPI</title></head>
<body>
<h1>Monitor EPI</h1>
<p>Serviço em execução.</p>
<p><a href="/health">Estado em JSON (/health)</a></p>
</body></html>
"""


def start_http_server(
    host: str,
    port: int,
    status_fn: Callable[[], dict],
) -> ThreadingHTTPServer:
    """
    Arranca servidor em thread daemon. status_fn() deve devolver um dict JSON-serializável.
    """

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            log.debug("%s - %s", self.address_string(), fmt % args)

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path in ("/", "/index.html"):
                body = _HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/health":
                try:
                    payload = status_fn()
                except Exception as e:
                    payload = {"ok": False, "error": str(e)}
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    t = threading.Thread(target=server.serve_forever, name="http-health", daemon=True)
    t.start()
    log.info("HTTP em http://%s:%s/ (e /health)", host, port)
    return server

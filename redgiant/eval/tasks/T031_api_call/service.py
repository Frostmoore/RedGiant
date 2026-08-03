"""Servizio locale deterministico per T031 (avviato dall'harness, mai dal
modello). Risponde su 127.0.0.1:8765 con JSON fisso."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PAYLOAD = {"service": "atlas-monitor", "version": "2.4.1",
           "uptime_days": 17, "healthy": True}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(PAYLOAD).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silenzioso
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8765), H).serve_forever()

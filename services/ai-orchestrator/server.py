"""Non-clinical placeholder for the constrained local LLM orchestrator."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/healthz":
            self.send_error(404)
            return
        response = json.dumps({"status": "placeholder", "llm_calls_enabled": False}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

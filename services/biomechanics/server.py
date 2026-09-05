"""HTTP boundary for non-clinical IMU preprocessing in the local dev stack."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from preprocessing import preprocess_transport_events

MAX_REQUEST_BYTES = 10 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "PhoenixBiomechanics/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/healthz":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "status": "ok",
                "clinical_scoring": False,
                "capabilities": ["timestamp_normalization", "resampling", "raw_filtering"],
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/preprocess":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            request = self._read_json()
            events = request["events"]
            signal_quality = request["signal_quality"]
            if not isinstance(events, list) or not isinstance(signal_quality, dict):
                raise ValueError("events must be a list and signal_quality must be an object")
            result = preprocess_transport_events(
                events,
                signal_quality=signal_quality,
                target_rate_hz=float(request.get("target_rate_hz", 20.0)),
                filter_window_samples=int(request.get("filter_window_samples", 3)),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"detail": str(error)})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "allowed": result.allowed,
                "reasons": result.reasons,
                "sample_rate_hz": result.sample_rate_hz,
                "parameters": result.parameters,
                "frames": result.frames,
                "clinical_scoring": False,
            },
        )

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length < 1 or content_length > MAX_REQUEST_BYTES:
            raise ValueError("invalid request body size")
        value = json.loads(self.rfile.read(content_length))
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        response = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def build_server(host: str = "0.0.0.0", port: int = 8080) -> HTTPServer:
    return HTTPServer((host, port), Handler)


if __name__ == "__main__":
    build_server().serve_forever()

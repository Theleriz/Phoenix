"""Dependency-free client for the internal non-clinical preprocessing service."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any


class PreprocessingUnavailable(RuntimeError):
    """The raw event is persisted, but technical preprocessing cannot run."""


class BiomechanicsClient:
    def __init__(self, url: str, *, timeout_seconds: float = 5.0) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds

    async def preprocess(
        self, *, events: list[dict[str, Any]], signal_quality: dict[str, Any]
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._preprocess_sync, events, signal_quality)

    def _preprocess_sync(
        self, events: list[dict[str, Any]], signal_quality: dict[str, Any]
    ) -> dict[str, Any]:
        body = json.dumps(
            {"events": events, "signal_quality": signal_quality}, ensure_ascii=False
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                if not 200 <= response.status < 300:
                    raise PreprocessingUnavailable(f"Biomechanics returned HTTP {response.status}")
                payload = json.loads(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise PreprocessingUnavailable("Biomechanics service is unavailable") from error
        if not isinstance(payload, dict):
            raise PreprocessingUnavailable("Biomechanics returned an invalid response")
        return payload

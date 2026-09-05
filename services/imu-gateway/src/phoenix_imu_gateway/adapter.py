"""Hardware-independent asynchronous adapter contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .models import RawIMUPacket, SensorInfo


class IMUAdapter(ABC):
    """Transport contract; implementations must never issue clinical feedback."""

    @abstractmethod
    async def discover(self) -> list[SensorInfo]:
        """Return known sensors. Hardware discovery needs an approved implementation."""

    @abstractmethod
    async def connect(self, sensor_id: str) -> None:
        """Connect one configured sensor."""

    @abstractmethod
    async def stream(self) -> AsyncIterator[RawIMUPacket]:
        """Yield raw, sequence-numbered samples."""

    @abstractmethod
    async def disconnect(self, sensor_id: str) -> None:
        """Disconnect one configured sensor."""

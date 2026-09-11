from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Connector(ABC):
    id: str
    label: str

    @abstractmethod
    async def snapshot(self) -> dict[str, Any]:
        """Return normalized data; never expose connector credentials."""


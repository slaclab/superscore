"""
Base shim abstract base class
"""
from __future__ import annotations

from typing import Any, Callable

from superscore.model import EpicsData


class _BaseShim:
    async def get(self, address: str) -> EpicsData:
        raise NotImplementedError

    async def put(self, address: str, value: Any):
        raise NotImplementedError

    def monitor(self, address: str, callback: Callable):
        raise NotImplementedError

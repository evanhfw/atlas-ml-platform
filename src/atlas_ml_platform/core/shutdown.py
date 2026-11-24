import asyncio


class RequestTracker:
    """Track in-flight HTTP requests and wait for a bounded drain."""

    def __init__(self) -> None:
        self._in_flight: int = 0
        self._idle: asyncio.Event = asyncio.Event()
        self._idle.set()

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def begin(self) -> None:
        self._in_flight += 1
        self._idle.clear()

    def end(self) -> None:
        if self._in_flight <= 0:
            return
        self._in_flight -= 1
        if self._in_flight == 0:
            self._idle.set()

    async def wait_for_idle(self, timeout_seconds: float) -> bool:
        if self._in_flight == 0:
            return True
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return False
        return True

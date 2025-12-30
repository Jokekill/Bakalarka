import asyncio
from typing import Optional, Awaitable, Callable


class SelfPlayController:
    """Manages a single running self-play task."""
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def stop(self) -> None:
        self._stop.set()

    async def start(self, runner: Callable[[asyncio.Event], Awaitable[None]]) -> None:
        if self.running:
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(runner(self._stop))

        # prevent "Task exception was never retrieved"
        def _cb(t: asyncio.Task) -> None:
            try:
                exc = t.exception()
                if exc:
                    print(f'[self-play] task failed: {exc!r}')
            except asyncio.CancelledError:
                pass

        self._task.add_done_callback(_cb)

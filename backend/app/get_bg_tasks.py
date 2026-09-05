import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class BackgroundTasks:

    def __init__(self):
        self._tasks: set[asyncio.Task[Any]] = set()

    def save_reference(self, task: asyncio.Task[Any]) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def defer(self, coro: Coroutine[Any, Any, Any]) -> None:
        self.save_reference(asyncio.create_task(coro))

    def is_empty(self) -> bool:
        return not self._tasks

    async def wait_until_empty(self) -> None:
        if self._tasks:
            logger.warning(
                "Waiting for background tasks",
                count=len(self._tasks),
            )
            result = await asyncio.gather(*self._tasks, return_exceptions=True)
            for r in result:
                logger.warning(f"Background task result: {r.with_traceback}")


background_tasks = BackgroundTasks()

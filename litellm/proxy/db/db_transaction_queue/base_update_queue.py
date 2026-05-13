"""
Base class for in memory buffer for database transactions
"""

import asyncio
import time
from typing import Optional

from litellm._logging import verbose_proxy_logger
from litellm._service_logger import ServiceLogging

service_logger_obj = (
    ServiceLogging()
)  # used for tracking metrics for In memory buffer, redis buffer, pod lock manager
from litellm.constants import (
    LITELLM_ASYNCIO_QUEUE_MAXSIZE,
    MAX_IN_MEMORY_QUEUE_FLUSH_COUNT,
    MAX_SIZE_IN_MEMORY_QUEUE,
)


PENDING_AGGREGATION_WAIT_TIMEOUT_SECONDS = 5.0


class BaseUpdateQueue:
    """Base class for in memory buffer for database transactions"""

    _threshold_warnings_emitted: bool = False

    def __init__(self):
        self.update_queue = asyncio.Queue(maxsize=LITELLM_ASYNCIO_QUEUE_MAXSIZE)
        self.MAX_SIZE_IN_MEMORY_QUEUE = MAX_SIZE_IN_MEMORY_QUEUE
        self._aggregation_lock = asyncio.Lock()
        self._aggregation_task: Optional[asyncio.Task] = None
        self._last_queue_full_warning_time = 0.0
        BaseUpdateQueue._maybe_emit_threshold_warnings()

    @classmethod
    def _maybe_emit_threshold_warnings(cls) -> None:
        """Emit misconfiguration warnings once per process, not per queue instance."""
        if cls._threshold_warnings_emitted:
            return
        cls._threshold_warnings_emitted = True
        if MAX_SIZE_IN_MEMORY_QUEUE >= LITELLM_ASYNCIO_QUEUE_MAXSIZE:
            verbose_proxy_logger.warning(
                "Misconfigured queue thresholds: MAX_SIZE_IN_MEMORY_QUEUE (%d) >= LITELLM_ASYNCIO_QUEUE_MAXSIZE (%d). "
                "The spend aggregation check will never trigger because the asyncio.Queue blocks at %d items. "
                "Set MAX_SIZE_IN_MEMORY_QUEUE to a value less than LITELLM_ASYNCIO_QUEUE_MAXSIZE (recommended: 80%% of it).",
                MAX_SIZE_IN_MEMORY_QUEUE,
                LITELLM_ASYNCIO_QUEUE_MAXSIZE,
                LITELLM_ASYNCIO_QUEUE_MAXSIZE,
            )
        if MAX_IN_MEMORY_QUEUE_FLUSH_COUNT < MAX_SIZE_IN_MEMORY_QUEUE:
            verbose_proxy_logger.warning(
                "Misconfigured queue flush limit: MAX_IN_MEMORY_QUEUE_FLUSH_COUNT (%d) < MAX_SIZE_IN_MEMORY_QUEUE (%d). "
                "Spend queue aggregation may need multiple passes under load. "
                "Set MAX_IN_MEMORY_QUEUE_FLUSH_COUNT to at least MAX_SIZE_IN_MEMORY_QUEUE.",
                MAX_IN_MEMORY_QUEUE_FLUSH_COUNT,
                MAX_SIZE_IN_MEMORY_QUEUE,
            )

    async def add_update(self, update):
        """Enqueue an update."""
        verbose_proxy_logger.debug("Adding update to queue: %s", update)
        await self.update_queue.put(update)
        await self._emit_new_item_added_to_queue_event(
            queue_size=self.update_queue.qsize()
        )

    async def flush_all_updates_from_in_memory_queue(self):
        """Get all updates from the queue."""
        updates = []
        while True:
            # Circuit breaker to ensure we're not stuck dequeuing updates. Protect CPU utilization
            if len(updates) >= MAX_IN_MEMORY_QUEUE_FLUSH_COUNT:
                verbose_proxy_logger.debug(
                    "Max in memory queue flush count reached, stopping flush"
                )
                break
            try:
                updates.append(self.update_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return updates

    def _schedule_queue_aggregation_if_needed(self) -> None:
        """Schedule queue aggregation without doing CPU-heavy work on the producer path."""
        if self.update_queue.qsize() < self.MAX_SIZE_IN_MEMORY_QUEUE:
            return

        now = time.monotonic()
        if now - self._last_queue_full_warning_time >= 30:
            verbose_proxy_logger.warning(
                "Spend update queue is full. Scheduling background aggregation to concatenate entries."
            )
            self._last_queue_full_warning_time = now

        if self._aggregation_task is not None and not self._aggregation_task.done():
            return

        self._aggregation_task = asyncio.create_task(
            self._aggregate_queue_updates_if_needed()
        )
        self._aggregation_task.add_done_callback(self._log_aggregation_task_exception)

    def _log_aggregation_task_exception(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            verbose_proxy_logger.error(
                "Spend update queue aggregation failed: %s", str(e)
            )

    async def _aggregate_queue_updates_if_needed(self) -> None:
        async with self._aggregation_lock:
            if self.update_queue.qsize() < self.MAX_SIZE_IN_MEMORY_QUEUE:
                return
            await self.aggregate_queue_updates()

    async def _wait_for_pending_aggregation(self) -> None:
        """
        Wait for an in-flight aggregation task to finish.

        Callers must drain the queue before invoking this. The aggregation task's
        terminal `put` of its compacted result can block when producers refill the
        queue, so waiting without first making space risks deadlock. A timeout
        backstop ensures flush still makes progress if the aggregator is wedged.

        Any non-cancellation exception raised by the aggregation task itself is
        swallowed here (with an error log) so the flush caller can keep the items
        it has already drained. Without this, the drained items would be silently
        dropped on the floor when the exception propagates out.
        """
        task = self._aggregation_task
        if task is None or task.done() or task is asyncio.current_task():
            return
        try:
            await asyncio.wait_for(
                asyncio.shield(task), timeout=PENDING_AGGREGATION_WAIT_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            verbose_proxy_logger.warning(
                "Timed out waiting for spend queue aggregation to finish; "
                "proceeding with flush. The aggregated result will be picked up "
                "on the next flush.",
            )
        except asyncio.CancelledError:
            # Cancellation must propagate so callers (and asyncio) handle
            # shutdown correctly. Swallowing here would break task lifecycle.
            raise
        except Exception as e:
            # Any other exception from the aggregation task is already logged
            # by _log_aggregation_task_exception's done callback. Re-log here
            # for context and continue so the flush caller does not lose its
            # already-drained items.
            verbose_proxy_logger.error(
                "Spend queue aggregation task raised: %s. Continuing flush "
                "with items already drained from the queue.",
                e,
            )

    async def aggregate_queue_updates(self):
        """Subclasses aggregate queue entries into fewer queue entries."""
        raise NotImplementedError()

    async def _emit_new_item_added_to_queue_event(
        self,
        queue_size: Optional[int] = None,
    ):
        """placeholder, emit event when a new item is added to the queue"""
        pass

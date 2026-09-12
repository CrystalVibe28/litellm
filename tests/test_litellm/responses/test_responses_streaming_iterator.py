"""
Regression tests for LIT-4210: the streaming iterators must never run the sync
success_handler on the thread-pool executor concurrently with
async_success_handler. Concurrent mutation of the shared response object /
model_call_details from two threads segfaults pydantic-core (customer pods
crashed with exit 139 whenever any CustomLogger was registered).
"""

import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from typing import Final

import httpx
import pytest

import litellm
from litellm.integrations.custom_logger import CustomLogger
from litellm.litellm_core_utils import thread_pool_executor as thread_pool_executor_module
from litellm.responses import streaming_iterator as responses_streaming_iterator_module
from litellm.litellm_core_utils.litellm_logging import Logging as LitellmLogging
from litellm.responses.streaming_iterator import ResponsesAPIStreamingIterator
from litellm.responses.streaming_iterator import SyncResponsesAPIStreamingIterator
from litellm.llms.openai.responses.transformation import OpenAIResponsesAPIConfig
from litellm.types.llms.openai import ResponsesAPIResponse


_COMPLETED_EVENT: Final = (
    b'data: {"type":"response.completed","response":{"id":"resp_test","object":"response",'
    b'"created_at":1,"status":"completed","model":"gpt-5.5","output":[]}}\n\n'
)


class ClosingAsyncStream(httpx.AsyncByteStream):
    def __init__(self, outcome: str) -> None:
        self.outcome = outcome
        self.closed = False
        self.started = asyncio.Event()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        self.started.set()
        if self.outcome == "cancel":
            await asyncio.Event().wait()
        if self.outcome == "error":
            raise httpx.ReadError("synthetic stream failure")
        if self.outcome == "complete":
            yield _COMPLETED_EVENT
            raise AssertionError("The terminal event must release the connection without another read")

    async def aclose(self) -> None:
        self.closed = True


class ClosingSyncStream(httpx.SyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        yield _COMPLETED_EVENT
        raise AssertionError("The terminal event must release the connection without another read")

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ("complete", "empty", "error", "cancel", "close"))
async def test_response_stream_releases_connection(outcome: str) -> None:
    stream: Final = ClosingAsyncStream(outcome)
    response: Final = httpx.Response(200, stream=stream)
    iterator: Final = ResponsesAPIStreamingIterator(
        response=response,
        model="gpt-5.5",
        responses_api_provider_config=OpenAIResponsesAPIConfig(),
        logging_obj=_make_logging_obj(),
    )
    if outcome == "close":
        await iterator.aclose()
    elif outcome == "cancel":
        pending: Final = asyncio.create_task(anext(iterator))
        await stream.started.wait()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    elif outcome == "error":
        with pytest.raises(httpx.ReadError):
            await anext(iterator)
    elif outcome == "empty":
        with pytest.raises(StopAsyncIteration):
            await anext(iterator)
    else:
        assert (await anext(iterator)).type == "response.completed"
    assert stream.closed
    assert response.is_closed
    with pytest.raises(StopAsyncIteration):
        await anext(iterator)


def test_sync_response_stream_closes_at_terminal_event() -> None:
    stream: Final = ClosingSyncStream()
    response: Final = httpx.Response(200, stream=stream)
    iterator: Final = SyncResponsesAPIStreamingIterator(
        response=response,
        model="gpt-5.5",
        responses_api_provider_config=OpenAIResponsesAPIConfig(),
        logging_obj=_make_logging_obj(),
    )
    assert next(iterator).type == "response.completed"
    assert stream.closed
    assert response.is_closed
    with pytest.raises(StopIteration):
        next(iterator)


class RecordingCustomLogger(CustomLogger):
    def __init__(self):
        super().__init__()
        self.async_hook_started: float | None = None
        self.async_hook_finished: float | None = None

    async def _record(self):
        self.async_hook_started = time.monotonic()
        await asyncio.sleep(0.2)
        self.async_hook_finished = time.monotonic()

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        await self._record()

    async def async_log_stream_event(self, kwargs, response_obj, start_time, end_time):
        await self._record()


class RecordingExecutor:
    def __init__(self, inner):
        self._inner = inner
        self.submits: list = []

    def submit(self, fn, *args, **kwargs):
        self.submits.append((time.monotonic(), fn))
        return self._inner.submit(fn, *args, **kwargs)

    def submit_times_for(self, logging_obj) -> list:
        return [t for t, fn in self.submits if getattr(fn, "__self__", None) is logging_obj]


@pytest.fixture(autouse=True)
def _isolate_callbacks():
    saved = (
        litellm.callbacks,
        litellm.success_callback,
        litellm._async_success_callback,
        litellm.failure_callback,
        litellm._async_failure_callback,
    )
    yield
    (
        litellm.callbacks,
        litellm.success_callback,
        litellm._async_success_callback,
        litellm.failure_callback,
        litellm._async_failure_callback,
    ) = saved


@pytest.fixture
def recording_executor(monkeypatch):
    recording = RecordingExecutor(thread_pool_executor_module.executor)
    monkeypatch.setattr(thread_pool_executor_module, "executor", recording)
    monkeypatch.setattr(responses_streaming_iterator_module, "executor", recording)
    return recording


def _make_logging_obj() -> LitellmLogging:
    logging_obj = LitellmLogging(
        model="gpt-5.4-nano",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
        call_type="aresponses",
        start_time=time.time(),
        litellm_call_id="lit-4210-test",
        function_id="lit-4210-test",
    )
    logging_obj.model_call_details["litellm_params"] = {"aresponses": True}
    return logging_obj


def _make_iterator(logging_obj: LitellmLogging) -> ResponsesAPIStreamingIterator:
    iterator = ResponsesAPIStreamingIterator(
        response=httpx.Response(200),
        model="gpt-5.4-nano",
        responses_api_provider_config=None,
        logging_obj=logging_obj,
    )
    iterator.completed_response = ResponsesAPIResponse(
        id="resp_lit4210",
        created_at=1700000000.0,
        model="gpt-5.4-nano",
        object="response",
        output=[],
        parallel_tool_calls=True,
        tool_choice="auto",
        tools=[],
        error=None,
        incomplete_details=None,
        instructions=None,
        metadata={},
        temperature=1.0,
        top_p=1.0,
    )
    return iterator


@pytest.mark.asyncio
async def test_custom_logger_only_never_submits_sync_success_handler(recording_executor):
    recorder = RecordingCustomLogger()
    litellm.success_callback = [recorder]
    litellm._async_success_callback = [recorder]

    logging_obj = _make_logging_obj()
    iterator = _make_iterator(logging_obj)

    iterator._log_completed_response(is_async=True)
    await asyncio.sleep(0.6)

    assert recorder.async_hook_started is not None
    assert recording_executor.submit_times_for(logging_obj) == []


@pytest.mark.asyncio
async def test_sync_callbacks_run_only_after_async_handler_completes(recording_executor):
    recorder = RecordingCustomLogger()
    sync_events: list = []

    def sync_callback(kwargs, response_obj, start_time, end_time):
        sync_events.append(time.monotonic())

    litellm.success_callback = [recorder, sync_callback]
    litellm._async_success_callback = [recorder]

    logging_obj = _make_logging_obj()
    iterator = _make_iterator(logging_obj)

    iterator._log_completed_response(is_async=True)
    await asyncio.sleep(0.8)

    assert recorder.async_hook_finished is not None
    submit_times = recording_executor.submit_times_for(logging_obj)
    assert len(submit_times) == 1
    assert submit_times[0] >= recorder.async_hook_finished

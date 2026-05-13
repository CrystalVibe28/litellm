# What this tests
## This tests the proxy server startup
import sys, os, json
import traceback
from dotenv import load_dotenv

load_dotenv()
import os, io

# this file is to test litellm/proxy

sys.path.insert(
    0, os.path.abspath("../..")
)  # Adds the parent directory to the system path
import pytest, logging, asyncio
import litellm
from litellm.proxy.proxy_server import (
    router,
    save_worker_config,
    initialize,
    proxy_startup_event,
    llm_model_list,
    proxy_shutdown_event,
)


@pytest.mark.asyncio
async def test_proxy_gunicorn_startup_direct_config():
    """
    gunicorn startup requires the config to be passed in via environment variables

    We support saving either the config or the dict as an environment variable.

    Test both approaches
    """
    try:
        from litellm._logging import verbose_proxy_logger, verbose_router_logger
        import logging

        # unset set DATABASE_URL in env for this test
        # set prisma client to None
        setattr(litellm.proxy.proxy_server, "prisma_client", None)
        database_url = os.environ.pop("DATABASE_URL", None)

        verbose_proxy_logger.setLevel(level=logging.DEBUG)
        verbose_router_logger.setLevel(level=logging.DEBUG)
        filepath = os.path.dirname(os.path.abspath(__file__))
        # test with worker_config = config yaml
        config_fp = f"{filepath}/test_configs/test_config_no_auth.yaml"
        os.environ["WORKER_CONFIG"] = config_fp
        async with proxy_startup_event(app=None) as _:
            pass
    except Exception as e:
        if "Already connected to the query engine" in str(e):
            pass
        else:
            pytest.fail(f"An exception occurred - {str(e)}")
    finally:
        # restore DATABASE_URL after the test
        if database_url is not None:
            os.environ["DATABASE_URL"] = database_url


@pytest.mark.asyncio
async def test_proxy_gunicorn_startup_config_dict():
    try:
        from litellm._logging import verbose_proxy_logger, verbose_router_logger
        import logging

        verbose_proxy_logger.setLevel(level=logging.DEBUG)
        verbose_router_logger.setLevel(level=logging.DEBUG)
        # unset set DATABASE_URL in env for this test
        # set prisma client to None
        setattr(litellm.proxy.proxy_server, "prisma_client", None)
        database_url = os.environ.pop("DATABASE_URL", None)

        filepath = os.path.dirname(os.path.abspath(__file__))
        # test with worker_config = config yaml
        config_fp = f"{filepath}/test_configs/test_config_no_auth.yaml"
        # test with worker_config = dict
        worker_config = {"config": config_fp}
        os.environ["WORKER_CONFIG"] = json.dumps(worker_config)
        async with proxy_startup_event(app=None) as _:
            pass
    except Exception as e:
        if "Already connected to the query engine" in str(e):
            pass
        else:
            pytest.fail(f"An exception occurred - {str(e)}")
    finally:
        # restore DATABASE_URL after the test
        if database_url is not None:
            os.environ["DATABASE_URL"] = database_url


# test_proxy_gunicorn_startup()


@pytest.mark.asyncio
async def test_proxy_shutdown_stops_scheduler_before_prisma_disconnect(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import litellm.proxy.proxy_server as proxy_server

    events = []

    class MockScheduler:
        state = 1  # STATE_RUNNING

        def pause(self):
            pass

        def shutdown(self, wait=True):
            # wait=False is expected: we drain in-flight jobs ourselves before
            # this call, so APScheduler does not need to (and cannot, for the
            # AsyncIOExecutor) wait for pending coroutines.
            events.append("scheduler_shutdown")

    class MockPrismaClient:
        async def disconnect(self):
            events.append("prisma_disconnect")

    mock_jwt_handler = MagicMock()
    mock_jwt_handler.close = AsyncMock()

    monkeypatch.setattr(proxy_server, "scheduler", MockScheduler())
    monkeypatch.setattr(proxy_server, "spend_logs_queue_monitor_task", None)
    monkeypatch.setattr(proxy_server, "prisma_client", MockPrismaClient())
    monkeypatch.setattr(proxy_server, "jwt_handler", mock_jwt_handler)
    monkeypatch.setattr(proxy_server, "db_writer_client", None)
    monkeypatch.setattr(litellm, "cache", None)

    await proxy_server.proxy_shutdown_event()

    assert events == ["scheduler_shutdown", "prisma_disconnect"]
    assert proxy_server.scheduler is None
    mock_jwt_handler.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_proxy_shutdown_runs_scheduler_shutdown_off_event_loop(monkeypatch):
    """
    APScheduler.shutdown(wait=True) is synchronous. It must be offloaded to a
    thread executor so the asyncio event loop stays responsive during teardown.
    """
    import threading
    from unittest.mock import AsyncMock, MagicMock

    import litellm.proxy.proxy_server as proxy_server

    main_thread_id = threading.get_ident()
    scheduler_thread_ids: list[int] = []

    class MockScheduler:
        def shutdown(self, wait=True):
            scheduler_thread_ids.append(threading.get_ident())

    mock_jwt_handler = MagicMock()
    mock_jwt_handler.close = AsyncMock()

    monkeypatch.setattr(proxy_server, "scheduler", MockScheduler())
    monkeypatch.setattr(proxy_server, "spend_logs_queue_monitor_task", None)
    monkeypatch.setattr(proxy_server, "prisma_client", None)
    monkeypatch.setattr(proxy_server, "jwt_handler", mock_jwt_handler)
    monkeypatch.setattr(proxy_server, "db_writer_client", None)
    monkeypatch.setattr(litellm, "cache", None)

    await proxy_server.proxy_shutdown_event()

    assert len(scheduler_thread_ids) == 1
    assert scheduler_thread_ids[0] != main_thread_id


@pytest.mark.asyncio
async def test_proxy_shutdown_drains_inflight_scheduler_jobs(monkeypatch):
    """
    APScheduler's AsyncIOExecutor.shutdown cancels every pending future, which
    would surface CancelledError out of in-flight DB-using jobs (e.g.
    update_daily_tag_spend reading from Prisma). Our shutdown must:
      1. pause() the scheduler so no new jobs start;
      2. await pending coroutine job tasks (with timeout); and
      3. only then shut down (with wait=False since the drain already happened).
    """
    from unittest.mock import AsyncMock, MagicMock

    import litellm.proxy.proxy_server as proxy_server

    events: list[str] = []
    job_started = asyncio.Event()
    job_can_finish = asyncio.Event()

    async def fake_job():
        job_started.set()
        await job_can_finish.wait()
        events.append("job_completed")

    job_task = asyncio.create_task(fake_job())
    await job_started.wait()

    class MockExecutor:
        def __init__(self, tasks):
            self._pending_futures = tasks

    class MockScheduler:
        state = 1  # STATE_RUNNING

        def __init__(self, executor_tasks):
            self._executors = {"default": MockExecutor(executor_tasks)}

        def pause(self):
            events.append("pause")

        def shutdown(self, wait=True):
            events.append(f"shutdown(wait={wait})")

    async def release_job_soon():
        await asyncio.sleep(0)
        job_can_finish.set()

    asyncio.create_task(release_job_soon())

    mock_jwt_handler = MagicMock()
    mock_jwt_handler.close = AsyncMock()

    monkeypatch.setattr(proxy_server, "scheduler", MockScheduler([job_task]))
    monkeypatch.setattr(proxy_server, "spend_logs_queue_monitor_task", None)
    monkeypatch.setattr(proxy_server, "prisma_client", None)
    monkeypatch.setattr(proxy_server, "jwt_handler", mock_jwt_handler)
    monkeypatch.setattr(proxy_server, "db_writer_client", None)
    monkeypatch.setattr(litellm, "cache", None)

    await proxy_server.proxy_shutdown_event()

    # pause must happen before job completion, and shutdown(wait=False) must
    # happen after - i.e. we drained the in-flight job instead of cancelling.
    assert events.index("pause") < events.index("job_completed")
    assert events.index("job_completed") < events.index("shutdown(wait=False)")
    assert not job_task.cancelled()

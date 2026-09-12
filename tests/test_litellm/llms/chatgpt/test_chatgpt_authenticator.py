import base64
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Final
from unittest.mock import Mock, mock_open, patch

import httpx
import pytest

from litellm.llms.chatgpt.authenticator import Authenticator
from litellm.llms.chatgpt.common_utils import GetAccessTokenError, RefreshAccessTokenError
from litellm.llms.custom_httpx.http_handler import HTTPHandler
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
from litellm.litellm_core_utils.litellm_logging import Logging
import litellm


def _make_jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def _b64(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{_b64(header)}.{_b64(payload)}."


class TestChatGPTAuthenticator:
    def test_refresh_lock_excludes_another_process(self, authenticator: Authenticator, tmp_path: Path) -> None:
        marker: Final = tmp_path / "lock-progress"
        code: Final = (
            "from pathlib import Path\n"
            "import sys\n"
            "from litellm.llms.chatgpt.authenticator import Authenticator\n"
            "auth = Authenticator()\n"
            "marker = Path(sys.argv[1])\n"
            "marker.write_text('started')\n"
            "with auth._refresh_lock():\n"
            "    marker.write_text('acquired')\n"
        )
        with authenticator._refresh_lock():
            process: Final = subprocess.Popen(
                [sys.executable, "-c", code, str(marker)],
                env={**os.environ, "LITELLM_LOCAL_MODEL_COST_MAP": "True"},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline: Final = time.monotonic() + 15
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert marker.exists(), "Child did not start"
                time.sleep(0.1)
                assert marker.read_text() == "started"
                assert process.poll() is None
            except BaseException:
                process.kill()
                process.wait(timeout=5)
                raise
        try:
            assert process.wait(timeout=10) == 0
            assert marker.read_text() == "acquired"
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    @pytest.mark.asyncio
    async def test_async_provider_resolution_does_not_block_loop(self, authenticator: Authenticator) -> None:
        started: Final = threading.Event()
        loop_running: Final = threading.Event()
        token: Final = _make_jwt({"exp": time.time() + 3600})
        authenticator._write_auth_file({"access_token": "old", "refresh_token": "refresh", "expires_at": 0})

        def refresh(request: httpx.Request) -> httpx.Response:
            started.set()
            assert loop_running.wait(2), "OAuth refresh blocked the event loop"
            return httpx.Response(200, json={"access_token": token, "id_token": token})

        async def heartbeat() -> None:
            while not started.is_set():
                await asyncio.sleep(0)
            loop_running.set()

        def upstream(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=(
                    'data: {"type":"response.completed","response":{"id":"resp_test","object":"response",'
                    '"created_at":1,"status":"completed","model":"gpt-5.5","output":[]}}\n\n'
                ),
            )

        handler: Final = AsyncHTTPHandler()
        await handler.close()
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as upstream_client:
            handler.client = upstream_client
            with httpx.Client(transport=httpx.MockTransport(refresh)) as oauth_client:
                with patch(
                    "litellm.llms.chatgpt.authenticator._get_httpx_client",
                    return_value=HTTPHandler(client=oauth_client),
                ):
                    beat: Final = asyncio.create_task(heartbeat())
                    try:
                        result: Final = await litellm.aresponses(model="chatgpt/gpt-5.5", input="hi", client=handler)
                        assert result.object == "response"
                        await beat
                    finally:
                        beat.cancel()

    @pytest.mark.parametrize("provider", ("chatgpt", "openai"))
    @pytest.mark.parametrize("still_unauthorized", (False, True))
    @pytest.mark.parametrize("is_async", (False, True))
    @pytest.mark.asyncio
    async def test_http_refresh_once(
        self,
        authenticator: Authenticator,
        provider: str,
        still_unauthorized: bool,
        is_async: bool,
    ) -> None:
        token: Final = _make_jwt({"exp": time.time() + 3600})
        authenticator._write_auth_file(
            {"access_token": "rejected", "refresh_token": "refresh", "expires_at": time.time() + 3600}
        )
        calls: Final = Mock()
        refresh_calls: Final = Mock()

        def upstream(request: httpx.Request) -> httpx.Response:
            calls()
            assert request.content == b'{"input":"hi"}'
            if request.headers["authorization"] == "Bearer rejected" or still_unauthorized:
                return httpx.Response(401, json={"error": {"message": "unauthorized"}})
            assert request.headers["authorization"] == f"Bearer {token}"
            return httpx.Response(200, json={"ok": True})

        def refresh(request: httpx.Request) -> httpx.Response:
            refresh_calls()
            return httpx.Response(200, json={"access_token": token, "id_token": token})

        logging_obj: Final = Logging(
            model="gpt-5.5",
            messages=[],
            stream=False,
            call_type="responses",
            start_time=time.time(),
            litellm_call_id="test",
            function_id="test",
        )
        logging_obj.custom_llm_provider = provider

        async def send() -> httpx.Response:
            if is_async:
                handler: Final = AsyncHTTPHandler()
                await handler.close()
                async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as async_client:
                    handler.client = async_client
                    return await handler.post(
                        "https://chatgpt.test/responses",
                        content=b'{"input":"hi"}',
                        headers={"Authorization": "Bearer rejected"},
                        logging_obj=logging_obj,
                    )
            with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
                return HTTPHandler(client=client).post(
                    "https://chatgpt.test/responses",
                    content=b'{"input":"hi"}',
                    headers={"Authorization": "Bearer rejected"},
                    logging_obj=logging_obj,
                )

        with httpx.Client(transport=httpx.MockTransport(refresh)) as oauth_client:
            with patch(
                "litellm.llms.chatgpt.authenticator._get_httpx_client", return_value=HTTPHandler(client=oauth_client)
            ):
                if provider == "openai" or still_unauthorized:
                    with pytest.raises(httpx.HTTPStatusError):
                        await send()
                else:
                    assert (await send()).json() == {"ok": True}
        assert calls.call_count == (2 if provider == "chatgpt" else 1)
        assert refresh_calls.call_count == (1 if provider == "chatgpt" else 0)

    @pytest.fixture
    def authenticator(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Authenticator:
        monkeypatch.setenv("CHATGPT_TOKEN_DIR", str(tmp_path))
        return Authenticator()

    def test_get_access_token_from_file(self, authenticator):
        future_time = time.time() + 3600
        auth_data = json.dumps({"access_token": "token-123", "expires_at": future_time})

        with patch("builtins.open", mock_open(read_data=auth_data)):
            token = authenticator.get_access_token()
            assert token == "token-123"

    def test_concurrent_refresh_is_shared(self, authenticator: Authenticator) -> None:
        token: Final = _make_jwt({"exp": time.time() + 3600})
        calls: Final = Mock()
        authenticator._write_auth_file({"access_token": "old", "refresh_token": "refresh-old", "expires_at": 0})

        def refresh(request: httpx.Request) -> httpx.Response:
            calls()
            assert json.loads(request.content)["refresh_token"] == "refresh-old"
            time.sleep(0.03)
            return httpx.Response(200, json={"access_token": token, "id_token": token, "refresh_token": "refresh-new"})

        with httpx.Client(transport=httpx.MockTransport(refresh)) as client:
            handler: Final = HTTPHandler(client=client)
            with ThreadPoolExecutor(max_workers=8) as pool:
                tokens: Final = tuple(
                    pool.map(lambda _: Authenticator(http_client=handler).get_access_token(), range(8))
                )
            assert tokens == (token,) * 8
            calls.assert_called_once()
            assert Authenticator(http_client=handler).refresh_access_token("old") == token
            calls.assert_called_once()
        assert json.loads(Path(authenticator.auth_file).read_text())["refresh_token"] == "refresh-new"

    def test_failed_write_preserves_credentials(self, authenticator: Authenticator) -> None:
        authenticator._write_auth_file({"access_token": "original"})
        with patch("os.replace", side_effect=OSError("test failure")):
            with pytest.raises(GetAccessTokenError, match="persist"):
                authenticator._write_auth_file({"access_token": "replacement"})
        assert json.loads(Path(authenticator.auth_file).read_text()) == {"access_token": "original"}
        assert tuple(Path(authenticator.token_dir).iterdir()) == (Path(authenticator.auth_file),)

    def test_missing_login_fails_without_device_flow(self, authenticator: Authenticator) -> None:
        with pytest.raises(GetAccessTokenError, match="sign-in required"):
            authenticator.get_access_token()

    def test_incomplete_token_response_is_redacted(self, authenticator: Authenticator) -> None:
        def refresh(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"access_token": "sensitive-test-token"})

        with httpx.Client(transport=httpx.MockTransport(refresh)) as client:
            instance: Final = Authenticator(http_client=HTTPHandler(client=client))
            with pytest.raises(RefreshAccessTokenError) as error:
                instance._refresh_tokens("synthetic-refresh")
        assert "sensitive-test-token" not in str(error.value)

    def test_get_account_id_from_id_token(self, authenticator):
        id_token = _make_jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct-123"}})
        auth_data = json.dumps({"id_token": id_token})

        with (
            patch("builtins.open", mock_open(read_data=auth_data)),
            patch.object(authenticator, "_write_auth_file") as mock_write,
        ):
            account_id = authenticator.get_account_id()
            assert account_id == "acct-123"
            mock_write.assert_not_called()

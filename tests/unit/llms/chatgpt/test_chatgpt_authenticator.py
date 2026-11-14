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
from unittest.mock import MagicMock, Mock, mock_open, patch

import httpx
import pytest
import httpx
import respx

import litellm
from litellm.constants import DEFAULT_REQUEST_TIMEOUT_SECONDS, HTTP_HANDLER_CONNECT_TIMEOUT_SECONDS
from litellm.litellm_core_utils.litellm_logging import Logging
from litellm.llms.chatgpt.authenticator import (
    TOKEN_REFRESH_TIMEOUT_SECONDS,
    Authenticator,
    get_cached_authenticator,
    get_chatgpt_auth_file,
)
from litellm.llms.chatgpt.common_utils import GetAccessTokenError, RefreshAccessTokenError
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
from litellm.types.router import GenericLiteLLMParams


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
                    "litellm.llms.chatgpt.authenticator.get_httpx_client",
                    return_value=HTTPHandler(client=oauth_client),
                ):
                    beat: Final = asyncio.create_task(heartbeat())
                    try:
                        result: Final = await litellm.aresponses(model="chatgpt/gpt-5.5", input="hi", client=handler)
                        assert result.object == "response"
                        await beat
                    finally:
                        beat.cancel()

    @pytest.mark.parametrize("is_async", (False, True))
    @pytest.mark.asyncio
    async def test_rejected_client_supplied_token_is_not_retried_with_the_gateway_token(
        self, authenticator: Authenticator, is_async: bool
    ) -> None:
        authenticator._write_auth_file(
            {"access_token": "gateway-token", "refresh_token": "refresh", "expires_at": time.time() + 3600}
        )
        sent_tokens: Final = Mock()

        def upstream(request: httpx.Request) -> httpx.Response:
            sent_tokens(request.headers["authorization"])
            return httpx.Response(401, json={"error": {"message": "unauthorized"}})

        logging_obj: Final = Logging(
            model="gpt-5.5",
            messages=[],
            stream=False,
            call_type="responses",
            start_time=time.time(),
            litellm_call_id="test",
            function_id="test",
        )
        logging_obj.custom_llm_provider = "chatgpt"

        with pytest.raises(httpx.HTTPStatusError):
            if is_async:
                handler: Final = AsyncHTTPHandler()
                await handler.close()
                async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as async_client:
                    handler.client = async_client
                    await handler.post(
                        "https://chatgpt.test/responses",
                        content=b'{"input":"hi"}',
                        headers={"Authorization": "Bearer client-token"},
                        logging_obj=logging_obj,
                    )
            else:
                with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
                    HTTPHandler(client=client).post(
                        "https://chatgpt.test/responses",
                        content=b'{"input":"hi"}',
                        headers={"Authorization": "Bearer client-token"},
                        logging_obj=logging_obj,
                    )

        sent_tokens.assert_called_once_with("Bearer client-token")

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
                "litellm.llms.chatgpt.authenticator.get_httpx_client", return_value=HTTPHandler(client=oauth_client)
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

    def test_incomplete_token_response_is_redacted(self, authenticator: Authenticator) -> None:
        def refresh(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"access_token": "sensitive-test-token"})

        with httpx.Client(transport=httpx.MockTransport(refresh)) as client:
            instance: Final = Authenticator(http_client=HTTPHandler(client=client))
            with pytest.raises(RefreshAccessTokenError) as error:
                instance._refresh_tokens("synthetic-refresh")
        assert "sensitive-test-token" not in str(error.value)

    @pytest.mark.parametrize(
        ("request_timeout", "expected_read"),
        [
            (DEFAULT_REQUEST_TIMEOUT_SECONDS, TOKEN_REFRESH_TIMEOUT_SECONDS),
            (TOKEN_REFRESH_TIMEOUT_SECONDS * 4.0, TOKEN_REFRESH_TIMEOUT_SECONDS),
            (TOKEN_REFRESH_TIMEOUT_SECONDS / 3.0, TOKEN_REFRESH_TIMEOUT_SECONDS / 3.0),
        ],
    )
    def test_refresh_tokens_uses_bounded_timeout(self, authenticator, monkeypatch, request_timeout, expected_read):
        monkeypatch.setattr(litellm, "request_timeout", request_timeout)
        monkeypatch.setattr(litellm, "request_timeout_explicitly_set", False)
        client = MagicMock()
        response = MagicMock()
        response.json.return_value = {
            "access_token": "token-new",
            "id_token": "id-123",
        }
        client.post.return_value = response

        with patch(  # test-quality-ok: requested seam for asserting timeout propagation
            "litellm.llms.chatgpt.authenticator.get_httpx_client", return_value=client
        ):
            refreshed = authenticator._refresh_tokens("refresh-123")

        assert refreshed["access_token"] == "token-new"
        timeout = client.post.call_args.kwargs["timeout"]
        assert timeout.read == expected_read
        assert timeout.connect == HTTP_HANDLER_CONNECT_TIMEOUT_SECONDS

    @pytest.mark.asyncio
    async def test_get_access_token_refuses_device_code_login_in_event_loop(self, authenticator):
        with (
            patch("builtins.open", side_effect=FileNotFoundError),
            patch.object(authenticator, "_login_device_code") as mock_login,
            patch.object(authenticator, "_wait_for_access_token") as mock_wait,
        ):
            with pytest.raises(GetAccessTokenError) as exc:
                authenticator.get_access_token()

        assert exc.value.status_code == 401
        assert "event loop" in str(exc.value)
        assert authenticator.auth_file not in str(exc.value)
        mock_login.assert_not_called()
        mock_wait.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_access_token_refuses_cooldown_wait_in_event_loop(self, authenticator):
        auth_data = json.dumps({"device_code_requested_at": time.time()})

        with (
            patch("builtins.open", mock_open(read_data=auth_data)),
            patch.object(authenticator, "_login_device_code") as mock_login,
            patch.object(authenticator, "_wait_for_access_token") as mock_wait,
        ):
            with pytest.raises(GetAccessTokenError) as exc:
                authenticator.get_access_token()

        assert exc.value.status_code == 401
        assert "event loop" in str(exc.value)
        assert authenticator.auth_file not in str(exc.value)
        mock_login.assert_not_called()
        mock_wait.assert_not_called()

    def test_get_access_token_refuses_device_code_login_in_worker_thread(self, authenticator):
        with (
            patch("builtins.open", side_effect=FileNotFoundError),
            patch.object(authenticator, "_login_device_code") as mock_login,
            patch.object(authenticator, "_wait_for_access_token") as mock_wait,
        ):
            with ThreadPoolExecutor(max_workers=1) as pool:
                with pytest.raises(GetAccessTokenError) as exc:
                    pool.submit(authenticator.get_access_token).result()

        assert exc.value.status_code == 401
        assert "worker thread" in str(exc.value)
        assert authenticator.auth_file not in str(exc.value)
        mock_login.assert_not_called()
        mock_wait.assert_not_called()

    def test_get_access_token_device_code_login_without_event_loop(self, authenticator):
        with patch.object(authenticator, "_login_device_code", return_value={"access_token": "tok"}):
            token = authenticator.get_access_token()

        assert token == "tok"

    def test_get_account_id_from_id_token(self, authenticator):
        id_token = _make_jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct-123"}})
        auth_data = json.dumps({"id_token": id_token})

        with (
            patch("builtins.open", mock_open(read_data=auth_data)),
            patch.object(authenticator, "_write_auth_file") as mock_write,
        ):
            account_id = authenticator.get_account_id()
            assert account_id == "acct-123"
            mock_write.assert_called_once()
            assert mock_write.call_args[0][0]["account_id"] == "acct-123"

    def test_get_account_id_prefers_stored_value_without_rewriting_file(self, authenticator):
        id_token = _make_jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct-from-token"}})
        auth_data = json.dumps({"account_id": "acct-stored", "id_token": id_token})

        with (
            patch("builtins.open", mock_open(read_data=auth_data)),
            patch.object(authenticator, "_write_auth_file") as mock_write,
        ):
            assert authenticator.get_account_id() == "acct-stored"
            mock_write.assert_not_called()

    def test_get_account_id_without_login_returns_none(self, authenticator):
        with (
            patch("builtins.open", mock_open(read_data="{}")),
            patch.object(authenticator, "_write_auth_file") as mock_write,
        ):
            assert authenticator.get_account_id() is None
            mock_write.assert_not_called()


def _write_auth_record(path: Path, token: str, account_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "access_token": token,
                "account_id": account_id,
                "expires_at": 4102444800,
            }
        )
    )


class TestChatGPTMultiAccountAuthenticator:
    @pytest.fixture(autouse=True)
    def fixed_clock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("time.time", lambda: 1700000000)

    def test_explicit_auth_file_overrides_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHATGPT_TOKEN_DIR", str(tmp_path / "env-dir"))
        monkeypatch.setenv("CHATGPT_AUTH_FILE", "env.json")
        custom_file: Final = tmp_path / "account-a" / "auth.json"

        authenticator: Final = Authenticator(auth_file=str(custom_file))

        assert authenticator.auth_file == str(custom_file)
        assert authenticator.token_dir == str(custom_file.parent)
        assert not custom_file.parent.exists()
        authenticator._write_auth_file({"access_token": "token-a"})
        assert json.loads(custom_file.read_text())["access_token"] == "token-a"

    def test_default_auth_file_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHATGPT_TOKEN_DIR", str(tmp_path / "env-dir"))
        monkeypatch.setenv("CHATGPT_AUTH_FILE", "env.json")

        authenticator: Final = Authenticator()

        assert authenticator.auth_file == str(tmp_path / "env-dir" / "env.json")

    def test_bare_filename_auth_file_resolves_against_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        authenticator: Final = Authenticator(auth_file="auth.json")

        assert authenticator.auth_file == str(tmp_path / "auth.json")
        assert authenticator.token_dir == str(tmp_path)

    def test_two_auth_files_are_isolated(self, tmp_path: Path) -> None:
        file_a: Final = tmp_path / "account-a.json"
        file_b: Final = tmp_path / "account-b.json"
        _write_auth_record(file_a, "token-a", "acct-a")
        _write_auth_record(file_b, "token-b", "acct-b")

        authenticator_a: Final = Authenticator(auth_file=str(file_a))
        authenticator_b: Final = Authenticator(auth_file=str(file_b))

        assert authenticator_a.get_access_token() == "token-a"
        assert authenticator_a.get_account_id() == "acct-a"
        assert authenticator_b.get_access_token() == "token-b"
        assert authenticator_b.get_account_id() == "acct-b"

    def test_get_cached_authenticator_reuses_instance_per_path(self, tmp_path: Path) -> None:
        file_a: Final = tmp_path / "account-a.json"
        file_b: Final = tmp_path / "account-b.json"

        authenticator_a: Final = get_cached_authenticator(str(file_a))

        assert get_cached_authenticator(str(file_a)) is authenticator_a
        assert get_cached_authenticator(str(file_b)) is not authenticator_a

    def test_get_chatgpt_auth_file(self) -> None:
        assert get_chatgpt_auth_file(None) is None
        assert get_chatgpt_auth_file({}) is None
        assert get_chatgpt_auth_file({"chatgpt_auth_file": ""}) is None
        assert get_chatgpt_auth_file({"chatgpt_auth_file": "/a/auth.json"}) == "/a/auth.json"
        assert get_chatgpt_auth_file(GenericLiteLLMParams()) is None
        assert get_chatgpt_auth_file(GenericLiteLLMParams(chatgpt_auth_file="/b/auth.json")) == "/b/auth.json"

    def test_relative_and_absolute_auth_file_share_cached_authenticator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        get_cached_authenticator.cache_clear()
        auth_file: Final = tmp_path / "x" / "auth.json"
        auth_file.parent.mkdir(parents=True)
        auth_file.write_text("{}")

        relative_key: Final = get_chatgpt_auth_file({"chatgpt_auth_file": "x/auth.json"})
        absolute_key: Final = get_chatgpt_auth_file({"chatgpt_auth_file": str(auth_file)})
        assert relative_key is not None and absolute_key is not None

        assert get_cached_authenticator(relative_key) is get_cached_authenticator(absolute_key)


def test_refresh_keeps_saved_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.time", lambda: 1700000000)
    auth_file: Final = tmp_path / "selected.json"
    auth_file.write_text(
        json.dumps(
            {
                "access_token": "expired-example-token",
                "refresh_token": "example-refresh-token",
                "expires_at": 1,
                "account_id": "acct-selected-workspace",
            }
        )
    )
    token: Final = _make_jwt({"exp": 4102444800, "https://api.openai.com/auth": {"chatgpt_account_id": "acct-default"}})
    authenticator: Final = Authenticator(auth_file=str(auth_file))
    with respx.mock as transport:
        transport.post("https://auth.openai.com/oauth/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": token, "id_token": token, "refresh_token": "example-rotated-refresh"},
            )
        )
        assert authenticator.get_access_token() == token
    assert authenticator.get_account_id(token) == "acct-selected-workspace"
    assert json.loads(auth_file.read_text())["refresh_token"] == "example-rotated-refresh"

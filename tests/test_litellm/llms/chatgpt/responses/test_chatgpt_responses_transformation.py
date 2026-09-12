"""
Tests for ChatGPT subscription Responses API transformation

Source: litellm/llms/chatgpt/responses/transformation.py
"""

import json
import time
from pathlib import Path
from typing import Final
from unittest.mock import MagicMock, patch

import httpx
import pytest

import litellm
from litellm.llms.chatgpt.responses.transformation import ChatGPTResponsesAPIConfig
from litellm.llms.openai.common_utils import OpenAIError
from litellm.main import responses_api_bridge_check
from litellm.types.router import GenericLiteLLMParams
from litellm.types.utils import LlmProviders
from litellm.utils import ProviderConfigManager
from litellm.llms.chatgpt.common_utils import get_chatgpt_user_agent, merge_chatgpt_headers
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler


class TestChatGPTResponsesAPITransformation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("stream", (False, True))
    async def test_async_responses_wire_contract(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        stream: bool,
    ) -> None:
        monkeypatch.setenv("CHATGPT_TOKEN_DIR", str(tmp_path))
        monkeypatch.setenv("CHATGPT_API_BASE", "https://chatgpt.test/backend-api/codex")
        (tmp_path / "auth.json").write_text(
            json.dumps({"access_token": "test-token", "account_id": "test-account", "expires_at": time.time() + 3600})
        )

        def upstream(request: httpx.Request) -> httpx.Response:
            body: Final = json.loads(request.content)
            assert body["instructions"] == "Caller instructions"
            assert body["input"] == [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
            assert body["prompt_cache_key"] == "cache-key"
            assert body["stream"] is True
            assert body["store"] is False
            assert request.headers["authorization"] == "Bearer test-token"
            assert request.headers["chatgpt-account-id"] == "test-account"
            assert request.headers["thread-id"] == "caller-thread"
            assert request.headers["x-codex-turn-state"] == "opaque-state"
            assert "x-forwarded-for" not in request.headers
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
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            handler.client = client
            result: Final = await litellm.aresponses(
                model="chatgpt/gpt-5.5",
                input="hello",
                stream=stream,
                client=handler,
                instructions="Caller instructions",
                extra_headers={
                    "authorization": "wrong",
                    "ChatGPT-Account-Id": "wrong",
                    "Thread-Id": "caller-thread",
                    "X-Codex-Turn-State": "opaque-state",
                    "X-Forwarded-For": "private",
                },
                extra_body={"store": True, "prompt_cache_key": "cache-key"},
            )
            if stream:
                events: Final = tuple([event async for event in result])
                assert events[-1].type == "response.completed"
            else:
                assert result.object == "response"
                assert result.output == []

    def test_instructions_default_is_explicit_and_caller_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from litellm.llms.chatgpt.common_utils import normalize_chatgpt_responses_request

        monkeypatch.setenv("CHATGPT_DEFAULT_INSTRUCTIONS", "Configured default")
        assert normalize_chatgpt_responses_request({})["instructions"] == "Configured default"
        assert normalize_chatgpt_responses_request({"instructions": ""})["instructions"] == ""
        assert normalize_chatgpt_responses_request({"instructions": "Caller"})["instructions"] == "Caller"
        monkeypatch.setenv("CHATGPT_DEFAULT_INSTRUCTIONS", "")
        assert normalize_chatgpt_responses_request({})["instructions"] == ""

    def test_codex_identity_and_explicit_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CHATGPT_USER_AGENT", raising=False)
        assert get_chatgpt_user_agent("codex_cli_rs").startswith("codex_cli_rs/0.154.0 (")
        monkeypatch.setenv("CHATGPT_USER_AGENT", "custom-codex/2.0")
        assert get_chatgpt_user_agent("codex_cli_rs") == "custom-codex/2.0"

    def test_headers_are_case_insensitive_and_do_not_leak_proxy_metadata(self) -> None:
        headers: Final = merge_chatgpt_headers(
            {"user-agent": "default", "session_id": "original"},
            {"User-Agent": "explicit", "Session-Id": "session", "Via": "proxy", "X-LiteLLM-Key": "internal"},
        )
        assert headers == {"user-agent": "explicit", "session-id": "session"}

    @pytest.mark.parametrize("stream", (False, True))
    def test_responses_wire_headers(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stream: bool) -> None:
        monkeypatch.setenv("CHATGPT_TOKEN_DIR", str(tmp_path))
        monkeypatch.setenv("CHATGPT_API_BASE", "https://chatgpt.test/backend-api/codex")
        (tmp_path / "auth.json").write_text(
            json.dumps({"access_token": "test-token", "account_id": "test-account", "expires_at": time.time() + 3600})
        )

        def upstream(request: httpx.Request) -> httpx.Response:
            body: Final = json.loads(request.content)
            assert body["instructions"] == "Keep my caller instructions"
            assert body["input"] == [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
            assert body["prompt_cache_key"] == "caller-cache"
            assert body["text"] == {"verbosity": "low"}
            assert body["stream"] is True
            assert body["store"] is False
            assert "temperature" not in body
            assert request.headers["authorization"] == "Bearer test-token"
            assert request.headers["chatgpt-account-id"] == "test-account"
            assert request.headers["user-agent"] == "custom-codex/2.0"
            assert request.headers["session-id"] == "caller-session"
            assert "via" not in request.headers
            assert "x-litellm-secret" not in request.headers
            assert len(request.headers.get_list("authorization")) == 1
            assert len(request.headers.get_list("user-agent")) == 1
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=(
                    'data: {"type":"response.completed","response":{"id":"resp_test","object":"response",'
                    '"created_at":1,"status":"completed","model":"gpt-5.5","output":[]}}\n\n'
                ),
            )

        with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
            result: Final = litellm.responses(
                model="chatgpt/gpt-5.5",
                input="hello",
                stream=stream,
                client=HTTPHandler(client=client),
                instructions="Keep my caller instructions",
                extra_body={
                    "stream": False,
                    "store": True,
                    "temperature": 0.2,
                    "prompt_cache_key": "caller-cache",
                    "text": {"verbosity": "low"},
                },
                extra_headers={
                    "User-Agent": "custom-codex/2.0",
                    "Authorization": "wrong",
                    "CHATGPT-ACCOUNT-ID": "wrong-account",
                    "session_id": "caller-session",
                    "Via": "proxy",
                    "X-LiteLLM-Secret": "internal",
                },
            )
            if stream:
                events: Final = tuple(result)
                assert events[-1].type == "response.completed"
            else:
                assert result.object == "response"
                assert result.output == []

    @pytest.mark.parametrize(
        "model_name",
        [
            "chatgpt/gpt-5.5",
            "chatgpt/gpt-5.6-luna",
            "chatgpt/gpt-5.6-sol",
            "chatgpt/gpt-5.6-terra",
            "chatgpt/gpt-5.4",
            "chatgpt/gpt-5.4-pro",
            "chatgpt/gpt-5.3-chat-latest",
            "chatgpt/gpt-5.3-instant",
            "chatgpt/gpt-5.3-codex",
            "chatgpt/gpt-5.3-codex-spark",
        ],
    )
    def test_chatgpt_provider_config_registration(self, model_name):
        config = ProviderConfigManager.get_provider_responses_api_config(
            model=model_name,
            provider=LlmProviders.CHATGPT,
        )

        assert config is not None
        assert isinstance(config, ChatGPTResponsesAPIConfig)
        assert config.custom_llm_provider == LlmProviders.CHATGPT

    @pytest.mark.parametrize(
        "model_name",
        [
            "chatgpt/gpt-5.5",
            "chatgpt/gpt-5.6-luna",
            "chatgpt/gpt-5.6-sol",
            "chatgpt/gpt-5.6-terra",
        ],
    )
    def test_chatgpt_responses_model_metadata(self, model_name: str, local_model_cost_map: None) -> None:
        model_info = litellm.get_model_info(model_name)

        assert model_info["litellm_provider"] == "chatgpt"
        assert model_info["mode"] == "responses"
        assert model_info["supported_endpoints"] == [
            "/v1/chat/completions",
            "/v1/responses",
        ]
        assert model_info["max_input_tokens"] == 1050000
        assert model_info["max_output_tokens"] == 128000

    @pytest.mark.parametrize(
        "model_name",
        [
            "gpt-5.5",
            "gpt-5.6-luna",
            "gpt-5.6-sol",
            "gpt-5.6-terra",
        ],
    )
    def test_chatgpt_models_bridge_chat_completions_to_responses(
        self, model_name: str, local_model_cost_map: None
    ) -> None:
        """A chat completions request for these models must take the Responses bridge.

        `gpt-5.6-*` also exists as an openai chat model, so an unregistered
        chatgpt model resolves to mode "chat" here and never reaches the bridge.
        """
        model_info, resolved_model = responses_api_bridge_check(
            model=model_name,
            custom_llm_provider="chatgpt",
        )

        assert model_info["mode"] == "responses"
        assert resolved_model == model_name

    @patch("litellm.llms.chatgpt.responses.transformation.Authenticator")
    def test_chatgpt_responses_endpoint_url(self, mock_authenticator_class):
        mock_auth_instance = MagicMock()
        mock_auth_instance.get_api_base.return_value = "https://chatgpt.example.com"
        mock_authenticator_class.return_value = mock_auth_instance

        config = ChatGPTResponsesAPIConfig()

        url = config.get_complete_url(api_base=None, litellm_params={})
        assert url == "https://chatgpt.example.com/responses"

        custom_url = config.get_complete_url(api_base="https://custom.chatgpt.com", litellm_params={})
        assert custom_url == "https://custom.chatgpt.com/responses"

        url_with_slash = config.get_complete_url(api_base="https://chatgpt.example.com/", litellm_params={})
        assert url_with_slash == "https://chatgpt.example.com/responses"

    @patch("litellm.llms.chatgpt.responses.transformation.Authenticator")
    def test_validate_environment_headers(self, mock_authenticator_class):
        mock_auth_instance = MagicMock()
        mock_auth_instance.get_access_token.return_value = "access-123"
        mock_auth_instance.get_account_id.return_value = "acct-123"
        mock_authenticator_class.return_value = mock_auth_instance

        config = ChatGPTResponsesAPIConfig()
        litellm_params = GenericLiteLLMParams(litellm_session_id="session-123")
        headers = config.validate_environment(
            headers={"originator": "custom-origin"},
            model="gpt-5.2",
            litellm_params=litellm_params,
        )

        assert headers["Authorization"] == "Bearer access-123"
        assert headers["ChatGPT-Account-Id"] == "acct-123"
        assert headers["originator"] == "custom-origin"
        assert headers["content-type"] == "application/json"
        assert headers["accept"] == "text/event-stream"
        assert headers["session-id"] == "session-123"

    @pytest.mark.parametrize(
        "model_name",
        [
            "chatgpt/gpt-5.2-codex",
            "chatgpt/gpt-5.3-codex",
        ],
    )
    def test_chatgpt_forces_streaming_and_reasoning_include(self, model_name):
        config = ChatGPTResponsesAPIConfig()
        request = config.transform_responses_api_request(
            model=model_name,
            input="hi",
            response_api_optional_request_params={},
            litellm_params=GenericLiteLLMParams(),
            headers={},
        )

        assert request["stream"] is True
        assert "reasoning.encrypted_content" in request["include"]
        assert request["instructions"] == ""

    @pytest.mark.parametrize(
        "model_name",
        [
            "chatgpt/gpt-5.2-codex",
            "chatgpt/gpt-5.3-codex-spark",
        ],
    )
    def test_chatgpt_drops_unsupported_responses_params(self, model_name):
        config = ChatGPTResponsesAPIConfig()
        request = config.transform_responses_api_request(
            model=model_name,
            input="hi",
            response_api_optional_request_params={
                # unsupported by ChatGPT Codex
                "user": "user_123",
                "temperature": 0.2,
                "top_p": 0.9,
                "context_management": [{"type": "compaction", "compact_threshold": 200000}],
                "metadata": {"foo": "bar"},
                "max_output_tokens": 123,
                "stream_options": {"include_usage": True},
                # supported and should be preserved
                "truncation": "auto",
                "previous_response_id": "resp_123",
                "reasoning": {"effort": "medium"},
                "tools": [{"type": "function", "function": {"name": "hello"}}],
                "tool_choice": {"type": "function", "function": {"name": "hello"}},
            },
            litellm_params=GenericLiteLLMParams(),
            headers={},
        )

        assert "user" not in request
        assert "temperature" not in request
        assert "top_p" not in request
        assert "context_management" not in request
        assert "metadata" not in request
        assert "max_output_tokens" not in request
        assert "stream_options" not in request

        assert request["truncation"] == "auto"
        assert request["previous_response_id"] == "resp_123"
        assert request["reasoning"] == {"effort": "medium"}
        assert request["tools"] == [{"type": "function", "function": {"name": "hello"}}]
        assert request["tool_choice"] == {
            "type": "function",
            "function": {"name": "hello"},
        }

    @pytest.mark.parametrize(
        ("model_name", "response_model"),
        [
            ("chatgpt/gpt-5.2-codex", "gpt-5.2-codex"),
            ("chatgpt/gpt-5.3-codex", "gpt-5.3-codex"),
        ],
    )
    def test_chatgpt_non_stream_sse_response_parsing(self, model_name: str, response_model: str):
        config = ChatGPTResponsesAPIConfig()
        response_payload = {
            "id": "resp_test",
            "object": "response",
            "created_at": 1700000000,
            "status": "completed",
            "model": response_model,
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Hello!"}],
                }
            ],
        }
        sse_body = "\n".join(
            [
                f"data: {json.dumps({'type': 'response.completed', 'response': response_payload})}",
                "data: [DONE]",
                "",
            ]
        )
        raw_response = httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_body)
        logging_obj = MagicMock()

        parsed = config.transform_response_api_response(
            model=model_name,
            raw_response=raw_response,
            logging_obj=logging_obj,
        )

        assert parsed.output_text == "Hello!"

    @pytest.mark.parametrize(
        ("model_name", "response_model"),
        [
            ("chatgpt/gpt-5.2-codex", "gpt-5.2-codex"),
            ("chatgpt/gpt-5.3-codex", "gpt-5.3-codex"),
        ],
    )
    def test_chatgpt_non_stream_sse_response_recovers_output_items(self, model_name: str, response_model: str):
        config = ChatGPTResponsesAPIConfig()
        response_payload = {
            "id": "resp_test",
            "object": "response",
            "created_at": 1700000000,
            "status": "completed",
            "model": response_model,
            "output": [],
        }
        streamed_output_item = {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Hello from stream!"}],
        }
        sse_body = "\n".join(
            [
                f"data: {json.dumps({'type': 'response.output_item.done', 'output_index': 0, 'item': streamed_output_item})}",
                f"data: {json.dumps({'type': 'response.completed', 'response': response_payload})}",
                "data: [DONE]",
                "",
            ]
        )
        raw_response = httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_body)
        logging_obj = MagicMock()

        parsed = config.transform_response_api_response(
            model=model_name,
            raw_response=raw_response,
            logging_obj=logging_obj,
        )

        assert parsed.output_text == "Hello from stream!"

    def test_chatgpt_non_stream_sse_recovers_whitespace_padded_chunks(self):
        """Chunks with leading whitespace before `data:` must still parse.

        `_strip_sse_data_from_chunk` only matches the prefix at position 0,
        so without an outer `.strip()` such chunks would fail JSON parsing
        and silently drop the contained event.
        """
        config = ChatGPTResponsesAPIConfig()
        response_payload = {
            "id": "resp_test",
            "object": "response",
            "created_at": 1700000000,
            "status": "completed",
            "model": "gpt-5.4",
            "output": [],
        }
        streamed_output_item = {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Recovered from padded"}],
        }
        sse_body = "\n".join(
            [
                f"   data:  {json.dumps({'type': 'response.output_item.done', 'output_index': 0, 'item': streamed_output_item})}   ",
                f"\tdata: {json.dumps({'type': 'response.completed', 'response': response_payload})}",
                "data: [DONE]",
                "",
            ]
        )
        raw_response = httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_body)
        logging_obj = MagicMock()

        parsed = config.transform_response_api_response(
            model="chatgpt/gpt-5.4",
            raw_response=raw_response,
            logging_obj=logging_obj,
        )

        assert parsed.output_text == "Recovered from padded"

    @pytest.mark.parametrize(
        "error_chunk",
        [
            {
                "type": "response.failed",
                "response": {"error": {"message": "ChatGPT upstream failed"}},
            },
            {
                "type": "error",
                "error": {"message": "ChatGPT upstream failed"},
            },
        ],
    )
    def test_chatgpt_non_stream_sse_response_raises_openai_error(self, error_chunk):
        config = ChatGPTResponsesAPIConfig()
        sse_body = "\n".join(
            [
                f"data: {json.dumps(error_chunk)}",
                "data: [DONE]",
                "",
            ]
        )
        raw_response = httpx.Response(502, headers={"content-type": "text/event-stream"}, text=sse_body)
        logging_obj = MagicMock()

        with pytest.raises(OpenAIError) as exc_info:
            config.transform_response_api_response(
                model="chatgpt/gpt-5.4",
                raw_response=raw_response,
                logging_obj=logging_obj,
            )

        assert "ChatGPT upstream failed" in str(exc_info.value)
        assert exc_info.value.status_code == 502

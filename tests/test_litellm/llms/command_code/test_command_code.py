import json

import httpx
import pytest

import litellm
from litellm.llms.command_code.common_utils import COMMAND_CODE_ZDR_HEADER, with_command_code_zdr_header
from litellm.llms.command_code.messages.transformation import CommandCodeMessagesConfig
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
from litellm.types.utils import LlmProviders
from litellm.utils import ProviderConfigManager

CHAT_MODEL = "deepseek/deepseek-v4.1-flash-fast"
MESSAGES_MODEL = "claude-haiku-5-5"
CHAT_PATH = "/provider/v1/chat/completions"
MESSAGES_PATH = "/provider/v1/messages"

_UPSTREAM_BODIES = {
    CHAT_PATH: {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": CHAT_MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    },
    MESSAGES_PATH: {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": MESSAGES_MODEL,
        "content": [{"type": "text", "text": "pong"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    },
}
_ZDR_REJECTION = {
    "error": {
        "message": "This model has no zero-data-retention upstream. Remove the x-cmd-zdr header or choose a different model.",
        "type": "invalid_request_error",
        "code": "cmd_zdr_no_providers",
    }
}


@pytest.fixture(autouse=True)
def command_code_env(monkeypatch):
    monkeypatch.delenv("COMMAND_CODE_API_BASE", raising=False)
    monkeypatch.delenv("COMMAND_CODE_API_KEY", raising=False)
    ProviderConfigManager._get_provider_anthropic_messages_config_cached.cache_clear()


def _complete(model: str, **kwargs) -> tuple[httpx.Request, str]:
    requests: list[httpx.Request] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_UPSTREAM_BODIES[request.url.path])

    client = HTTPHandler()
    client.client = httpx.Client(transport=httpx.MockTransport(upstream))
    response = litellm.completion(
        model=f"command_code/{model}",
        messages=[{"role": "user", "content": "ping"}],
        api_key="sk-command-code",
        client=client,
        **kwargs,
    )
    assert len(requests) == 1
    return requests[0], response.choices[0].message.content


def _rejecting_zdr(requests: list[httpx.Request]):
    def upstream(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(422, json=_ZDR_REJECTION)

    return upstream


@pytest.mark.parametrize(
    "model, path, auth_header, auth_value",
    [
        (CHAT_MODEL, CHAT_PATH, "authorization", "Bearer sk-command-code"),
        (MESSAGES_MODEL, MESSAGES_PATH, "x-api-key", "sk-command-code"),
    ],
)
def test_completion_translates_to_the_models_native_endpoint(model, path, auth_header, auth_value):
    request, content = _complete(model)

    assert request.url.host == "api.commandcode.ai"
    assert request.url.path == path
    assert request.headers[auth_header] == auth_value
    assert json.loads(request.content)["model"] == model
    assert content == "pong"


@pytest.mark.parametrize("model", [CHAT_MODEL, MESSAGES_MODEL])
def test_zero_data_retention_is_not_requested_by_default(model):
    request, _ = _complete(model)

    assert COMMAND_CODE_ZDR_HEADER not in request.headers


@pytest.mark.parametrize("model", [CHAT_MODEL, MESSAGES_MODEL])
@pytest.mark.parametrize(
    "header_kwargs",
    [
        {"extra_headers": {"x-cmd-zdr": "1"}},
        {"extra_headers": {"X-Cmd-Zdr": 1}},
        {"extra_headers": {"x-cmd-zdr": True}},
        {"extra_headers": {"x-cmd-zdr": "true"}},
        {"headers": {"x-cmd-zdr": "1"}},
        {"headers": {"x-cmd-zdr": "0"}, "extra_headers": {"X-Cmd-Zdr": "1"}},
        {"headers": {"x-cmd-zdr": "1"}, "extra_headers": {"X-Cmd-Zdr": "0"}},
    ],
)
def test_zero_data_retention_is_requested_when_the_deployment_or_the_client_asks_for_it(model, header_kwargs):
    request, _ = _complete(model, **header_kwargs)

    assert request.headers.get_list(COMMAND_CODE_ZDR_HEADER) == ["1"]


@pytest.mark.parametrize("model", [CHAT_MODEL, MESSAGES_MODEL])
@pytest.mark.parametrize("value", ["0", "false", "", 0, False])
def test_disabled_zero_data_retention_values_are_not_sent(model, value):
    request, _ = _complete(model, extra_headers={"x-cmd-zdr": value, "x-other": "kept"})

    assert COMMAND_CODE_ZDR_HEADER not in request.headers
    assert request.headers["x-other"] == "kept"


def test_zdr_header_helper_keeps_unrelated_headers():
    assert with_command_code_zdr_header({"X-Cmd-Zdr": "TRUE", "x-cmd-zdr": "0", "x-other": "kept"}) == {
        "x-other": "kept",
        COMMAND_CODE_ZDR_HEADER: "1",
    }


@pytest.mark.parametrize("stream", [False, True])
def test_zdr_rejection_is_raised_once_with_the_upstream_message_even_with_drop_params(monkeypatch, stream):
    monkeypatch.setattr(litellm, "drop_params", True)
    requests: list[httpx.Request] = []
    client = HTTPHandler()
    client.client = httpx.Client(transport=httpx.MockTransport(_rejecting_zdr(requests)))

    with pytest.raises(litellm.BadRequestError) as raised:
        litellm.completion(
            model=f"command_code/{CHAT_MODEL}",
            messages=[{"role": "user", "content": "ping"}],
            api_key="sk-command-code",
            client=client,
            extra_headers={"x-cmd-zdr": "1"},
            stream=stream,
            num_retries=0,
        )

    assert "This model has no zero-data-retention upstream" in str(raised.value)
    assert not litellm._should_retry(raised.value.status_code)
    assert [request.headers.get_list(COMMAND_CODE_ZDR_HEADER) for request in requests] == [["1"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_async_zdr_rejection_is_raised_instead_of_returning_none(monkeypatch, stream):
    monkeypatch.setattr(litellm, "drop_params", True)
    requests: list[httpx.Request] = []
    client = AsyncHTTPHandler()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(_rejecting_zdr(requests)))

    with pytest.raises(litellm.BadRequestError, match="This model has no zero-data-retention upstream"):
        await litellm.acompletion(
            model=f"command_code/{CHAT_MODEL}",
            messages=[{"role": "user", "content": "ping"}],
            api_key="sk-command-code",
            client=client,
            extra_headers={"x-cmd-zdr": "1"},
            stream=stream,
            num_retries=0,
        )

    assert len(requests) == 1


@pytest.mark.asyncio
async def test_router_does_not_retry_a_zdr_rejection():
    requests: list[httpx.Request] = []
    client = AsyncHTTPHandler()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(_rejecting_zdr(requests)))
    router = litellm.Router(
        model_list=[
            {
                "model_name": "fast",
                "litellm_params": {
                    "model": f"command_code/{CHAT_MODEL}",
                    "api_key": "sk-command-code",
                    "extra_headers": {"x-cmd-zdr": "1"},
                },
            }
        ],
        num_retries=3,
        retry_after=0,
    )

    with pytest.raises(litellm.BadRequestError, match="This model has no zero-data-retention upstream"):
        await router.acompletion(model="fast", messages=[{"role": "user", "content": "ping"}], client=client)

    assert len(requests) == 1


def test_native_messages_surface_is_only_offered_for_claude_models():
    assert isinstance(
        ProviderConfigManager.get_provider_anthropic_messages_config(MESSAGES_MODEL, LlmProviders.COMMAND_CODE),
        CommandCodeMessagesConfig,
    )
    assert ProviderConfigManager.get_provider_anthropic_messages_config(CHAT_MODEL, LlmProviders.COMMAND_CODE) is None


def test_messages_passthrough_sends_the_api_key_and_a_normalized_zdr_header(monkeypatch):
    monkeypatch.setenv("COMMAND_CODE_API_KEY", "sk-env")
    config = CommandCodeMessagesConfig()

    headers, _ = config.validate_anthropic_messages_environment(
        headers={"X-Cmd-Zdr": "true"},
        model=MESSAGES_MODEL,
        messages=[{"role": "user", "content": "ping"}],
        optional_params={},
        litellm_params={},
    )
    url = config.get_complete_url(
        api_base=None, api_key=None, model=MESSAGES_MODEL, optional_params={}, litellm_params={}
    )

    assert headers["x-api-key"] == "sk-env"
    assert [value for name, value in headers.items() if name.lower() == COMMAND_CODE_ZDR_HEADER] == ["1"]
    assert url == "https://api.commandcode.ai/provider/v1/messages"


def test_provider_is_resolved_from_the_prefix_and_from_the_api_base(monkeypatch):
    monkeypatch.setenv("COMMAND_CODE_API_KEY", "sk-env")

    model, provider, api_key, api_base = litellm.get_llm_provider(f"command_code/{CHAT_MODEL}")
    _, provider_from_base, _, _ = litellm.get_llm_provider(
        MESSAGES_MODEL, api_base="https://api.commandcode.ai/provider/v1"
    )

    assert (model, provider, api_key, api_base) == (
        CHAT_MODEL,
        "command_code",
        "sk-env",
        "https://api.commandcode.ai/provider/v1",
    )
    assert provider_from_base == "command_code"

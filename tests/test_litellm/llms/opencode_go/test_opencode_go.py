import json

import httpx
import pytest

import litellm
from litellm.litellm_core_utils.get_provider_specific_headers import ProviderSpecificHeaderUtils
from litellm.llms.custom_httpx.http_handler import HTTPHandler
from litellm.llms.opencode_go.common_utils import (
    OPENCODE_GO_SESSION_HEADER,
    get_opencode_go_api_format,
    with_opencode_go_session_header,
)
from litellm.llms.opencode_go.messages.transformation import OpenCodeGoMessagesConfig
from litellm.llms.opencode_go.responses.transformation import OpenCodeGoResponsesAPIConfig
from litellm.proxy.litellm_pre_call_utils import add_provider_specific_headers_to_request
from litellm.types.router import GenericLiteLLMParams
from litellm.types.utils import LlmProviders
from litellm.utils import ProviderConfigManager

CHAT_MODEL = "wire-chat-model"
MESSAGES_MODEL = "wire-messages-model"
RESPONSES_MODEL = "wire-responses-model"

_UPSTREAM_BODIES = {
    "/zen/go/v1/chat/completions": {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": CHAT_MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    },
    "/zen/go/v1/messages": {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": MESSAGES_MODEL,
        "content": [{"type": "text", "text": "pong"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    },
    "/zen/go/v1/responses": {
        "id": "resp_1",
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "model": RESPONSES_MODEL,
        "output": [
            {
                "type": "message",
                "id": "msg_1",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "pong", "annotations": []}],
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    },
}


@pytest.fixture(autouse=True)
def opencode_go_models(monkeypatch):
    for model, entry in (
        (CHAT_MODEL, {"mode": "chat", "supported_endpoints": ["/v1/chat/completions"]}),
        (MESSAGES_MODEL, {"mode": "chat", "supported_endpoints": ["/v1/messages"]}),
        (RESPONSES_MODEL, {"mode": "responses", "supported_endpoints": ["/v1/responses"]}),
    ):
        monkeypatch.setitem(
            litellm.model_cost,
            f"opencode_go/{model}",
            {**entry, "litellm_provider": "opencode_go", "max_tokens": 64, "max_output_tokens": 64},
        )
    monkeypatch.delenv("OPENCODE_GO_API_BASE", raising=False)
    ProviderConfigManager._get_provider_anthropic_messages_config_cached.cache_clear()


def _complete(model: str, **kwargs) -> tuple[httpx.Request, str]:
    requests: list[httpx.Request] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_UPSTREAM_BODIES[request.url.path])

    client = HTTPHandler()
    client.client = httpx.Client(transport=httpx.MockTransport(upstream))
    response = litellm.completion(
        model=f"opencode_go/{model}",
        messages=[{"role": "user", "content": "ping"}],
        api_key="sk-opencode",
        client=client,
        **kwargs,
    )
    assert len(requests) == 1
    return requests[0], response.choices[0].message.content


@pytest.mark.parametrize(
    "model, path, auth_header, auth_value, body_key",
    [
        (CHAT_MODEL, "/zen/go/v1/chat/completions", "authorization", "Bearer sk-opencode", "messages"),
        (MESSAGES_MODEL, "/zen/go/v1/messages", "x-api-key", "sk-opencode", "max_tokens"),
        (RESPONSES_MODEL, "/zen/go/v1/responses", "authorization", "Bearer sk-opencode", "input"),
    ],
)
def test_completion_translates_to_the_models_native_endpoint(model, path, auth_header, auth_value, body_key):
    request, content = _complete(model)

    assert request.url.host == "opencode.ai"
    assert request.url.path == path
    assert request.headers[auth_header] == auth_value
    body = json.loads(request.content)
    assert body["model"] == model
    assert body_key in body
    assert content == "pong"


@pytest.mark.parametrize("model", [CHAT_MODEL, MESSAGES_MODEL, RESPONSES_MODEL])
def test_completion_generates_a_session_header_when_the_client_sends_none(model):
    first, _ = _complete(model)
    second, _ = _complete(model)

    assert first.headers[OPENCODE_GO_SESSION_HEADER]
    assert second.headers[OPENCODE_GO_SESSION_HEADER]
    assert first.headers[OPENCODE_GO_SESSION_HEADER] != second.headers[OPENCODE_GO_SESSION_HEADER]


@pytest.mark.parametrize("model", [CHAT_MODEL, MESSAGES_MODEL, RESPONSES_MODEL])
@pytest.mark.parametrize(
    "header_kwargs",
    [
        {"headers": {"x-opencode-session": "client-session"}},
        {"headers": {"X-OpenCode-Session": "client-session"}},
        {"extra_headers": {"X-OpenCode-Session": "client-session"}},
    ],
)
def test_completion_keeps_the_client_session_header(model, header_kwargs):
    request, _ = _complete(model, **header_kwargs)

    assert request.headers.get_list(OPENCODE_GO_SESSION_HEADER) == ["client-session"]


@pytest.mark.parametrize("model", [CHAT_MODEL, MESSAGES_MODEL, RESPONSES_MODEL])
def test_completion_reuses_the_litellm_session_id(model):
    request, _ = _complete(model, metadata={"session_id": "litellm-session"})

    assert request.headers.get_list(OPENCODE_GO_SESSION_HEADER) == ["litellm-session"]


@pytest.mark.parametrize(
    "litellm_params, expected",
    [
        ({"litellm_session_id": "session", "litellm_trace_id": "trace"}, "session"),
        ({"metadata": {"session_id": "metadata-session"}, "litellm_trace_id": "trace"}, "metadata-session"),
        ({"litellm_trace_id": "trace"}, "trace"),
    ],
)
def test_session_header_prefers_the_most_stable_known_identifier(litellm_params, expected):
    assert with_opencode_go_session_header(headers={}, litellm_params=litellm_params) == {
        OPENCODE_GO_SESSION_HEADER: expected
    }


def test_blank_client_session_header_is_replaced_not_duplicated():
    headers = with_opencode_go_session_header(
        headers={"X-OpenCode-Session": "", "x-other": "kept"},
        litellm_params={"litellm_session_id": "session"},
    )

    assert headers == {"x-other": "kept", OPENCODE_GO_SESSION_HEADER: "session"}


@pytest.mark.parametrize(
    "model, expected",
    [
        ("claude-haiku-5-5", "messages"),
        ("minimax-m3", "messages"),
        ("opencode_go/qwen3.8-max", "messages"),
        ("grok-4.7", "responses"),
        ("gpt-6-luna", "responses"),
        ("muse-spark-1.3-contributor", "responses"),
        ("glm-5.3", "chat"),
        ("some-future-model", "chat"),
    ],
)
def test_api_format_falls_back_to_the_model_name_without_a_cost_map_entry(monkeypatch, model, expected):
    monkeypatch.delitem(litellm.model_cost, f"opencode_go/{model.removeprefix('opencode_go/')}", raising=False)

    assert get_opencode_go_api_format(model) == expected


def test_cost_map_entry_overrides_the_model_name_fallback(monkeypatch):
    monkeypatch.setitem(
        litellm.model_cost,
        "opencode_go/grok-on-messages",
        {"litellm_provider": "opencode_go", "mode": "chat", "supported_endpoints": ["/v1/messages"]},
    )
    monkeypatch.setitem(
        litellm.model_cost,
        "opencode_go/claude-on-chat",
        {"litellm_provider": "opencode_go", "mode": "chat", "supported_endpoints": ["/v1/chat/completions"]},
    )

    assert get_opencode_go_api_format("grok-on-messages") == "messages"
    assert get_opencode_go_api_format("claude-on-chat") == "chat"


def test_unmapped_responses_model_is_bridged_to_the_responses_endpoint(monkeypatch):
    monkeypatch.delitem(litellm.model_cost, "opencode_go/grok-4.7", raising=False)

    request, content = _complete("grok-4.7")

    assert request.url.path == "/zen/go/v1/responses"
    assert content == "pong"


def test_native_surfaces_are_only_offered_for_models_that_speak_them():
    messages_configs = {
        model: ProviderConfigManager.get_provider_anthropic_messages_config(model, LlmProviders.OPENCODE_GO)
        for model in (CHAT_MODEL, MESSAGES_MODEL, RESPONSES_MODEL)
    }
    responses_configs = {
        model: ProviderConfigManager.get_provider_responses_api_config(LlmProviders.OPENCODE_GO, model)
        for model in (CHAT_MODEL, MESSAGES_MODEL, RESPONSES_MODEL)
    }

    assert isinstance(messages_configs[MESSAGES_MODEL], OpenCodeGoMessagesConfig)
    assert messages_configs[CHAT_MODEL] is None
    assert messages_configs[RESPONSES_MODEL] is None
    assert isinstance(responses_configs[RESPONSES_MODEL], OpenCodeGoResponsesAPIConfig)
    assert responses_configs[CHAT_MODEL] is None
    assert responses_configs[MESSAGES_MODEL] is None


@pytest.mark.parametrize(
    "client_headers, expected_session",
    [({}, "litellm-session"), ({"X-OpenCode-Session": "client-session"}, "client-session")],
)
def test_messages_passthrough_sends_api_key_and_session_headers(monkeypatch, client_headers, expected_session):
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "sk-env")
    config = OpenCodeGoMessagesConfig()

    headers, _ = config.validate_anthropic_messages_environment(
        headers=dict(client_headers),
        model=MESSAGES_MODEL,
        messages=[{"role": "user", "content": "ping"}],
        optional_params={},
        litellm_params={"litellm_session_id": "litellm-session"},
    )
    url = config.get_complete_url(
        api_base=None, api_key=None, model=MESSAGES_MODEL, optional_params={}, litellm_params={}
    )

    assert headers["x-api-key"] == "sk-env"
    assert [value for name, value in headers.items() if name.lower() == OPENCODE_GO_SESSION_HEADER] == [
        expected_session
    ]
    assert url == "https://opencode.ai/zen/go/v1/messages"


def test_responses_config_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("OPENCODE_GO_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENCODE_GO_API_KEY"):
        OpenCodeGoResponsesAPIConfig().validate_environment(
            headers={}, model=RESPONSES_MODEL, litellm_params=GenericLiteLLMParams()
        )


def test_proxy_scopes_the_client_session_header_to_opencode_go():
    data: dict = {}

    add_provider_specific_headers_to_request(
        data=data, headers={"x-opencode-session": "client-session", "x-unrelated": "dropped"}
    )
    scoped = data["provider_specific_header"]

    assert ProviderSpecificHeaderUtils.get_provider_specific_headers(scoped, "opencode_go") == {
        "x-opencode-session": "client-session"
    }
    assert ProviderSpecificHeaderUtils.get_provider_specific_headers(scoped, "openai") == {}


@pytest.mark.parametrize("model", [CHAT_MODEL, MESSAGES_MODEL, RESPONSES_MODEL])
def test_proxy_scoped_session_header_reaches_the_upstream_request(model):
    request, _ = _complete(
        model,
        provider_specific_header={
            "custom_llm_provider": "opencode_go",
            "extra_headers": {"x-opencode-session": "client-session"},
        },
    )

    assert request.headers.get_list(OPENCODE_GO_SESSION_HEADER) == ["client-session"]


def test_provider_is_resolved_from_the_prefix_and_from_the_api_base(monkeypatch):
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "sk-env")

    model, provider, api_key, api_base = litellm.get_llm_provider("opencode_go/glm-5.3")
    _, provider_from_base, _, _ = litellm.get_llm_provider("glm-5.3", api_base="https://opencode.ai/zen/go/v1")

    assert (model, provider, api_key, api_base) == ("glm-5.3", "opencode_go", "sk-env", "https://opencode.ai/zen/go/v1")
    assert provider_from_base == "opencode_go"

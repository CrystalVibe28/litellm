from unittest.mock import MagicMock
from dataclasses import replace

import pytest

from litellm import utils as litellm_utils
from litellm.litellm_core_utils.get_provider_specific_headers import (
    MODEL_GROUP_HEADERS_KEY,
    ModelGroupHeaderForwarding,
    ProviderSpecificHeaderUtils,
    apply_model_group_headers,
)
from litellm.types.utils import ProviderSpecificHeader
from litellm.utils import client


class _NoopCachingHandler:
    def __init__(self, **kwargs):
        pass

    def sync_set_cache(self, **kwargs):
        pass

    async def _async_get_cache(self, **kwargs):
        return None

    async def async_set_cache(self, **kwargs):
        pass


class _NoopExecutor:
    def submit(self, *args, **kwargs):
        pass


def _stub_client_side_effects(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(litellm_utils, "_get_cached_llm_caching_handler", lambda: _NoopCachingHandler)
    monkeypatch.setattr(litellm_utils, "post_call_processing", lambda **kwargs: None)
    monkeypatch.setattr(litellm_utils, "update_response_metadata", lambda **kwargs: None)
    monkeypatch.setattr(litellm_utils, "executor", _NoopExecutor())

    async def _no_async_deployment_hook(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_utils, "async_pre_call_deployment_hook", _no_async_deployment_hook)


@pytest.mark.parametrize("metadata_key", ["metadata", "litellm_metadata"])
def test_model_group_headers_are_local_to_each_deployment(metadata_key):
    original = {
        MODEL_GROUP_HEADERS_KEY: ModelGroupHeaderForwarding(
            models=("target/*",), headers=(("x-session", "chat-1"), ("anthropic-beta", "feature"))
        ),
        "headers": {"x-session": "explicit", "x-configured": "keep"},
        "extra_headers": {"x-deployment": "keep"},
        "model": "openai/target/upstream",
    }
    for model_name, expected_session in (("primary", "explicit"), ("target/model", "chat-1"), ("last", "explicit")):
        result = apply_model_group_headers(
            {
                **original,
                MODEL_GROUP_HEADERS_KEY: replace(original[MODEL_GROUP_HEADERS_KEY], deployment_model_name=model_name),
                metadata_key: {"deployment_model_name": "target/forged"},
            }
        )
        assert result["headers"]["x-session"] == expected_session
        assert result["headers"]["x-configured"] == "keep"
        assert result["extra_headers"] == {"x-deployment": "keep"}
        assert ("anthropic-beta" in result["headers"]) == (model_name == "target/model")
        assert MODEL_GROUP_HEADERS_KEY not in result
        assert original["headers"] == {"x-session": "explicit", "x-configured": "keep"}


def test_model_group_headers_do_not_match_upstream_model_or_unresolved_alias():
    kwargs = {
        MODEL_GROUP_HEADERS_KEY: ModelGroupHeaderForwarding(
            models=("target/*",), headers=(("x-session", "chat"),), deployment_model_name="unmatched"
        ),
        "model": "target/upstream-model",
        "metadata": {"model_group": "target/public-alias", "deployment_model_name": "unmatched"},
    }
    assert "headers" not in apply_model_group_headers(kwargs)


def test_model_group_headers_preserve_global_forwarding():
    kwargs = {
        MODEL_GROUP_HEADERS_KEY: ModelGroupHeaderForwarding(models=("target/*",), headers=(("x-session", "chat"),)),
        "headers": {"x-session": "chat", "x-global": "keep"},
        "metadata": {"deployment_model_name": "unmatched"},
    }
    assert apply_model_group_headers(kwargs)["headers"] == kwargs["headers"]


@pytest.mark.parametrize("metadata_key", ["metadata", "litellm_metadata"])
def test_client_wrapper_forwards_model_group_headers_to_sync_call(metadata_key, monkeypatch: pytest.MonkeyPatch):
    _stub_client_side_effects(monkeypatch)
    captured = []

    @client
    def fake_sync_call(**kwargs):
        captured.append(kwargs)
        return "ok"

    logger = MagicMock()
    fake_sync_call(
        model="target/model",
        headers={"x-session": "old", "x-global": "keep"},
        **{
            metadata_key: {"deployment_model_name": "target/model"},
            MODEL_GROUP_HEADERS_KEY: ModelGroupHeaderForwarding(
                models=("target/*",), headers=(("x-session", "forwarded"), ("x-feature", "enabled"))
            ),
            "litellm_logging_obj": logger,
            "caching": False,
        },
    )

    assert captured[0]["headers"] == {"x-global": "keep", "x-session": "forwarded", "x-feature": "enabled"}
    assert MODEL_GROUP_HEADERS_KEY not in captured[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata_key", ["metadata", "litellm_metadata"])
async def test_client_wrapper_forwards_model_group_headers_to_async_call(metadata_key, monkeypatch: pytest.MonkeyPatch):
    _stub_client_side_effects(monkeypatch)
    captured = []

    @client
    async def fake_async_call(**kwargs):
        captured.append(kwargs)
        return "ok"

    await fake_async_call(
        model="target/model",
        headers={"x-session": "old", "x-global": "keep"},
        **{
            metadata_key: {"deployment_model_name": "target/model"},
            MODEL_GROUP_HEADERS_KEY: ModelGroupHeaderForwarding(
                models=("target/*",), headers=(("x-session", "forwarded"), ("x-feature", "enabled"))
            ),
            "litellm_logging_obj": MagicMock(stream=False, _defer_async_logging=True),
            "caching": False,
        },
    )

    assert captured[0]["headers"] == {"x-global": "keep", "x-session": "forwarded", "x-feature": "enabled"}
    assert MODEL_GROUP_HEADERS_KEY not in captured[0]


def test_client_wrapper_forwards_headers_for_sync_async_request(monkeypatch: pytest.MonkeyPatch):
    _stub_client_side_effects(monkeypatch)
    captured = []

    @client
    def fake_sync_call(**kwargs):
        captured.append(kwargs)
        return "ok"

    fake_sync_call(
        model="target/model",
        aembedding=True,
        headers={"x-session": "old"},
        metadata={"deployment_model_name": "target/model"},
        **{
            MODEL_GROUP_HEADERS_KEY: ModelGroupHeaderForwarding(
                models=("target/*",), headers=(("x-session", "forwarded"),)
            ),
            "litellm_logging_obj": MagicMock(),
            "caching": False,
        },
    )

    assert captured[0]["headers"] == {"x-session": "forwarded"}
    assert MODEL_GROUP_HEADERS_KEY not in captured[0]


def test_client_wrapper_keeps_headers_unchanged_without_forwarding_setting(monkeypatch: pytest.MonkeyPatch):
    _stub_client_side_effects(monkeypatch)
    captured = []

    @client
    def fake_sync_call(**kwargs):
        captured.append(kwargs)
        return "ok"

    headers = {"x-session": "explicit"}
    fake_sync_call(
        model="target/model",
        headers=headers,
        metadata={"deployment_model_name": "target/model"},
        litellm_logging_obj=MagicMock(),
        caching=False,
    )

    assert captured[0]["headers"] == headers
    assert MODEL_GROUP_HEADERS_KEY not in captured[0]


class TestProviderSpecificHeaderUtils:
    def test_get_provider_specific_headers_matching_provider(self):
        """Test that the method returns extra_headers when custom_llm_provider matches."""
        provider_specific_header: ProviderSpecificHeader = {
            "custom_llm_provider": "openai",
            "extra_headers": {
                "Authorization": "Bearer token123",
                "Custom-Header": "value",
            },
        }
        custom_llm_provider = "openai"

        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, custom_llm_provider
        )

        expected = {"Authorization": "Bearer token123", "Custom-Header": "value"}
        assert result == expected

    def test_get_provider_specific_headers_no_match_or_none(self):
        """Test that the method returns empty dict when provider doesn't match or is None."""
        # Test case 1: Provider doesn't match
        provider_specific_header: ProviderSpecificHeader = {
            "custom_llm_provider": "anthropic",
            "extra_headers": {"Authorization": "Bearer token123"},
        }
        custom_llm_provider = "openai"

        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, custom_llm_provider
        )
        assert result == {}

        # Test case 2: provider_specific_header is None
        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            None, "openai"
        )
        assert result == {}

    def test_get_provider_specific_headers_multi_provider_anthropic_to_bedrock(self):
        """Test that anthropic headers work with bedrock provider (multi-provider support)."""
        provider_specific_header: ProviderSpecificHeader = {
            "custom_llm_provider": "anthropic,bedrock,bedrock_converse,vertex_ai",
            "extra_headers": {"anthropic-beta": "context-1m-2025-08-07"},
        }

        # Test bedrock provider
        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, "bedrock"
        )
        assert result == {"anthropic-beta": "context-1m-2025-08-07"}

        # Test anthropic provider
        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, "anthropic"
        )
        assert result == {"anthropic-beta": "context-1m-2025-08-07"}

        # Test bedrock_converse provider
        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, "bedrock_converse"
        )
        assert result == {"anthropic-beta": "context-1m-2025-08-07"}

        # Test vertex_ai provider
        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, "vertex_ai"
        )
        assert result == {"anthropic-beta": "context-1m-2025-08-07"}

    def test_get_provider_specific_headers_multi_provider_no_match(self):
        """Test that non-listed providers return empty dict with multi-provider list."""
        provider_specific_header: ProviderSpecificHeader = {
            "custom_llm_provider": "anthropic,bedrock,vertex_ai",
            "extra_headers": {"anthropic-beta": "test"},
        }

        # Test provider not in list
        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, "openai"
        )
        assert result == {}

    def test_get_provider_specific_headers_with_spaces(self):
        """Test that comma-separated list with spaces is handled correctly."""
        provider_specific_header: ProviderSpecificHeader = {
            "custom_llm_provider": "anthropic, bedrock, vertex_ai",
            "extra_headers": {"anthropic-beta": "test"},
        }

        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, "bedrock"
        )
        assert result == {"anthropic-beta": "test"}

    def test_get_provider_specific_headers_none_custom_llm_provider(self):
        """Test that None custom_llm_provider returns empty dict."""
        provider_specific_header: ProviderSpecificHeader = {
            "custom_llm_provider": "anthropic",
            "extra_headers": {"anthropic-beta": "test"},
        }

        result = ProviderSpecificHeaderUtils.get_provider_specific_headers(
            provider_specific_header, None
        )
        assert result == {}

    def test_get_provider_specific_headers_scopes_each_entry_independently(self):
        """Entries in a list each carry their own provider scope."""
        scoped_headers: list[ProviderSpecificHeader] = [
            {
                "custom_llm_provider": "anthropic,bedrock,vertex_ai",
                "extra_headers": {"anthropic-beta": "context-1m-2025-08-07"},
            },
            {
                "custom_llm_provider": "anthropic",
                "extra_headers": {"authorization": "Bearer sk-ant-oat01-fake-token"},
            },
        ]

        assert ProviderSpecificHeaderUtils.get_provider_specific_headers(
            scoped_headers, "anthropic"
        ) == {
            "anthropic-beta": "context-1m-2025-08-07",
            "authorization": "Bearer sk-ant-oat01-fake-token",
        }
        assert ProviderSpecificHeaderUtils.get_provider_specific_headers(
            scoped_headers, "bedrock"
        ) == {"anthropic-beta": "context-1m-2025-08-07"}
        assert (
            ProviderSpecificHeaderUtils.get_provider_specific_headers(
                scoped_headers, "openai"
            )
            == {}
        )

    def test_get_provider_specific_headers_empty_list(self):
        """An empty list of scoped entries contributes nothing."""
        result = ProviderSpecificHeaderUtils.get_provider_specific_headers([], "anthropic")
        assert result == {}

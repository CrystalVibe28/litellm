from litellm.constants import DEFAULT_ANTHROPIC_CHAT_MAX_TOKENS
from litellm.llms.anthropic.chat.transformation import AnthropicConfig
from litellm.llms.openai.chat.gpt_transformation import OpenAIGPTConfig
from litellm.llms.opencode_go.common_utils import (
    get_opencode_go_api_base,
    get_opencode_go_api_format,
    get_opencode_go_api_key,
    with_opencode_go_session_header,
)
from litellm.types.llms.openai import AllMessageValues
from litellm.utils import get_max_tokens


class OpenCodeGoChatConfig(OpenAIGPTConfig):
    @property
    def custom_llm_provider(self) -> str | None:
        return "opencode_go"

    def _get_openai_compatible_provider_info(
        self, api_base: str | None, api_key: str | None
    ) -> tuple[str | None, str | None]:
        return get_opencode_go_api_base(api_base), get_opencode_go_api_key(api_key)

    def validate_environment(
        self,
        headers: dict,  # mutable-ok: mirrors the base override signature
        model: str,
        messages: list[AllMessageValues],  # mutable-ok: mirrors the base override signature
        optional_params: dict,  # mutable-ok: mirrors the base override signature
        litellm_params: dict,  # mutable-ok: mirrors the base override signature
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> dict:  # mutable-ok: mirrors the base override signature
        return with_opencode_go_session_header(
            headers=super().validate_environment(
                headers=headers,
                model=model,
                messages=messages,
                optional_params=optional_params,
                litellm_params=litellm_params,
                api_key=get_opencode_go_api_key(api_key),
                api_base=api_base,
            ),
            litellm_params=litellm_params,
        )

    def get_complete_url(
        self,
        api_base: str | None,
        api_key: str | None,
        model: str,
        optional_params: dict,  # mutable-ok: mirrors the base override signature
        litellm_params: dict,  # mutable-ok: mirrors the base override signature
        stream: bool | None = None,
    ) -> str:
        return super().get_complete_url(
            api_base=get_opencode_go_api_base(api_base),
            api_key=api_key,
            model=model,
            optional_params=optional_params,
            litellm_params=litellm_params,
            stream=stream,
        )


class OpenCodeGoAnthropicChatConfig(AnthropicConfig):
    @property
    def custom_llm_provider(self) -> str | None:
        return "opencode_go"

    def should_strip_billing_metadata(self) -> bool:
        return True

    @staticmethod
    def get_max_tokens_for_model(model: str | None = None) -> int:
        if model is None:
            return DEFAULT_ANTHROPIC_CHAT_MAX_TOKENS
        try:
            return (
                get_max_tokens(f"opencode_go/{model.removeprefix('opencode_go/')}") or DEFAULT_ANTHROPIC_CHAT_MAX_TOKENS
            )
        except Exception:  # noqa: BLE001  # get_max_tokens raises a bare Exception for unmapped models
            return DEFAULT_ANTHROPIC_CHAT_MAX_TOKENS


def get_opencode_go_chat_config(model: str) -> OpenCodeGoChatConfig | OpenCodeGoAnthropicChatConfig:
    if get_opencode_go_api_format(model) == "messages":
        return OpenCodeGoAnthropicChatConfig()
    return OpenCodeGoChatConfig()

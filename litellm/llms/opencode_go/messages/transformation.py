from typing import Any  # noqa: TID251  # override below must mirror the legacy base signature

from litellm.llms.anthropic.experimental_pass_through.messages.transformation import (
    AnthropicMessagesConfig,
)
from litellm.llms.opencode_go.common_utils import (
    get_opencode_go_api_base,
    get_opencode_go_api_key,
    with_opencode_go_session_header,
)


class OpenCodeGoMessagesConfig(AnthropicMessagesConfig):
    @property
    def custom_llm_provider(self) -> str | None:
        return "opencode_go"

    def should_strip_billing_metadata(self) -> bool:
        return True

    def validate_anthropic_messages_environment(
        self,
        headers: dict,  # mutable-ok: mirrors the legacy base override signature
        model: str,
        messages: list[Any],  # mutable-ok: mirrors the legacy base override signature
        optional_params: dict,  # mutable-ok: mirrors the legacy base override signature
        litellm_params: dict,  # mutable-ok: mirrors the legacy base override signature
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> tuple[dict, str | None]:  # mutable-ok: mirrors the legacy base override signature
        validated_headers, validated_api_base = super().validate_anthropic_messages_environment(
            headers=headers,
            model=model,
            messages=messages,
            optional_params=optional_params,
            litellm_params=litellm_params,
            api_key=get_opencode_go_api_key(api_key),
            api_base=api_base,
        )
        return (
            with_opencode_go_session_header(headers=validated_headers, litellm_params=litellm_params),
            validated_api_base,
        )

    def get_complete_url(
        self,
        api_base: str | None,
        api_key: str | None,
        model: str,
        optional_params: dict,  # mutable-ok: mirrors the legacy base override signature
        litellm_params: dict,  # mutable-ok: mirrors the legacy base override signature
        stream: bool | None = None,
    ) -> str:
        return f"{get_opencode_go_api_base(api_base).removesuffix('/messages')}/messages"

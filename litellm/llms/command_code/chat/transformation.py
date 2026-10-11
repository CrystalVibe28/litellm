from litellm.llms.anthropic.chat.transformation import AnthropicConfig
from litellm.llms.command_code.common_utils import (
    get_command_code_api_base,
    get_command_code_api_format,
    get_command_code_api_key,
    with_command_code_zdr_header,
)
from litellm.llms.openai.chat.gpt_transformation import OpenAIGPTConfig
from litellm.types.llms.openai import AllMessageValues


class CommandCodeChatConfig(OpenAIGPTConfig):
    @property
    def custom_llm_provider(self) -> str | None:
        return "command_code"

    def _get_openai_compatible_provider_info(
        self, api_base: str | None, api_key: str | None
    ) -> tuple[str | None, str | None]:
        return get_command_code_api_base(api_base), get_command_code_api_key(api_key)

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
        return with_command_code_zdr_header(
            super().validate_environment(
                headers=headers,
                model=model,
                messages=messages,
                optional_params=optional_params,
                litellm_params=litellm_params,
                api_key=get_command_code_api_key(api_key),
                api_base=api_base,
            )
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
            api_base=get_command_code_api_base(api_base),
            api_key=api_key,
            model=model,
            optional_params=optional_params,
            litellm_params=litellm_params,
            stream=stream,
        )


class CommandCodeAnthropicChatConfig(AnthropicConfig):
    @property
    def custom_llm_provider(self) -> str | None:
        return "command_code"

    def should_strip_billing_metadata(self) -> bool:
        return True


def get_command_code_chat_config(model: str) -> CommandCodeChatConfig | CommandCodeAnthropicChatConfig:
    if get_command_code_api_format(model) == "messages":
        return CommandCodeAnthropicChatConfig()
    return CommandCodeChatConfig()

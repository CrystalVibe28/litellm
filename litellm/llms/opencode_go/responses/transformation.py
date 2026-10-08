from types import MappingProxyType
from typing import Final

from litellm.llms.openai.responses.transformation import OpenAIResponsesAPIConfig
from litellm.llms.opencode_go.common_utils import (
    get_opencode_go_api_base,
    get_opencode_go_api_key,
    with_opencode_go_session_header,
)
from litellm.types.router import GenericLiteLLMParams
from litellm.types.utils import LlmProviders


class OpenCodeGoResponsesAPIConfig(OpenAIResponsesAPIConfig):
    @property
    def custom_llm_provider(self) -> LlmProviders:
        return LlmProviders.OPENCODE_GO

    def validate_environment(
        self,
        headers: dict,  # mutable-ok: mirrors the base override signature
        model: str,
        litellm_params: GenericLiteLLMParams | None,
    ) -> dict:  # mutable-ok: mirrors the base override signature
        params: Final = litellm_params or GenericLiteLLMParams()
        api_key: Final = get_opencode_go_api_key(params.api_key)
        if not api_key:
            raise ValueError("OpenCode Go API key is required. Set api_key or OPENCODE_GO_API_KEY.")
        return with_opencode_go_session_header(
            headers=MappingProxyType({**headers, "Authorization": f"Bearer {api_key}"}),
            litellm_params=params.model_dump(),
        )

    def get_complete_url(
        self,
        api_base: str | None,
        litellm_params: dict,  # mutable-ok: mirrors the base override signature
    ) -> str:
        return f"{get_opencode_go_api_base(api_base).removesuffix('/responses')}/responses"

    def supports_native_websocket(self) -> bool:
        return False

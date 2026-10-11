from collections.abc import Mapping
from typing import Final, Literal, TypeAlias

from litellm.secret_managers.main import get_secret_str

COMMAND_CODE_API_BASE: Final = "https://api.commandcode.ai/provider/v1"
COMMAND_CODE_ZDR_HEADER: Final = "x-cmd-zdr"

CommandCodeApiFormat: TypeAlias = Literal["chat", "messages"]

# Source: GET https://api.commandcode.ai/provider/v1/models (2026-10-12). Claude models are
# served on /messages only, every other model is served on /chat/completions.
_MESSAGES_MODEL_PREFIX: Final = "claude-"
# Command Code enforces zero data retention only for the exact value "1". "true" is ignored upstream.
_ZDR_ENABLED_VALUES: Final = frozenset({"1", "true"})


def get_command_code_api_key(api_key: str | None = None) -> str | None:
    return api_key or get_secret_str("COMMAND_CODE_API_KEY")


def get_command_code_api_base(api_base: str | None = None) -> str:
    return (api_base or get_secret_str("COMMAND_CODE_API_BASE") or COMMAND_CODE_API_BASE).rstrip("/")


def get_command_code_api_format(model: str) -> CommandCodeApiFormat:
    return "messages" if model.removeprefix("command_code/").startswith(_MESSAGES_MODEL_PREFIX) else "chat"


def with_command_code_zdr_header(
    headers: Mapping[str, object],
) -> dict[str, object]:  # mutable-ok: provider configs return mutable HTTP headers
    zdr_values: Final = tuple(value for name, value in headers.items() if name.lower() == COMMAND_CODE_ZDR_HEADER)
    zdr_enabled: Final = any(str(value).strip().lower() in _ZDR_ENABLED_VALUES for value in zdr_values)
    other_headers: Final = tuple(item for item in headers.items() if item[0].lower() != COMMAND_CODE_ZDR_HEADER)
    return {  # mutable-ok: HTTP handlers update the request headers in place
        name: value for name, value in (*other_headers, *(((COMMAND_CODE_ZDR_HEADER, "1"),) if zdr_enabled else ()))
    }

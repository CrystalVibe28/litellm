from collections.abc import Mapping
from typing import Final, Literal, TypeAlias
from uuid import uuid4

import litellm
from litellm.secret_managers.main import get_secret_str

OPENCODE_GO_API_BASE: Final = "https://opencode.ai/zen/go/v1"
OPENCODE_GO_SESSION_HEADER: Final = "x-opencode-session"

OpenCodeGoApiFormat: TypeAlias = Literal["chat", "messages", "responses"]

# Source: https://opencode.ai/v2/docs/console/go/ (2026-10-09). Only used for models
# without an `opencode_go/<model>` cost-map entry, which otherwise decides the format.
_MESSAGES_MODEL_PREFIXES: Final = ("claude-", "minimax-", "qwen3.7-plus", "qwen3.8-")
_RESPONSES_MODEL_PREFIXES: Final = ("gpt-", "grok-", "muse-spark-")


def get_opencode_go_api_key(api_key: str | None = None) -> str | None:
    return api_key or get_secret_str("OPENCODE_GO_API_KEY") or get_secret_str("OPENCODE_API_KEY")


def get_opencode_go_api_base(api_base: str | None = None) -> str:
    return (api_base or get_secret_str("OPENCODE_GO_API_BASE") or OPENCODE_GO_API_BASE).rstrip("/")


def _api_format_from_model_name(model_name: str) -> OpenCodeGoApiFormat:
    if model_name.startswith(_RESPONSES_MODEL_PREFIXES):
        return "responses"
    if model_name.startswith(_MESSAGES_MODEL_PREFIXES):
        return "messages"
    return "chat"


def get_opencode_go_api_format(model: str) -> OpenCodeGoApiFormat:
    model_name: Final = model.removeprefix("opencode_go/")
    entry: Final = litellm.model_cost.get(f"opencode_go/{model_name}")
    if entry is None:
        return _api_format_from_model_name(model_name)
    if entry.get("mode") == "responses":
        return "responses"
    if "/v1/messages" in (entry.get("supported_endpoints") or ()):
        return "messages"
    return "chat"


def _known_session_id(litellm_params: Mapping[str, object]) -> str | None:
    metadata: Final = litellm_params.get("metadata")
    candidates: Final = (
        litellm_params.get("litellm_session_id"),
        metadata.get("session_id") if isinstance(metadata, Mapping) else None,
        litellm_params.get("litellm_trace_id"),
    )
    return next((str(candidate) for candidate in candidates if candidate), None)


def with_opencode_go_session_header(
    headers: Mapping[str, str],
    litellm_params: Mapping[str, object],
) -> dict[str, str]:  # mutable-ok: provider configs return mutable HTTP headers
    client_session_id: Final = next(
        (value for name, value in headers.items() if name.lower() == OPENCODE_GO_SESSION_HEADER and value), None
    )
    session_id: Final = client_session_id or _known_session_id(litellm_params) or str(uuid4())
    other_headers: Final = tuple(item for item in headers.items() if item[0].lower() != OPENCODE_GO_SESSION_HEADER)
    return {  # mutable-ok: HTTP handlers update the request headers in place
        name: value for name, value in (*other_headers, (OPENCODE_GO_SESSION_HEADER, session_id))
    }

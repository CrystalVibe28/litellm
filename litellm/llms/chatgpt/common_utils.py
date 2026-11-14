"""
Constants and helpers for ChatGPT subscription OAuth.
"""

import base64
import hashlib
import json
import os
import platform
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, TypeAlias
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import JsonValue, TypeAdapter

from litellm.litellm_core_utils.get_provider_specific_headers import ProviderSpecificHeaderUtils
from litellm.litellm_core_utils.provider_affinity import get_caller_litellm_session_id, get_requested_session_id
from litellm.llms.base_llm.chat.transformation import BaseLLMException

if TYPE_CHECKING:
    from litellm.types.router import GenericLiteLLMParams

_STRING_HEADERS: Final = TypeAdapter(Mapping[str, str])
_PARAMS: Final = TypeAdapter(Mapping[str, object])

# OAuth + API constants (derived from openai/codex)
CHATGPT_AUTH_BASE: Final = "https://auth.openai.com"
CHATGPT_DEVICE_CODE_URL: Final = f"{CHATGPT_AUTH_BASE}/api/accounts/deviceauth/usercode"
CHATGPT_DEVICE_TOKEN_URL: Final = f"{CHATGPT_AUTH_BASE}/api/accounts/deviceauth/token"
CHATGPT_OAUTH_TOKEN_URL: Final = f"{CHATGPT_AUTH_BASE}/oauth/token"
CHATGPT_DEVICE_VERIFY_URL: Final = f"{CHATGPT_AUTH_BASE}/codex/device"
CHATGPT_API_BASE: Final = "https://chatgpt.com/backend-api/codex"
CHATGPT_CLIENT_ID: Final = "app_EMoamEEZ73f0CkXaXp7hrann"
CHATGPT_ACCOUNT_ID_HEADER: Final = "ChatGPT-Account-Id"
OPENAI_AUTH_CLAIM_KEY: Final = "https://api.openai.com/auth"

JsonObject: TypeAlias = Mapping[str, JsonValue]
_JSON_OBJECT_ADAPTER: Final = TypeAdapter(JsonObject)
_EMPTY_CLAIMS: Final[JsonObject] = MappingProxyType({})

DEFAULT_ORIGINATOR: Final = "codex_cli_rs"
CODEX_CLIENT_VERSION: Final = "0.166.0"
DEFAULT_USER_AGENT: Final = f"codex_cli_rs/{CODEX_CLIENT_VERSION} (Unknown 0; unknown) unknown"
_INCLUDE_ADAPTER: Final = TypeAdapter(tuple[str, ...])
CHATGPT_SERVICE_TIERS: Final = MappingProxyType({"default": "default", "priority": "priority", "fast": "priority"})


class ChatGPTAuthError(BaseLLMException):
    def __init__(
        self,
        status_code,
        message,
        request: httpx.Request | None = None,
        response: httpx.Response | None = None,
        headers: httpx.Headers | dict | None = None,
        body: dict | None = None,
    ):
        super().__init__(
            status_code=status_code,
            message=message,
            request=request,
            response=response,
            headers=headers,
            body=body,
        )


class GetDeviceCodeError(ChatGPTAuthError):
    pass


class GetAccessTokenError(ChatGPTAuthError):
    pass


class RefreshAccessTokenError(ChatGPTAuthError):
    pass


def _safe_header_value(value: str) -> str:
    if not value:
        return ""
    return "".join(ch if 32 <= ord(ch) <= 126 else "_" for ch in value)


def _sanitize_user_agent_token(value: str) -> str:
    if not value:
        return ""
    return "".join(ch if (ch.isalnum() or ch in "-_./") else "_" for ch in value)


def _terminal_user_agent() -> str:
    term_program: Final = os.getenv("TERM_PROGRAM")
    if term_program:
        version: Final = os.getenv("TERM_PROGRAM_VERSION")
        token = f"{term_program}/{version}" if version else term_program
        return _sanitize_user_agent_token(token) or "unknown"

    wezterm_version: Final = os.getenv("WEZTERM_VERSION")
    if wezterm_version is not None:
        token = f"WezTerm/{wezterm_version}" if wezterm_version else "WezTerm"
        return _sanitize_user_agent_token(token) or "WezTerm"

    if os.getenv("ITERM_SESSION_ID") or os.getenv("ITERM_PROFILE") or os.getenv("ITERM_PROFILE_NAME"):
        return "iTerm.app"

    if os.getenv("TERM_SESSION_ID"):
        return "Apple_Terminal"

    if os.getenv("KITTY_WINDOW_ID") or "kitty" in (os.getenv("TERM") or ""):
        return "kitty"

    if os.getenv("ALACRITTY_SOCKET") or os.getenv("TERM") == "alacritty":
        return "Alacritty"

    konsole_version: Final = os.getenv("KONSOLE_VERSION")
    if konsole_version is not None:
        token = f"Konsole/{konsole_version}" if konsole_version else "Konsole"
        return _sanitize_user_agent_token(token) or "Konsole"

    if os.getenv("GNOME_TERMINAL_SCREEN"):
        return "gnome-terminal"

    vte_version: Final = os.getenv("VTE_VERSION")
    if vte_version is not None:
        token = f"VTE/{vte_version}" if vte_version else "VTE"
        return _sanitize_user_agent_token(token) or "VTE"

    if os.getenv("WT_SESSION"):
        return "WindowsTerminal"

    term: Final = os.getenv("TERM")
    if term:
        return _sanitize_user_agent_token(term) or "unknown"

    return "unknown"


def get_chatgpt_originator() -> str:
    originator: Final = os.getenv("CHATGPT_ORIGINATOR") or DEFAULT_ORIGINATOR
    return _safe_header_value(originator) or DEFAULT_ORIGINATOR


def get_chatgpt_user_agent(originator: str) -> str:
    override: Final = os.getenv("CHATGPT_USER_AGENT")
    if override:
        return _safe_header_value(override) or DEFAULT_USER_AGENT
    version: Final = CODEX_CLIENT_VERSION
    os_type: Final = platform.system() or "Unknown"
    os_version: Final = platform.release() or "0"
    arch: Final = platform.machine() or "unknown"
    terminal_ua: Final = _terminal_user_agent()
    suffix = os.getenv("CHATGPT_USER_AGENT_SUFFIX", "").strip()
    suffix = f" ({suffix})" if suffix else ""
    candidate: Final = f"{originator}/{version} ({os_type} {os_version}; {arch}) {terminal_ua}{suffix}"
    return _safe_header_value(candidate) or DEFAULT_USER_AGENT


def get_chatgpt_default_headers(
    access_token: str,
    account_id: str | None,
    session_id: str | None = None,
) -> dict[str, str]:
    originator: Final = get_chatgpt_originator()
    user_agent: Final = get_chatgpt_user_agent(originator)
    headers: Final = {
        "Authorization": f"Bearer {access_token}",
        "content-type": "application/json",
        "accept": "text/event-stream",
        "originator": originator,
        "user-agent": user_agent,
    }
    if session_id:
        headers["session-id"] = session_id
    if account_id:
        headers[CHATGPT_ACCOUNT_ID_HEADER] = account_id
    return headers


def decode_jwt_claims(token: str) -> JsonObject:
    try:
        parts: Final = token.split(".")
        if len(parts) < 2:
            return _EMPTY_CLAIMS
        payload_b64: Final = parts[1] + "=" * (-len(parts[1]) % 4)
        payload_bytes: Final = base64.urlsafe_b64decode(payload_b64)
        return _JSON_OBJECT_ADAPTER.validate_python(json.loads(payload_bytes.decode("utf-8")))
    except Exception:
        return _EMPTY_CLAIMS


def extract_chatgpt_account_id(token: str | None) -> str | None:
    if not token:
        return None
    auth_claims: Final = decode_jwt_claims(token).get(OPENAI_AUTH_CLAIM_KEY)
    if not isinstance(auth_claims, dict):
        return None
    account_id: Final = auth_claims.get("chatgpt_account_id")
    return account_id if isinstance(account_id, str) and account_id else None


def _bearer_token(value: str) -> str:
    scheme, separator, token = value.strip().partition(" ")
    if not separator:
        return scheme
    return token.strip() if scheme.lower() == "bearer" else ""


def is_chatgpt_oauth_key(value: str | None) -> bool:
    if value is None:
        return False
    return OPENAI_AUTH_CLAIM_KEY in decode_jwt_claims(_bearer_token(value))


@dataclass(frozen=True, slots=True)
class ChatGPTClientCredential:
    access_token: str
    account_id: str | None


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    return next((value for key, value in headers.items() if key.lower() == name), None)


def get_chatgpt_client_credential(headers: Mapping[str, str]) -> ChatGPTClientCredential | None:
    auth_header: Final = _header_value(headers, "authorization")
    if auth_header is None or not is_chatgpt_oauth_key(auth_header):
        return None
    access_token: Final = _bearer_token(auth_header)
    account_id: Final = _header_value(headers, CHATGPT_ACCOUNT_ID_HEADER.lower()) or extract_chatgpt_account_id(
        access_token
    )
    return ChatGPTClientCredential(access_token=access_token, account_id=account_id)


def select_chatgpt_client_credential_headers(headers: Mapping[str, str]) -> Mapping[str, str]:
    if get_chatgpt_client_credential(headers) is None:
        return MappingProxyType({})
    return MappingProxyType(
        {
            key: value
            for key, value in headers.items()
            if (key.lower() == "authorization" and is_chatgpt_oauth_key(value))
            or key.lower() == CHATGPT_ACCOUNT_ID_HEADER.lower()
        }
    )


def strip_chatgpt_client_credential_headers(headers: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(
        {
            key: value
            for key, value in headers.items()
            if key.lower() not in ("authorization", CHATGPT_ACCOUNT_ID_HEADER.lower())
        }
    )


def get_chatgpt_request_credential(
    params: "Mapping[str, object] | GenericLiteLLMParams | None",
) -> ChatGPTClientCredential | None:
    normalized: Final = _normalize_litellm_params(params)
    scoped: Final = normalized.get("provider_specific_header")
    extra: Final = normalized.get("extra_headers")
    headers: Final = ProviderSpecificHeaderUtils.validated_provider_specific_headers(
        provider_specific_header=scoped, custom_llm_provider="chatgpt"
    )
    return get_chatgpt_client_credential(headers) or get_chatgpt_client_credential(
        _STRING_HEADERS.validate_python(extra) if extra is not None else MappingProxyType({})
    )


def chatgpt_client_api_base(api_base: str | None) -> str:
    base: Final = api_base or CHATGPT_API_BASE
    parsed: Final = urlsplit(base)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "chatgpt.com"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
    ):
        raise ChatGPTAuthError(
            status_code=400, message="Client ChatGPT credentials require the official HTTPS ChatGPT endpoint"
        )
    return base


def merge_chatgpt_headers(*sources: Mapping[str, str]) -> dict[str, str]:
    names: Final = {
        "authorization": "Authorization",
        "chatgpt-account-id": "ChatGPT-Account-Id",
        "session_id": "session-id",
        "thread_id": "thread-id",
    }
    return {
        names.get(key.lower(), key.lower()): value
        for source in sources
        for key, value in source.items()
        if key.lower() not in {"forwarded", "via", "x-api-key"}
        and not key.lower().startswith(("x-forwarded-", "x-litellm-", "x-stainless-"))
    }


def finalize_chatgpt_request(
    self: object,
    headers: Mapping[str, str],
    optional_params: Mapping[str, object],
    request_data: Mapping[str, object],
    api_base: str,
    api_key: str | None = None,
    model: str | None = None,
    stream: bool | None = None,
    fake_stream: bool | None = None,
) -> tuple[dict[str, str], bytes | None]:
    return merge_chatgpt_headers(headers), None


def get_chatgpt_default_instructions() -> str:
    return os.getenv("CHATGPT_DEFAULT_INSTRUCTIONS", "")


def normalize_chatgpt_responses_request(request: Mapping[str, object]) -> dict[str, object]:
    allowed: Final = frozenset(
        (
            "model",
            "input",
            "instructions",
            "tools",
            "tool_choice",
            "reasoning",
            "previous_response_id",
            "truncation",
            "text",
            "max_output_tokens",
            "parallel_tool_calls",
            "prompt_cache_key",
            "client_metadata",
        )
    )
    included: Final = _INCLUDE_ADAPTER.validate_python(request.get("include") or ())
    user_input: Final = request.get("input")
    requested_tier: Final = request.get("service_tier")
    service_tier: Final = CHATGPT_SERVICE_TIERS.get(requested_tier) if isinstance(requested_tier, str) else None
    return {
        **{key: value for key, value in request.items() if key in allowed},
        **({"service_tier": service_tier} if service_tier is not None else {}),
        "input": [{"role": "user", "content": [{"type": "input_text", "text": user_input}]}]
        if isinstance(user_input, str)
        else user_input,
        "instructions": request.get("instructions")
        if isinstance(request.get("instructions"), str)
        else get_chatgpt_default_instructions(),
        "stream": True,
        "store": False,
        "include": list(dict.fromkeys((*included, "reasoning.encrypted_content"))),
    }


def _normalize_litellm_params(litellm_params: object) -> Mapping[str, object]:
    if isinstance(litellm_params, Mapping):
        return _PARAMS.validate_python(litellm_params)
    serializer: Final = getattr(litellm_params, "model_dump", None) or getattr(litellm_params, "dict", None)
    if not callable(serializer):
        return MappingProxyType({})
    try:
        return _PARAMS.validate_python(serializer())
    except Exception:
        return MappingProxyType({})


def _prompt_cache_session_id(prompt_cache_key: object) -> str | None:
    if not isinstance(prompt_cache_key, str) or not prompt_cache_key:
        return None
    return (
        prompt_cache_key
        if _safe_header_value(prompt_cache_key.strip()) == prompt_cache_key
        else hashlib.sha256(prompt_cache_key.encode("utf-8", "surrogatepass")).hexdigest()
    )


def get_chatgpt_session_id(litellm_params: object) -> str | None:
    params: Final = _normalize_litellm_params(litellm_params)
    return (
        get_caller_litellm_session_id(params)
        or get_requested_session_id(params)
        or _prompt_cache_session_id(params.get("prompt_cache_key"))
        or next(
            (
                str(value)
                for key in ("litellm_session_id", "litellm_trace_id", "litellm_call_id")
                if (value := params.get(key))
            ),
            None,
        )
    )


def ensure_chatgpt_session_id(litellm_params: object) -> str:
    return get_chatgpt_session_id(litellm_params) or str(uuid4())

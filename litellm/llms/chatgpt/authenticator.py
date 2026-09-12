import base64
import json
import os
import tempfile
import threading
import time
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Final, TypeAlias

import httpx
from pydantic import JsonValue, TypeAdapter, ValidationError

from litellm._logging import verbose_logger
from litellm.llms.custom_httpx.http_handler import HTTPHandler, _get_httpx_client

from .common_utils import (
    CHATGPT_API_BASE,
    CHATGPT_AUTH_BASE,
    CHATGPT_CLIENT_ID,
    CHATGPT_DEVICE_CODE_URL,
    CHATGPT_DEVICE_TOKEN_URL,
    CHATGPT_DEVICE_VERIFY_URL,
    CHATGPT_OAUTH_TOKEN_URL,
    GetAccessTokenError,
    GetDeviceCodeError,
    RefreshAccessTokenError,
)

TOKEN_EXPIRY_SKEW_SECONDS: Final = 60
DEVICE_CODE_TIMEOUT_SECONDS: Final = 15 * 60
DEVICE_CODE_POLL_SLEEP_SECONDS: Final = 5

OPENAI_AUTH_CLAIM_KEY: Final = "https://api.openai.com/auth"

JsonObject: TypeAlias = Mapping[str, JsonValue]

_JSON_OBJECT_ADAPTER: Final = TypeAdapter(JsonObject)
_AUTH_LOCK: Final = threading.RLock()


def _optional_str(value: JsonValue | None) -> str | None:
    return value if isinstance(value, str) else None


class Authenticator:
    def __init__(self, http_client: HTTPHandler | None = None) -> None:
        self._http_client = http_client
        self.token_dir = os.getenv(
            "CHATGPT_TOKEN_DIR",
            os.path.expanduser("~/.config/litellm/chatgpt"),
        )
        self.auth_file = os.path.join(self.token_dir, os.getenv("CHATGPT_AUTH_FILE", "auth.json"))
        self._ensure_token_dir()

    def get_api_base(self) -> str:
        return os.getenv("CHATGPT_API_BASE") or os.getenv("OPENAI_CHATGPT_API_BASE") or CHATGPT_API_BASE

    def get_access_token(self) -> str:
        auth_data: Final = self._read_auth_file()
        access_token: Final = _optional_str(auth_data.get("access_token")) if auth_data else None
        if auth_data and access_token and not self._is_token_expired(auth_data, access_token):
            return access_token
        if not auth_data or not _optional_str(auth_data.get("refresh_token")):
            raise GetAccessTokenError(
                status_code=401, message="ChatGPT sign-in required; run Authenticator().login() first"
            )
        with self._refresh_lock():
            return self._get_access_token_locked()

    def _get_access_token_locked(self) -> str:
        auth_data: Final = self._read_auth_file()
        if auth_data:
            access_token: Final = _optional_str(auth_data.get("access_token"))
            if access_token and not self._is_token_expired(auth_data, access_token):
                return access_token
            refresh_token: Final = _optional_str(auth_data.get("refresh_token"))
            if refresh_token:
                try:
                    refreshed: Final = self._refresh_tokens(refresh_token)
                    return refreshed["access_token"]
                except RefreshAccessTokenError as exc:
                    raise GetAccessTokenError(
                        status_code=401, message="ChatGPT token refresh failed; sign in again"
                    ) from exc
        raise GetAccessTokenError(
            status_code=401, message="ChatGPT sign-in required; run Authenticator().login() first"
        )

    def login(self) -> str:
        with self._refresh_lock():
            return self._login_device_code()["access_token"]

    def refresh_access_token(self, rejected_token: str) -> str:
        with self._refresh_lock():
            auth_data: Final = self._read_auth_file() or {}
            current: Final = _optional_str(auth_data.get("access_token"))
            if current and current != rejected_token and not self._is_token_expired(auth_data, current):
                return current
            refresh_token: Final = _optional_str(auth_data.get("refresh_token"))
            if not refresh_token:
                raise GetAccessTokenError(
                    status_code=401, message="ChatGPT sign-in required; no refresh token available"
                )
            return self._refresh_tokens(refresh_token)["access_token"]

    @contextmanager
    def _refresh_lock(self) -> Generator[None, None, None]:
        with _AUTH_LOCK, open(f"{self.auth_file}.lock", "a+b") as lock_file:
            deadline: Final = time.monotonic() + 60
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt

                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise GetAccessTokenError(
                            status_code=503, message="Timed out waiting for ChatGPT token refresh"
                        )
                    time.sleep(0.05)
            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt

                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def get_account_id(self) -> str | None:
        auth_data: Final = self._read_auth_file()
        if not auth_data:
            return None
        account_id: Final = _optional_str(auth_data.get("account_id"))
        if account_id:
            return account_id
        id_token: Final = auth_data.get("id_token")
        access_token: Final = auth_data.get("access_token")
        derived: Final = self._extract_account_id(_optional_str(id_token or access_token))
        return derived

    def _ensure_token_dir(self) -> None:
        if not os.path.exists(self.token_dir):
            os.makedirs(self.token_dir, exist_ok=True)

    def _read_auth_file(self) -> JsonObject | None:
        try:
            with open(self.auth_file, "r") as f:
                return _JSON_OBJECT_ADAPTER.validate_python(json.load(f))
        except OSError:
            return None
        except (json.JSONDecodeError, ValidationError):
            verbose_logger.warning("Invalid ChatGPT auth file; sign in again")
            return None

    def _write_auth_file(self, data: JsonObject) -> None:
        try:
            descriptor, temporary_path = tempfile.mkstemp(dir=self.token_dir)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary_path, self.auth_file)
            finally:
                Path(temporary_path).unlink(missing_ok=True)
        except OSError as exc:
            raise GetAccessTokenError(status_code=500, message="Unable to persist ChatGPT authentication") from exc

    def _is_token_expired(self, auth_data: JsonObject, access_token: str) -> bool:
        stored_expires_at: Final = auth_data.get("expires_at")
        if isinstance(stored_expires_at, (int, float)):
            return time.time() >= float(stored_expires_at) - TOKEN_EXPIRY_SKEW_SECONDS
        derived_expires_at: Final = self._get_expires_at(access_token)
        if derived_expires_at is None:
            return True
        return time.time() >= float(derived_expires_at) - TOKEN_EXPIRY_SKEW_SECONDS

    def _get_expires_at(self, token: str) -> int | None:
        claims: Final = self._decode_jwt_claims(token)
        exp: Final = claims.get("exp")
        if isinstance(exp, (int, float)):
            return int(exp)
        return None

    def _decode_jwt_claims(self, token: str) -> JsonObject:
        try:
            parts: Final = token.split(".")
            if len(parts) < 2:
                return {}
            payload_b64: Final = parts[1] + "=" * (-len(parts[1]) % 4)
            payload_bytes: Final = base64.urlsafe_b64decode(payload_b64)
            return _JSON_OBJECT_ADAPTER.validate_python(json.loads(payload_bytes.decode("utf-8")))
        except Exception:
            return {}

    def _extract_account_id(self, token: str | None) -> str | None:
        if not token:
            return None
        claims: Final = self._decode_jwt_claims(token)
        auth_claims: Final = claims.get(OPENAI_AUTH_CLAIM_KEY)
        if isinstance(auth_claims, dict):
            account_id: Final = auth_claims.get("chatgpt_account_id")
            if isinstance(account_id, str) and account_id:
                return account_id
        return None

    def _login_device_code(self) -> dict[str, str]:
        device_code: Final = self._request_device_code()
        print(  # noqa: T201
            "Sign in with ChatGPT using device code:\n"
            f"1) Visit {CHATGPT_DEVICE_VERIFY_URL}\n"
            f"2) Enter code: {device_code['user_code']}\n"
            "Device codes are a common phishing target. Never share this code.",
            flush=True,
        )
        auth_code: Final = self._poll_for_authorization_code(device_code)
        tokens: Final = self._exchange_code_for_tokens(auth_code)
        auth_data: Final = self._build_auth_record(tokens)
        self._write_auth_file(auth_data)
        return tokens

    def _request_device_code(self) -> dict[str, str]:
        try:
            client: Final = self._http_client or _get_httpx_client()
            resp: Final = client.post(
                CHATGPT_DEVICE_CODE_URL,
                json={"client_id": CHATGPT_CLIENT_ID},
            )
            resp.raise_for_status()
            data: Final = _JSON_OBJECT_ADAPTER.validate_python(resp.json())
        except httpx.HTTPStatusError as exc:
            raise GetDeviceCodeError(
                message=f"Failed to request device code: {exc}",
                status_code=exc.response.status_code,
            )
        except Exception:
            raise GetDeviceCodeError(
                message="Failed to request device code",
                status_code=400,
            ) from None

        device_auth_id: Final = _optional_str(data.get("device_auth_id"))
        user_code: Final = _optional_str(data.get("user_code") or data.get("usercode"))
        interval: Final = data.get("interval")
        if not device_auth_id or not user_code:
            raise GetDeviceCodeError(
                message="Device code response missing required fields",
                status_code=400,
            )
        return {
            "device_auth_id": device_auth_id,
            "user_code": user_code,
            "interval": str(interval or "5"),
        }

    def _poll_for_authorization_code(self, device_code: dict[str, str]) -> dict[str, str]:
        client: Final = self._http_client or _get_httpx_client()
        interval: Final = int(device_code.get("interval", "5"))
        start_time: Final = time.time()
        while time.time() - start_time < DEVICE_CODE_TIMEOUT_SECONDS:
            try:
                resp = client.post(
                    CHATGPT_DEVICE_TOKEN_URL,
                    json={
                        "device_auth_id": device_code["device_auth_id"],
                        "user_code": device_code["user_code"],
                    },
                )
                if resp.status_code == 200:
                    data = _JSON_OBJECT_ADAPTER.validate_python(resp.json())
                    authorization_code = _optional_str(data.get("authorization_code"))
                    code_challenge = _optional_str(data.get("code_challenge"))
                    code_verifier = _optional_str(data.get("code_verifier"))
                    if authorization_code and code_challenge and code_verifier:
                        return {
                            "authorization_code": authorization_code,
                            "code_challenge": code_challenge,
                            "code_verifier": code_verifier,
                        }
                if resp.status_code in (403, 404):
                    time.sleep(max(interval, DEVICE_CODE_POLL_SLEEP_SECONDS))
                    continue
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response else None
                if status_code in (403, 404):
                    time.sleep(max(interval, DEVICE_CODE_POLL_SLEEP_SECONDS))
                    continue
                raise GetAccessTokenError(
                    message=f"Polling failed: {exc}",
                    status_code=exc.response.status_code,
                )
            except Exception:
                raise GetAccessTokenError(
                    message="Device authorization polling failed",
                    status_code=400,
                ) from None
            time.sleep(max(interval, DEVICE_CODE_POLL_SLEEP_SECONDS))

        raise GetAccessTokenError(
            message="Timed out waiting for device authorization",
            status_code=408,
        )

    def _exchange_code_for_tokens(self, code_data: dict[str, str]) -> dict[str, str]:
        try:
            client: Final = self._http_client or _get_httpx_client()
            redirect_uri: Final = f"{CHATGPT_AUTH_BASE}/deviceauth/callback"
            body: Final = (
                "grant_type=authorization_code"
                f"&code={code_data['authorization_code']}"
                f"&redirect_uri={redirect_uri}"
                f"&client_id={CHATGPT_CLIENT_ID}"
                f"&code_verifier={code_data['code_verifier']}"
            )
            resp: Final = client.post(
                CHATGPT_OAUTH_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                content=body,
            )
            resp.raise_for_status()
            data: Final = _JSON_OBJECT_ADAPTER.validate_python(resp.json())
        except httpx.HTTPStatusError as exc:
            raise GetAccessTokenError(
                message=f"Token exchange failed: {exc}",
                status_code=exc.response.status_code,
            )
        except Exception:
            raise GetAccessTokenError(
                message="Token exchange failed",
                status_code=400,
            ) from None

        access_token: Final = _optional_str(data.get("access_token"))
        refresh_token: Final = _optional_str(data.get("refresh_token"))
        id_token: Final = _optional_str(data.get("id_token"))
        if not access_token or not refresh_token or not id_token:
            raise GetAccessTokenError(
                message="Token exchange response missing required fields",
                status_code=400,
            )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "id_token": id_token,
        }

    def _refresh_tokens(self, refresh_token: str) -> dict[str, str]:
        try:
            client: Final = self._http_client or _get_httpx_client()
            resp: Final = client.post(
                CHATGPT_OAUTH_TOKEN_URL,
                json={
                    "client_id": CHATGPT_CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "scope": "openid profile email",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data: Final = _JSON_OBJECT_ADAPTER.validate_python(resp.json())
        except httpx.HTTPStatusError as exc:
            raise RefreshAccessTokenError(
                message=f"Refresh token failed: {exc}",
                status_code=exc.response.status_code,
            )
        except Exception:
            raise RefreshAccessTokenError(
                message="Refresh token failed",
                status_code=400,
            ) from None

        access_token: Final = _optional_str(data.get("access_token"))
        id_token: Final = _optional_str(data.get("id_token"))
        if not access_token or not id_token:
            raise RefreshAccessTokenError(
                message="Refresh response missing required fields",
                status_code=400,
            )

        refreshed: Final = {
            "access_token": access_token,
            "refresh_token": _optional_str(data.get("refresh_token")) or refresh_token,
            "id_token": id_token,
        }
        auth_data: Final = self._build_auth_record(refreshed)
        self._write_auth_file(auth_data)
        return refreshed

    def _build_auth_record(self, tokens: dict[str, str]) -> JsonObject:
        access_token: Final = tokens.get("access_token")
        id_token: Final = tokens.get("id_token")
        expires_at: Final = self._get_expires_at(access_token) if access_token else None
        account_id: Final = self._extract_account_id(id_token or access_token)
        return {
            "access_token": access_token,
            "refresh_token": tokens.get("refresh_token"),
            "id_token": id_token,
            "expires_at": expires_at,
            "account_id": account_id,
        }

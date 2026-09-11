from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from pydantic import TypeAdapter

from litellm.types.utils import ProviderSpecificHeader

MODEL_GROUP_HEADERS_KEY: Final = "_model_group_forwarded_headers"
_HEADER_VALUES: Final = TypeAdapter(dict[str, str | bytes])
_METADATA_VALUES: Final = TypeAdapter(dict[str, object])
_EMPTY_VALUES: Final[Mapping[str, object]] = MappingProxyType({})


@dataclass(frozen=True)
class ModelGroupHeaderForwarding:
    models: tuple[str, ...]
    headers: tuple[tuple[str, str | bytes], ...]
    team_id: str | None = None
    deployment_model_name: str | None = None


def apply_model_group_headers(
    kwargs: Mapping[str, object],
) -> dict[str, object]:  # mutable-ok: client wrappers mutate their isolated transport kwargs
    forwarding: Final = kwargs.get(MODEL_GROUP_HEADERS_KEY)
    if not isinstance(forwarding, ModelGroupHeaderForwarding):
        return _METADATA_VALUES.validate_python(kwargs)

    from litellm.proxy.auth.auth_checks import (
        _check_model_access_helper,  # pyright: ignore[reportPrivateUsage]  # Preserve the proxy's existing wildcard and access-group matching.
    )
    from litellm.proxy.proxy_server import llm_router

    call_kwargs: Final = {  # mutable-ok: isolate each provider call from the router's retry kwargs
        key: value for key, value in kwargs.items() if key != MODEL_GROUP_HEADERS_KEY
    }
    model: Final = forwarding.deployment_model_name or kwargs.get("model")
    if not isinstance(model, str):
        return call_kwargs
    matches: Final = _check_model_access_helper(
        model=model,
        llm_router=llm_router,
        models=list(forwarding.models),  # mutable-ok: the existing access matcher requires a list
        team_id=forwarding.team_id,
    )
    if not matches:
        return call_kwargs

    existing: Final = _HEADER_VALUES.validate_python(kwargs.get("headers") or _EMPTY_VALUES)
    forwarded_names: Final = frozenset(key.lower() for key, _ in forwarding.headers)
    retained: Final = MappingProxyType(
        {key: value for key, value in existing.items() if key.lower() not in forwarded_names}
    )
    forwarded: Final = MappingProxyType(dict(forwarding.headers))
    return {  # mutable-ok: the client wrapper owns and mutates this per-attempt dictionary
        **call_kwargs,
        "headers": {  # mutable-ok: provider adapters expect mutable HTTP headers
            **retained,
            **forwarded,
        },
    }


class ProviderSpecificHeaderUtils:
    @staticmethod
    def get_provider_specific_headers(
        provider_specific_header: ProviderSpecificHeader | Sequence[ProviderSpecificHeader] | None,
        custom_llm_provider: str | None,
    ) -> dict:
        """
        Get the provider specific headers for the given custom llm provider.

        Accepts either a single ProviderSpecificHeader or a sequence of them. Each entry
        carries its own comma-separated provider list, so headers that are safe for several
        providers and headers that are safe for exactly one can travel on the same request
        without sharing a scope. Entries whose provider list does not contain
        `custom_llm_provider` contribute nothing.

        Returns:
            Dict: The provider specific headers for the given custom llm provider
        """
        if provider_specific_header is None or custom_llm_provider is None:
            return {}

        scoped_headers: Final = (
            (provider_specific_header,) if isinstance(provider_specific_header, dict) else provider_specific_header
        )

        matched_headers: Final = {}
        for scoped_header in scoped_headers:
            stored_providers = scoped_header.get("custom_llm_provider", "")
            provider_list = [p.strip() for p in stored_providers.split(",")]
            if custom_llm_provider in provider_list:
                matched_headers.update(scoped_header.get("extra_headers", {}))

        return matched_headers

# ChatGPT subscription proxy

The default client identity uses the shared Codex CLI `0.154.0` header format, pinned to [openai/codex](https://github.com/openai/codex/blob/6b9826e3aa83b1a5947db50f4332cb9c65f1b340/codex-rs/login/src/auth/default_client.rs). The version belongs to that compatibility baseline, not the installed LiteLLM package. OS and terminal information come from the running environment

`CHATGPT_USER_AGENT`, `CHATGPT_ORIGINATOR`, and `CHATGPT_USER_AGENT_SUFFIX` retain their existing meanings. Explicit request headers can override client identity, but Responses authentication uses the configured OAuth token and account. Header names are merged case-insensitively; the legacy `session_id` spelling is normalized to `session-id`

ChatGPT requests omit `Forwarded`, `Via`, `X-Forwarded-*`, `X-LiteLLM-*`, `X-Stainless-*`, and unrelated `X-API-Key` headers. These rules apply only to ChatGPT provider requests and do not change LiteLLM routing, local logging, or other providers. They do not reproduce a TLS fingerprint or establish that the caller is an official Codex binary

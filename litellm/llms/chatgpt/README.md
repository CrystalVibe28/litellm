# ChatGPT subscription proxy

The default client identity uses the shared Codex CLI `0.154.0` header format, pinned to [openai/codex](https://github.com/openai/codex/blob/6b9826e3aa83b1a5947db50f4332cb9c65f1b340/codex-rs/login/src/auth/default_client.rs). The version belongs to that compatibility baseline, not the installed LiteLLM package. OS and terminal information come from the running environment

`CHATGPT_USER_AGENT`, `CHATGPT_ORIGINATOR`, and `CHATGPT_USER_AGENT_SUFFIX` retain their existing meanings. Explicit request headers can override client identity, but Responses authentication uses the configured OAuth token and account. Header names are merged case-insensitively; the legacy `session_id` spelling is normalized to `session-id`

ChatGPT requests omit `Forwarded`, `Via`, `X-Forwarded-*`, `X-LiteLLM-*`, `X-Stainless-*`, and unrelated `X-API-Key` headers. These rules apply only to ChatGPT provider requests and do not change LiteLLM routing, local logging, or other providers. They do not reproduce a TLS fingerprint or establish that the caller is an official Codex binary

Responses preserve caller instructions, including an explicit empty string. When omitted, `CHATGPT_DEFAULT_INSTRUCTIONS` supplies an optional default; otherwise an empty string is sent. LiteLLM does not inject coding-agent instructions. Supported text formatting, parallel tool calls, prompt cache keys, and client metadata are forwarded. Caller session, thread, and turn-state headers are preserved without a conversation store or identifier remapping

The upstream always receives `stream=true` and `store=false`, including when `extra_body` is supplied. Unsupported fields are filtered after the final body merge. A downstream non-streaming request still returns a complete Responses object by parsing the upstream SSE; streaming requests return events

Sign in explicitly before starting the proxy with `python -c "from litellm.llms.chatgpt.authenticator import Authenticator; Authenticator().login()"`. The return value is not printed. Requests without valid credentials fail with a sign-in error instead of waiting for interactive device authorization. Existing auth files remain supported

Expired credentials are refreshed under thread and process locks, then persisted with atomic replacement. Async Responses and chat provider resolution move blocking authentication off the event loop. A replayable ChatGPT POST rejected with HTTP 401 can refresh and retry once before any stream output is returned; other providers retain their existing error handling. Responses iterators expose explicit close methods and close the provider response on termination or cancellation

String input is converted to one user message because the Codex backend requires an input list. Existing message and tool-result lists are forwarded without constructing a conversation history

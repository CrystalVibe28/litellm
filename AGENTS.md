Read @CLAUDE.md for coding guidelines

## crystalvibe28 custom patches

This repository is a personal fork of [BerriAI/litellm](https://github.com/BerriAI/litellm). The sections below list every fork-specific change so that they can be preserved (or consciously dropped) when merging upstream

Any request to merge, sync, pull in or update from upstream, in any wording and in any language, means: follow "Merging upstream" below exactly. The request does not need to repeat any of it. Read the patch sections before touching a file they list

### Remotes and branches

- **Remotes:** `upstream` = BerriAI/litellm, `origin` = the fork

| Branch | Purpose |
| ------ | ------- |
| `crystalvibe28/litellm_internal_staging.patch` | The main patch branch: upstream plus every custom patch. It receives upstream merges and custom patch branches. Small fixes may be committed on it directly (patch 5) |
| `litellm_<topic>` | One branch per custom feature or larger change. Kept after merging. Follow-up work on the same patch goes on the same branch and is merged again |
| `codex/chatgpt-image-bridge` | The topic branch of patch 1. It predates the `litellm_<topic>` naming rule and keeps its name |
| `litellm_agents_md_patch_registry` | Documentation-only branch for this file |
| `litellm_internal_staging` | Upstream's integration branch, the merge source. There is no local branch of that name at the moment, only `origin/litellm_internal_staging`, which is stale (2026-06-01) |
| `main` | Local mirror of `upstream/main`. Never commit to it. Only fast-forward it from `upstream` |
| `dogoin/v1.83.14-stable.patch.3-pr25603`, `dogoin/v1.83.14-stable.patch.3-pr25603-codex-image-bridge` | **Deprecated. Do not commit to them or branch from them.** Older patch branches on top of the release tag `v1.83.14-stable.patch.3`, superseded by the main patch branch |
| `pr-25603` | Local copy of upstream PR #25603, the source of patch 8. Read-only |

New branches follow the rule in `CLAUDE.md`: prefix `litellm_`, no `/` in the name

### Commit conventions

- **Language:** English, for every commit message in this repository. This overrides any general preference for another language
- **Format:** [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <imperative summary in lower case>`. The scope is optional. A body is allowed when the reason is not obvious from the subject
  - Types in use: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
  - Scopes in use: `chatgpt`, `proxy`, `router`, `auth`, `opencode_go`, `command_code`, `vercel_ai_gateway`, `agents`
- **Merge commits:**
  - Upstream: `chore: merge upstream litellm_internal_staging`
  - Custom branch: git's default subject, `Merge branch '<branch>' into crystalvibe28/litellm_internal_staging.patch`
- **Always** create a merge commit (`--no-ff`). Never rebase, squash or fast-forward a merge into the main patch branch
- **Author:** custom commits are authored by `CrystalVibe28`. No AI attribution lines
- Never force-push the main patch branch
- After every commit, update this file (see "Rule: keep this file in sync with every commit")

### Merging a custom patch branch

The target is always `crystalvibe28/litellm_internal_staging.patch`

1. Start the work from the current main patch branch: create `litellm_<topic>` from it, or continue on the patch's existing branch after merging the main patch branch into it
2. Commit on the branch, following the commit conventions
3. Switch to the main patch branch and merge with `git merge --no-ff <branch>`, keeping the default message
4. If the merge conflicts, keep both sides' intent: upstream's code is the base and the patch logic is re-applied on top (same principles as an upstream merge, below). Run the tests that cover the patch before completing the merge commit
5. Do not delete the branch
6. Update this file

### Merging upstream

The work has two phases, with a stop in between whenever there are conflicts

**Phase 1: prepare and merge**

1. Check that the working tree is clean. Never overwrite, restore or delete existing changes. If there are uncommitted changes, stop and report
2. Fetch from `upstream` and bring the local `litellm_internal_staging` up to the latest upstream commit
   - If `upstream` has no `litellm_internal_staging` branch (check with `git ls-remote upstream refs/heads/litellm_internal_staging`), do not guess a replacement. Report it, together with upstream's default branch (`git ls-remote --symref upstream HEAD`) and whether that branch contains the reference commit of the last upstream merge, and wait for the user to name the merge source
   - As of 2026-11-14 this is the case: upstream no longer has `litellm_internal_staging`, its default branch is `main`, and `upstream/main` contains the last merged commit `e907e5ee9b`
3. Switch to the local branch that tracks `crystalvibe28/litellm_internal_staging.patch`. If the branch name or its tracking relationship is unclear, report the current branch and remote state before going further
4. Look at the earlier upstream merge commits (`git log --first-parent --merges --grep="merge upstream"`) and reuse their message format: `chore: merge upstream litellm_internal_staging`
5. Merge with `git merge --no-ff`. No rebase, no squash
6. If there are no conflicts, run the checks from phase 2 step 4, complete the merge commit and report
7. If there are conflicts:
   - Leave the repository in the conflicted state. Do not resolve anything, do not create the merge commit, and do not run `git merge --abort`
   - List every conflicted file
   - For each one, compare upstream's change with the fork's patch and explain the cause of the conflict, how the two implementations differ, and the proposed way to integrate them. Use the patch sections of this file to identify what the fork's side is for
   - Stop and wait for instructions

**Phase 2: resolve, after the user has replied to the analysis**

1. Resolve by these principles:
   - The result must contain upstream's updates in full **and** keep every fork patch
   - Upstream's code is the base. Re-integrate the necessary patch logic on top of it
   - Where both sides implement the same or a similar feature, build on upstream's latest implementation and behaviour. Do not keep an old implementation that upstream has replaced. Port the fork's customisation onto upstream's version
   - Never settle a conflict by taking the whole of "ours" or the whole of "theirs" when that loses an important change from either side
   - Do not touch anything unrelated to the merge
2. Apply the standing resolutions:
   - Patch code carried across the merge follows upstream's current typing and lint style (PEP 604 unions, `Final`). Check the imports of every file a patch touches: a name upstream stopped importing fails only at runtime (patch 5)
   - `model_prices_and_context_window.json` and `litellm/model_prices_and_context_window_backup.json`: take upstream's file and re-insert the fork's entries (patches 1 and 6)
   - If upstream has merged PR #25603 or an equivalent, take upstream's version and drop patch 8
3. Make sure no conflict markers remain
4. Run the applicable format checks, tests and build. Run at least the test files listed under every patch whose files the merge touched
5. Once the result is confirmed, create the merge commit with the message from phase 1 step 4
6. Report:
   - which conflicts were resolved, and how each was integrated
   - how each fork patch was preserved
   - the merge commit's hash and message
   - the test and build results
7. Update this file: re-measure line ranges, move the reference commit, and record anything upstream superseded

### Rule: keep this file in sync with every commit

Every commit made in this fork must be reflected in this file. Do this as part of the commit task, without being asked

**When**

- Right after each commit. The hash is only known once the commit exists, so the update follows the commit
- Commit the update on its own as `docs(agents): <summary>` on `litellm_agents_md_patch_registry` (merge the main patch branch into it first), then merge it into the main patch branch like any other custom branch. One such commit may cover all the commits of the same task. Doc-only commits are not patches and are not listed here

**What to update**

| Kind of commit | Required update |
| -------------- | --------------- |
| New fork-specific change | Add a new numbered section at the end and a row in the Overview table |
| Follow-up to an existing patch | Update that patch's section: summary, reason, commit list, files and line ranges, status |
| Custom branch merged | Update the patch's status and its Overview row, then re-measure its line ranges at the new main patch branch |
| Upstream merge | Re-measure the line ranges of every merged patch, update the reference commits in "How to read the line ranges", and record anything upstream superseded |
| Patch dropped, reverted or superseded | Keep the section, mark it in the status line and say why. Do not delete it |

**Format of a patch section** (all in English, following the prose rules in `CLAUDE.md`)

1. Heading: `### <N>. <topic>`
2. `**Status:**` is required unless the patch is fully merged into the main patch branch and intact
3. `**What it changes**`: behaviour and mechanism, naming the functions, classes, setting keys and endpoints involved
4. `**Why**`: the problem that led to the change. Take it from the request that started the work. If the reason is inferred from the code, say so
5. `**Branch:**` the branch the work was committed on
6. `**Commits**`: one line each, `` `<10-char hash>` (YYYY-MM-DD) `<full subject>` ``
7. `**Files and line ranges**`: grouped per commit, with the reference commit stated. Follow "How to read the line ranges"
8. `**Merge notes**`: what must be re-applied or re-checked after an upstream merge

**Checks before finishing**

- Every hash listed exists: `git log -1 <hash>`
- The Overview table and the sections agree on branch, status and commits
- Nothing is recorded that was not actually committed
- No secrets, hostnames of private deployments, or customer names

### How to read the line ranges

- Ranges are `git blame` attributions: the lines each commit **still owns** at the reference commit. They are current locations, not the hunks at commit time, and they drift with every upstream merge
- Patches merged into the main patch branch are measured at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8`, against the last merged upstream commit `e907e5ee9b` (2026-09-10). Commits after `a8b6251ee8` only touch this file
- Patches that are **not merged** are measured at their own branch tip, which sits on an older upstream base, so their numbers do not match the main patch branch
- "merge `<hash>`" marks lines of the same patch that were re-resolved during an upstream merge and are now attributed to that merge commit
- "new" marks a file that does not exist upstream
- To measure one file: `git blame -s -l <ref> -- <path>`, then collect the line numbers attributed to the commit, restricted to the lines `git diff -U0 <upstream commit> <ref> -- <path>` reports as added
- To regenerate the commit list: `git log --branches --no-merges --author=CrystalVibe28 --format="%h %ad %s" --date=short`

### Overview

| # | Patch | Branch | In main patch branch | Commits |
| - | ----- | ------ | -------------------- | ------- |
| 1 | ChatGPT image generation and image edit bridge | `codex/chatgpt-image-bridge` | Yes, except `db3eda4bb9` | `ffd11fdfa3`, `49c53492e6`, `f3a65bd26b`, `f97780a636`, `4c653a5749`, `4f42ead4ca`, `4b168229b5`, `1f84f188e7`, `e59ef32ddd`, `bc3f09f362`, `765cc80adf`, `efdc5a22cd`, `405a41d302`, `ed72e3200b`, `f61c2b2b0a`, `e9094c1907`, `db3eda4bb9` (prototype: `b817d9fe75`) |
| 2 | ChatGPT / Codex proxy hardening | `litellm_chatgpt_codex_proxy` | Yes | `d95fa1c143`, `9226119a6c`, `afbecb53ce`, `cc305c99c5` |
| 3 | Internal user header budgets | `litellm_openwebui_user_header_budget_investigation` | Yes | `8ad82302e3`, `6bda0f7b9e`, `16bf658dcb` |
| 4 | Forward client headers by selected deployment | `litellm_forward_headers_by_deployment` | Yes | `a4c0d19106` |
| 5 | Proxy startup fix for an undefined `Optional` | `crystalvibe28/litellm_internal_staging.patch` | Yes | `f3c816c9dc` |
| 6 | OpenCode Go provider | `litellm_opencode_go_provider` | Yes | `74eba73f9a`, `86a8f2ca49` |
| 7 | Command Code provider | `litellm_command_code_provider` | Yes | `8c6f11bdff` |
| 8 | Vercel AI Gateway `reasoning_effort` | `crystalvibe28/litellm_internal_staging.patch` (cherry-pick) | Yes | `f9d3395a0b` |

---

### 1. ChatGPT image generation and image edit bridge

**Status:** in the main patch branch, except `db3eda4bb9`, the tip of `codex/chatgpt-image-bridge`, which has never been merged. The main patch branch therefore still accepts only `size` on image edits and silently drops every other param, whatever `drop_params` says

**What it changes**

- `ChatGPTImageGenerationConfig` (`image_generation/generation_transformation.py`) turns an OpenAI Images request into a Responses request that uses the `image_generation` tool with an internal responses model, and posts it to the Codex `/responses` endpoint with the authenticator's token, account id and session id
- `image_generation/response_parsing.py` reads the upstream SSE stream or JSON, rebuilds an `ImageResponse` with `ImageObject`s and `ImageUsage`, dedupes images and keeps the upstream error status
- `ChatGPTImageEditConfig` (`image_edit/transformation.py`) reuses the same path. Input images are sent as base64 `input_image` items in a JSON body, and `use_multipart_form_data()` returns `False`
- Wiring: `CHATGPT` in the provider list of `litellm/images/main.py`, provider config lookup in `litellm/utils.py`, lazy exports in `litellm/__init__.py` and `_lazy_imports_registry.py`, the `partial_images` and `stream` literals in `litellm/types/llms/openai.py`, and a `chatgpt/gpt-image-2` entry in `model_prices_and_context_window.json`
- `db3eda4bb9` (not merged): image edit supports the same params as generation (`size`, `output_format`), and `map_openai_params` honours `drop_params`, raising `ValueError` for an unsupported param unless `drop_params=True`

**Why**

- Upstream cannot serve `/v1/images/generations` or `/v1/images/edits` through the `chatgpt/` provider (ChatGPT subscription over OAuth), because the Codex backend only exposes image generation as a tool on the Responses API
- The fork wants Images API clients to use `gpt-image-2` on a ChatGPT plan, with correct usage and cost accounting. This reason is inferred from the commits and the code

**Branch:** `codex/chatgpt-image-bridge`. The prototype `b817d9fe75` lives only on the deprecated `dogoin/v1.83.14-stable.patch.3-pr25603-codex-image-bridge`

**Commits**

- `b817d9fe75` (2026-05-14) `feat(chatgpt): add image generation bridge` (prototype, same content as `ffd11fdfa3`)
- `ffd11fdfa3` (2026-05-14) `feat(chatgpt): support image generation`
- `49c53492e6` (2026-05-14) `fix(chatgpt): avoid recursive image extraction`
- `f3a65bd26b` (2026-05-14) `test(chatgpt): cover image generation transformation`
- `f97780a636` (2026-05-14) `fix(chatgpt): limit image generation params`
- `4c653a5749` (2026-05-14) `docs: document chatgpt image responses fallback`
- `4f42ead4ca` (2026-05-14) `fix(chatgpt): remove image responses env override`
- `4b168229b5` (2026-05-14) `fix(chatgpt): ignore request api_base for image generation`
- `1f84f188e7` (2026-05-15) `feat(chatgpt): support image edits`
- `e59ef32ddd` (2026-05-15) `feat: add ChatGPT GPT Image 2 pricing metadata`
- `bc3f09f362` (2026-05-15) `fix: register ChatGPT image edit config lazy import`
- `765cc80adf` (2026-05-15) `fix: remove hardcoded gpt-image-2 size constraints`
- `efdc5a22cd` (2026-05-16) `test(chatgpt): cover image generation patch diff`
- `405a41d302` (2026-05-16) `fix: remove pdf input support from gpt-image-2`
- `ed72e3200b` (2026-05-16) `refactor(chatgpt): split image transformation modules`
- `f61c2b2b0a` (2026-05-17) `fix(chatgpt): avoid recursive image usage parsing`
- `e9094c1907` (2026-05-17) `fix: preserve ChatGPT image stream error status`
- `db3eda4bb9` (2026-05-17) `fix: align ChatGPT image edit drop params behavior` (not merged)

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8` unless stated)

`ffd11fdfa3`

- `litellm/__init__.py`: 2040-2041
- `litellm/_lazy_imports_registry.py`: 309, 1177, 1179-1180
- `litellm/images/main.py`: 388
- `litellm/llms/chatgpt/image_generation/__init__.py`: 2 (new, shared with `ed72e3200b`)
- `litellm/types/llms/openai.py`: 1147, 1151
- `litellm/utils.py`: 9092-9097

`1f84f188e7`

- `litellm/__init__.py`: 2037
- `litellm/_lazy_imports_registry.py`: 1181, 1183-1184
- `litellm/utils.py`: 9293, 9295-9296

`bc3f09f362`

- `litellm/_lazy_imports_registry.py`: 310

`ed72e3200b`

- `litellm/__init__.py`: 2036, 2038-2039
- `litellm/_lazy_imports_registry.py`: 1178, 1182
- `litellm/utils.py`: 9294
- `litellm/llms/chatgpt/image_generation/__init__.py`: 1, 3 (new)
- `litellm/llms/chatgpt/image_generation/generation_transformation.py`: 1-307 (new). The whole file belongs to this patch except 21, 24, 55-56 and 111-115, which belong to patch 2. Merge `cd1476d14e` re-resolved about 30 single lines for upstream's lint style
- `litellm/llms/chatgpt/image_generation/response_parsing.py`: 1-276 (new), except the lines of `f61c2b2b0a` and `e9094c1907`. Merge `cd1476d14e` re-resolved about 25 single lines
- `litellm/llms/chatgpt/image_edit/__init__.py`: 1-3 (new)
- `litellm/llms/chatgpt/image_edit/transformation.py`: 1-169 (new; merge `cd1476d14e`: 4, 32, 40, 42, 48-50, 65, 82-84, 87, 89, 121, 126, 164)
- `tests/test_litellm/llms/chatgpt/chatgpt_image_test_utils.py`: 1-10 (new)
- `tests/test_litellm/llms/chatgpt/image_edit/test_transformation.py`: 1-189 (new)
- `tests/test_litellm/llms/chatgpt/image_generation/test_request_transformation.py`: 1-394 (new), except 131, 185-190, 199, 240 and 346, which belong to patch 2
- `tests/test_litellm/llms/chatgpt/image_generation/test_response_parsing.py`: 1-131, 191-270 (new)
- `tests/test_litellm/llms/chatgpt/image_generation/test_usage.py`: 1-30, 79-247 (new)

`f61c2b2b0a`

- `litellm/llms/chatgpt/image_generation/response_parsing.py`: 88-103, 106-107
- `tests/test_litellm/llms/chatgpt/image_generation/test_usage.py`: 31-78

`e9094c1907`

- `litellm/llms/chatgpt/image_generation/response_parsing.py`: 165, 167, 169-171, 173-187, 195-198
- `tests/test_litellm/llms/chatgpt/image_generation/test_response_parsing.py`: 132-190

`e59ef32ddd`, `405a41d302`

- `model_prices_and_context_window.json`: 28127-28135, the `chatgpt/gpt-image-2` entry, now attributed to merge `cd1476d14e`

`49c53492e6`, `f3a65bd26b`, `f97780a636`, `4c653a5749`, `4f42ead4ca`, `4b168229b5`, `765cc80adf`, `efdc5a22cd`

- No surviving lines. Their code was moved into the split modules by `ed72e3200b`, which now owns it

`db3eda4bb9` (at `codex/chatgpt-image-bridge @ db3eda4bb9`, not merged)

- `litellm/llms/chatgpt/image_edit/transformation.py`: 33-36, 45-57
- `tests/test_litellm/llms/chatgpt/image_edit/test_transformation.py`: 120-169

**Merge notes**

- Keep the `CHATGPT` entry in `litellm/images/main.py`, both provider config branches in `litellm/utils.py`, the lazy exports, and the `partial_images` / `stream` literals
- Image edit stays JSON, never multipart
- The OAuth token is only ever sent to the authenticator's base URL, never to a caller-supplied `api_base` (`4b168229b5`)
- Usage and error parsing stay non-recursive and keep the real upstream status code
- The `chatgpt/gpt-image-2` entry exists only in `model_prices_and_context_window.json`. It is missing from `litellm/model_prices_and_context_window_backup.json`
- The topic branch sits on a much older upstream base than the main patch branch. Merging `db3eda4bb9` will conflict with the lint rewrites of `cd1476d14e` in `image_edit/transformation.py`. Re-apply the change on the current file instead of taking the branch's version

---

### 2. ChatGPT / Codex proxy hardening

**What it changes**

- `d95fa1c143`: the outbound identity becomes a pinned Codex CLI `0.154.0` header set. `merge_chatgpt_headers` in `common_utils.py` merges headers case-insensitively, normalises `session_id` / `thread_id` to `session-id` / `thread-id`, strips `Forwarded`, `Via`, `X-Forwarded-*`, `X-LiteLLM-*`, `X-Stainless-*` and `X-API-Key`, and forces the OAuth `Authorization` and `ChatGPT-Account-Id`. `finalize_chatgpt_request` is the `sign_request` hook for the chat, responses and image configs. Caller `extra_headers` are passed through for `chatgpt` in `llm_http_handler.py`
- `9226119a6c`: `normalize_chatgpt_responses_request` replaces the hardcoded Codex system prompt. Caller `instructions` are preserved, including an empty string, with the `CHATGPT_DEFAULT_INSTRUCTIONS` env var or `""` as the fallback. Fields are whitelisted (`text`, `parallel_tool_calls`, `prompt_cache_key` and `client_metadata` are now allowed), and `stream=true`, `store=false` and `include: reasoning.encrypted_content` are always forced. Non-streaming callers still get a full response object, built by aggregating the upstream SSE
- `afbecb53ce`: `Authenticator` refresh is guarded by an `RLock` plus a cross-process file lock (`msvcrt` or `fcntl`) with a 60 second timeout, auth file writes are atomic (temp file, `fsync`, `os.replace`), and secrets stay out of error messages. `HTTPHandler` and `AsyncHTTPHandler` refresh the token and resend once on a 401 when the body is replayable. The Responses streaming iterators close their connections on completion or cancel. Provider lookup for `chatgpt/` models runs in a thread because auth does blocking I/O
- `cc305c99c5`: the image generation `validate_environment` forces the OAuth `Authorization` and `ChatGPT-Account-Id`, so proxy callers cannot override them

**Why**

- Upstream's `chatgpt/` provider identifies itself with a LiteLLM-derived user agent, forwards proxy and SDK headers to the backend, injects a long hardcoded Codex system prompt into every Responses call, drops fields the backend supports, and refreshes OAuth tokens without any locking
- The fork needs LiteLLM to look like a faithful Codex client and to be safe for concurrent, long-running proxy use: no injected prompt, no leaked caller headers, no refresh races, no leaked connections. This reason is inferred from the commits and the code

**Branch:** `litellm_chatgpt_codex_proxy`

**Commits**

- `d95fa1c143` (2026-09-12) `fix(chatgpt): align outbound Codex identity and normalize proxy headers`
- `9226119a6c` (2026-09-12) `fix(chatgpt): preserve proxy request semantics and aggregate non-streaming responses`
- `afbecb53ce` (2026-09-12) `fix(chatgpt): harden OAuth refresh and streaming connection lifecycle`
- `cc305c99c5` (2026-09-12) `fix(chatgpt): preserve OAuth identity for image proxy requests`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8`)

`d95fa1c143`

- `litellm/llms/chatgpt/README.md`: 1-7 (new)
- `litellm/llms/chatgpt/chat/transformation.py`: 11, 13, 20, 65-69
- `litellm/llms/chatgpt/common_utils.py`: 7, 26-27, 131, 157, 163, 170, 172-179, 181-189, 191-192
- `litellm/llms/chatgpt/image_generation/generation_transformation.py`: 21, 24, 56
- `litellm/llms/chatgpt/responses/transformation.py`: 27, 29, 39, 66-70
- `litellm/llms/custom_httpx/llm_http_handler.py`: 2689, 2691
- `tests/test_litellm/llms/chatgpt/image_generation/test_request_transformation.py`: 131, 199, 240, 346
- `tests/test_litellm/llms/chatgpt/responses/test_chatgpt_responses_transformation.py`: 8-10, 23, 99-111, 114-120, 129-149, 151, 160-168, 175, 258, 261, 284, 324, 363, 386, 404, 427, 467, 500

`9226119a6c`

- `litellm/llms/chatgpt/README.md`: 8-11
- `litellm/llms/chatgpt/common_utils.py`: 164-169, 171, 194-213, 216-217, 221-227
- `litellm/llms/chatgpt/responses/transformation.py`: 30, 87
- `litellm/llms/custom_httpx/llm_http_handler.py`: 2718-2722, 2919-2923
- `tests/test_litellm/llms/chatgpt/responses/test_chatgpt_responses_transformation.py`: 24, 28-44, 46-98, 112-113, 121-122, 124-128, 150, 152-159, 169-174, 305

`afbecb53ce`

- `litellm/llms/chatgpt/README.md`: 12-17
- `litellm/llms/chatgpt/authenticator.py`: 4-5, 7-9, 16, 40, 48-49, 61-72, 84-134, 136-139, 141, 165-166, 171-179, 181, 238, 250, 252, 254, 261, 271, 307, 309, 311, 321, 342, 344, 346, 353, 364, 373, 382, 384, 386, 392
- `litellm/llms/chatgpt/chat/transformation.py`: 19
- `litellm/llms/chatgpt/common_utils.py`: 12, 28, 146, 180, 190, 214-215, 218-220
- `litellm/llms/chatgpt/image_generation/generation_transformation.py`: 55
- `litellm/llms/chatgpt/responses/transformation.py`: 38
- `litellm/llms/custom_httpx/http_handler.py`: 62-90, 769-777, 1422-1430
- `litellm/llms/custom_httpx/llm_http_handler.py`: 2882-2888, 2890-2894
- `litellm/main.py`: 617-624
- `litellm/responses/main.py`: 539-542
- `litellm/responses/streaming_iterator.py`: 14, 860-865, 867-868, 913-918, 956-960, 962-963, 1008-1010
- `tests/test_litellm/llms/chatgpt/test_chatgpt_authenticator.py`: 2, 4-7, 9-12, 14, 18-22, 36-191, 193-195, 205-208, 210-248, 251, 260
- `tests/test_litellm/llms/chatgpt/responses/test_chatgpt_responses_transformation.py`: 45, 123
- `tests/test_litellm/responses/test_responses_streaming_iterator.py`: 11-12, 23-24, 28-114

`cc305c99c5`

- `litellm/llms/chatgpt/image_generation/generation_transformation.py`: 111-115
- `tests/test_litellm/llms/chatgpt/image_generation/test_request_transformation.py`: 185-190

**Merge notes**

- Keep the `custom_llm_provider == "chatgpt"` branches in both the sync and async Responses paths of `llm_http_handler.py`: header merging, `normalize_chatgpt_responses_request`, and forcing `stream` on
- Keep the 401 refresh and retry (`_can_refresh_chatgpt`, `_chatgpt_retry_request`) in `HTTPHandler` and `AsyncHTTPHandler`
- Keep `close` / `aclose` and the `finished` guards in `litellm/responses/streaming_iterator.py`
- Keep the `asyncio.to_thread` offloading for `chatgpt/` models in `litellm/main.py` and `litellm/responses/main.py`
- Keep `sign_request` on the chat, responses and image configs. OAuth identity headers always win over caller headers
- Never re-add a default system prompt
- `litellm/llms/chatgpt/README.md` documents these rules and must stay in sync with the code
- The pinned Codex CLI version (`0.154.0`) is a constant the fork maintains by hand. Upstream changes to the user agent must not replace it

---

### 3. Internal user header budgets

**What it changes**

- `8ad82302e3`: `_apply_internal_user_header_mapping_for_auth` in `user_api_key_auth.py` runs at the start of `_run_centralized_common_checks`, before the user and budget lookups, so the header-mapped internal user (and not the owner of the shared key) is the identity whose budget is checked. It reuses the existing `LiteLLMProxyRequestSetup.add_internal_user_from_user_mapping`
- `6bda0f7b9e`: admin keys (`PROXY_ADMIN`, `PROXY_ADMIN_VIEW_ONLY`) are remapped too, but only on LLM routes. The helper returns whether the `user_id` changed, and when it did, the forced admin `user_object` shortcut is skipped so the mapped user's budget applies
- `16bf658dcb`: the resolved `end_user_id` is written onto the auth object, and that object is passed to the auth exception handler, so budget-exceeded errors and failure hooks keep the mapped user context

**Why**

- Open WebUI uses one shared key, often an admin key, for all of its users and sends the real end user in a header. Upstream maps that header to an internal user only after the budget checks, so per-user budgets were never enforced. This reason is inferred from the branch name, the commits and the code

**Branch:** `litellm_openwebui_user_header_budget_investigation`

**Commits**

- `8ad82302e3` (2026-06-02) `fix(proxy): enforce internal user header budgets`
- `6bda0f7b9e` (2026-06-02) `fix(proxy): enforce mapped internal user budgets for admin keys`
- `16bf658dcb` (2026-06-02) `fix(proxy): preserve mapped user context in budget errors`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8`)

`8ad82302e3`

- `litellm/proxy/auth/user_api_key_auth.py`: 2470-2472, 2474-2475, 2722-2724, 2728-2730, 2735-2740, 2742-2743 (merge `90f9c09983`: 2644, 2741; merge `cd1476d14e`: 2469, 2734; line 2725 belongs to patch 5)

`6bda0f7b9e`

- `litellm/proxy/auth/user_api_key_auth.py`: 2473, 2726-2727, 2731-2733

`16bf658dcb`

- `litellm/proxy/auth/user_api_key_auth.py`: 2492-2493
- `tests/test_litellm/proxy/auth/test_auth_exception_handler.py`: 448-472, 474-481, 483-485, 488-490, 492-493, 527, 529 (merge `90f9c09983`: 473, 482, 486-487, 491)
- `litellm/proxy/auth/auth_exception_handler.py`: no surviving lines. The optional `user_api_key_auth_obj` parameter this commit added is now identical to upstream

All three commits

- `tests/test_litellm/proxy/auth/test_user_api_key_auth.py`: 8, 365, 3872-4194, 4609-4611, 4666, 4677, all attributed to merge `cd1476d14e`, which re-placed the patch's tests

**Merge notes**

- The mapping must run before the user, team and budget checks in `_run_centralized_common_checks`
- Admin keys are never remapped on non-LLM routes
- The admin `user_object` override stays conditional on `not mapped_internal_user_for_auth`
- The exception handler must still receive the mutated auth object
- `_run_centralized_common_checks` is a hot upstream function, and upstream merges have already re-resolved this patch twice

---

### 4. Forward client headers by selected deployment

**What it changes**

- Pre-call (`litellm_pre_call_utils.py`) stores a frozen `ModelGroupHeaderForwarding` (allowed models, filtered client headers, team id) under `MODEL_GROUP_HEADERS_KEY` in the request data, instead of deciding on the spot
- `Router` replaces it with a copy carrying `deployment_model_name` once a deployment is selected, including in the `alist_batches` helper
- The sync and async `client()` wrappers in `litellm/utils.py` call `apply_model_group_headers` (`get_provider_specific_headers.py`). It re-runs the proxy's `_check_model_access_helper` (wildcard and access group matching) against the selected model, merges the forwarded headers case-insensitively on a match, and removes the internal key
- `MODEL_GROUP_HEADERS_KEY` is added to `_UNTRUSTED_ROOT_CONTROL_FIELDS` and `_TRANSPORT_ONLY_CREDENTIAL_KEYS`, so clients cannot spoof it and it is never logged

**Why**

- Upstream decides `forward_client_headers_to_llm_api` once, by matching the requested model group name. That is wrong for fallbacks, wildcards and aliases, where the deployment the router finally picks has a different model name than the one the client asked for. This reason is inferred from the commit and the code

**Branch:** `litellm_forward_headers_by_deployment`

**Commits**

- `a4c0d19106` (2026-09-12) `fix(router): forward client headers based on the selected deployment model`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8`)

`a4c0d19106`

- `litellm/litellm_core_utils/get_provider_specific_headers.py`: 1-3, 6-7, 10-64
- `litellm/proxy/litellm_pre_call_utils.py`: 35-38, 79-81, 232, 1413-1429
- `litellm/router.py`: 34, 83, 3798-3800, 6541-6545
- `litellm/utils.py`: 87, 1466-1468, 1773-1775
- `tests/test_litellm/litellm_core_utils/test_provider_specific_headers.py`: 1-3, 6, 8-9, 11, 14-196
- `tests/test_litellm/proxy/test_litellm_pre_call_utils.py`: 7915-7948
- `tests/test_litellm/test_router.py`: 15143-15238

**Merge notes**

- `MODEL_GROUP_HEADERS_KEY` must be removed before the provider call and must never reach logs or the request body
- The key stays in `_UNTRUSTED_ROOT_CONTROL_FIELDS` and `_TRANSPORT_ONLY_CREDENTIAL_KEYS`
- `Router` must stamp `deployment_model_name` on every path that dispatches to a deployment. Check new upstream dispatch paths
- The wrappers in `litellm/utils.py` apply the headers before anything else runs
- The early return in pre-call only fires when `litellm.model_group_settings.forward_client_headers_to_llm_api` is set and `llm_router` exists. Otherwise behaviour must stay identical to upstream
- Patch 7 relies on this patch for the client-sent `x-cmd-zdr` header

---

### 5. Proxy startup fix for an undefined `Optional`

**What it changes**

- The helper added by patch 3 was annotated `general_settings: Optional[dict]`. The annotation is now `dict | None`

**Why**

- Upstream removed `typing.Optional` from `user_api_key_auth.py` in a lint refactor. After that upstream merge the patch's annotation raised `NameError` at import time and the proxy could not start

**Branch:** committed directly on `crystalvibe28/litellm_internal_staging.patch`. It is also contained in `litellm_opencode_go_provider` and `litellm_command_code_provider`, which were branched after it

**Commits**

- `f3c816c9dc` (2026-09-13) `fix(auth): resolve undefined Optional annotation blocking proxy startup`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8`)

`f3c816c9dc`

- `litellm/proxy/auth/user_api_key_auth.py`: 2725

**Merge notes**

- This is the reason for the standing resolution on typing style and imports in "Merging upstream". A merge that compiles can still fail at proxy start, so start the proxy or import the touched modules after an upstream merge

---

### 6. OpenCode Go provider

**What it changes**

- `74eba73f9a`: adds the `opencode_go` provider for `https://opencode.ai/zen/go/v1`, under `litellm/llms/opencode_go/` (`chat/`, `messages/`, `responses/`, `common_utils.py`)
  - Each model is served on exactly one of three wire formats, so chat, `/v1/messages` and `/v1/responses` requests are routed to `/chat/completions`, `/messages` (Anthropic style, `x-api-key` auth) or `/responses`. The format comes from the model's cost map entry and falls back to the model name
  - Every upstream request carries `x-opencode-session`. A client-sent value is kept (case-insensitive match), otherwise the LiteLLM session id, trace id or a generated id is used
  - The proxy scopes the client header to this provider through `provider_specific_header`, so it works without `forward_client_headers_to_llm_api` and never leaks to other providers. The Responses path now applies provider-specific headers too
  - Wiring in `litellm/main.py`, `utils.py`, `get_llm_provider_logic.py`, `responses/main.py`, `llm_http_handler.py`, the Anthropic chat handler, both cost maps, both provider endpoint JSON files, `provider_create_fields.json` and the dashboard provider list
- `86a8f2ca49`: text-only content arrays are flattened to strings, `reasoning_effort` is forwarded instead of rejected, and the `claude-haiku-5-5` cost map entry gains the thinking capability flags

**Why**

- Upstream has no OpenCode Go provider
- `x-opencode-session` is mandatory in practice: requests without it are rejected, whatever the official documentation says
- `86a8f2ca49` came out of live testing. Some backends silently drop system prompts sent as content arrays, `reasoning_effort` was being rejected, and `claude-haiku-5-5` needs adaptive thinking

**Branch:** `litellm_opencode_go_provider`

**Commits**

- `74eba73f9a` (2026-10-09) `feat(opencode_go): add OpenCode Go provider`
- `86a8f2ca49` (2026-10-12) `fix(opencode_go): keep system prompts, reasoning_effort and Claude thinking working`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8`)

`74eba73f9a`

- `litellm/llms/opencode_go/__init__.py`, `chat/__init__.py`, `messages/__init__.py`, `responses/__init__.py`: empty (new)
- `litellm/llms/opencode_go/common_utils.py`: 1-68 (new)
- `litellm/llms/opencode_go/chat/transformation.py`: 10-22, 34-38, 75-145 (new)
- `litellm/llms/opencode_go/messages/transformation.py`: 1-54 (new)
- `litellm/llms/opencode_go/responses/transformation.py`: 1-42 (new)
- `litellm/__init__.py`: 703, 982-983, 1232, 1550
- `litellm/_lazy_imports_registry.py`: 128, 616
- `litellm/constants.py`: 628, 868
- `litellm/litellm_core_utils/get_llm_provider_logic.py`: 330-332, 741-745
- `litellm/llms/anthropic/chat/handler.py`: 462, 464
- `litellm/llms/custom_httpx/llm_http_handler.py`: 206, 2690, 2696, 2889, 2897
- `litellm/main.py`: 117-122, 1062-1064, 2476-2527, 5831-5832
- `litellm/proxy/litellm_pre_call_utils.py`: 162, 3404, 3420-3423, 3429
- `litellm/responses/main.py`: 21, 1142-1152
- `litellm/types/utils.py`: 3995
- `litellm/utils.py`: 8076-8079, 8212-8217, 8517-8521, 8713-8719
- `model_prices_and_context_window.json`: 64566-64589, 64600-65347
- `litellm/model_prices_and_context_window_backup.json`: 64557-64580, 64591-65338
- `provider_endpoints_support.json`: 2886-2894
- `litellm/provider_endpoints_support_backup.json`: 2557-2565
- `litellm/proxy/public_endpoints/provider_create_fields.json`: 1994-2021
- `ui/litellm-dashboard/src/components/provider_info_helpers.tsx`: 130, 247
- `tests/test_litellm/llms/opencode_go/__init__.py`: empty (new)
- `tests/test_litellm/llms/opencode_go/test_opencode_go.py`: 1-76, 80-91, 99-123, 168-355 (new)

`86a8f2ca49`

- `litellm/llms/opencode_go/chat/transformation.py`: 1-9, 23-33, 39-74
- `model_prices_and_context_window.json`: 64590-64599
- `litellm/model_prices_and_context_window_backup.json`: 64581-64590
- `tests/test_litellm/llms/opencode_go/test_opencode_go.py`: 77-79, 92-98, 124-167

**Merge notes**

- `x-opencode-session` is always sent and stays scoped to this provider
- The two cost map files must stay in sync, and the `opencode_go` entries must keep their wire format and thinking flags. Upstream rewrites these files constantly: take upstream's file and re-insert the block
- Text-only content arrays are flattened. Arrays with non-text parts are left alone
- Keep every registration listed under `74eba73f9a`. A missing one usually fails only when the provider is first used
- The Responses path must keep applying provider-specific headers
- Patches 6 and 7 add adjacent lines in the same registration lists. Keep both

---

### 7. Command Code provider

**What it changes**

- Adds the `command_code` provider for `https://api.commandcode.ai/provider/v1`, under `litellm/llms/command_code/` (`chat/`, `messages/`, `common_utils.py`)
- Claude models are served only on `/messages` and every other model on `/chat/completions`. Chat and `/v1/messages` requests are translated to the right endpoint, and `/v1/responses` goes through the chat completions bridge
- Zero data retention is off by default. `x-cmd-zdr` can be set in the deployment's `extra_headers`, or sent by the client when the model group is listed in `forward_client_headers_to_llm_api` (patch 4). Truthy values are normalised to `1`, other values are dropped, case-variant duplicates are collapsed, and a client cannot switch off what the deployment enabled
- The provider uses the shared HTTP handler, not the OpenAI SDK handler. A 422 such as `cmd_zdr_no_providers` is raised once with the upstream message, is not retried, and still triggers fallbacks

**Why**

- Upstream has no Command Code provider
- The backend only honours the exact value `1` for `x-cmd-zdr`, hence the normalisation
- The OpenAI SDK handler's `drop_params` retry loop returns `None` after two 422 responses, which hides the real error

**Branch:** `litellm_command_code_provider`

**Commits**

- `8c6f11bdff` (2026-10-12) `feat(command_code): add Command Code provider`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8`)

`8c6f11bdff`

- `litellm/llms/command_code/__init__.py`, `chat/__init__.py`, `messages/__init__.py`: empty (new)
- `litellm/llms/command_code/common_utils.py`: 1-38 (new)
- `litellm/llms/command_code/chat/transformation.py`: 1-75 (new)
- `litellm/llms/command_code/messages/transformation.py`: 1-51 (new)
- `litellm/__init__.py`: 1551
- `litellm/_lazy_imports_registry.py`: 129, 617
- `litellm/constants.py`: 629, 869
- `litellm/litellm_core_utils/get_llm_provider_logic.py`: 333-335, 746-750
- `litellm/main.py`: 108-113, 2528-2579, 5833-5834
- `litellm/types/utils.py`: 3996
- `litellm/utils.py`: 8080-8083, 8218-8223, 8522-8526
- `provider_endpoints_support.json`: 638-646
- `litellm/provider_endpoints_support_backup.json`: 603-611
- `litellm/proxy/public_endpoints/provider_create_fields.json`: 2022-2049
- `ui/litellm-dashboard/src/components/provider_info_helpers.tsx`: 131, 248
- `tests/test_litellm/llms/command_code/__init__.py`: empty (new)
- `tests/test_litellm/llms/command_code/test_command_code.py`: 1-253 (new)

**Merge notes**

- The provider stays on the shared HTTP handler
- Keep the ZDR normalisation and the rule that a client cannot downgrade the deployment's setting
- A 422 is raised once, without retries
- Claude models route to `/messages`
- Keep every registration listed above. They sit next to patch 6's lines
- This patch has no cost map entries

---

### 8. Vercel AI Gateway `reasoning_effort`

**Status:** in the main patch branch as a cherry-pick of upstream PR #25603, which upstream had not merged at the last upstream merge. Drop this patch as soon as upstream ships the same feature

**What it changes**

- `get_supported_openai_params` of the Vercel AI Gateway chat config advertises `reasoning_effort`
- `map_openai_params` pops `reasoning_effort` and writes `extra_body["reasoning"] = {"effort": ..., "enabled": True}`, the shape the gateway expects. `extra_body` is seeded from whatever the parent class already set instead of being overwritten

**Why**

- Upstream's Vercel AI Gateway config has no reasoning support, so `reasoning_effort` never reached the gateway. This reason is inferred from the PR title and the code

**Branch:** no topic branch. `f9d3395a0b` was cherry-picked onto `crystalvibe28/litellm_internal_staging.patch` on 2026-05-15 from `1e64174fce` on the local branch `pr-25603`

**Commits**

- `f9d3395a0b` (2026-04-12) `feat(vercel_ai_gateway): convert reasoning_effort to Vercel AI Gateway extra_body format` (external author, committed by `CrystalVibe28`)

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ a8b6251ee8`)

`f9d3395a0b`

- `litellm/llms/vercel_ai_gateway/chat/transformation.py`: 31-32, 51, 59-61 (merge `cd1476d14e`: 52, 58)
- `tests/test_litellm/llms/vercel_ai_gateway/chat/test_vercel_ai_gateway_transformation.py`: 101-149

**Merge notes**

- If upstream merges #25603 or an equivalent, take upstream's version and mark this patch as superseded instead of applying both
- `extra_body` merging stays non-destructive, so `providerOptions` and `reasoning` can coexist

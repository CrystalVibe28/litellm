Do not write comments unless they are any of:
- absolutely necessary to explain some very complex business logic (in which case, keep it concise and clear)
- used as an input for tools to read and act on. For example:
  - a lint or type checker suppression like `# mutable-ok` or `# pyright: ignore[reportArgumentType]  # <reason>` when introducing a truly unavoidable violation
- a TODO or FIXME
  - Not great to have those, but if it's unavoidable, make sure to include a strong, concise reason for why it's there or, better yet, link to a GitHub issue for the follow-up work

Explanation: The point of this rule is to keep out AI slop comments. AI writes way too many and way too verbose comments. Code comments are, in a way, a violation of DRY code. You must update logic in two locations to change the code, and "hard to change" is literally the definition of tech debt. We should instead aim to write code that is intuitive and clear, even at a glance, to the reader, being both easy to maintain and high performance

Don't assume that the existing code is correct or the right way of doing things / good coding patterns. In fact, there are a lot of bad coding practices, overly complex code, code smells, etc. If something doesn't look right, speak up. Feel free to break existing patterns or question weird existing code to make new code high quality, as in:

- correct
- secure
- performant
- readable
- easy to maintain/change
- modern

In descending order of importance

When adding new features, add meaningful tests. Don't add tests that don't check anything substantial and is there just to make the code coverage pass. Yes, code coverage is important, but I'd rather have no signal whether the code is working than tests that don't fail when code is broken. The goal is to have tests that would fail before the feature was added/if the code was mutated in a way that breaks the feature and succeed only when the feature is fully working. I should run mutation testing and see > 90% kill rate

Same thing for bug fixes. The tests should make it so that this specific bug can never happen again without failing tests (i.e., regression)

Never test structure or implementation details of code, only function of it. A test should catch a change that breaks behavior by accident. If the only way it can fail is someone deliberately undoing the change, don't write it

A test must only fail when litellm code changes. Never pin facts we don't own (a vendor's price, a third party's field, an upstream default, today's date) as literals or as "X must be absent". Assert the invariant our code guarantees instead, e.g. two rows agree, a value is within range, a field is derived from another. If an outside fact is truly load-bearing, cite its source and date next to the assertion so a reader can tell stale from broken

`tests/unit/` mirrors `litellm/` in a parallel path (see `tests/unit/AGENTS.md`). Name tests `test_<filename>.py`, but always match the existing test file in the directory you touch — many provider dirs use longer descriptive names (e.g. `test_anthropic_chat_transformation.py`) to avoid ambiguity across sibling folders. For bug fixes, extend the existing mapped test file rather than creating a new one. Only create a new test file for a new feature (provider, endpoint, or transformation module) that has no mapped test yet, following that directory's naming convention (or `test_<filename>.py` if you're the first test there). One focused regression test beats many shallow ones

End-to-end tests belong in `tests/e2e/`. A rule about one directory's files, like its harness or which CI runs it, goes in that directory's `AGENTS.md`, never only in a README or here. Read a directory's `AGENTS.md` before editing files in it

When creating PRs, target the repository's current default branch for both internal and external / OSS contributions. Check it with `python3 litellm/scripts/default_branch.py --branch` instead of assuming a branch name or relying on cached `origin/HEAD`

When writing a PR body, treat the comments and imperative instructions inside .github/PULL_REQUEST_TEMPLATE/general.md as rules to follow, not just layout. Agent harnesses may strip HTML comments from copies of that file injected into context, so read .github/PULL_REQUEST_TEMPLATE/general.md from disk before writing a PR body to make sure you see every comment rule. A section you have nothing to put in (Relevant issues, Affected release, Linear ticket, Caveats, QA runbook, and so on) is removed entirely, heading included, never left as an empty title

Same applies for filing bug reports and feature requests, with .github/ISSUE_TEMPLATE/bug_report.yml and .github/ISSUE_TEMPLATE/feature_request.yml, respectively

If you're resolving a linear ticket, in the "## Linear ticket" section of the PR, say "Resolves LIT-1234", replacing "LIT-1234" with the actual ticket id that you're resolving. If you don't have the ticket id, don't make one up or search for it. Just drop the section

Run QA proxies with `python litellm/proxy/proxy_cli.py --config litellm/proxy/dev_config.yaml --num_workers 2 --detailed_debug --reload --use_v2_migration_resolver 2>&1 | tee litellm.log`, and swap its `--config` for a copy of `litellm/proxy/dev_config.yaml` that points both `router_settings` (`redis_host`, `redis_port`) and `general_settings.coordination_redis` (`host`, `port`) at one dedicated Redis instance, with credentials when required, so the workers share router state and spend, budget, and rate-limit counters. Check that two worker PIDs are serving, and use the same worker count and Redis setup for the before and after proof. When the PR is about `--run_gunicorn`, `--run_hypercorn`, or `--run_granian`, which `--reload` does not support, drop `--reload`. When it is about behavior without Redis, drop Redis. When the proxy prints `"workers" flag is ignored when reloading is enabled`, that checkout or its uvicorn reloads only one worker, so drop the two-worker check for it. Say in the proof which part you dropped and why

Simple PRs may skip before/after e2e when the full diff is mechanical and focused checks completely prove it, such as #49030 restoring an existing helper name. Trace affected callers and run relevant tests/static checks at the tip. For a bug fix, establish that the regression catches the original defect. Size alone never qualifies. New behavior, API/provider semantics, auth, billing, persistence, concurrency or uncertain integration risk need live e2e. In Screenshots / Proof of Fix, record `E2E exception at <tip SHA>`, scope, rationale, commands and results. Tests count as proof only for this exception. Reassess changed diffs, retain CI/bot gates, and honor explicit e2e requests (2026-10-28, unnecessary live QA for #49030)

For other PRs, proof must show the end user's real flow before and after, with commands and output against a live proxy and real provider calls where applicable. The body alone must let a reviewer rerun it, with the proxy command, config, env var names and client code exactly as run, and long blocks collapsed in <details>. Pytest alone is insufficient. For UI or interactive coding-tool flows, drive that surface and embed before/after screenshots, with URLs, clicks and input fields a reviewer can reproduce

If you ever write any human-facing text (pull requests, issues, commit messages, discussion posts, github comments, release notes, docs, etc.), always follow these guidelines to sound less AI-y:
- don't use emojis
- don't use "—". Don't use ";" or ":" unless it would be nonsensical not to. Instead, reach for ",", ".", conjunction words, etc. in descending order of preference: vary among them, weighted toward the front of the list, and skip "," where it would cause a comma splice or the sentence is getting long. Overusing any one of them also feels AI-y. A word cap does not penalize you for adding more sentences
- don't use the pattern "It's not X, it's Y", "You're not X, you're Y", etc.
- unless explicitly asked, don't use bulleted or numbered lists unless it would be nonsensical not to. Instead, prefer prose
- don't use →. Instead, prefer not to use arrows, and if need be, use -> instead
- use plain, simple, everyday engineering language: the common phrase engineers actually say over rare compact phrasing, in grammatically complete sentences. When explicitly asked to use bullets or ordered lists and structure legitimately helps the reader, prefer nested bullets (any depth is fine) over dense lines in a flat structure

Don't hesitate to use values in .env to get needed API keys and other secrets, as long as you never add them to conversation history, commit them, or include them in GitHub issues / PRs

Python max line length is 120, not 88

The five lint gates (`litellm/scripts/ruff_strict_gate.py`, `litellm/scripts/type_discipline_gate.py`, `litellm/scripts/test_quality_gate.py`, `litellm/scripts/openapi_docs_gate.py`, `litellm/scripts/type_check_gate.py`) compare each rule's codebase count on your branch against the count at its merge-base with the default branch, and a rule may not grow. There are no budget files to edit or ratchet: when a gate fails, fix the violations the branch introduced or remove at least as many of that rule elsewhere in the tree. The one exception is `reportAny` / `reportExplicitAny`, which share a fixed codebase-wide cap in `ANY_CAPS` in `litellm/scripts/type_check_gate.py` because Any spreads past the lines you touch. A branch may add Anys while the total stays under that cap. Only lower `ANY_CAPS`, and only in its own PR to the default branch, never raise it on a feature branch

`make check` (f.k.a. `make pre-commit`, which still works identically as an alias) saves its complete output to a log file in .git (overwriting previous logs) and prints that path as its first and last output lines. To inspect a run, read or grep that log instead of re-running the multi-minute checks just to see a different slice

`make check`, `make lint`, `litellm/scripts/pre_commit_lint.sh`, and the standalone lint gates (`litellm/scripts/ruff_strict_gate.py`, `litellm/scripts/type_discipline_gate.py`, `litellm/scripts/type_check_gate.py`) each hold one of 2 machine-wide slots, so when other sessions or worktrees on the same box are already running heavy work, yours prints "all N machine-wide slots are busy" followed by "queueing" and then stays quiet until a slot frees. Give the command a long timeout and let it wait rather than killing it, retrying it, or assuming it hung. Don't change the # of machine-wide slots or make it unlimited by setting `LITELLM_GATE_SLOTS=0`

If you're trying to create a new function that relies on untyped stuff, instead of adding more Any's and pushing `reportAny` / `reportExplicitAny` closer to their cap in `ANY_CAPS`, just validate it in the caller with Pydantic (a model or `TypeAdapter` that returns the typed thing or raises will do) and then pass the now typed variable in

If you get an LIT001 fail, refactor the code to follow functional programming best practices rather than introducing mutable data structures. For example, build values in one shot with comprehensions or generators wrapped in `tuple()` / `MappingProxyType()` / `frozenset()` instead of seeding an empty `list`/`dict`/`set` and mutating it over time. Ideally, `# mutable-ok` is never used. Reach for it only as a genuine last resort when an immutable rewrite is truly impossible, and always pair it with a real reason

Every lint or type suppression must name the exact rule inside brackets and carry a reason comment, e.g. `# pyright: ignore[reportArgumentType]  # stubs lack async overload` or `# noqa: TID251  # <reason>`. `# type: ignore` is banned (LIT009): `[tool.pyright]` in pyproject.toml sets `enableTypeIgnoreComments` to false, so it silently does nothing

Commit and push your work when you're done without asking

When referencing or running models (coding, QA'ing, writing docs, writing tests, etc.), use the latest model in that model family unless otherwise specified. Treat your training knowledge, memories, configs, and tests as stale, and determine the family's latest with model_prices_and_context_window.json or the web

Always pull before starting any work. The checkout or worktree may be sitting on a stale branch

Internal contributors branch a new PR off the repository's current default branch, with a branch name prefixed with litellm_

Do not add `Co-Authored-By: Claude` or any Claude attribution to commit messages. Never use a `claude/` prefix or put a `/` in a branch name. Do not add "Generated with Claude Code" (or any similar attribution) to PR descriptions or comments. Do not create a new PR/branch off the existing PR to fix/add something that is related and could've just been committed directly to the existing PR's branch

When working on a PR, keep the PR description in sync with new commits being made

All GitHub comments must be human-readable and 15-25 words max

Monkeypatching attributes of a class to do testing is an anti-pattern. Prefer dependency-injecting things into classes. That way, at unit test time, you can pass a mocked dependency in

Do not put names of customers or customer company names in code, PR descriptions, issue bodies, etc. This means never mention literally any company name. Especially if you're about to say a sentence mentioning that the reason the PR exists was a feature/model/bug fix/etc. requested by a company. That's the indication that you should replace that company name with "the customer". e.g. not "Model request from Acme (Pylon #1234)" but "Model request from a customer (Pylon #1234)". This is because the codebase is public. The only exception is for publicly known providers or vendors such as OpenAI, Anthropic, AWS Bedrock, etc. only IF we're adding support for that provider/vendor in general and NOT if that PR or whatnot was a request by one of them, and they're actually one of our customers.

CI supply-chain safety: Never pipe a remote script into a shell (`curl ... | bash`, `wget ... | sh`). Download the artifact to a file, verify its SHA-256 checksum, then install. Pin every external tool to a specific version with a full URL (not `latest` or `stable`). Verify checksums for all downloaded binaries, using the provider's official `.sha256` / `.sha256sum` sidecar when available. These rules apply to every download in CI

Prisma migrations apply synchronously at proxy boot, before it serves traffic, so a migration must only change schema, never rewrite rows. No `UPDATE`, `DELETE` or `MERGE`, and no `INSERT ... SELECT`: on a spend-log-sized table any of those is minutes of downtime plus a doubled heap that plain autovacuum won't give back. `tests/code_coverage_tests/check_migrations_no_data_rewrites.py` enforces this. When a rewrite is genuinely bounded and has to ship inside the migration, mark the statement `-- data-migration-ok: <what bounds it>`

Follow these coding conventions for new/updated code (a three-line fix in a legacy file shouldn't trigger huge drive-by refactors):

- Composition over inheritance
- Never-nester: early returns over deep nesting
- Don't throw. Model failures as values (One function (e.g., raise_public) maps error union to existing public exception contracts via exhaustive match + assert_never)
- No mutation. Don't reassign variables, global or local. Instead of mutable lists and dicts, prefer tuples, frozen dataclasses (with slots=True), `MappingProxyType`, etc.
  - Annotate every variable with `: Final` (LIT010). Unpacking and walrus targets cannot carry the annotation, so they are implicitly final. Don't rebind them. Never rebind or mutate function parameters (LIT011). `self`/`cls` attribute stores are the exception. If rebinding or in-place mutation is truly unavoidable, suppress with `# rebind-ok: <reason>`
  - Qualify every TypedDict field with `ReadOnly[...]` (LIT012), which nests freely with `Required` / `NotRequired` / `Annotated` in any order. If making the key writable is truly unavoidable, suppress with `# writable-ok: <reason>`
  - Comprehensions take at most one `for` clause and one `if` clause (LIT014). Split stacked clauses into a helper generator, a named intermediate, or a plain loop. Suppress with `# comprehension-ok: <reason>` only when unavoidable
  - Every pydantic model must be frozen (LIT015), set via `model_config = ConfigDict(frozen=True)`, a dict-literal `model_config`, an inner `class Config`, or the class keywords. Subclasses inherit it unless they override it. Replace in-place field writes with `model_copy(update=...)`. If making the model mutable is truly unavoidable, suppress with `# frozen-ok: <reason>` on the `class` line
- Use dependency injection
- Fully typed. No `Any` or coarse types like `dict[str, Any]` or just `dict`. Every function parameter must be strongly typed
- Use tagged unions + match
- No monster files or god objects
- No file sprawl: deliberate file and folder structure
- Standard over hand-rolled: use the official SDK or a library where one exists. Where none does, follow industry standards instead of inventing local conventions
- API-fragmentation-aware: when logic must branch on which API surface produced or consumes data (e.g. chat completions vs Anthropic Messages vs Responses API shapes), proactively look for an existing shared helper (e.g. `litellm_core_utils/prompt_templates/factory.py`) before writing per-surface parsing in the new module. If none exists, add one there instead of duplicating the same format-detection logic in every new guardrail/integration
- Current default for new model names: logic that picks behavior from a model-name table (tokenizer, message framing, supported params) gives a provider's model the table does not list yet that provider's current behavior, never its oldest, since providers ship names faster than any table is updated

Follow conventional commits for commit names and PR titles

## Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs**

Before implementing:
- State your assumptions explicitly. If uncertain, ask
- If multiple interpretations exist, present them. Don't pick silently
- If a simpler approach exists, say so. Push back when warranted
- If something is unclear, stop. Name what's confusing. Ask

## Simplicity First

**Minimum code that solves the problem. Nothing speculative**

- No features beyond what was asked
- No abstractions for single-use code
- No "flexibility" or "configurability" that wasn't requested
- No error handling for impossible scenarios
- If you write 200 lines and it could be 50, rewrite it

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify

Before requesting maintainer review, verify the current PR tip passes required CI and code coverage and has acceptable reviews from the review bots on the PR, such as Veria and Bugbot. Inspect warnings and findings, fix actionable issues, and rerun the affected checks and reviewers after changes. Record evidence for any false positive or unavailable review. Never treat a pending or missing bot result as a pass. Do not lower coverage thresholds or raise `ANY_CAPS` to satisfy a check

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
| `main` | Local mirror of `upstream/main`, which it tracks, and the merge source for upstream merges. Never commit to it. Only fast-forward it from `upstream` |
| `litellm_internal_staging` | Upstream's former default branch and the merge source up to `cd1476d14e` (2026-09-11). Upstream has deleted it. Only the stale `origin/litellm_internal_staging` (2026-06-01) remains, and there is no local branch. Do not merge from it. The main patch branch keeps the name for continuity |
| `dogoin/v1.83.14-stable.patch.3-pr25603`, `dogoin/v1.83.14-stable.patch.3-pr25603-codex-image-bridge` | **Deprecated. Do not commit to them or branch from them.** Older patch branches on top of the release tag `v1.83.14-stable.patch.3`, superseded by the main patch branch |
| `pr-25603` | Local copy of upstream PR #25603, the source of patch 8. Read-only |

New branches follow the rule earlier in this file: prefix `litellm_`, no `/` in the name

### Commit conventions

- **Language:** English, for every commit message in this repository. This overrides any general preference for another language
- **Format:** [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <imperative summary in lower case>`. The scope is optional. A body is allowed when the reason is not obvious from the subject
  - Types in use: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
  - Scopes in use: `chatgpt`, `proxy`, `router`, `auth`, `opencode_go`, `command_code`, `vercel_ai_gateway`, `agents`
- **Merge commits:**
  - Upstream: `chore: merge upstream main`. Merges made before upstream's default branch changed used `chore: merge upstream litellm_internal_staging`
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
2. Confirm the merge source, then update it
   - The merge source is upstream's default branch, `main`. Verified with `gh` on 2026-11-14: the default branch of BerriAI/litellm is `main`, `litellm_internal_staging` no longer exists there (HTTP 404), and `upstream/main` contains the last merged upstream commit `e907e5ee9b`
   - Check it again every time: `gh repo view BerriAI/litellm --json defaultBranchRef -q .defaultBranchRef.name`. If the answer is not `main`, do not guess. Report the new default branch and whether it contains the reference commit of the last upstream merge, and wait for the user to name the merge source
   - `git fetch upstream`, then fast-forward the local `main`, which tracks `upstream/main`: `git fetch upstream main:main` from another branch, or `git merge --ff-only upstream/main` on `main`. If `main` cannot be fast-forwarded, it has local commits it should not have: stop and report
3. Switch to the local branch that tracks `crystalvibe28/litellm_internal_staging.patch`. If the branch name or its tracking relationship is unclear, report the current branch and remote state before going further
4. Look at the earlier upstream merge commits (`git log --first-parent --merges --grep="merge upstream"`) and reuse their message format with the current source branch: `chore: merge upstream main`
5. Merge with `git merge --no-ff main`. No rebase, no squash
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
   - `model_prices_and_context_window.json` and `litellm/model_prices_and_context_window_backup.json`: take upstream's file and re-insert the fork's only entry, `chatgpt/gpt-image-2` (patch 1), into both files, because upstream's `test_model_prices_backup_is_synchronized` requires them to be identical
   - Upstream owns the `opencode_go` provider and ChatGPT image generation. Never re-add the fork's `litellm/llms/opencode_go/` package or re-register `ChatGPTImageGenerationConfig` for generation (patches 1 and 6)
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

**Format of a patch section** (all in English, following the prose rules earlier in this file)

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
- Patches merged into the main patch branch are measured at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7`, the merge of the last merged upstream commit `ca4c6c0a6d` (2026-11-14), which is on `upstream/main`. Commits after `adaf3181f7` only touch this file
- Patches that are **not merged** are measured at their own branch tip, which sits on an older upstream base, so their numbers do not match the main patch branch
- "merge `<hash>`" marks lines of the same patch that were re-resolved during an upstream merge and are now attributed to that merge commit
- "new" marks a file that does not exist upstream
- Upstream moved `tests/test_litellm/` to `tests/unit/` and `ui/` to `litellm/ui/` before `ca4c6c0a6d`. Every path below uses the new location
- To measure one file: `git blame -s -l <ref> -- <path>`, then collect the line numbers attributed to the commit, restricted to the lines `git diff -U0 <upstream commit> <ref> -- <path>` reports as added. Blame sometimes credits a fork line to an unrelated commit that holds identical text. Such lines are listed under the patch they belong to
- To regenerate the commit list: `git log --branches --no-merges --author=CrystalVibe28 --format="%h %ad %s" --date=short`

### Overview

| # | Patch | Branch | In main patch branch | Commits |
| - | ----- | ------ | -------------------- | ------- |
| 1 | ChatGPT image edit bridge (generation superseded by upstream) | `codex/chatgpt-image-bridge` | Image edit only, without `db3eda4bb9` | `ffd11fdfa3`, `49c53492e6`, `f3a65bd26b`, `f97780a636`, `4c653a5749`, `4f42ead4ca`, `4b168229b5`, `1f84f188e7`, `e59ef32ddd`, `bc3f09f362`, `765cc80adf`, `efdc5a22cd`, `405a41d302`, `ed72e3200b`, `f61c2b2b0a`, `e9094c1907`, `db3eda4bb9` (prototype: `b817d9fe75`) |
| 2 | ChatGPT / Codex proxy hardening | `litellm_chatgpt_codex_proxy` | Yes | `d95fa1c143`, `9226119a6c`, `afbecb53ce`, `cc305c99c5` |
| 3 | Internal user header budgets | `litellm_openwebui_user_header_budget_investigation` | Yes | `8ad82302e3`, `6bda0f7b9e`, `16bf658dcb` |
| 4 | Forward client headers by selected deployment | `litellm_forward_headers_by_deployment` | Yes | `a4c0d19106` |
| 5 | Proxy startup fix for an undefined `Optional` | `crystalvibe28/litellm_internal_staging.patch` | Yes | `f3c816c9dc` |
| 6 | OpenCode Go provider | `litellm_opencode_go_provider` | Superseded by upstream. Four behaviours ported onto upstream's provider | `74eba73f9a`, `86a8f2ca49` |
| 7 | Command Code provider | `litellm_command_code_provider` | Yes | `8c6f11bdff` |
| 8 | Vercel AI Gateway `reasoning_effort` | `crystalvibe28/litellm_internal_staging.patch` (cherry-pick) | Yes | `f9d3395a0b` |

---

### 1. ChatGPT image generation and image edit bridge

**Status:** partly superseded by upstream in merge `adaf3181f7`. Upstream now serves `chatgpt/` image generation itself (PR #48522), so generation follows upstream's path and the fork keeps only the image edit bridge. `db3eda4bb9`, the tip of `codex/chatgpt-image-bridge`, has never been merged, so image edits still accept only `size` and silently drop every other param, whatever `drop_params` says

**What it changes**

- Image generation is upstream's: `litellm/images/main.py` sends `chatgpt/` requests to the Codex `images/generations` endpoint through the OpenAI-compatible path (`_chatgpt_image_params`, `_chatgpt_image_headers`) and forwards client-supplied OAuth credentials. `CHATGPT` is no longer in the `llm_http_handler` provider list and `get_provider_image_generation_config` no longer returns the fork's config
- `ChatGPTImageEditConfig` (`image_edit/transformation.py`) is the surviving feature. It turns an Images Edits request into a Responses request that uses the `image_generation` tool with an internal responses model, and posts it to the Codex `/responses` endpoint with the authenticator's token, account id and session id. Input images are sent as base64 `input_image` items in a JSON body, and `use_multipart_form_data()` returns `False`
- `ChatGPTImageGenerationConfig` (`image_generation/generation_transformation.py`) stays as the request builder and response transformer that the edit config delegates to. It is still exported from `litellm` but nothing routes generation requests to it
- `image_generation/response_parsing.py` reads the upstream SSE stream or JSON, rebuilds an `ImageResponse` with `ImageObject`s and `ImageUsage`, dedupes images and keeps the upstream error status
- Wiring: the `CHATGPT` branch of `get_provider_image_edit_config` in `litellm/utils.py`, lazy exports in `litellm/__init__.py` and `_lazy_imports_registry.py`, the `partial_images` and `stream` literals in `litellm/types/llms/openai.py`, and a `chatgpt/gpt-image-2` entry in both cost map files
- `db3eda4bb9` (not merged): image edit supports the same params as generation (`size`, `output_format`), and `map_openai_params` honours `drop_params`, raising `ValueError` for an unsupported param unless `drop_params=True`

**Why**

- Upstream could not serve `/v1/images/generations` or `/v1/images/edits` through the `chatgpt/` provider (ChatGPT subscription over OAuth) when the patch was written. It has since added generation but still has no image edit, which the Codex backend only exposes as a tool on the Responses API
- The fork wants Images API clients to use `gpt-image-2` on a ChatGPT plan, with correct usage and cost accounting. This reason is inferred from the commits and the code
- The owner chose upstream's generation path during the 2026-11-14 upstream merge, without a live comparison against the fork's bridge

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

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7` unless stated)

`ffd11fdfa3`

- `litellm/__init__.py`: 2239-2240
- `litellm/llms/chatgpt/image_generation/__init__.py`: 2 (new, shared with `ed72e3200b`)
- `litellm/types/llms/openai.py`: 1272, 1276

`1f84f188e7`

- `litellm/__init__.py`: 2236

`ed72e3200b`

- `litellm/__init__.py`: 2235, 2237-2238
- `litellm/llms/chatgpt/image_generation/__init__.py`: 1, 3 (new)
- `litellm/llms/chatgpt/image_generation/generation_transformation.py`: 1-307 (new). The whole file belongs to this patch except 21, 24, 55-56 and 111-115, which belong to patch 2. Merge `cd1476d14e` re-resolved about 30 single lines for upstream's lint style
- `litellm/llms/chatgpt/image_generation/response_parsing.py`: 1-276 (new), except the lines of `f61c2b2b0a` and `e9094c1907`. Merge `cd1476d14e` re-resolved about 25 single lines
- `litellm/llms/chatgpt/image_edit/__init__.py`: 1-3 (new)
- `litellm/llms/chatgpt/image_edit/transformation.py`: 1-169 (new; merge `cd1476d14e`: 4, 32, 40, 42, 48-50, 65, 82-84, 87, 89, 121, 126, 164)
- `tests/unit/llms/chatgpt/chatgpt_image_test_utils.py`: 1-10 (new)
- `tests/unit/llms/chatgpt/image_edit/__init__.py`, `tests/unit/llms/chatgpt/image_generation/__init__.py`: empty (new, added in merge `adaf3181f7`)
- `tests/unit/llms/chatgpt/image_edit/test_transformation.py`: 1-189 (new; merge `adaf3181f7`: 11)
- `tests/unit/llms/chatgpt/image_generation/test_request_transformation.py`: 1-383 (new), except 120, 174-179, 188, 229 and 335, which belong to patch 2
- `tests/unit/llms/chatgpt/image_generation/test_response_parsing.py`: 1-131, 191-270 (new; merge `adaf3181f7`: 7)
- `tests/unit/llms/chatgpt/image_generation/test_usage.py`: 1-30, 79-247 (new; merge `adaf3181f7`: 6)

`f61c2b2b0a`

- `litellm/llms/chatgpt/image_generation/response_parsing.py`: 88-103, 106-107
- `tests/unit/llms/chatgpt/image_generation/test_usage.py`: 31-78

`e9094c1907`

- `litellm/llms/chatgpt/image_generation/response_parsing.py`: 165, 167, 169-171, 173-187, 195-198
- `tests/unit/llms/chatgpt/image_generation/test_response_parsing.py`: 132-190

Merge `adaf3181f7`

- `litellm/_lazy_imports_registry.py`: 428-432, the two entries in upstream's new `LITELLM_ATTRIBUTES` mapping
- `litellm/utils.py`: 11357-11360, the `CHATGPT` branch of `get_provider_image_edit_config`
- `model_prices_and_context_window.json`, `litellm/model_prices_and_context_window_backup.json`: 34911-34919, the `chatgpt/gpt-image-2` entry (`e59ef32ddd`, `405a41d302`)

`49c53492e6`, `f3a65bd26b`, `f97780a636`, `4c653a5749`, `4f42ead4ca`, `4b168229b5`, `bc3f09f362`, `765cc80adf`, `efdc5a22cd`

- No surviving lines. Their code was moved into the split modules by `ed72e3200b` or re-placed by merge `adaf3181f7`

Dropped in merge `adaf3181f7`

- The `CHATGPT` entry in the `llm_http_handler` provider list of `litellm/images/main.py`, the `CHATGPT` branch of `get_provider_image_generation_config` in `litellm/utils.py`, and `test_chatgpt_image_generation_config_registered`

`db3eda4bb9` (at `codex/chatgpt-image-bridge @ db3eda4bb9`, not merged)

- `litellm/llms/chatgpt/image_edit/transformation.py`: 33-36, 45-57
- `tests/test_litellm/llms/chatgpt/image_edit/test_transformation.py`: 120-169

**Merge notes**

- Generation is upstream's. Do not put `CHATGPT` back into the `llm_http_handler` provider list of `litellm/images/main.py` and do not re-register the generation config, or upstream's `tests/unit/images/test_main.py` cases for client credential forwarding fail
- Keep the `CHATGPT` branch in `get_provider_image_edit_config`, the lazy exports, and the `partial_images` / `stream` literals
- If upstream adds `chatgpt/` image edit, take upstream's version and drop the rest of this patch
- Image edit stays JSON, never multipart
- The OAuth token is only ever sent to the authenticator's base URL, never to a caller-supplied `api_base` (`4b168229b5`)
- Usage and error parsing stay non-recursive and keep the real upstream status code
- The `chatgpt/gpt-image-2` entry must be in both cost map files and identical in both
- The topic branch sits on a much older upstream base than the main patch branch. Merging `db3eda4bb9` will conflict with the lint rewrites of `cd1476d14e` in `image_edit/transformation.py`. Re-apply the change on the current file instead of taking the branch's version

---

### 2. ChatGPT / Codex proxy hardening

**Status:** in the main patch branch. Merge `adaf3181f7` rebuilt it on upstream's reworked `chatgpt` provider (per-deployment auth files, client-supplied OAuth credentials, implicit device-code login), raised the pinned Codex version to `0.166.0` and added a guard to the 401 retry

**What it changes**

- `d95fa1c143`: the outbound identity is a pinned Codex CLI header set, `CODEX_CLIENT_VERSION = "0.166.0"` since merge `adaf3181f7`. `merge_chatgpt_headers` in `common_utils.py` merges headers case-insensitively, normalises `session_id` / `thread_id` to `session-id` / `thread-id`, strips `Forwarded`, `Via`, `X-Forwarded-*`, `X-LiteLLM-*`, `X-Stainless-*` and `X-API-Key`, and forces the resolved `Authorization` and `ChatGPT-Account-Id`. `finalize_chatgpt_request` is the `sign_request` hook for the chat, responses and image edit configs. The shared Responses handlers validate the merged headers for the providers in `_PROVIDERS_VALIDATING_MERGED_RESPONSES_HEADERS`
- `9226119a6c`: `normalize_chatgpt_responses_request` replaces the hardcoded Codex system prompt. Caller `instructions` are preserved, including an empty string, with the `CHATGPT_DEFAULT_INSTRUCTIONS` env var or `""` as the fallback. Fields are whitelisted (`text`, `parallel_tool_calls`, `prompt_cache_key`, `client_metadata` and upstream's `max_output_tokens` are allowed, and `service_tier` is mapped through `CHATGPT_SERVICE_TIERS`), and `stream=true`, `store=false` and `include: reasoning.encrypted_content` are always forced. Since merge `adaf3181f7` the normalisation runs in `ChatGPTResponsesAPIConfig.transform_responses_api_request` and in upstream's `transform_extra_body` hook, and upstream's own SSE aggregation serves non-streaming callers. String input is passed through as upstream does and system items become developer items
- `afbecb53ce`: `Authenticator` refresh is guarded by an `RLock` plus a cross-process file lock (`msvcrt` or `fcntl`) with a 60 second timeout, auth file writes are atomic (temp file, `fsync`, `os.replace`), and secrets stay out of error messages. Since merge `adaf3181f7` a missing or unrefreshable login follows upstream: `get_access_token` raises early when login cannot block, otherwise it runs upstream's device-code login with its cooldown inside the fork's lock, and `_account_id` persists a derived account id under the lock after re-reading the file. `HTTPHandler` and `AsyncHTTPHandler` refresh the token and resend once on a 401 when the body is replayable and `Authenticator.issued_access_token` confirms the rejected token is the gateway's own, so a client-supplied token is never replaced by the gateway account's. The Responses streaming iterators close their connections on completion or cancel. Provider lookup for `chatgpt/` models runs in a thread because auth does blocking I/O
- `cc305c99c5`: the image `validate_environment` forces the OAuth `Authorization` and `ChatGPT-Account-Id`, so proxy callers cannot override them. It now only serves image edits (patch 1)

**Why**

- Upstream's `chatgpt/` provider identifies itself with a LiteLLM-derived user agent, forwards proxy and SDK headers to the backend, injects a long hardcoded Codex system prompt into every Responses call, drops fields the backend supports, and refreshes OAuth tokens without any locking
- The fork needs LiteLLM to look like a faithful Codex client and to be safe for concurrent, long-running proxy use: no injected prompt, no leaked caller headers, no refresh races, no leaked connections. This reason is inferred from the commits and the code
- `0.166.0` is the Codex version upstream tracks in its Codex model catalog. Upstream's provider does not pin a Codex version at all. The owner asked to "use upstream's" version during the 2026-11-14 merge and this was read as raising the pin, after checking that the `rust-v0.166.0` user agent format is unchanged
- The 401 retry guard was added because upstream now forwards client-supplied ChatGPT credentials, and the unguarded retry would have resent such a request with the gateway account's token

**Branch:** `litellm_chatgpt_codex_proxy`

**Commits**

- `d95fa1c143` (2026-09-12) `fix(chatgpt): align outbound Codex identity and normalize proxy headers`
- `9226119a6c` (2026-09-12) `fix(chatgpt): preserve proxy request semantics and aggregate non-streaming responses`
- `afbecb53ce` (2026-09-12) `fix(chatgpt): harden OAuth refresh and streaming connection lifecycle`
- `cc305c99c5` (2026-09-12) `fix(chatgpt): preserve OAuth identity for image proxy requests`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7`)

`d95fa1c143`

- `litellm/llms/chatgpt/README.md`: 1-2, 4-7 (new)
- `litellm/llms/chatgpt/chat/transformation.py`: 15, 19, 27, 119-123
- `litellm/llms/chatgpt/common_utils.py`: 47, 152, 178, 293, 300, 302-309, 311-319, 321-322
- `litellm/llms/chatgpt/image_generation/generation_transformation.py`: 21, 24, 56
- `litellm/llms/chatgpt/responses/transformation.py`: 36, 39, 60, 103-104, 106-107
- `tests/unit/llms/chatgpt/image_generation/test_request_transformation.py`: 120, 188, 229, 335
- `tests/unit/llms/chatgpt/responses/test_chatgpt_responses_transformation.py`: 9, 28, 113-114, 116-125, 128-134, 143-163, 165, 174-182, 189, 349

`9226119a6c`

- `litellm/llms/chatgpt/README.md`: 8-11
- `litellm/llms/chatgpt/common_utils.py`: 294-299, 301, 324-338, 340-344, 349-350, 355-361
- `litellm/llms/chatgpt/responses/transformation.py`: 40, 124
- `tests/unit/llms/chatgpt/responses/test_chatgpt_responses_transformation.py`: 29, 42-58, 60-112, 126-127, 135-136, 138-142, 164, 166-173, 183-188, 370

`afbecb53ce`

- `litellm/llms/chatgpt/README.md`: 12, 14-17
- `litellm/llms/chatgpt/authenticator.py`: 3-4, 6-7, 9, 47, 91, 103-107, 109-111, 126, 153-168, 170-202, 238-239, 245-253, 255, 308, 310, 312, 319, 365, 367, 369, 400, 402, 404, 411, 440, 442, 444, 450
- `litellm/llms/chatgpt/chat/transformation.py`: 26
- `litellm/llms/chatgpt/common_utils.py`: 48, 310, 320, 345-346, 352-354
- `litellm/llms/chatgpt/image_generation/generation_transformation.py`: 55
- `litellm/llms/chatgpt/responses/transformation.py`: 59
- `litellm/llms/custom_httpx/http_handler.py`: 70-77, 79-82, 87-101, 1092-1098, 1903-1909
- `litellm/responses/main.py`: 993
- `litellm/responses/streaming_iterator.py`: 29, 1278-1279, 1281-1283, 1285, 1287, 1340-1345, 1386, 1388, 1391-1392, 1438-1440
- `tests/unit/llms/chatgpt/responses/test_chatgpt_responses_transformation.py`: 59, 137

`cc305c99c5`

- `litellm/llms/chatgpt/image_generation/generation_transformation.py`: 111-115
- `tests/unit/llms/chatgpt/image_generation/test_request_transformation.py`: 174-179

Merge `adaf3181f7`

- `litellm/llms/chatgpt/README.md`: 3, 13
- `litellm/llms/chatgpt/authenticator.py`: 19, 90, 108, 112-125, 137-138, 140, 150-152, 169, 222-225, 296, 329, 379, 422, 459
- `litellm/llms/chatgpt/common_utils.py`: 46, 49, 339, 347-348, 351
- `litellm/llms/chatgpt/responses/transformation.py`: 105, 119, 126-133
- `litellm/llms/custom_httpx/http_handler.py`: 78, 83-86, 1086-1091, 1901-1902
- `litellm/llms/custom_httpx/llm_http_handler.py`: 333, 3074, 3080-3084, 3287, 3293-3297 (shared with patch 6)
- `litellm/main.py`: 907-908, 919-921
- `litellm/responses/main.py`: 984-985, 994-995
- `litellm/responses/streaming_iterator.py`: 1280, 1286, 1387
- `tests/unit/llms/chatgpt/responses/test_chatgpt_responses_transformation.py`: 115, 830
- `tests/unit/llms/chatgpt/test_chatgpt_authenticator.py`: 2, 4-7, 12, 14, 21, 28-29, 44-247, 249, 261-264, 266-300, 382
- `tests/unit/responses/test_responses_streaming_iterator.py`: 12, 27, 32-115

**Merge notes**

- Keep the merged-header validation for the providers in `_PROVIDERS_VALIDATING_MERGED_RESPONSES_HEADERS` in both the sync and async Responses paths of `llm_http_handler.py`. The rest of that section is upstream's: normalisation lives in the provider config (`transform_responses_api_request`, `transform_extra_body`), not in the shared handler
- Keep the 401 refresh and retry (`_can_refresh_chatgpt`, `_chatgpt_retry_request`) in `HTTPHandler` and `AsyncHTTPHandler`, including the `issued_access_token` guard
- Keep `close` / `aclose` and the `finished` guards in `litellm/responses/streaming_iterator.py`. They only close a real `httpx.Response`, and the early exit still awaits pending logging
- Keep the `asyncio.to_thread` offloading for `chatgpt/` models in `litellm/main.py` and `litellm/responses/main.py`
- Keep `sign_request` on the chat, responses and image configs. The resolved identity headers always win over caller headers. Upstream's client-supplied credential branches stay intact
- Login follows upstream's behaviour, always inside the fork's refresh lock. Do not bring back the fork's removed `login()` method
- Never re-add a default system prompt
- `litellm/llms/chatgpt/README.md` documents these rules and must stay in sync with the code
- The pinned Codex CLI version (`0.166.0`) is a constant the fork maintains by hand. Upstream changes to the user agent must not replace it
- `test_refresh_lock_excludes_another_process` spawns a subprocess and fails on Windows under the environment stripping of `tests/unit/conftest.py`. The lock itself was verified with a standalone script

---

### 3. Internal user header budgets

**What it changes**

- `8ad82302e3`: `_apply_internal_user_header_mapping_for_auth` in `user_api_key_auth.py` runs at the start of `run_centralized_common_checks` (upstream renamed it from `_run_centralized_common_checks` and kept an alias), before the user and budget lookups, so the header-mapped internal user (and not the owner of the shared key) is the identity whose budget is checked. It reuses the existing `LiteLLMProxyRequestSetup.add_internal_user_from_user_mapping`
- `6bda0f7b9e`: admin keys (`PROXY_ADMIN`, `PROXY_ADMIN_VIEW_ONLY`) are remapped too, but only on LLM routes. The helper returns whether the `user_id` changed, and when it did, the forced admin `user_object` shortcut is skipped so the mapped user's budget applies
- `16bf658dcb`: the resolved `end_user_id` is written onto the auth object, and that object is passed to the auth exception handler, so budget-exceeded errors and failure hooks keep the mapped user context. Since merge `adaf3181f7` the write-back happens when the key has an end-user budget, which is upstream's condition, or when the header mapping was applied

**Why**

- Open WebUI uses one shared key, often an admin key, for all of its users and sends the real end user in a header. Upstream maps that header to an internal user only after the budget checks, so per-user budgets were never enforced. This reason is inferred from the branch name, the commits and the code

**Branch:** `litellm_openwebui_user_header_budget_investigation`

**Commits**

- `8ad82302e3` (2026-06-02) `fix(proxy): enforce internal user header budgets`
- `6bda0f7b9e` (2026-06-02) `fix(proxy): enforce mapped internal user budgets for admin keys`
- `16bf658dcb` (2026-06-02) `fix(proxy): preserve mapped user context in budget errors`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7`)

`8ad82302e3`

- `litellm/proxy/auth/user_api_key_auth.py`: 3971-3973, 3975-3976, 4371-4373, 4377-4379, 4384-4387, 4389, 4391-4392 (merge `90f9c09983`: 4161, 4390; merge `cd1476d14e`: 3970, 4383; merge `adaf3181f7`: 3995, 4388; line 4374 belongs to patch 5)

`6bda0f7b9e`

- `litellm/proxy/auth/user_api_key_auth.py`: 3974, 4375-4376, 4380-4382

`16bf658dcb`

- `tests/unit/proxy/auth/test_auth_exception_handler.py`: 457-481, 483-490, 492-494, 497-499, 501-502, 536, 538 (merge `90f9c09983`: 482, 491, 495-496, 500)
- `litellm/proxy/auth/user_api_key_auth.py`: no surviving lines of its own. The write-back is line 3995, attributed to merge `adaf3181f7`
- `litellm/proxy/auth/auth_exception_handler.py`: no surviving lines. The optional `user_api_key_auth_obj` parameter this commit added is now identical to upstream

All three commits

- `tests/unit/proxy/auth/test_user_api_key_auth_request_flow.py`: 5053-5376, attributed to merge `adaf3181f7`, which moved the patch's five tests into the file upstream split out of `test_user_api_key_auth.py`

**Merge notes**

- The mapping must run before the user, team and budget checks in `run_centralized_common_checks`
- Admin keys are never remapped on non-LLM routes
- The admin `user_object` override stays conditional on `not mapped_internal_user_for_auth`
- The `end_user_id` write-back keeps both conditions: upstream's key end-user budget and the fork's applied header mapping
- The exception handler must still receive the mutated auth object
- `run_centralized_common_checks` is a hot upstream function, and upstream merges have already re-resolved this patch three times

---

### 4. Forward client headers by selected deployment

**What it changes**

- Pre-call (`litellm_pre_call_utils.py`) stores a frozen `ModelGroupHeaderForwarding` (allowed models, filtered client headers, team id) under `MODEL_GROUP_HEADERS_KEY` in the request data, instead of deciding on the spot
- The router replaces it with a copy carrying `deployment_model_name` once a deployment is selected. Since merge `adaf3181f7` `litellm/router.py` is upstream's thin facade and the stamping lives in `update_kwargs_with_deployment` (`litellm/router_rust/invoke/shaping.py`) and in `alist_batches` (`litellm/router_rust/invoke/endpoints.py`)
- The sync and async `client()` wrappers in `litellm/utils.py` call `apply_model_group_headers` (`get_provider_specific_headers.py`). It re-runs the proxy's `_check_model_access_helper` (wildcard and access group matching) against the selected model, merges the forwarded headers case-insensitively on a match, and removes the internal key
- `MODEL_GROUP_HEADERS_KEY` is added to `_UNTRUSTED_ROOT_CONTROL_FIELDS` and `_TRANSPORT_ONLY_CREDENTIAL_KEYS`, so clients cannot spoof it and it is never logged

**Why**

- Upstream decides `forward_client_headers_to_llm_api` once, by matching the requested model group name. That is wrong for fallbacks, wildcards and aliases, where the deployment the router finally picks has a different model name than the one the client asked for. This reason is inferred from the commit and the code

**Branch:** `litellm_forward_headers_by_deployment`

**Commits**

- `a4c0d19106` (2026-09-12) `fix(router): forward client headers based on the selected deployment model`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7`)

`a4c0d19106`

- `litellm/litellm_core_utils/get_provider_specific_headers.py`: 2-3, 13-66
- `litellm/proxy/litellm_pre_call_utils.py`: 65-68, 129-131, 442, 1905-1921
- `litellm/utils.py`: 122, 2132-2134, 2414-2416
- `tests/unit/litellm_core_utils/test_provider_specific_headers.py`: 1-3, 6, 8-9, 11, 14-17, 20-25, 27-198 (merge `adaf3181f7`: 18-19, 26)
- `tests/unit/proxy/test_litellm_pre_call_utils.py`: 10157-10190

Merge `adaf3181f7`

- `litellm/router_rust/invoke/shaping.py`: 34, 429-431
- `litellm/router_rust/invoke/endpoints.py`: 33, 2304-2310, 2312-2314
- `tests/unit/test_router/test_router.py`: 20517-20612

**Merge notes**

- `MODEL_GROUP_HEADERS_KEY` must be removed before the provider call and must never reach logs or the request body
- The key stays in `_UNTRUSTED_ROOT_CONTROL_FIELDS` and `_TRANSPORT_ONLY_CREDENTIAL_KEYS`
- The router must stamp `deployment_model_name` on every path that dispatches to a deployment. `litellm/router.py` has no fork lines any more. Check `litellm/router_rust/invoke/` for new upstream dispatch paths that bypass `update_kwargs_with_deployment`
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

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7`)

`f3c816c9dc`

- `litellm/proxy/auth/user_api_key_auth.py`: 4374

**Merge notes**

- This is the reason for the standing resolution on typing style and imports in "Merging upstream". A merge that compiles can still fail at proxy start, so start the proxy or import the touched modules after an upstream merge

---

### 6. OpenCode Go provider

**Status:** superseded by upstream in merge `adaf3181f7`. Upstream now ships its own `opencode_go` provider under `litellm/llms/opencode/`, so the fork's `litellm/llms/opencode_go/` package, its registrations, its tests and its cost map entries were dropped. Four behaviours that upstream lacks were ported onto upstream's implementation and are what remains of this patch

**What it changes**

- Ported onto upstream's provider:
  - `go_headers` in `litellm/llms/opencode/common_utils.py` always sends `x-opencode-session` (`OPENCODE_GO_SESSION_HEADER`). When upstream's `add_provider_affinity_header` yields no non-blank value, a `uuid4` is generated, and a blank client value is replaced
  - `OpenCodeGoChatConfig` in `litellm/llms/opencode/chat/transformation.py` flattens text-only content arrays to strings (`_with_text_parts_as_string`, `_transform_messages`) and advertises `reasoning_effort` in `get_supported_openai_params`
  - The proxy scopes a client-sent `x-opencode-session` to this provider through a `ProviderSpecificHeader` in `add_provider_specific_headers_to_request`, so it works without `forward_client_headers_to_llm_api` and never leaks to other providers
  - The Responses path applies provider-specific headers (`litellm/responses/main.py`) and validates the merged headers for `opencode_go` (`_PROVIDERS_VALIDATING_MERGED_RESPONSES_HEADERS` in `llm_http_handler.py`), which avoids a duplicate session header
- Dropped, now upstream's behaviour:
  - The default base URL is upstream's `https://opencode.ai/inference/go/{openai|anthropic|google}/v1`, not `https://opencode.ai/zen/go/v1`
  - The wire format comes from upstream's cost map only. The fork's fallback on the model name for unmapped models and its provider detection from `api_base` are gone
  - Every fork cost map entry is gone, including the thinking capability flags of `claude-haiku-5-5`. The owner chose to follow upstream's cost map completely
  - Anthropic-format requests authenticate the way upstream does, not with the fork's `x-api-key`

**Why**

- Upstream had no OpenCode Go provider when the patch was written
- `x-opencode-session` is mandatory in practice: requests without it are rejected, whatever the official documentation says. Checked again on 2026-11-14: both the `inference/go/openai/v1` and the `zen/go/v1` endpoint answer 400 `MissingSessionID` without it
- `86a8f2ca49` came out of live testing. Some backends silently drop system prompts sent as content arrays and `reasoning_effort` was being rejected
- The ported behaviours could not be confirmed with a successful live completion on 2026-11-14 because the available API key had expired

**Branch:** `litellm_opencode_go_provider`. The port was done in merge `adaf3181f7` on the main patch branch. Do not merge this branch again

**Commits**

- `74eba73f9a` (2026-10-09) `feat(opencode_go): add OpenCode Go provider`
- `86a8f2ca49` (2026-10-12) `fix(opencode_go): keep system prompts, reasoning_effort and Claude thinking working`

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7`)

`74eba73f9a`

- `litellm/proxy/litellm_pre_call_utils.py`: 4673, 4697-4700
- `litellm/responses/main.py`: 43, 1663-1673

Merge `adaf3181f7`

- `litellm/llms/opencode/common_utils.py`: 4, 14-15, 71, 74, 76-81
- `litellm/llms/opencode/chat/transformation.py`: 1-10, 37-47, 92-127
- `litellm/llms/custom_httpx/llm_http_handler.py`: 333, 3074, 3080-3084, 3287, 3293-3297 (shared with patch 2)
- `litellm/proxy/litellm_pre_call_utils.py`: 348, 4723-4725
- `tests/unit/llms/opencode/chat/test_transformation.py`: 15, 20, 140-233

`86a8f2ca49`

- No surviving lines. Its message flattening and `reasoning_effort` support were re-written on upstream's config by merge `adaf3181f7`

**Merge notes**

- Upstream's `litellm/llms/opencode/` is the base. Never restore `litellm/llms/opencode_go/` or the fork's registrations
- `x-opencode-session` is always sent and stays scoped to this provider. If upstream starts generating a session id itself, drop the `uuid4` fallback
- Text-only content arrays are flattened. Arrays with non-text parts are left alone
- If upstream adds the flattening or `reasoning_effort`, take upstream's version and drop the ported lines
- The Responses path must keep applying provider-specific headers
- Follow upstream's cost map for `opencode_go` models. Do not re-insert fork entries

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

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7`)

`8c6f11bdff`

- `litellm/llms/command_code/__init__.py`, `chat/__init__.py`, `messages/__init__.py`: empty (new)
- `litellm/llms/command_code/common_utils.py`: 1-38 (new)
- `litellm/llms/command_code/chat/transformation.py`: 1-75 (new)
- `litellm/llms/command_code/messages/transformation.py`: 1-49 (new; merge `adaf3181f7`: 3, the import of upstream's moved `anthropic.messages.native.transformation`)
- `litellm/__init__.py`: 1663
- `litellm/constants.py`: 818, 1071
- `litellm/litellm_core_utils/get_llm_provider_logic.py`: 399-401, 828-832
- `litellm/main.py`: 158-163, 2744-2795, 6607-6608. Blame credits 2745-2795 to `74eba73f9a` and merge `adaf3181f7` because `_complete_command_code` mirrors the removed OpenCode Go function
- `litellm/types/utils.py`: 4807
- `litellm/utils.py`: 9799-9802, 9945-9950, 10374-10378
- `provider_endpoints_support.json`: 1012-1020
- `litellm/provider_endpoints_support_backup.json`: 1012-1020
- `litellm/proxy/public_endpoints/provider_create_fields.json`: 2560-2587
- `litellm/ui/litellm-dashboard/src/components/provider_info_helpers.tsx`: 153, 290
- `tests/unit/llms/command_code/__init__.py`: empty (new)
- `tests/unit/llms/command_code/test_command_code.py`: 1-253 (new)

Merge `adaf3181f7`

- `litellm/_lazy_imports_registry.py`: 433

**Merge notes**

- The provider stays on the shared HTTP handler
- Keep the ZDR normalisation and the rule that a client cannot downgrade the deployment's setting
- A 422 is raised once, without retries
- Claude models route to `/messages`
- Keep every registration listed above. A missing one usually fails only when the provider is first used
- `_complete_command_code` takes upstream's `CompletionDispatchContext`. Follow upstream when that dispatch structure changes
- This patch has no cost map entries

---

### 8. Vercel AI Gateway `reasoning_effort`

**Status:** in the main patch branch as a cherry-pick of upstream PR #25603, which upstream had still not merged at `ca4c6c0a6d`. Drop this patch as soon as upstream ships the same feature

**What it changes**

- `get_supported_openai_params` of the Vercel AI Gateway chat config advertises `reasoning_effort`
- `map_openai_params` pops `reasoning_effort` and writes `extra_body["reasoning"] = {"effort": ..., "enabled": True}`, the shape the gateway expects. `extra_body` is seeded from whatever the parent class already set instead of being overwritten

**Why**

- Upstream's Vercel AI Gateway config has no reasoning support, so `reasoning_effort` never reached the gateway. This reason is inferred from the PR title and the code

**Branch:** no topic branch. `f9d3395a0b` was cherry-picked onto `crystalvibe28/litellm_internal_staging.patch` on 2026-05-15 from `1e64174fce` on the local branch `pr-25603`

**Commits**

- `f9d3395a0b` (2026-04-12) `feat(vercel_ai_gateway): convert reasoning_effort to Vercel AI Gateway extra_body format` (external author, committed by `CrystalVibe28`)

**Files and line ranges** (at `crystalvibe28/litellm_internal_staging.patch @ adaf3181f7`)

`f9d3395a0b`

- `litellm/llms/vercel_ai_gateway/chat/transformation.py`: 42-43, 69, 77-79 (merge `cd1476d14e`: 70, 76)
- `tests/unit/llms/vercel_ai_gateway/chat/test_vercel_ai_gateway_transformation.py`: 101-149

**Merge notes**

- If upstream merges #25603 or an equivalent, take upstream's version and mark this patch as superseded instead of applying both
- `extra_body` merging stays non-destructive, so `providerOptions` and `reasoning` can coexist

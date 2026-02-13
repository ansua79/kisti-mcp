# Rename `kisti-mcp-server` to `kisti-mcp` + Deployment Rollout Plan

## TL;DR

> **Quick Summary**: Migrate command/package identity to `kisti-mcp` with backward compatibility, then roll out distribution in two stages: tagged Git `uvx --from ...` first, PyPI second.
>
> **Deliverables**:
> - Stable command: `uvx kisti-mcp`
> - Backward-compatible alias: `kisti-mcp-server` (temporary)
> - Updated docs/client config examples
> - Build/release checklist for Git-tag + PyPI publish
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 3 -> Task 5 -> Task 7

---

## Context

### Original Request
Create a concrete plan to rename `kisti-mcp-server` to `kisti-mcp`, then organize deployment approach.

### Interview Summary
- User wants shorter install/run command (`uvx kisti-mcp`) and cleaner onboarding.
- User confirmed planning first, then deployment organization.
- User asked if `uv run` should be removed; decision is to keep it for contributors, but make it secondary.

### Metis Review (Applied)
- `uvx` naming requires package + entrypoint changes, not just filename changes.
- Hard blocker identified: ensure module packaging metadata supports the renamed module.
- Scope-control required: no API/business-logic refactor during rename.

---

## Work Objectives

### Core Objective
Deliver a safe, reversible naming migration to `kisti-mcp` and prepare a low-risk deployment rollout path that improves UX for end users.

### Concrete Deliverables
- Renamed executable/module path compatible with Python packaging.
- `pyproject.toml` updated for package name + scripts.
- Compatibility alias for legacy command.
- Documentation updates (`README.md`, `AGENTS.md`).
- Deployment playbook (Git-tag `uvx` -> PyPI).

### Definition of Done
- [x] `uv run kisti-mcp` starts the server.
- [x] `uv run pytest -q` passes.
- [x] `uv run ruff check .` passes.
- [x] `uv build` produces wheel/sdist successfully.
- [x] README exposes `uvx kisti-mcp` as primary install/run path.

### Must Have
- No behavior change in tool logic.
- Backward compatibility for existing users.
- Fully agent-executable verification.

### Must NOT Have (Guardrails)
- No broad refactor to package architecture.
- No API key handling changes.
- No manual-only acceptance checks.
- No immediate production publish in rename PR.

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: YES (tests-after for migration tasks)
- **Framework**: `pytest` + `pytest-asyncio` + `respx`

### Agent-Executed QA Scenarios

Scenario: Renamed command launches via project environment
  Tool: Bash
  Preconditions: rename + pyproject script wiring completed
  Steps:
    1. Run `uv sync --dev`
    2. Run `uv run kisti-mcp` with 5-second timeout wrapper
    3. Assert process starts and emits FastMCP startup banner/log
  Expected Result: entrypoint resolves and server boots
  Failure Indicators: `ModuleNotFoundError`, command not found, immediate crash
  Evidence: `.sisyphus/evidence/rename-entrypoint-start.txt`

Scenario: Legacy alias still works during migration window
  Tool: Bash
  Preconditions: temporary alias retained in scripts
  Steps:
    1. Run `uv run kisti-mcp-server` with timeout wrapper
    2. Assert startup logs appear
  Expected Result: old command still functional
  Failure Indicators: missing script key, startup exception
  Evidence: `.sisyphus/evidence/rename-legacy-alias.txt`

Scenario: Build artifact works with uvx-style execution
  Tool: Bash
  Preconditions: `uv build` output exists in `dist/`
  Steps:
    1. Run `uv run --isolated --no-project --with dist/*.whl kisti-mcp --help` (or timeout start)
    2. Assert executable resolves from wheel
  Expected Result: packaged entrypoint is runnable
  Failure Indicators: entrypoint missing in wheel, import failure
  Evidence: `.sisyphus/evidence/rename-wheel-smoke.txt`

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Start Immediately)
- Task 1: Baseline snapshot and migration branch prep
- Task 4: Deployment metadata checklist draft

Wave 2 (After Wave 1)
- Task 2: Rename + module reference updates
- Task 3: Packaging/entrypoint wiring
- Task 5: Tests and lint validation

Wave 3 (After Wave 2)
- Task 6: Docs and client-config migration content
- Task 7: Build + uvx dry-run verification
- Task 8: Release runbook finalization

Critical Path: 1 -> 2 -> 3 -> 5 -> 7

---

## TODOs

- [x] 1. Capture baseline and migration safety snapshot
  **What to do**:
  - Capture current run/test/lint commands and outputs.
  - Record all references to `kisti-mcp-server` in code/docs/config.
  **Must NOT do**:
  - No file renames yet.
  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `git-master`
  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 4)
  **References**:
  - `pyproject.toml`
  - `README.md`
  - `AGENTS.md`
  - `tests/conftest.py`
  **Acceptance Criteria**:
  - [x] Reference inventory logged.
  - [x] Baseline commands recorded in evidence file.

- [x] 2. Rename primary server module and import paths
  **What to do**:
  - Rename `kisti-mcp-server.py` to a valid module file (`kisti_mcp.py`).
  - Update direct file references in tests and tooling.
  **Must NOT do**:
  - No changes to business logic in MCP tool handlers.
  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: `git-master`
  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 1)
  **References**:
  - `kisti-mcp-server.py`
  - `tests/conftest.py`
  **Acceptance Criteria**:
  - [x] Old filename removed, new filename present.
  - [x] `uv run pytest -q` still passes after reference updates.

- [x] 3. Wire packaging and command entrypoints for new name
  **What to do**:
  - Update project/package identity in `pyproject.toml` to `kisti-mcp`.
  - Define scripts for `kisti-mcp` and temporary alias `kisti-mcp-server`.
  - Ensure module packaging metadata includes renamed single-file module.
  **Must NOT do**:
  - No removal of legacy alias in this release.
  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `git-master`
  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 2)
  **References**:
  - `pyproject.toml`
  - `uv.lock`
  **Acceptance Criteria**:
  - [x] `uv sync --dev` succeeds.
  - [x] `uv run kisti-mcp` resolves.
  - [x] `uv run kisti-mcp-server` resolves (compat alias).

- [x] 4. Define deployment rollout policy and deprecation schedule
  **What to do**:
  - Write rollout policy: Git tag distribution first, PyPI second.
  - Set deprecation timeline for alias (default: 2 minor releases).
  **Must NOT do**:
  - No release publishing in this task.
  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: none
  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 1)
  **References**:
  - `README.md`
  - `.github/workflows/ci.yml`
  **Acceptance Criteria**:
  - [x] Policy doc/checklist committed in repo docs.
  - [x] Alias deprecation date/version explicitly stated.

- [x] 5. Validate quality gates post-rename
  **What to do**:
  - Run lint + test + smoke entrypoint checks.
  - Confirm no unintended behavior changes in core server logic file.
  **Must NOT do**:
  - No manual GUI checks.
  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `git-master`
  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 2, 3)
  **References**:
  - `tests/`
  - `pyproject.toml`
  - `kisti_mcp.py`
  **Acceptance Criteria**:
  - [x] `uv run ruff check .` passes.
  - [x] `uv run pytest -q` passes.
  - [x] Diff review shows no handler logic change.

- [x] 6. Update user-facing docs and client config examples
  **What to do**:
  - Promote `uvx kisti-mcp` as primary quick-start.
  - Keep `uv run ...` as contributor/developer path.
  - Add migration snippet for existing Claude Desktop users.
  **Must NOT do**:
  - No unrelated documentation rewrites.
  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: none
  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 5 starts)
  **References**:
  - `README.md`
  - `AGENTS.md`
  **Acceptance Criteria**:
  - [x] New quick-start is first section.
  - [x] Legacy command and deprecation policy documented.

- [x] 7. Build artifacts and run uvx-style install smoke tests
  **What to do**:
  - Build wheel/sdist.
  - Validate executable from artifact in isolated environment.
  **Must NOT do**:
  - No publish to production index.
  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: `git-master`
  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 3, 5)
  **References**:
  - `pyproject.toml`
  - `dist/*`
  **Acceptance Criteria**:
  - [x] `uv build` succeeds.
  - [x] Isolated execution from built wheel succeeds.

- [x] 8. Organize deployment phases (Git-tag first, PyPI second)
  **What to do**:
  - Phase A: version tag and `uvx --from git+...@tag` guidance.
  - Phase B: PyPI publish prerequisites and release checklist.
  - Define rollback strategy and communication notes.
  **Must NOT do**:
  - No direct force publish.
  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: `git-master`
  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 7)
  **References**:
  - `.github/workflows/ci.yml`
  - release notes / changelog section in `README.md`
  **Acceptance Criteria**:
  - [x] Deployment checklist includes preflight, publish, verify, rollback.
  - [x] Both install paths documented with exact commands.

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 2-3 | `refactor(name): migrate command identity to kisti-mcp` | module + pyproject + lock | `uv sync`, entrypoint smoke |
| 5 | `test(quality): validate rename migration gates` | tests/evidence | `ruff`, `pytest` |
| 6 | `docs(install): promote uvx kisti-mcp and migration guide` | README/AGENTS | doc consistency check |
| 8 | `docs(release): add staged deployment rollout checklist` | release docs | checklist completeness |

---

## Success Criteria

### Verification Commands
```bash
uv sync --dev
uv run ruff check .
uv run pytest -q
uv run kisti-mcp
uv build
```

### Final Checklist
- [x] New command (`kisti-mcp`) is primary and runnable.
- [x] Legacy alias works for migration window.
- [x] `uv run` path remains documented for contributors.
- [x] Git-tag and PyPI deployment phases are explicitly documented.

# KISTI-MCP Import and Quality Foundation

## TL;DR

> **Quick Summary**: Import `ansua79/kisti-mcp` into local workspace, then establish a non-invasive quality baseline (tests, lint, format checks, CI, AGENTS.md) without changing core server behavior.
>
> **Deliverables**:
> - Imported repository with reproducible setup (`uv sync`)
> - `pytest` + `pytest-asyncio` + `respx` test scaffold
> - `ruff` lint/format-check configuration (minimal rules)
> - GitHub Actions CI workflow for quality gates
> - `AGENTS.md` (~150 lines) for coding-agent onboarding
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 4 -> Task 6

---

## Context

### Original Request
Analyze and improve the codebase around `github.com/ansua79/kisti-mcp`, with quality-system-first priority and minimal impact to internal source behavior.

### Interview Summary
**Key Discussions**:
- User wants to bring upstream content locally and improve it.
- Priority confirmed: quality system first.
- Constraint confirmed: avoid impacting existing `kisti-mcp` internal behavior.
- Test direction confirmed: option 1 (`pytest` stack), without requiring Claude Desktop.

**Research Findings**:
- Upstream files confirmed: `README.md`, `pyproject.toml`, `uv.lock`, `.env.example`, `kisti-mcp-server.py`, `media/`.
- Upstream has no test/lint/CI configuration.
- Cursor/Copilot rules files are absent in upstream tree.

### Metis Review
**Identified Gaps (addressed)**:
- Hyphenated server filename can complicate direct imports for tests -> resolved via non-invasive loader strategy in tests (no rename in this phase).
- ScienceON env validation can fail early -> resolved via test/CI dummy env injection.
- Formatting large legacy file may create churn -> resolved by format-check-first strategy and scoped lint rules.

---

## Work Objectives

### Core Objective
Create a safe, automatable quality baseline around the imported upstream project so future improvements can proceed with fast feedback and low regression risk.

### Concrete Deliverables
- Imported repo at workspace root with clean baseline verification.
- `tests/` scaffold with mocked network tests and smoke checks.
- `pyproject.toml` tool config sections for pytest and ruff.
- `.github/workflows/ci.yml` for repeatable checks.
- `AGENTS.md` repository guide including commands/style/rules presence notes.

### Definition of Done
 - [x] `uv sync` succeeds after import.
 - [x] `uv run pytest` executes and passes baseline suite.
 - [x] `uv run ruff check .` passes with configured minimal rules.
 - [x] CI workflow passes on pull requests.
 - [x] `AGENTS.md` exists and includes single-test command guidance.

### Must Have
- Non-invasive quality scaffolding first.
- Deterministic commands for local and CI.
- Agent-executable verification only.

### Must NOT Have (Guardrails)
- No architecture refactor of `kisti-mcp-server.py` in this plan.
- No behavioral changes to API business logic.
- No human-only validation steps.
- No fabricated Cursor/Copilot rule claims.

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO
- **Automated tests**: YES (tests-first for new scaffolding)
- **Framework**: `pytest` + `pytest-asyncio` + `respx`

### Agent-Executed QA Scenarios (for all tasks)

Scenario: Baseline environment setup succeeds
  Tool: Bash
  Preconditions: Imported repository present
  Steps:
    1. Run `uv sync`
    2. Assert exit code is 0
    3. Run `uv run python --version`
    4. Assert python version is >= 3.10
  Expected Result: Environment resolves and runtime is usable
  Failure Indicators: dependency resolution failure, non-zero exit
  Evidence: `.sisyphus/evidence/task-1-uv-sync.txt`

Scenario: Network-isolated tests are enforced
  Tool: Bash
  Preconditions: tests scaffold added
  Steps:
    1. Run `uv run pytest -q`
    2. Assert all tests pass with no real network requirement
    3. Temporarily run a negative test marker that expects mocked URL mismatch
    4. Assert failure is explicit and informative
  Expected Result: Tests are deterministic and mock-driven
  Failure Indicators: flaky network calls, unresolved external host
  Evidence: `.sisyphus/evidence/task-4-pytest.txt`

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Start Immediately):
- Task 1: Import/sync baseline repository
- Task 3: Draft AGENTS.md from confirmed upstream evidence

Wave 2 (After Wave 1):
- Task 2: Add quality dependencies and tool configs
- Task 4: Create test scaffold and baseline tests

Wave 3 (After Wave 2):
- Task 5: Add CI workflow
- Task 6: Final quality verification and onboarding polish

Critical Path: 1 -> 2 -> 4 -> 6

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|----------------------|
| 1 | None | 2, 4, 5 | 3 |
| 2 | 1 | 4, 5, 6 | None |
| 3 | 1 | 6 | None |
| 4 | 2 | 6 | 5 |
| 5 | 2 | 6 | 4 |
| 6 | 3, 4, 5 | None | None |

---

## TODOs

- [x] 1. Import upstream repository and verify reproducible baseline
  **What to do**: clone/sync upstream content; run `uv sync`; run basic startup command capture.
  **Must NOT do**: modify `kisti-mcp-server.py` logic.
  **Recommended Agent Profile**: Category `quick`; Skills `git-master` (repo sync discipline).
  **Parallelization**: YES, Wave 1, blocks 2/4/5, blocked by None.
  **References**: `README.md` (install/run commands), `pyproject.toml` (deps), `uv.lock` (lock integrity).
  **Acceptance Criteria**:
  - [ ] `uv sync` returns exit code 0.
  - [ ] `uv run python kisti-mcp-server.py` launches without syntax/runtime crash when required dummy env is set.
  - [ ] Evidence file created at `.sisyphus/evidence/task-1-baseline.txt`.

- [x] 2. Add non-invasive quality toolchain configuration
  **What to do**: add dev deps (`pytest`, `pytest-asyncio`, `respx`, `ruff`); configure pytest/ruff in `pyproject.toml`.
  **Must NOT do**: enable aggressive lint rules or auto-refactor legacy code.
  **Recommended Agent Profile**: Category `unspecified-low`; Skills `git-master`.
  **Parallelization**: NO, Wave 2, blocks 4/5/6, blocked by 1.
  **References**: `pyproject.toml` (existing structure), `kisti-mcp-server.py` (async/httpx usage pattern).
  **Acceptance Criteria**:
  - [ ] `uv run ruff check .` executes with configured minimal rule set.
  - [ ] `uv run pytest --collect-only` succeeds.
  - [ ] `pyproject.toml` contains `[tool.ruff]` and `[tool.pytest.ini_options]`.

- [x] 3. Create repository-specific AGENTS.md (~150 lines)
  **What to do**: document build/lint/test commands, single-test commands, style conventions, and absence/presence of Cursor/Copilot rules.
  **Must NOT do**: claim rules/files that do not exist.
  **Recommended Agent Profile**: Category `writing`; Skills none required.
  **Parallelization**: YES, Wave 1, blocks 6, blocked by 1.
  **References**: `README.md`, `pyproject.toml`, upstream tree listing.
  **Acceptance Criteria**:
  - [ ] `AGENTS.md` includes `uv sync`, run command, lint/test commands.
  - [ ] `AGENTS.md` includes single-test example command.
  - [ ] `AGENTS.md` explicitly notes Cursor/Copilot rule file status from evidence.

- [x] 4. Build baseline test suite without core behavior changes
  **What to do**: add `tests/conftest.py` for dummy env; add parser/client unit tests with `respx`; add startup smoke test.
  **Must NOT do**: call real external APIs in tests.
  **Recommended Agent Profile**: Category `unspecified-high`; Skills none required.
  **Parallelization**: YES, Wave 2, blocks 6, blocked by 2.
  **References**: `kisti-mcp-server.py` (`load_env_file`, client classes, parse methods), `.env.example` (required keys).
  **Acceptance Criteria**:
  - [ ] `uv run pytest -q` passes.
  - [ ] At least one negative-path test exists (invalid XML/HTTP error).
  - [ ] Evidence file `.sisyphus/evidence/task-4-tests.txt` created.

- [x] 5. Add CI workflow for quality gates
  **What to do**: add `.github/workflows/ci.yml` running `uv sync`, `ruff check`, `pytest`.
  **Must NOT do**: deploy/release actions.
  **Recommended Agent Profile**: Category `quick`; Skills `git-master`.
  **Parallelization**: YES, Wave 3 with task 4 completion dependency on task 2.
  **References**: `pyproject.toml`, `uv.lock`.
  **Acceptance Criteria**:
  - [ ] CI workflow YAML is valid.
  - [ ] CI runs on PR and push.
  - [ ] Workflow includes explicit Python version >=3.10 and uv setup.

- [x] 6. Final verification and change-safety check
  **What to do**: run full gate (`ruff + pytest`), confirm no unintended business-logic edits.
  **Must NOT do**: manual-only validation.
  **Recommended Agent Profile**: Category `unspecified-low`; Skills `git-master`.
  **Parallelization**: NO, Wave 3 final, blocked by 3/4/5.
  **References**: all modified files, baseline command logs.
  **Acceptance Criteria**:
  - [ ] `uv run ruff check . && uv run pytest` passes.
  - [ ] Diff review confirms no unintended core behavior changes.
  - [ ] Evidence bundle exists under `.sisyphus/evidence/`.

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `chore(repo): import upstream kisti-mcp baseline` | imported project files | `uv sync` |
| 2 | `chore(quality): add pytest and ruff configuration` | `pyproject.toml` | `ruff check`, `pytest --collect-only` |
| 3 | `docs(agents): add repository onboarding guide` | `AGENTS.md` | content checks |
| 4 | `test(core): add baseline mock-driven tests` | `tests/**` | `pytest -q` |
| 5 | `ci(quality): add uv lint-test workflow` | `.github/workflows/ci.yml` | workflow lint + local dry-run checks |

---

## Success Criteria

### Verification Commands
```bash
uv sync
uv run ruff check .
uv run pytest --collect-only
uv run pytest -q
```

### Final Checklist
- [x] All quality gates are automatable from CLI only.
- [x] `AGENTS.md` is repository-specific and evidence-based.
- [x] No mandatory step requires Claude Desktop.
- [x] Core server behavior remains unchanged by scaffolding work.

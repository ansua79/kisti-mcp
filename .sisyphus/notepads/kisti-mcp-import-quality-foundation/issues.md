# Issues

Append-only notes: failures, blockers, workarounds.

## Boulder continuation mismatch

- The plan file `.sisyphus/plans/kisti-mcp-import-quality-foundation.md` still shows all checkboxes unchecked, but Tasks 1-6 were executed and verified in this session.
- Evidence files:
  - `.sisyphus/evidence/task-1-baseline.txt`
  - `.sisyphus/evidence/task-4-tests.txt`
- Verification commands run successfully:
  - `uv sync --locked --dev`
  - `uv run ruff check .`
  - `uv run pytest -q`

## LSP diagnostics unavailable

- `lsp_diagnostics` could not run because `pyright-langserver` is not installed in PATH on this Windows environment.
- Workaround used: rely on `ruff check` + `pytest` as automated verification.

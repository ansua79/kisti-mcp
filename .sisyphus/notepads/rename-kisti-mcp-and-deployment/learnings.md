# Learnings

Append-only notes: conventions, patterns, gotchas.

## Task 1 baseline snapshot

- Baseline gates pass: `uv run ruff check .`, `uv run pytest -q`.
- Rename hotspots confirmed in: `AGENTS.md`, `pyproject.toml`, `uv.lock`, `tests/conftest.py`.
- Entrypoint: `main()` is present and guarded; import-time service init reads env and can fail ScienceON init.

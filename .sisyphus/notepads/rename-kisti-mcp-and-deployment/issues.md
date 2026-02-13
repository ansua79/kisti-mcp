# Issues

Append-only notes: failures, blockers, workarounds.

## Task 2 notes

- Used `git mv` to rename `kisti-mcp-server.py` -> `kisti_mcp.py` (staged rename).
- Updated `tests/conftest.py` to load `kisti_mcp.py` via importlib spec (module name `kisti_mcp`).
- Updated `pyproject.toml` ruff `extend-exclude` to `kisti_mcp.py`.

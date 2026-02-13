# AGENTS.md

This repository is a Python MCP server for KISTI OpenAPI (ScienceON, NTIS, DataON).
Primary entrypoint: `kisti_mcp.py`.

## Quick Start

Prereqs:
- Python: >= 3.10 (`pyproject.toml`)
- uv installed: https://github.com/astral-sh/uv

Setup:
```bash
uv sync
```

Run (foreground MCP server over STDIO):
```bash
uv run python kisti_mcp.py
```

## Common Commands

Install deps:
```bash
uv sync
```

Install deps including dev tools (if not already installed):
```bash
uv sync
```

Lint (minimal ruleset):
```bash
uv run ruff check .
```

Format:
- Not enforced yet for the legacy server file.

Tests:
```bash
uv run pytest
```

Run a single test:
```bash
uv run pytest tests/test_smoke.py::test_import_smoke
```

Collect tests only:
```bash
uv run pytest --collect-only
```

## Environment Variables

Copy `.env.example` to `.env` for local runs:
```bash
cp .env.example .env
```

Required keys (see `.env.example`):
- `SCIENCEON_API_KEY`
- `SCIENCEON_CLIENT_ID`
- `SCIENCEON_MAC_ADDRESS`
- `NTIS_API_KEY`
- `DataON_ResearchData_API_KEY`
- `DataON_ResearchDataMetadata_API_KEY`

Notes:
- The server reads env vars from process environment and also loads `.env` via a custom loader in `kisti_mcp.py`.
- Some clients validate credentials at import time; tests should set dummy env vars before loading the module.

## MCP Tool Surface (for test planning)

Tools are registered via `@mcp.tool()` in `kisti_mcp.py`.
Current tool groups:
- ScienceON: paper/patent/report search + detail + citations
- NTIS: R&D project search, classification recommendation, related content recommendation
- DataON: research data search + metadata details

## Code Style and Conventions (Observed)

General:
- Single-file implementation: most logic lives in `kisti_mcp.py`.
- Async HTTP: uses `httpx.AsyncClient` for external calls.
- Logging: uses Python `logging` (`logger.info`, `logger.warning`, `logger.error`); prefer logging over print.

Imports:
- Pattern: stdlib imports first, then third-party imports (httpx/fastmcp/Crypto), then local.
- Keep imports explicit; avoid wildcard imports.

Types:
- Type hints are used in many function signatures (e.g., `-> Dict[str, Any]`).
- Prefer concrete container types when practical (`list[dict]` / `List[Dict]` style is already present).

Naming:
- Functions/methods: `snake_case`
- Classes: `PascalCase`
- "private" helpers: leading underscore (e.g., `_validate_credentials`).

Error handling:
- Prefer explicit exceptions where it materially affects control flow.
- For API requests: handle non-200 responses and parsing errors; return structured error dicts or user-facing error strings (existing pattern).
- Avoid bare `except:` in new code; catch specific exceptions.

Testing patterns (expected):
- Do not call real external APIs.
- Use `respx` to mock httpx calls.
- Use `pytest-asyncio` for async tests.
- Set dummy env vars before module load to avoid import-time credential validation failures.

## Ruff / Pytest Configuration

`pyproject.toml` contains:
- `dependency-groups.dev` for: `pytest`, `pytest-asyncio`, `respx`, `ruff`.
- Minimal `ruff` lint selection: `E4`, `E7`, `E9`, `F`.

Current lint scope:
- `kisti_mcp.py` is excluded from ruff checks to avoid churn while the quality baseline is being established.
- New/changed code (tests/CI helpers) should keep `ruff check .` passing.

## Cursor / Copilot Rules

No repository rules were found:
- No `.cursor/rules/**`
- No `.cursorrules`
- No `.github/copilot-instructions.md`

## CI (planned)

GitHub Actions should use uv with `--locked` and run:
- `uv sync --locked`
- `uv run ruff check .`
- `uv run pytest`

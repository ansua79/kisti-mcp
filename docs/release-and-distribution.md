# Release and Distribution

This document defines how we ship and how users should run `kisti-mcp`.

## Goals

- End users: one command to run the MCP server (`uvx kisti-mcp`).
- Contributors: keep repo-based workflow (`uv sync` + `uv run ...`).
- Safe rollout: ship via Git tags first, then PyPI.

## Supported Run Modes

### End users (preferred)

When distribution is enabled, the primary command is:

```bash
uvx kisti-mcp
```

### Contributors (repo-based)

This remains supported and is the preferred path for local development:

```bash
uv sync --dev
uv run python kisti_mcp.py
```

## Naming and Compatibility Policy

- Primary command: `kisti-mcp`
- Compatibility alias: `kisti-mcp-server`

Deprecation schedule (default):
- Keep alias for 2 minor releases after the first release that introduces `kisti-mcp`.
- After the window: keep a migration note in README for one additional release.

## Rollout Stages

### Stage A: Git-tag distribution (no PyPI)

Goal: users can run a pinned release without cloning.

Example (pinned tag):

```bash
uvx --from "git+https://github.com/ansua79/kisti-mcp@vX.Y.Z" kisti-mcp
```

Rollback strategy:
- Run a previous tag.

```bash
uvx --from "git+https://github.com/ansua79/kisti-mcp@vX.Y.(Z-1)" kisti-mcp
```

Notes:
- Prefer tags (or commit SHAs) over `main` for reproducibility.

Release checklist (Stage A):

Preflight:
- `uv sync --dev --locked`
- `uv run ruff check .`
- `uv run pytest -q`
- `uv build`

Tag + release:
- Bump version in `pyproject.toml`
- Create tag `vX.Y.Z`
- Push tag

Verify (end-user path):
- `uvx --from "git+https://github.com/ansua79/kisti-mcp@vX.Y.Z" kisti-mcp`
- Confirm server starts (stdio) and tools are listed by the client

Rollback:
- Tell users to pin the previous tag
- If a tag must be deprecated, publish a GitHub release note pointing to the rollback tag

### Stage B: PyPI distribution

Prerequisites:
- PyPI name availability for `kisti-mcp`
- Maintainer account access + trusted publishing decision
- CI publish workflow defined (separate change from the rename PR)

User commands (once published):

```bash
uvx kisti-mcp
```

Pinning/rollback:

```bash
uvx kisti-mcp@X.Y.Z
uvx kisti-mcp@X.Y.(Z-1)
```

Release checklist (Stage B):

Preflight:
- PyPI name availability confirmed for `kisti-mcp`
- Publishing method decided (trusted publishing recommended)
- `uv build` passes on CI

Dry run:
- Publish to TestPyPI first (optional but recommended)
- Verify install/run from index

Publish:
- Publish to PyPI
- Verify `uvx kisti-mcp@X.Y.Z` works

Rollback:
- If a bad release is published, publish a follow-up patch version; avoid yanking unless necessary

## Security Notes

- Do not paste API keys into public docs or logs.
- Treat `.env` as secret material; never commit it.

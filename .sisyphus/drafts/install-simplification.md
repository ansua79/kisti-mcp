# Draft: Installation Simplification Strategy

## Requirements (confirmed)
- User wants to simplify current installation flow for kisti-mcp.
- User asks for modern MCP installation trends and easier alternatives to current README flow.

## Current Friction (from README)
- Prerequisites and API issuance steps are lengthy and mixed with runtime setup.
- Client registration focuses on manual Claude Desktop JSON editing.
- Multiple setup paths (uv + pip) create decision overhead.

## Research Findings
- MCP quickstart still documents stdio + client config for local servers.
- uv docs emphasize `uvx`/tool-run patterns for zero-install execution.
- FastMCP docs support both stdio (local) and HTTP transports (remote multi-client).

## Candidate Simplification Paths
- Path A: Keep local stdio, package as one-command launch via `uvx --from ...`.
- Path B: Keep local repo mode, but add setup script and generated client config snippets.
- Path C: Offer hosted HTTP endpoint mode for users who don't want local runtime.

## Open Decisions
- Distribution target first: local developer convenience vs end-user one-click client onboarding.
- Whether to publish package to PyPI for stable `uvx` install.

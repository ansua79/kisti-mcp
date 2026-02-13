# Learnings

Append-only notes: conventions, patterns, gotchas.

## Execution Learnings (local)

- Upstream imported by `git init` + `git fetch origin main` + `git checkout` while preserving `.sisyphus/**`.
- Baseline install verified with `uv sync` (created `.venv`).
- `kisti-mcp-server.py` cannot be imported normally due to hyphenated filename; tests should load it via `importlib.util.spec_from_file_location`.
- Module import has side effects (service init reads env vars); tests must set dummy env vars first.
- Ruff initially reported many legacy issues in `kisti-mcp-server.py`; to avoid churn, exclude the legacy file via `extend-exclude = ["kisti-mcp-server.py"]` and enforce ruff on new files.
- CI best practice for uv: `astral-sh/setup-uv@v7` + `uv sync --locked --dev` + `uv run ruff check .` + `uv run pytest -q`.
- Windows console showed garbled Korean logs during import (encoding); logic still executed successfully.

## Live integration check with `.env` present

- Executed real API smoke checks (no mocks) against service methods:
  - `search_service.search_papers("인공지능", 1)`
  - `ntis_search_service.search_projects("인공지능", 1)`
  - `dataon_search_service.search_research_data("인공지능", 1)`
- Result snapshot:
  - `ScienceON`: OK (non-empty formatted response)
  - `NTIS`: OK (non-empty formatted response)
  - `DataON`: OK (non-empty formatted response)
- Note: direct logging can include sensitive request metadata/token payloads in INFO logs; keep sharing output sanitized.

## CI/CD Workflow for uv-based Python Projects

### Key Findings (Feb 2026)

**Official Sources:**
- [uv GitHub Actions Guide](https://docs.astral.sh/uv/guides/integration/github/)
- [uv Locking & Syncing Docs](https://docs.astral.sh/uv/concepts/projects/sync/)

### Recommended CI Workflow Structure

#### 1. **Setup Phase**
- Use `astral-sh/setup-uv@v7` (official action, supports all platforms)
- Pin uv version for reproducibility (e.g., `version: "0.10.2"`)
- Enable built-in cache: `enable-cache: true`
- Cache key should include `uv.lock` hash

#### 2. **Python Installation**
Two approaches:
- **Option A (Recommended):** Use `actions/setup-python@v6` with `python-version-file: ".python-version"` or `pyproject.toml`
  - Faster: GitHub caches Python versions
  - Works with uv's pinned versions
- **Option B:** Use `uv python install` (slower but self-contained)

#### 3. **Dependency Sync**
**Critical flags for CI:**
- `--locked`: Fail if lockfile is outdated (prevents accidental updates)
- `--dev`: Include development dependencies (default in uv)
- `--all-extras`: Include all optional dependencies (if needed)
- `--no-install-project`: Skip installing the project itself (useful for multi-step builds)

**Real-world pattern:**
```yaml
- name: Install dependencies
  run: uv sync --locked --all-extras --dev
```

#### 4. **Quality Gates (Linting & Testing)**
Use `uv run` to execute tools in the synced environment:
```yaml
- name: Lint with ruff
  run: uv run ruff check .

- name: Format check
  run: uv run ruff format --check .

- name: Run tests
  run: uv run pytest tests/
```

#### 5. **Caching Strategy**
**Built-in (Recommended):**
```yaml
- uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true
    cache-dependency-glob: |
      pyproject.toml
      uv.lock
```

**Manual (for self-hosted runners):**
```yaml
env:
  UV_CACHE_DIR: /tmp/.uv-cache

- uses: actions/cache@v5
  with:
    path: /tmp/.uv-cache
    key: uv-${{ runner.os }}-${{ hashFiles('uv.lock') }}
    restore-keys: |
      uv-${{ runner.os }}-${{ hashFiles('uv.lock') }}
      uv-${{ runner.os }}

- name: Minimize cache
  run: uv cache prune --ci
```

### Platform-Specific Considerations

#### Linux (ubuntu-latest)
- Standard setup works out-of-box
- Cache directory: `/tmp/.uv-cache`
- No special flags needed

#### Windows (windows-latest)
- Use `shell: bash` for cross-platform compatibility
- Cache directory: `%TEMP%\.uv-cache` or use `${{ runner.temp }}`
- Example:
```yaml
- name: Install dependencies
  shell: bash
  run: uv sync --locked
```

#### macOS (macos-latest)
- Works identically to Linux
- Cache directory: `/var/folders/.../` or `/tmp/.uv-cache`

### Real-World Examples (from GitHub)

**Microsoft AutoGen** (checks.yml):
```yaml
- uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- run: uv sync --locked --all-extras
```

**FastAPI** (build-docs.yml):
```yaml
- uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true
    cache-dependency-glob: |
      pyproject.toml
      uv.lock
- name: Install docs extras
  run: uv sync --locked --no-dev --group docs
```

**Pydantic** (ci.yml):
```yaml
- uses: astral-sh/setup-uv@v7
  with:
    python-version: ${{ matrix.python-version }}
- run: uv sync --group testing-extra
```

### Matrix Testing (Multiple Python Versions)

```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12", "3.13"]

steps:
  - uses: astral-sh/setup-uv@v7
    with:
      python-version: ${{ matrix.python-version }}
  - run: uv sync --locked
  - run: uv run pytest tests/
```

### Minimal Quality Gate Workflow

```yaml
name: CI

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      
      - uses: actions/setup-python@v6
        with:
          python-version-file: ".python-version"
      
      - name: Install dependencies
        run: uv sync --locked --all-extras --dev
      
      - name: Lint
        run: uv run ruff check .
      
      - name: Format check
        run: uv run ruff format --check .
      
      - name: Tests
        run: uv run pytest tests/
```

### Key Gotchas & Best Practices

1. **Always use `--locked` in CI** - Prevents accidental lockfile updates
2. **Pin uv version** - Ensures reproducible builds across time
3. **Use `cache-dependency-glob`** - Include both `pyproject.toml` and `uv.lock`
4. **Separate lint/format/test jobs** - Allows parallel execution and clearer failure messages
5. **Use `uv run` for all tool invocations** - Ensures tools run in the synced environment
6. **For Windows, use `shell: bash`** - Ensures cross-platform compatibility
7. **Cache pruning** - Use `uv cache prune --ci` to keep cache size manageable

### Flags Reference

| Flag | Purpose | CI Use |
|------|---------|--------|
| `--locked` | Fail if lockfile outdated | ✅ Always in CI |
| `--dev` | Include dev dependencies | ✅ Default, include explicitly |
| `--all-extras` | Include all optional deps | ⚠️ Only if needed |
| `--no-dev` | Exclude dev dependencies | ⚠️ For production builds |
| `--no-install-project` | Skip project installation | ⚠️ For multi-step builds |
| `--frozen` | Use lockfile without checking | ❌ Avoid in CI |


## Task 1: Tool Surface Mapping (Upstream Baseline Analysis)

### Execution Date
2026-02-13

### Objective
Map all `@mcp.tool()` decorators, their signatures, and required environment variables from upstream `kisti-mcp-server.py` to establish reproducible baseline for test scaffolding.

### Findings

#### Tool Inventory (12 total)

**ScienceON Service (7 tools)**
- `search_scienceon_papers(query: str, max_results: int = 10) -> str` [line 2727]
- `search_scienceon_paper_details(cn: str) -> str` [line 2748]
- `search_scienceon_patents(query: str, max_results: int = 10) -> str` [line 2767]
- `search_scienceon_patent_details(cn: str) -> str` [line 2788]
- `search_scienceon_patent_citations(cn: str) -> str` [line 2807]
- `search_scienceon_reports(query: str, max_results: int = 10) -> str` [line 2826]
- `search_scienceon_report_details(cn: str) -> str` [line 2847]

**NTIS Service (3 tools)**
- `search_ntis_rnd_projects(query: str, max_results: int = 10) -> str` [line 2888]
- `search_ntis_science_tech_classifications(query: str = "", classification_type: str = "standard", max_results: int = 10, research_goal: str = "", research_content: str = "", expected_effect: str = "", korean_keywords: str = "", english_keywords: str = "") -> str` [line 2952]
- `search_ntis_related_content_recommendations(pjt_id: str, max_results: int = 15) -> str` [line 2979]

**DataON Service (2 tools)**
- `search_dataon_research_data(query: str, max_results: int = 10, from_pos: int = 0, sort_con: str = "", sort_arr: str = "desc") -> str` [line 3011]
- `search_dataon_research_data_details(svc_id: str) -> str` [line 3039]

#### Environment Variables (6 total)

**ScienceON (3 vars, all required)**
- `SCIENCEON_API_KEY` [line 749] - accessed via `os.getenv() or env_vars.get()`
- `SCIENCEON_CLIENT_ID` [line 750] - accessed via `os.getenv() or env_vars.get()`
- `SCIENCEON_MAC_ADDRESS` [line 751] - accessed via `os.getenv() or env_vars.get()`
- Validation: `ScienceONClient._validate_credentials()` [line 756] raises `ValueError` if any missing

**NTIS (1 var, optional with warning)**
- `NTIS_API_KEY` [line 132] - accessed via `os.getenv() or env_vars.get()`
- Validation: `NTISClient._validate_credentials()` [line 138] logs warning if missing, does not raise

**DataON (2 vars, all required)**
- `DataON_ResearchData_API_KEY` [line 961] - accessed via `os.getenv() or env_vars.get()`
- `DataON_ResearchDataMetadata_API_KEY` [line 962] - accessed via `os.getenv() or env_vars.get()`
- Validation: `DataONClient._validate_credentials()` [line 968] raises `ValueError` if any missing

#### Early-Import Side Effects (CRITICAL)

Service initialization occurs at module import time (lines 2700-2720):

1. **ScienceON** [lines 2700-2704]
   - Instantiates `ScienceONClient()` → triggers `_validate_credentials()` → raises `ValueError` if env vars missing
   - Caught by try/except → sets `search_service = None`
   - All 7 ScienceON tools check `if search_service is None` and return error string

2. **NTIS** [lines 2706-2710]
   - Instantiates `NTISClient()` → triggers `_validate_credentials()` → logs warning if env var missing
   - Caught by try/except → sets `ntis_search_service = None`
   - All 3 NTIS tools check `if ntis_search_service is None` and return error string

3. **DataON** [lines 2712-2716]
   - Instantiates `DataONClient()` → triggers `_validate_credentials()` → raises `ValueError` if env vars missing
   - Caught by try/except → sets `dataon_search_service = None`
   - All 2 DataON tools check `if dataon_search_service is None` and return error string

**Implication**: Tests MUST inject all 6 env vars before importing server module, or services will be None and tools will return error strings (not exceptions).

#### Test Scaffolding Requirements

**Dummy Environment Setup** (required in conftest.py):
```python
os.environ["SCIENCEON_API_KEY"] = "dummy_key"
os.environ["SCIENCEON_CLIENT_ID"] = "dummy_client"
os.environ["SCIENCEON_MAC_ADDRESS"] = "00:00:00:00:00:00"
os.environ["NTIS_API_KEY"] = "dummy_key"
os.environ["DataON_ResearchData_API_KEY"] = "dummy_key"
os.environ["DataON_ResearchDataMetadata_API_KEY"] = "dummy_key"
```

**Mock Strategy**:
- Use `respx` to mock `httpx.AsyncClient` calls
- Mock token generation (ScienceON requires AES encryption)
- Mock XML/JSON response parsing
- Mock at client level (ScienceONClient, NTISClient, DataONClient)

**Negative Test Cases**:
- Missing env vars → service init fails → tools return error strings (not exceptions)
- Invalid XML/JSON → parsing errors → tools return error strings
- Network timeouts → httpx timeout errors → tools return error strings

### Evidence
- Upstream file: `https://raw.githubusercontent.com/ansua79/kisti-mcp/main/kisti-mcp-server.py` (3045 lines)
- `.env.example` confirms all 6 env var names
- All tool decorators and env var accesses verified via grep and line-by-line inspection

### Blockers
None - baseline mapping complete and actionable.

### Next Steps
- Task 2: Add pytest/ruff/respx to pyproject.toml
- Task 4: Create tests/conftest.py with dummy env injection
- Task 4: Create tests/test_tools.py with respx mocks for each tool

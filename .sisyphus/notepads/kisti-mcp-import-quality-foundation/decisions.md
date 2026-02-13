# Decisions

Append-only notes: decisions made and rationale.

---

## Correction: Required env var names for this repo

The examples above incorrectly mention `OPENAI_API_KEY` and `SCIENCE_ON_API_KEY`.

For `ansua79/kisti-mcp`, the correct env vars (per `.env.example` and `kisti-mcp-server.py`) are:
- SCIENCEON_API_KEY
- SCIENCEON_CLIENT_ID
- SCIENCEON_MAC_ADDRESS
- NTIS_API_KEY
- DataON_ResearchData_API_KEY
- DataON_ResearchDataMetadata_API_KEY

`OPENAI_API_KEY` is not required for module import or server startup.

## Task 4: Testing Strategies for Hyphenated Filename (kisti-mcp-server.py)

### Problem Statement
The module kisti-mcp-server.py uses a hyphenated filename, which violates PEP 508 naming conventions and prevents direct import via import kisti-mcp-server. This requires non-invasive loader strategies for testing without renaming the file.

### Ranked Testing Strategies (Non-Invasive)

#### Strategy 1: runpy.run_path() - RECOMMENDED
Rank: 5/5 stars (Best for smoke tests and startup validation)

Pros:
- No import machinery manipulation needed
- Executes code in fresh namespace
- Works with any filename (hyphenated, spaces, etc.)
- Minimal setup; no sys.path manipulation
- Ideal for startup/integration tests

Cons:
- Cannot directly test individual functions without refactoring
- Module globals are isolated (not reusable across tests)
- Best for "does it run?" not "does this function work?"

Runnable Example:
```python
import runpy
import os

def test_server_startup_with_dummy_env():
    env_backup = os.environ.copy()
    try:
        os.environ['OPENAI_API_KEY'] = 'dummy-key-for-testing'
        os.environ['SCIENCE_ON_API_KEY'] = 'dummy-key-for-testing'
        
        result = runpy.run_path(
            'kisti-mcp-server.py',
            run_name='__main__'
        )
        
        assert 'XMLParser' in result or 'ScienceONClient' in result
        
    finally:
        os.environ.clear()
        os.environ.update(env_backup)
```

Windows PowerShell:
```powershell
$env:OPENAI_API_KEY = "dummy-key"
$env:SCIENCE_ON_API_KEY = "dummy-key"
uv run pytest tests/test_startup_smoke.py -v
```

Linux/CI Bash:
```bash
export OPENAI_API_KEY="dummy-key"
export SCIENCE_ON_API_KEY="dummy-key"
uv run pytest tests/test_startup_smoke.py -v
```

---

#### Strategy 2: importlib.machinery.SourceFileLoader - RECOMMENDED FOR UNIT TESTS
Rank: 4/5 stars (Best for unit testing individual functions)

Pros:
- Loads module as if it were importable
- Allows direct function/class access
- Works with hyphenated filenames
- Reusable across multiple tests
- Supports mocking and patching

Cons:
- Slightly more setup code
- Module cached in sys.modules (cleanup needed between tests)
- Requires importlib knowledge

Runnable Example:
```python
import sys
import importlib.util
from pathlib import Path
import pytest

@pytest.fixture
def kisti_server_module():
    module_path = Path(__file__).parent.parent / 'kisti-mcp-server.py'
    
    spec = importlib.util.spec_from_file_location(
        'kisti_mcp_server',
        module_path
    )
    
    module = importlib.util.module_from_spec(spec)
    sys.modules['kisti_mcp_server'] = module
    spec.loader.exec_module(module)
    
    yield module
    
    if 'kisti_mcp_server' in sys.modules:
        del sys.modules['kisti_mcp_server']

def test_xml_parser_with_valid_input(kisti_server_module):
    parser = kisti_server_module.XMLParser()
    result = parser.parse('<root><item>test</item></root>')
    assert result is not None
```

Windows PowerShell:
```powershell
$env:OPENAI_API_KEY = "dummy-key"
$env:SCIENCE_ON_API_KEY = "dummy-key"
uv run pytest tests/test_parser.py::test_xml_parser_with_valid_input -v
```

Linux/CI Bash:
```bash
export OPENAI_API_KEY="dummy-key"
export SCIENCE_ON_API_KEY="dummy-key"
uv run pytest tests/test_parser.py::test_xml_parser_with_valid_input -v
```

---

#### Strategy 3: Subprocess Smoke Test - FALLBACK
Rank: 3/5 stars (Best for integration/CI validation)

Pros:
- Completely isolated execution
- No import machinery needed
- Closest to real-world usage
- Works on any platform

Cons:
- Cannot test individual functions
- Slower (subprocess overhead)
- Harder to mock/patch
- Limited introspection

Runnable Example:
```python
import subprocess
import os
import sys

def test_server_runs_without_error():
    env = os.environ.copy()
    env['OPENAI_API_KEY'] = 'dummy-key'
    env['SCIENCE_ON_API_KEY'] = 'dummy-key'
    
    result = subprocess.run(
        [sys.executable, 'kisti-mcp-server.py', '--help'],
        capture_output=True,
        timeout=5,
        env=env,
        text=True
    )
    
    assert result.returncode in [0, 1]
```

Windows PowerShell:
```powershell
$env:OPENAI_API_KEY = "dummy-key"
$env:SCIENCE_ON_API_KEY = "dummy-key"
uv run pytest tests/test_subprocess_smoke.py -v
```

Linux/CI Bash:
```bash
export OPENAI_API_KEY="dummy-key"
export SCIENCE_ON_API_KEY="dummy-key"
uv run pytest tests/test_subprocess_smoke.py -v
```

---

### Recommended Approach for Task 4

Use Strategy 1 + Strategy 2 in combination:

1. Strategy 1 (runpy.run_path) for startup smoke tests
   - Validates module loads without syntax errors
   - Checks for required globals (classes, functions)
   - Minimal setup; fast execution

2. Strategy 2 (importlib.machinery.SourceFileLoader) for unit tests
   - Tests individual parser/client functions
   - Supports mocking with respx for HTTP calls
   - Reusable fixture in conftest.py

3. Strategy 3 (subprocess) for CI integration tests
   - Validates real-world execution
   - Runs in isolated environment
   - Catches import/runtime issues early

### Implementation Plan for Task 4

File Structure:
tests/
  conftest.py              # Fixtures: kisti_server_module, dummy_env
  test_startup_smoke.py    # Strategy 1: runpy.run_path smoke tests
  test_parser.py           # Strategy 2: XMLParser unit tests
  test_client.py           # Strategy 2: ScienceONClient unit tests (with respx)
  test_integration.py      # Strategy 3: subprocess integration tests

conftest.py Skeleton:
```python
import pytest
import os
import sys
import importlib.util
from pathlib import Path

@pytest.fixture
def dummy_env():
    env_backup = os.environ.copy()
    os.environ['OPENAI_API_KEY'] = 'test-key-12345'
    os.environ['SCIENCE_ON_API_KEY'] = 'test-key-12345'
    yield
    os.environ.clear()
    os.environ.update(env_backup)

@pytest.fixture
def kisti_server_module(dummy_env):
    module_path = Path(__file__).parent.parent / 'kisti-mcp-server.py'
    spec = importlib.util.spec_from_file_location(
        'kisti_mcp_server',
        module_path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules['kisti_mcp_server'] = module
    spec.loader.exec_module(module)
    yield module
    if 'kisti_mcp_server' in sys.modules:
        del sys.modules['kisti_mcp_server']
```

### pytest Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
markers = [
    "smoke: startup/integration smoke tests",
    "unit: unit tests with mocked dependencies",
    "integration: subprocess/real-world tests",
]
```

### Verification Commands

Windows PowerShell:
```powershell
$env:OPENAI_API_KEY = "test-key"
$env:SCIENCE_ON_API_KEY = "test-key"

uv run pytest tests/ -v
uv run pytest tests/ -m smoke -v
uv run pytest tests/test_startup_smoke.py::test_server_startup_with_dummy_env -v
```

Linux/CI Bash:
```bash
export OPENAI_API_KEY="test-key"
export SCIENCE_ON_API_KEY="test-key"

uv run pytest tests/ -v
uv run pytest tests/ -m smoke -v
uv run pytest tests/test_startup_smoke.py::test_server_startup_with_dummy_env -v
```

### Key Constraints Met

✅ No renaming of kisti-mcp-server.py
✅ No behavior changes to core server logic
✅ Works on Windows PowerShell and Linux bash
✅ Supports future mocking with respx for HTTP tests
✅ Handles ScienceON env var validation via dummy injection
✅ Minimal, non-invasive setup

### Next Steps (Task 4 Execution)

1. Create tests/conftest.py with fixtures from skeleton above
2. Create tests/test_startup_smoke.py using Strategy 1
3. Create tests/test_parser.py using Strategy 2 (if parser is exposed)
4. Create tests/test_client.py using Strategy 2 + respx mocking
5. Add pytest config to pyproject.toml
6. Run verification commands and capture output to .sisyphus/evidence/task-4-tests.txt

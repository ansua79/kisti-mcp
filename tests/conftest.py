import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture
def dummy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Required by clients at module import time.
    monkeypatch.setenv("SCIENCEON_API_KEY", "dummy")
    monkeypatch.setenv("SCIENCEON_CLIENT_ID", "dummy")
    monkeypatch.setenv("SCIENCEON_MAC_ADDRESS", "00-00-00-00-00-00")
    monkeypatch.setenv("NTIS_API_KEY", "dummy")
    monkeypatch.setenv("DataON_ResearchData_API_KEY", "dummy")
    monkeypatch.setenv("DataON_ResearchDataMetadata_API_KEY", "dummy")


@pytest.fixture
def kisti_server_module(dummy_env: None):
    module_path = Path(__file__).resolve().parent.parent / "kisti_mcp.py"

    spec = importlib.util.spec_from_file_location("kisti_mcp", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules["kisti_mcp"] = module

    spec.loader.exec_module(module)
    yield module

    sys.modules.pop("kisti_mcp", None)

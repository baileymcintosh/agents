from __future__ import annotations

import sys
import shutil
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def pytest_configure(config: pytest.Config) -> None:
    """Always route tmp_path dirs into .pytest_tmp, even when addopts is overridden."""
    try:
        if not config.option.basetemp:
            config.option.basetemp = str(ROOT / ".pytest_tmp")
    except AttributeError:
        pass
SRC = ROOT / "src"
TEST_TMP_ROOT = ROOT / "reports" / "_test_tmp"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def temp_dir() -> Path:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TMP_ROOT / f"case_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

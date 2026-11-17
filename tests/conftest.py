import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("BASIRA_HOME", str(PROJECT_ROOT / ".test_home"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("BASIRA_PROJECT_ROOT", str(PROJECT_ROOT))


@pytest.fixture()
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BASIRA_HOME", str(tmp_path))
    from basira import config

    import importlib
    importlib.reload(config)
    yield tmp_path


@pytest.fixture()
def db(tmp_home):
    from basira.db.database import Database

    database = Database(tmp_home / "test.db")
    yield database
    database.close()

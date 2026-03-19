from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
	return tmp_path / "test.db"


@pytest.fixture()
def app_client(tmp_db_path: Path):
	# Import inside fixture so tests can control db path before init.
	import db

	db.set_db_path(tmp_db_path)
	db.init_db()

	from fastapi.testclient import TestClient
	import main

	return TestClient(main.app)


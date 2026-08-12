from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
_scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
if str(_scripts_dir) not in sys.path:
	sys.path.insert(0, str(_scripts_dir))


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
	return tmp_path / "test.db"


@pytest.fixture()
def app_client(tmp_db_path: Path):
	# Import inside fixture so tests can control db path before init.
	import db
	import file_search

	db.set_db_path(tmp_db_path)
	db.init_db()
	file_search.reset_search_roots()

	from fastapi.testclient import TestClient
	import main

	return TestClient(main.app)


@pytest.fixture()
def file_search_roots(tmp_path: Path):
	"""Three isolated search roots for get_file tests."""
	import file_search

	root1 = tmp_path / "root1"
	root2 = tmp_path / "root2"
	root3 = tmp_path / "root3"
	for root in (root1, root2, root3):
		root.mkdir(parents=True, exist_ok=True)

	file_search.set_search_roots([root1, root2, root3])
	yield root1, root2, root3
	file_search.reset_search_roots()


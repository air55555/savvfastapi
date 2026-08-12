from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from helpers import write_minimal_png
import file_search


# ---------------------------------------------------------------------------
# Unit tests: file_search module
# ---------------------------------------------------------------------------


class TestValidatePngFilename:
	@pytest.mark.parametrize(
		"filename",
		[
			"image.png",
			"Image.PNG",
			"cube_26_03_16_12_37_cr10p_cheese_1_2cluster0p_1.png",
			"a-b_c.d.png",
		],
	)
	def test_accepts_safe_png_names(self, filename: str):
		assert file_search.validate_png_filename(filename) == filename

	@pytest.mark.parametrize(
		"filename,expected_detail",
		[
			("", "filename is required"),
			("   ", "filename is required"),
			("../secret.png", "filename must not contain path separators"),
			("subdir/image.png", "filename must not contain path separators"),
			(r"..\..\windows.png", "filename must not contain path separators"),
			("/etc/passwd.png", "filename must not contain path separators"),
			("C:\\temp\\image.png", "filename must not contain path separators"),
			("..png", "filename must not contain '..'"),
			("image.jpg", "filename must be a .png file with safe characters"),
			("image.png.exe", "filename must be a .png file with safe characters"),
			("image png.png", "filename must be a .png file with safe characters"),
			("image$.png", "filename must be a .png file with safe characters"),
		],
	)
	def test_rejects_unsafe_or_invalid_names(self, filename: str, expected_detail: str):
		with pytest.raises(ValueError, match=expected_detail):
			file_search.validate_png_filename(filename)


class TestFindPngFile:
	def test_finds_file_in_first_root(self, file_search_roots):
		root1, root2, _root3 = file_search_roots
		expected = write_minimal_png(root1 / "first.png")

		found = file_search.find_png_file("first.png")
		assert found is not None
		assert found.path == (root1 / "first.png").resolve()
		assert found.root == root1.resolve()
		assert found.size_bytes == len(expected)

	def test_skips_first_root_and_finds_in_second(self, file_search_roots):
		root1, root2, _root3 = file_search_roots
		expected = write_minimal_png(root2 / "second_root.png")

		found = file_search.find_png_file("second_root.png")
		assert found is not None
		assert found.path == (root2 / "second_root.png").resolve()
		assert found.root == root2.resolve()
		assert found.size_bytes == len(expected)

	def test_prefers_first_root_when_same_name_in_multiple_roots(self, file_search_roots):
		root1, root2, root3 = file_search_roots
		write_minimal_png(root1 / "dup.png", color=(255, 0, 0))
		write_minimal_png(root2 / "dup.png", color=(0, 255, 0))
		write_minimal_png(root3 / "dup.png", color=(0, 0, 255))

		found = file_search.find_png_file("dup.png")
		assert found is not None
		assert found.root == root1.resolve()

	def test_returns_none_when_not_found(self, file_search_roots):
		assert file_search.find_png_file("missing.png") is None

	def test_rejects_path_traversal_even_if_file_exists(self, file_search_roots):
		root1, _, _ = file_search_roots
		write_minimal_png(root1 / "safe.png")

		with pytest.raises(ValueError):
			file_search.find_png_file("../root1/safe.png")

	def test_stat_metadata_populated(self, file_search_roots):
		root1, _, _ = file_search_roots
		path = root1 / "meta.png"
		write_minimal_png(path)

		found = file_search.find_png_file("meta.png")
		assert found is not None
		assert found.size_bytes == path.stat().st_size
		assert found.modified_at.tzinfo == timezone.utc
		assert isinstance(found.modified_at, datetime)


class TestSearchRootConfiguration:
	def test_set_and_reset_search_roots(self, tmp_path: Path):
		custom = tmp_path / "custom"
		custom.mkdir()
		write_minimal_png(custom / "custom.png")

		file_search.set_search_roots([custom])
		found = file_search.find_png_file("custom.png")
		assert found is not None
		assert found.root == custom.resolve()

		file_search.reset_search_roots()
		# Default roots should not contain our temp file.
		assert file_search.find_png_file("custom.png") is None

	def test_env_override_parsed_as_comma_separated_list(self, tmp_path: Path, monkeypatch):
		root_a = tmp_path / "env_a"
		root_b = tmp_path / "env_b"
		root_a.mkdir()
		root_b.mkdir()
		write_minimal_png(root_b / "from_env.png")

		monkeypatch.setenv("SAVVFASTAPI_FILE_SEARCH_ROOTS", f"{root_a},{root_b}")
		file_search.reset_search_roots()

		found = file_search.find_png_file("from_env.png")
		assert found is not None
		assert found.root == root_b.resolve()

	def test_default_search_roots_are_path_objects(self):
		file_search.reset_search_roots()
		roots = file_search.get_search_roots()
		assert len(roots) >= 1
		assert all(isinstance(root, Path) for root in roots)

	def test_find_png_file_does_not_crash_with_default_roots(self):
		file_search.reset_search_roots()
		# Should return None (not found) or a match — never raise TypeError.
		result = file_search.find_png_file("cube_11_08_11_20_24_cheese_2_detect.png")
		assert result is None or isinstance(result, file_search.FoundFile)

# ---------------------------------------------------------------------------
# API integration tests: GET /api/get_file
# ---------------------------------------------------------------------------


class TestGetFileEndpoint:
	def test_returns_png_with_correct_content_type(self, app_client, file_search_roots):
		root1, _, _ = file_search_roots
		expected_bytes = write_minimal_png(root1 / "preview.png")

		response = app_client.get("/api/get_file", params={"filename": "preview.png"})
		assert response.status_code == 200
		assert response.headers["content-type"].startswith("image/png")
		assert response.content == expected_bytes

	def test_returns_metadata_headers(self, app_client, file_search_roots):
		root1, _, _ = file_search_roots
		path = root1 / "with_meta.png"
		write_minimal_png(path)

		response = app_client.get("/api/get_file", params={"filename": "with_meta.png"})
		assert response.status_code == 200
		assert response.headers["x-file-name"] == "with_meta.png"
		assert int(response.headers["x-file-size"]) == path.stat().st_size
		assert response.headers["x-search-root"] == str(root1.resolve())
		assert "T" in response.headers["x-file-modified"]  # ISO-8601

	def test_404_when_file_missing(self, app_client, file_search_roots):
		response = app_client.get("/api/get_file", params={"filename": "no_such_file.png"})
		assert response.status_code == 404
		assert "not found" in response.json()["detail"].lower()

	def test_400_for_invalid_filename(self, app_client, file_search_roots):
		response = app_client.get("/api/get_file", params={"filename": "../escape.png"})
		assert response.status_code == 400
		assert "path separators" in response.json()["detail"].lower()

	def test_422_when_filename_query_param_missing(self, app_client):
		response = app_client.get("/api/get_file")
		assert response.status_code == 422

	@pytest.mark.parametrize(
		"bad_filename",
		[
			"../secret.png",
			"folder/image.png",
			"photo.jpg",
			"",
		],
	)
	def test_400_or_422_for_bad_filenames(self, app_client, file_search_roots, bad_filename: str):
		response = app_client.get("/api/get_file", params={"filename": bad_filename})
		assert response.status_code in {400, 422}

	def test_search_order_first_root_wins(self, app_client, file_search_roots):
		root1, root2, _ = file_search_roots
		first_bytes = write_minimal_png(root1 / "priority.png", color=(255, 0, 0))
		write_minimal_png(root2 / "priority.png", color=(0, 255, 0))

		response = app_client.get("/api/get_file", params={"filename": "priority.png"})
		assert response.status_code == 200
		assert response.content == first_bytes
		assert response.headers["x-search-root"] == str(root1.resolve())

	def test_falls_back_to_later_root(self, app_client, file_search_roots):
		_root1, root2, _root3 = file_search_roots
		expected_bytes = write_minimal_png(root2 / "only_in_second.png")

		response = app_client.get("/api/get_file", params={"filename": "only_in_second.png"})
		assert response.status_code == 200
		assert response.content == expected_bytes
		assert response.headers["x-search-root"] == str(root2.resolve())

	def test_case_insensitive_png_extension_in_filename(self, app_client, file_search_roots):
		root1, _, _ = file_search_roots
		# File on disk uses lowercase .png
		write_minimal_png(root1 / "MixedCase.PNG".lower())

		response = app_client.get("/api/get_file", params={"filename": "MixedCase.PNG"})
		assert response.status_code == 200

	def test_content_disposition_uses_filename(self, app_client, file_search_roots):
		root1, _, _ = file_search_roots
		write_minimal_png(root1 / "download_me.png")

		response = app_client.get("/api/get_file", params={"filename": "download_me.png"})
		assert response.status_code == 200
		assert "download_me.png" in response.headers.get("content-disposition", "")

	def test_logs_request_via_middleware(self, app_client, file_search_roots):
		root1, _, _ = file_search_roots
		write_minimal_png(root1 / "logged.png")

		_ = app_client.get("/api/get_file", params={"filename": "logged.png"})
		logs = app_client.get("/api/logs?limit=10").json()
		paths = [row["path"] for row in logs]
		assert "/api/get_file" in paths

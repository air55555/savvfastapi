from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Comma-separated list of directories searched in order (first match wins).
_DEFAULT_SEARCH_ROOTS = [
	"D:\HSM_CAPTURE_ANALYSIS\Defect_Cheese",
	_PROJECT_ROOT / "HSM_CAPTURE",
	_PROJECT_ROOT / "HSM_detect_2clust",
]

_search_roots: list[Path] | None = None

_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.png$", re.IGNORECASE)


@dataclass(frozen=True)
class FoundFile:
	path: Path
	root: Path
	size_bytes: int
	modified_at: datetime
	created_at: datetime | None


def _parse_roots_from_env() -> list[Path]:
	raw = os.getenv("SAVVFASTAPI_FILE_SEARCH_ROOTS", "").strip()
	if not raw:
		return list(_DEFAULT_SEARCH_ROOTS)
	return [Path(part.strip()) for part in raw.split(",") if part.strip()]


def get_search_roots() -> list[Path]:
	global _search_roots
	if _search_roots is None:
		_search_roots = _parse_roots_from_env()
	return list(_search_roots)


def set_search_roots(roots: list[Path | str]) -> None:
	"""Override search roots (used in tests)."""
	global _search_roots
	_search_roots = [Path(root) for root in roots]


def reset_search_roots() -> None:
	"""Restore search roots from environment/default configuration."""
	global _search_roots
	_search_roots = None


def validate_png_filename(filename: str) -> str:
	"""
	Validate and normalize a PNG filename (basename only, no path components).

	Raises ValueError when the name is unsafe or not a .png file.
	"""
	if not filename or not isinstance(filename, str):
		raise ValueError("filename is required")

	name = filename.strip()
	if not name:
		raise ValueError("filename is required")

	# Reject any path separators or absolute paths early.
	if name != Path(name).name:
		raise ValueError("filename must not contain path separators")
	if Path(name).is_absolute():
		raise ValueError("filename must not be an absolute path")
	if ".." in name:
		raise ValueError("filename must not contain '..'")

	if not _SAFE_FILENAME_RE.match(name):
		raise ValueError("filename must be a .png file with safe characters")

	return name


def _stat_datetime(ts: float) -> datetime:
	return datetime.fromtimestamp(ts, tz=timezone.utc)


def find_png_file(filename: str, roots: list[Path] | None = None) -> FoundFile | None:
	"""
	Search roots in order for filename. Return metadata for the first existing file.
	"""
	safe_name = validate_png_filename(filename)
	search_roots = roots if roots is not None else get_search_roots()

	for root in search_roots:
		candidate = (root / safe_name).resolve()
		root_resolved = root.resolve()

		# Ensure resolved path stays inside the configured root.
		try:
			candidate.relative_to(root_resolved)
		except ValueError:
			continue

		if not candidate.is_file():
			continue

		stat = candidate.stat()
		created_at = None
		if hasattr(stat, "st_birthtime"):
			created_at = _stat_datetime(stat.st_birthtime)
		elif os.name == "nt":
			created_at = _stat_datetime(stat.st_ctime)

		return FoundFile(
			path=candidate,
			root=root_resolved,
			size_bytes=stat.st_size,
			modified_at=_stat_datetime(stat.st_mtime),
			created_at=created_at,
		)

	return None

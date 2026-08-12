"""
Look up SSCC (and full palletes_scan row) by cube / HDR name.

Matches rows where Msg or Details contain the cube key, e.g.:
  Details: source=cube_24_05_10_20_39/cube_24_05_10_20_39_cheese_2.hdr; ...
  Msg:     hsm_ingest:cube_24_05_10_20_39/cube_24_05_10_20_39_cheese_2.hdr

Accepts folder paths, .hdr paths, HDR stems, or cube folder names.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_connection, set_db_path  # noqa: E402

HDR_STEM_RE = re.compile(
	r"^(cube_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}(?:_cr\d+p)?_cheese_\d+)",
	re.IGNORECASE,
)
CUBE_PREFIX_RE = re.compile(r"^(cube_\d{2}_\d{2}_\d{2}_\d{2}_\d{2})")


def _basename_stem(name: str) -> str:
	"""Strip path, hsm_ingest: prefix, and .hdr extension."""
	text = name.strip().replace("\\", "/")
	if ":" in text:
		text = text.split(":", 1)[1]
	text = text.rsplit("/", 1)[-1]
	if text.lower().endswith(".hdr"):
		text = text[:-4]
	return text


def parse_cubename(cubename: str) -> tuple[Optional[str], Optional[str]]:
	"""
	Return (hdr_stem, cube_prefix) parsed from various cube name formats.
	"""
	stem = _basename_stem(cubename)
	hdr_match = HDR_STEM_RE.match(stem)
	if hdr_match:
		hdr_stem = hdr_match.group(1)
		cube_match = CUBE_PREFIX_RE.match(hdr_stem)
		return hdr_stem, cube_match.group(1) if cube_match else None

	cube_match = CUBE_PREFIX_RE.match(stem)
	if cube_match:
		return None, cube_match.group(1)

	return None, None


def fetch_palletes_scan_by_key(key: str) -> Optional[dict]:
	conn = get_connection()
	try:
		cur = conn.execute(
			"""
			SELECT id, IDPoint, SSCC, Details, Status, Result, Msg, created_at
			FROM palletes_scan
			WHERE Msg LIKE '%' || ? || '%' OR Details LIKE '%' || ? || '%'
			ORDER BY id DESC
			LIMIT 1
			""",
			(key, key),
		)
		row = cur.fetchone()
		return dict(row) if row else None
	finally:
		conn.close()


def get_palletes_scan_by_cubename(cubename: str) -> Optional[dict]:
	"""
	Return the newest palletes_scan row for a cube / HDR name, or None.
	"""
	hdr_stem, cube_prefix = parse_cubename(cubename)
	if hdr_stem:
		row = fetch_palletes_scan_by_key(hdr_stem)
		if row:
			return row
	if cube_prefix:
		return fetch_palletes_scan_by_key(cube_prefix)
	return None


def _run_ingest_hsm_capture() -> None:
	_scripts = Path(__file__).resolve().parent
	if str(_scripts) not in sys.path:
		sys.path.insert(0, str(_scripts))
	import ingest_hsm_capture  # noqa: E402

	argv = sys.argv
	try:
		sys.argv = ["ingest_hsm_capture"]
		ingest_hsm_capture.main()
	finally:
		sys.argv = argv


def get_sscc_by_cubename(cubename: str) -> Optional[str]:
	"""Return SSCC for a cube / HDR name, or None if not found."""
	_run_ingest_hsm_capture()
	row = get_palletes_scan_by_cubename(cubename)
	return str(row["SSCC"]) if row else None


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Look up SSCC from palletes_scan by cube / HDR name."
	)
	parser.add_argument(
		"cubename",
		help="Cube folder, HDR path, or stem (e.g. cube_24_05_10_20_39_cheese_2)",
	)
	parser.add_argument(
		"--db",
		help="Path to savvfastapi SQLite DB (default: SAVVFASTAPI_DB_PATH or ./savvfastapi.db)",
	)
	parser.add_argument(
		"--full",
		action="store_true",
		help="Print full palletes_scan row instead of SSCC only",
	)
	args = parser.parse_args()

	if args.db:
		set_db_path(args.db)

	row = get_palletes_scan_by_cubename(args.cubename)
	if not row:
		print(f"No palletes_scan row for cubename={args.cubename!r}", file=sys.stderr)
		return 1

	if args.full:
		for key in ("id", "IDPoint", "SSCC", "Details", "Status", "Result", "Msg", "created_at"):
			print(f"{key}\t{row[key]}")
	else:
		print(row["SSCC"])
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

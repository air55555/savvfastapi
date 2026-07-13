"""
Insert one sample bg_analyze row into palletes_scan.

Usage:
  python scripts/seed_bg_analyze_sample_data.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
from db import init_db, insert_palletes_scan  # noqa: E402
from scripts.get_sscc_by_cubename import get_sscc_by_cubename

def write_bg_analyze_sample_row() -> None:
	"""Write one sample bg_analyze row into palletes_scan."""
	init_db()

	sscc = get_sscc_by_cubename("cube_27_03_18_11_16")

	print(sscc)

	insert_palletes_scan(
		'Сыр п/т"БЛголл"мдж45%вес       ',
		sscc,
		(
			"bg_analyze file=cube_27_03_18_11_16_cr10p_cheese_1_2cluster0p.png; "
			"match=RT; key=cube_27_03_18_11_16_cr10p_cheese_1; "
			"bg_pct=99.979572; other_pct=0.020428; matched_palletes_scan_id=4306"
		),
		"analyzed",
		"99.9796",
		"0.0204",
	)


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Insert one sample bg_analyze row into palletes_scan."
	)
	parser.add_argument(
		"--db-path",
		type=Path,
		default=None,
		help="Optional SQLite DB path (default: savvfastapi.db or SAVVFASTAPI_DB_PATH)",
	)
	args = parser.parse_args()

	if args.db_path is not None:
		db.set_db_path(args.db_path)

	write_bg_analyze_sample_row()
	print(f"Inserted 1 bg_analyze sample row into {db.DB_PATH}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

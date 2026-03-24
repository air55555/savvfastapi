from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1]))

from db import get_connection, init_db  # noqa: E402


FOLDER_RE = re.compile(r"^cube_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})$")
CHEESE_HDR_RE = re.compile(r".*_cheese_\d+\.hdr$", re.IGNORECASE)
HSM_CAPTURE_ROOT = Path(r"D:\HSM_CAPTURE")


def parse_hdr_sizes(hdr_path: Path) -> Tuple[Optional[int], Optional[int]]:
	samples = None
	lines = None
	for raw in hdr_path.read_text(encoding="utf-8", errors="ignore").splitlines():
		line = raw.strip()
		if "=" not in line:
			continue
		key, value = [x.strip().lower() for x in line.split("=", 1)]
		if key == "samples":
			try:
				samples = int(value)
			except ValueError:
				pass
		elif key == "lines":
			try:
				lines = int(value)
			except ValueError:
				pass
	return samples, lines


def folder_timestamp(folder: Path) -> Optional[datetime]:
	m = FOLDER_RE.match(folder.name)
	if not m:
		return None
	day, month, hour, minute, second = [int(x) for x in m.groups()]
	year = datetime.fromtimestamp(folder.stat().st_mtime).year
	try:
		return datetime(year, month, day, hour, minute, second)
	except ValueError:
		return None


def nearest_set_pallet_request(ts: datetime, tolerance_seconds: int) -> Optional[Dict]:
	start = (ts - timedelta(seconds=tolerance_seconds)).strftime("%Y-%m-%d %H:%M:%S")
	end = (ts + timedelta(seconds=tolerance_seconds)).strftime("%Y-%m-%d %H:%M:%S")
	target = ts.strftime("%Y-%m-%d %H:%M:%S")

	conn = get_connection()
	try:
		cur = conn.execute(
			"""
			SELECT id, SSCC, IDPoint, Message, Weight, created_at
			FROM set_pallet_requests
			WHERE created_at BETWEEN ? AND ?
			ORDER BY ABS((julianday(created_at) - julianday(?)) * 86400.0) ASC, id DESC
			LIMIT 1
			""",
			(start, end, target),
		)
		row = cur.fetchone()
		return dict(row) if row else None
	finally:
		conn.close()


def upsert_scan_row(
	id_point: str,
	sscc: str,
	details: str,
	status: str,
	result: str,
	msg: str,
) -> bool:
	"""
	Insert a scan row only once for this exact source marker (Msg).
	Returns True when inserted, False when already exists.
	"""
	conn = get_connection()
	try:
		conn.execute("BEGIN IMMEDIATE")
		existing = conn.execute(
			"SELECT id FROM palletes_scan WHERE Msg = ? LIMIT 1",
			(msg,),
		).fetchone()
		if existing:
			conn.commit()
			return False

		conn.execute(
			"""
			INSERT INTO palletes_scan(IDPoint, SSCC, Details, Status, Result, Msg)
			VALUES(?, ?, ?, ?, ?, ?)
			""",
			(id_point, sscc, details, status, result, msg),
		)
		conn.commit()
		return True
	except Exception:
		conn.rollback()
		raise
	finally:
		conn.close()


def process_folder(folder: Path, tolerance_seconds: int) -> Tuple[int, int]:
	ts = folder_timestamp(folder)
	if ts is None:
		return 0, 0

	req = nearest_set_pallet_request(ts, tolerance_seconds=tolerance_seconds)
	sscc = req["SSCC"] if req else "UNKNOWN_SSCC"
	id_point = req["IDPoint"] if req else "UNKNOWN_IDPOINT"
	if req:
		# Write SSCC marker filename without extension into cube folder.
		(folder / sscc).write_text(sscc, encoding="utf-8")

	inserted = 0
	skipped = 0
	for hdr in sorted(folder.iterdir()):
		if not hdr.is_file() or not CHEESE_HDR_RE.match(hdr.name):
			continue
		w, h = parse_hdr_sizes(hdr)
		details = f"source={folder.name}/{hdr.name}; w={w if w is not None else 'NA'}; h={h if h is not None else 'NA'}"
		msg = f"hsm_ingest:{folder.name}/{hdr.name}"
		ok = upsert_scan_row(
			id_point=id_point,
			sscc=sscc,
			details=details,
			status="Scanned",
			result="Ok" if (w and h) else "InvalidHDR",
			msg=msg,
		)
		if ok:
			inserted += 1
		else:
			skipped += 1
	return inserted, skipped


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Ingest newest HSM_CAPTURE cube folders and write parsed cheese HDR sizes to palletes_scan."
	)
	parser.add_argument("--root", default=str(HSM_CAPTURE_ROOT), help="Root folder with cube_* dirs")
	parser.add_argument("--tolerance-seconds", type=int, default=5, help="Time match window for set_pallet_requests")
	parser.add_argument("--limit-folders", type=int, default=0, help="Process only newest N folders (0 = all)")
	args = parser.parse_args()

	root = Path(args.root)
	if not root.exists():
		print(f"Root does not exist: {root}")
		return 1

	init_db()

	cube_dirs = [d for d in root.iterdir() if d.is_dir() and d.name.startswith("cube_")]
	cube_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)  # newest first
	if args.limit_folders > 0:
		cube_dirs = cube_dirs[: args.limit_folders]

	total_inserted = 0
	total_skipped = 0
	for folder in cube_dirs:
		inserted, skipped = process_folder(folder, tolerance_seconds=args.tolerance_seconds)
		if inserted or skipped:
			print(f"{folder.name}: inserted={inserted}, skipped={skipped}")
		total_inserted += inserted
		total_skipped += skipped

	print(f"Done. total_inserted={total_inserted}, total_skipped={total_skipped}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())


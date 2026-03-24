from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1]))

from db import get_connection, init_db  # noqa: E402


DEFAULT_ROOT = Path("HSM_CAPTURE")


def _folder_name(ts: datetime) -> str:
	return f"cube_{ts.day:02d}_{ts.month:02d}_{ts.hour:02d}_{ts.minute:02d}_{ts.second:02d}"


def _envi_hdr(samples: int, lines: int) -> str:
	return (
		"ENVI\n"
		"description = {\n"
		"  Specim FX10E hyperspectral cube}\n"
		f"samples = {samples}\n"
		f"lines = {lines}\n"
		"bands = 114\n"
		"header offset = 0\n"
		"file type = ENVI Standard\n"
		"data type = 4\n"
		"interleave = bil\n"
		"byte order = 0\n"
		"exposure time = 2000.0\n"
		"exposure time units = microseconds\n"
	)


def _write_small_file(path: Path, content: bytes) -> None:
	path.write_bytes(content)


def _set_mtime(path: Path, ts: datetime) -> None:
	epoch = ts.timestamp()
	time.sleep(0.01)
	path.touch(exist_ok=True)
	path = path.resolve()
	import os
	os.utime(path, (epoch, epoch))


def _insert_set_pallet_request(sscc: str, id_point: str, created_at: datetime) -> None:
	conn = get_connection()
	try:
		conn.execute(
			"""
			INSERT INTO set_pallet_requests(SSCC, IDPoint, Message, Weight, created_at)
			VALUES(?, ?, ?, ?, ?)
			""",
			(sscc, id_point, "PalletOnID", 123.45, created_at.strftime("%Y-%m-%d %H:%M:%S")),
		)
		conn.commit()
	finally:
		conn.close()


def build_test_data(root: Path, count: int) -> List[Tuple[Path, str]]:
	root.mkdir(parents=True, exist_ok=True)
	init_db()

	now = datetime.now().replace(microsecond=0)
	result: List[Tuple[Path, str]] = []
	for i in range(count):
		# Newest first, each folder shifted by 1 minute.
		base = now - timedelta(minutes=i)
		folder = root / _folder_name(base)
		folder.mkdir(parents=True, exist_ok=True)

		base_name = folder.name
		main_hdr = folder / f"{base_name}.hdr"
		main_img = folder / f"{base_name}.img"
		cheese1_hdr = folder / f"{base_name}_cheese_1.hdr"
		cheese1_img = folder / f"{base_name}_cheese_1.img"
		cheese2_hdr = folder / f"{base_name}_cheese_2.hdr"
		cheese2_img = folder / f"{base_name}_cheese_2.img"
		preview = folder / f"preview_{base_name.replace('cube_', '')}.png"

		main_hdr.write_text(_envi_hdr(640, 320), encoding="utf-8")
		cheese1_hdr.write_text(_envi_hdr(639, 325), encoding="utf-8")
		cheese2_hdr.write_text(_envi_hdr(512, 241), encoding="utf-8")
		_write_small_file(main_img, b"\x00" * 1024)
		_write_small_file(cheese1_img, b"\x01" * 512)
		_write_small_file(cheese2_img, b"\x02" * 512)
		_write_small_file(preview, b"\x89PNG\r\n\x1a\n")

		for p in [main_hdr, main_img, cheese1_hdr, cheese1_img, cheese2_hdr, cheese2_img, preview]:
			_set_mtime(p, base)
		_set_mtime(folder, base)

		sscc = f"TESTSSCC{i+1:06d}"
		id_point = f"ID{(i % 3) + 1}"
		# Tie DB record to folder time exactly (ingester tolerance is +-5s).
		_insert_set_pallet_request(sscc=sscc, id_point=id_point, created_at=base)

		# Write SSCC marker filename without extension inside cube dir.
		(folder / sscc).write_text(sscc, encoding="utf-8")
		result.append((folder, sscc))

	return result


def main() -> int:
	parser = argparse.ArgumentParser(description="Create HSM_CAPTURE test dirs/files and tie folder times to set_pallet_requests.")
	parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Target HSM_CAPTURE root directory")
	parser.add_argument("--count", type=int, default=3, help="Number of cube_* folders to create")
	args = parser.parse_args()

	created = build_test_data(Path(args.root), args.count)
	print(f"Created {len(created)} folders under: {Path(args.root).resolve()}")
	for folder, sscc in created:
		print(f"{folder.name} -> SSCC={sscc}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())


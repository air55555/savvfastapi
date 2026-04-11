"""
Analyze PNGs: background %% (max RGB bin), then insert palletes_scan rows.

Matches existing ingest rows by HDR stem, e.g. Msg/Details contain
  cube_26_03_16_02_13_cr10p_cheese_1
as in: hsm_ingest:cube_26_03_16_02_13/cube_26_03_16_02_13_cr10p_cheese_1.hdr
Cube-only matching is wrong when one cube has several cheeses (different SSCC).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
from db import get_connection, init_db, insert_palletes_scan  # noqa: E402

import importlib.util  # noqa: E402

_helpers = Path(__file__).resolve().parent / "find_similar_middle_particles.py"
_spec = importlib.util.spec_from_file_location("find_similar_middle_particles", _helpers)
_fsmp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fsmp)
load_rgb = _fsmp.load_rgb
stats_background_and_other = _fsmp.stats_background_and_other

# PNG examples:
#   cube_26_03_16_02_13_cr10p_cheese_1_10cluster0p.png  -> stem matches .hdr in Msg
#   cube_27_03_12_21_51_cheese_3_cluster.png              -> optional _crNp
HDR_STEM_RE = re.compile(
	r"^(cube_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}(?:_cr\d+p)?_cheese_\d+)",
	re.IGNORECASE,
)
CUBE_PREFIX_RE = re.compile(r"^(cube_\d{2}_\d{2}_\d{2}_\d{2}_\d{2})")


def hdr_stem_from_png_filename(name: str) -> Optional[str]:
	m = HDR_STEM_RE.match(name)
	return m.group(1) if m else None


def cube_key_from_filename(name: str) -> Optional[str]:
	m = CUBE_PREFIX_RE.match(name)
	return m.group(1) if m else None


def fetch_palletes_scan_by_substring(key: str) -> Optional[dict]:
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


def resolve_source_row(filename: str) -> tuple[Optional[dict], str, str]:
	"""
	Returns (row, match_kind, key_used).
	match_kind: 'hdr_stem' | 'cube_fallback' | 'none'
	"""
	stem = hdr_stem_from_png_filename(filename)
	if stem:
		row = fetch_palletes_scan_by_substring(stem)
		if row:
			return row, "hdr_stem", stem

	cube_key = cube_key_from_filename(filename)
	if cube_key:
		row = fetch_palletes_scan_by_substring(cube_key)
		if row:
			return row, "cube_fallback", cube_key

	return None, "none", stem or cube_key or ""


def process_file(path: Path, dry_run: bool) -> tuple[bool, str]:
	img = load_rgb(path)
	_bg, bg_pct, other_pct, _n_oc, _off, _n_bg, _n_o = stats_background_and_other(img)
	msg_value = f"{100.0 - bg_pct:.4f}"

	prev, match_kind, key_used = resolve_source_row(path.name)
	if not prev:
		hint = (
			"expected PNG name to start like cube_DD_MM_HH_MM_SS_cr10p_cheese_N "
			"(or _cheese_N without cr10p), matching Msg/Details from hsm_ingest"
		)
		return False, f"{path.name}: no palletes_scan row ({hint}), skip"

	id_point = str(prev["IDPoint"])
	sscc = str(prev["SSCC"])
	details = (
		f"bg_analyze file={path.name}; match={match_kind}; key={key_used}; "
		f"bg_pct={bg_pct:.6f}; other_pct={other_pct:.6f}; "
		f"matched_palletes_scan_id={prev['id']}"
	)
	status = "analyzed"
	result = f"{bg_pct:.4f}"

	if dry_run:
		return True, (
			f"[dry-run] would insert SSCC={sscc} IDPoint={id_point} "
			f"Status={status} Result={result} Msg={msg_value} ({path.name}) [{match_kind}]"
		)

	insert_palletes_scan(id_point, sscc, details, status, result, msg_value)
	return True, f"inserted {path.name} SSCC={sscc} Msg={msg_value} [{match_kind}]"


def main() -> int:
	parser = argparse.ArgumentParser(
		description=(
			"Analyze detect PNGs: background %%, match palletes_scan by HDR stem "
			"(cube_*_cr10p_cheese_*), insert Status=analyzed, Msg=100-bg%%."
		)
	)
	parser.add_argument(
		"--scan-dir",
		type=Path,
		required=True,
		help="Directory containing PNGs (e.g. HSM_CAPTURE/.../detect or HSM_detect_2clust)",
	)
	parser.add_argument(
		"--glob",
		default="*.png",
		help="Glob for files under scan-dir (default: *.png)",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Print actions without writing to the database",
	)
	args = parser.parse_args()

	scan_dir = args.scan_dir
	if not scan_dir.is_dir():
		print(f"Not a directory: {scan_dir}", flush=True)
		return 1

	init_db()
	print(f"Using DB file: {db.DB_PATH}", flush=True)

	paths = sorted(scan_dir.glob(args.glob))
	if not paths:
		print(f"No files matching {args.glob!r} in {scan_dir}", flush=True)
		return 0

	ok_n = 0
	for p in paths:
		if not p.is_file():
			continue
		ok, line = process_file(p, dry_run=args.dry_run)
		print(line, flush=True)
		if ok:
			ok_n += 1

	print(f"Done. processed_ok={ok_n} / {len(paths)}", flush=True)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

from __future__ import annotations

import argparse
import shutil
import sys
from fnmatch import fnmatch
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_ROOT, _SCRIPTS):
	if str(_p) not in sys.path:
		sys.path.insert(0, str(_p))

import ingest_hsm_capture as hsm  # noqa: E402


def unique_target_path(target_dir: Path, src_name: str) -> Path:
	base = Path(src_name).stem
	ext = Path(src_name).suffix
	candidate = target_dir / src_name
	i = 1
	while candidate.exists():
		candidate = target_dir / f"{base}_{i}{ext}"
		i += 1
	return candidate


def matches_wildcard(filename: str, wildcard: str) -> bool:
	# Substring match: wrap with * unless the pattern already contains * (then use as-is).
	# So e.g. _cr10p_cheese_?_2cluster0p becomes *_cr10p_cheese_?_2cluster0p* and ? matches one char.
	pattern = wildcard
	if "*" not in wildcard:
		pattern = f"*{wildcard}*"
	return fnmatch(filename, pattern)


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Copy all files from cube_*/detect subdirs into one directory."
	)
	parser.add_argument(
		"--root",
		default=str(hsm.HSM_CAPTURE_ROOT),
		help="HSM_CAPTURE root directory",
	)
	parser.add_argument(
		"--detect-subdir",
		default="detect",
		help="Name of per-cube detect folder (default: detect)",
	)
	parser.add_argument(
		"--out",
		default="HSM_CAPTURE_DETECT_ALL",
		help="Target directory where all detect files are copied",
	)
	parser.add_argument(
		"--wildcard",
		default="_cr10p_cheese_?_2cluster0p",
		help='Filename fnmatch; ? = one char. Default matches *_cr10p_cheese_?_2cluster0p*',
	)
	args = parser.parse_args()

	root = Path(args.root)
	if not root.is_dir():
		print(f"HSM_CAPTURE root not found: {root}")
		return 1

	out_dir = Path(args.out)
	out_dir.mkdir(parents=True, exist_ok=True)

	total_dirs = 0
	total_files = 0
	total_copied = 0
	cube_dirs = [d for d in root.iterdir() if d.is_dir() and d.name.startswith("cube_")]
	for cube in cube_dirs:
		detect_dir = cube / args.detect_subdir
		if not detect_dir.is_dir():
			continue
		total_dirs += 1
		for src in detect_dir.iterdir():
			if not src.is_file():
				continue
			total_files += 1
			if not matches_wildcard(src.name, args.wildcard):
				continue
			dst = unique_target_path(out_dir, src.name)
			shutil.copy2(src, dst)
			total_copied += 1

	print(f"wildcard: {args.wildcard}")
	print(f"total files: {total_files}")
	print(f"total dirs: {total_dirs}")
	print(f"total copied files: {total_copied}")
	print(f"output dir: {out_dir.resolve()}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())


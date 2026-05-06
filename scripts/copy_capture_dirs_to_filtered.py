from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


DEFAULT_FILTERED_DIR = Path(r"C:\Users\1\PycharmProjects\savvfastapi\HSM_detect_2clust\test\filtered")
DEFAULT_CAPTURE_ROOT = Path(r"C:\Users\1\PycharmProjects\savvfastapi\HSM_CAPTURE")

# Example PNG:
# cube_27_03_18_11_16_cr10p_cheese_1_2cluster0p_1.png
CUBE_KEY_RE = re.compile(r"^(cube_\d{2}_\d{2}_\d{2}_\d{2}_\d{2})")


def extract_cube_key(filename: str) -> str | None:
    match = CUBE_KEY_RE.match(filename)
    if not match:
        return None
    return match.group(1)


def unique_ordered_cube_keys(filtered_dir: Path) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    for png_path in sorted(filtered_dir.glob("*.png")):
        key = extract_cube_key(png_path.name)
        if key is None or key in seen:
            continue
        seen.add(key)
        keys.append(key)

    return keys


def copy_cube_dirs(
    filtered_dir: Path, capture_root: Path, overwrite_existing: bool, dry_run: bool
) -> tuple[int, int, int]:
    cube_keys = unique_ordered_cube_keys(filtered_dir)
    copied_count = 0
    missing_count = 0

    for cube_key in cube_keys:
        src_dir = capture_root / cube_key
        dst_dir = filtered_dir / cube_key

        if not src_dir.is_dir():
            print(f"[missing] {src_dir}")
            missing_count += 1
            continue

        if dst_dir.exists() and not overwrite_existing:
            print(f"[skip exists] {dst_dir}")
            continue

        if dry_run:
            print(f"[dry-run copy] {src_dir} -> {dst_dir}")
            copied_count += 1
            continue

        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=overwrite_existing)
        print(f"[copied] {src_dir} -> {dst_dir}")
        copied_count += 1

    return len(cube_keys), copied_count, missing_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan filtered PNG files, extract cube_* prefix, and copy matching "
            "directories from HSM_CAPTURE into filtered."
        )
    )
    parser.add_argument(
        "--filtered-dir",
        default=str(DEFAULT_FILTERED_DIR),
        help="Directory containing filtered PNG files.",
    )
    parser.add_argument(
        "--capture-root",
        default=str(DEFAULT_CAPTURE_ROOT),
        help="Root directory with source cube_* folders (e.g. HSM_CAPTURE).",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Overwrite destination if cube folder already exists in filtered.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be copied without writing files.",
    )
    args = parser.parse_args()

    filtered_dir = Path(args.filtered_dir)
    capture_root = Path(args.capture_root)

    if not filtered_dir.is_dir():
        print(f"Filtered directory not found: {filtered_dir}")
        return 1
    if not capture_root.is_dir():
        print(f"Capture root not found: {capture_root}")
        return 1

    total_keys, copied_count, missing_count = copy_cube_dirs(
        filtered_dir=filtered_dir,
        capture_root=capture_root,
        overwrite_existing=args.overwrite_existing,
        dry_run=args.dry_run,
    )

    print(f"cube keys found: {total_keys}")
    print(f"copied dirs: {copied_count}")
    print(f"missing source dirs: {missing_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

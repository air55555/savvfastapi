from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from save_point_spectrum_to_ecostress_db import save_two_region_averages  # noqa: E402


def _collect_maps(root: Path, pattern: str) -> list[Path]:
    return sorted(root.glob(f"**/detect/{pattern}"))


def run_batch(
    root: Path,
    db_path: Path,
    pattern: str = "cube*_cr10p_*_2cluster0p.png",
    limit: int = 0,
) -> int:
    if not root.is_dir():
        print(f"Root folder not found: {root}")
        return 1

    maps = _collect_maps(root, pattern)
    if limit > 0:
        maps = maps[:limit]

    print(f"Root: {root}")
    print(f"DB: {db_path}")
    print(f"Pattern: {pattern}")
    print(f"Found PNG maps: {len(maps)}")

    ok_count = 0
    fail_count = 0
    for map_path in maps:
        try:
            res = save_two_region_averages(map_path=map_path, db_path=db_path)
            ok_count += 1
            print(
                f"OK {map_path.name} | "
                f"bg={res['background_pixels']} ({res['background_percent']:.4f}%) | "
                f"def={res['defects_pixels']} ({res['defects_percent']:.4f}%)"
            )
        except Exception as exc:
            fail_count += 1
            print(f"FAIL {map_path}: {exc}")

    print(f"Done. success={ok_count}, failed={fail_count}, total={len(maps)}")
    return 0 if fail_count == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch compute 2-region average spectra from detect map PNGs."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("HSM_CAPTURE"),
        help="Root directory to scan recursively (default: HSM_CAPTURE).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        required=True,
        help="Path to ECOSTRESS-style SQLite DB.",
    )
    parser.add_argument(
        "--pattern",
        default="cube*_cr10p_*_2cluster0p.png",
        help="Filename wildcard for maps inside detect subdirs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only first N matched maps (0 = all).",
    )
    args = parser.parse_args()
    return run_batch(
        root=args.root,
        db_path=args.db,
        pattern=args.pattern,
        limit=args.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())

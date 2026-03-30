"""
Process every cube_* folder under HSM_CAPTURE (newest first).
Wrapper around process_hsm_capture.process_hsm_capture_dirs with limit=0 (all).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ingest_hsm_capture as hsm  # noqa: E402
from process_hsm_capture import (  # noqa: E402
    DETECT_SUBDIR,
    process_hsm_capture_dirs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process all cube_* subdirs under HSM_CAPTURE (cluster PNG per folder)."
    )
    parser.add_argument(
        "--root",
        default=str(hsm.HSM_CAPTURE_ROOT),
        help="HSM_CAPTURE root directory",
    )
    parser.add_argument("-k", "--clusters", type=int, default=10)
    parser.add_argument("--max-iter", type=int, default=3)
    parser.add_argument(
        "--crop-percent",
        type=int,
        default=1,
        help="Per-side crop %% for cluster overlay (0 = full cluster map PNG).",
    )
    parser.add_argument(
        "--suffix",
        default=".png",
        help=f"Output under each cube: {DETECT_SUBDIR}/{{stem}}{{suffix}}",
    )
    parser.add_argument(
        "--output-subdir",
        default=DETECT_SUBDIR,
        help=f"Subfolder under each cube_* for PNGs (default: {DETECT_SUBDIR})",
    )
    args = parser.parse_args()

    return process_hsm_capture_dirs(
        Path(args.root),
        limit=0,
        clusters=args.clusters,
        max_iter=args.max_iter,
        crop_percent=args.crop_percent,
        suffix=args.suffix,
        output_subdir=args.output_subdir or "",
    )


if __name__ == "__main__":
    raise SystemExit(main())

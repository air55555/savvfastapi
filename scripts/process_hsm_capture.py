"""
Process HSM_CAPTURE cube folders (newest first): run batch_cluster only on
*_cheese_*.hdr files; write one cluster PNG per cheese HDR in each subdir.
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

import batch_cluster  # noqa: E402
import ingest_hsm_capture as hsm  # noqa: E402

DETECT_SUBDIR = "detect"


def list_cheese_hdrs(cube_dir: Path) -> list[Path]:
    """All ENVI headers matching *_cheese_*.hdr in folder, sorted by name."""
    return sorted(
        p
        for p in cube_dir.glob("*.hdr")
        if "_cheese_" in p.name.lower()
    )


def process_hsm_capture_dirs(
    root: Path,
    *,
    limit: int = 0,
    clusters: int = 5,
    max_iter: int = 100,
    crop_percent: int = 10,
    suffix: str = ".png",
    output_subdir: str = DETECT_SUBDIR,
) -> int:
    """
    Scan `root` for cube_* directories (newest first by folder timestamp).
    `limit`: 0 = process all; else only the N newest.
    Returns 0 if OK, 1 if root missing.
    """
    root = Path(root)
    if not root.is_dir():
        print(f"HSM_CAPTURE root not found: {root}")
        return 1

    cube_dirs = [d for d in root.iterdir() if d.is_dir() and d.name.startswith("cube_")]
    cube_dirs.sort(key=hsm.cube_dir_sort_key, reverse=True)
    if limit > 0:
        cube_dirs = cube_dirs[:limit]

    for cube in cube_dirs:
        cheese_hdrs = list_cheese_hdrs(cube)
        if not cheese_hdrs:
            print(f"{cube.name}: skip (no *_cheese_*.hdr)")
            continue
        detect_dir = cube / output_subdir if output_subdir else cube
        detect_dir.mkdir(parents=True, exist_ok=True)
        for hdr in cheese_hdrs:
            out_png = detect_dir / f"{hdr.stem}{suffix}"
            try:
                saved = batch_cluster.run_pipeline(
                    hdr,
                    out_png,
                    clusters=clusters,
                    max_iter=max_iter,
                    crop_percent=crop_percent,
                )
                rel = Path(saved).relative_to(cube)
                print(f"{cube.name}: OK -> {rel} ({hdr.name})")
            except Exception as e:
                print(f"{cube.name}: FAIL ({hdr.name}): {e}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan HSM_CAPTURE cube_* dirs (newest first), run batch_cluster, write PNG in each subdir."
    )
    parser.add_argument(
        "--root",
        default=str(hsm.HSM_CAPTURE_ROOT),
        help="HSM_CAPTURE root (default: same as ingest_hsm_capture)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only N newest folders (0 = all)",
    )
    parser.add_argument("-k", "--clusters", type=int, default=5)
    parser.add_argument("--max-iter", type=int, default=100)
    parser.add_argument(
        "--crop-percent",
        type=int,
        default=10,
        help="Per-side crop %% for overlay (0 = full cluster map only, same k-means on full cube).",
    )
    parser.add_argument(
        "--suffix",
        default=".png",
        help="Output: {cube}/{output-subdir}/{cheese_hdr_stem}{suffix}",
    )
    parser.add_argument(
        "--output-subdir",
        default=DETECT_SUBDIR,
        help=f"Subfolder under each cube_* for PNGs (default: {DETECT_SUBDIR}; empty = cube root)",
    )
    args = parser.parse_args()

    return process_hsm_capture_dirs(
        Path(args.root),
        limit=args.limit,
        clusters=args.clusters,
        max_iter=args.max_iter,
        crop_percent=args.crop_percent,
        suffix=args.suffix,
        output_subdir=args.output_subdir or "",
    )


if __name__ == "__main__":
    raise SystemExit(main())

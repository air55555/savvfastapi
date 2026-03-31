"""
Crop ENVI HSI cubes under HSM_CAPTURE/cube_* and write cropped cubes.

Naming:
  - For "..._cheese_<n>.hdr" -> "..._cr{p}p_cheese_<n>.hdr"
  - Otherwise -> "..._cr{p}p.hdr"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import spectral.io.envi as envi

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ingest_hsm_capture as hsm  # noqa: E402


CHEESE_RE = re.compile(r"^(?P<base>.+)_cheese_(?P<num>\d+)$", re.IGNORECASE)


def compute_crop_window(h: int, w: int, crop_percent: int) -> Tuple[int, int, int, int]:
    """
    Return (top, bottom, left, right) for cropping percent from each edge.
    This is effectively a center crop that removes p% from each side.
    """
    p = abs(int(crop_percent))
    if p <= 0:
        return 0, h, 0, w

    top = int(h * p / 100.0)
    left = int(w * p / 100.0)
    bottom = h - top
    right = w - left
    if top >= bottom or left >= right:
        # Crop too large; keep full frame to avoid producing empty output.
        return 0, h, 0, w
    return top, bottom, left, right


def cropped_tag(crop_percent: int, prefix: str = "cr") -> str:
    return f"{prefix}{abs(int(crop_percent))}p"


def make_output_stem(input_stem: str, crop_percent: int, tag_prefix: str = "cr") -> str:
    """
    Build output file stem from input stem by inserting a crop tag.
    """
    tag = cropped_tag(crop_percent, prefix=tag_prefix)

    m = CHEESE_RE.match(input_stem)
    if m:
        base = m.group("base")
        num = m.group("num")
        return f"{base}_{tag}_cheese_{num}"

    return f"{input_stem}_{tag}"


def iter_cube_hdrs(cube_dir: Path, hdr_glob: str) -> Iterable[Path]:
    for p in cube_dir.glob(hdr_glob):
        if p.is_file() and p.suffix.lower() == ".hdr":
            yield p


def _dtype_from_envi_metadata(img: "envi.SpyFile") -> np.dtype:
    md = img.metadata or {}
    dtype_code = str(md.get("data type", "4"))
    mapping = {code: dt for code, dt in envi.dtype_map}
    # Default to float32 if unknown.
    return np.dtype(mapping.get(dtype_code, np.float32))


def crop_and_save_envi_cube(
    hdr_path: Path,
    out_hdr_path: Path,
    *,
    crop_percent: int,
    tag_prefix: str = "cr",
    force: bool = False,
) -> Optional[Path]:
    """
    Load cube, crop center window, write ENVI output.
    Returns out_hdr_path on success, None on skip.
    """
    if out_hdr_path.exists() and not force:
        return None

    out_hdr_path.parent.mkdir(parents=True, exist_ok=True)

    img = envi.open(str(hdr_path))
    md = img.metadata or {}

    # Parse dimensions from metadata (avoids relying on the data payload).
    h = int(md.get("lines", md.get("LINES", 0)))
    w = int(md.get("samples", md.get("SAMPLES", 0)))
    if h <= 0 or w <= 0:
        # Fallback: load the array to figure shape.
        arr_full = img.load()
        if arr_full.ndim != 3:
            raise ValueError(f"Unsupported cube array shape: {arr_full.shape} ({hdr_path})")
        h, w = int(arr_full.shape[0]), int(arr_full.shape[1])
    else:
        # We'll still need the full array to crop.
        arr_full = img.load()

    if arr_full.ndim == 3:
        lines, samples, bands = arr_full.shape
    elif arr_full.ndim == 2:
        lines, samples = arr_full.shape
        bands = 1
        arr_full = arr_full[:, :, None]
    else:
        raise ValueError(f"Unsupported cube array shape: {arr_full.shape} ({hdr_path})")

    top, bottom, left, right = compute_crop_window(lines, samples, crop_percent)
    cropped = arr_full[top:bottom, left:right, :]

    dtype = _dtype_from_envi_metadata(img)
    cropped = np.asarray(cropped, dtype=dtype)

    interleave = str(md.get("interleave", "bil")).lower()
    byteorder_raw = md.get("byte order", 0)
    try:
        byteorder = int(byteorder_raw)
    except Exception:
        byteorder = 0

    # Keep original metadata where possible, but fix dims for the new cube.
    out_md = dict(md)
    out_md["lines"] = str(cropped.shape[0])
    out_md["samples"] = str(cropped.shape[1])
    out_md["bands"] = str(cropped.shape[2])

    # spectral will choose the `.img` extension by default.
    envi.save_image(
        str(out_hdr_path),
        cropped,
        dtype=dtype,
        force=force,
        interleave=interleave,
        byteorder=byteorder,
        metadata=out_md,
    )
    return out_hdr_path


def process_all_cubes(
    root: Path,
    *,
    crop_percent: int,
    hdr_glob: str,
    tag_prefix: str,
    out_subdir: str,
    force: bool,
    limit: int,
) -> int:
    root = Path(root)
    if not root.is_dir():
        print(f"Root not found: {root}")
        return 1

    cube_dirs = [d for d in root.iterdir() if d.is_dir() and d.name.startswith("cube_")]
    cube_dirs.sort(key=hsm.cube_dir_sort_key, reverse=True)
    if limit > 0:
        cube_dirs = cube_dirs[:limit]

    tag = cropped_tag(crop_percent, prefix=tag_prefix).lower()

    total = 0
    skipped = 0
    for cube_dir in cube_dirs:
        out_dir = cube_dir / out_subdir if out_subdir else cube_dir
        for hdr_path in iter_cube_hdrs(cube_dir, hdr_glob):
            in_stem = hdr_path.stem
            if f"_{tag}_" in in_stem.lower() or in_stem.lower().endswith(f"_{tag}"):
                # Avoid re-cropping our own outputs.
                skipped += 1
                continue

            out_stem = make_output_stem(in_stem, crop_percent, tag_prefix=tag_prefix)
            out_hdr_path = out_dir / f"{out_stem}.hdr"

            out = crop_and_save_envi_cube(
                hdr_path,
                out_hdr_path,
                crop_percent=crop_percent,
                tag_prefix=tag_prefix,
                force=force,
            )
            if out is None:
                skipped += 1
                continue
            total += 1
            rel_in = hdr_path.relative_to(root)
            rel_out = out_hdr_path.relative_to(root)
            print(f"OK: {rel_in} -> {rel_out}")

    print(f"Done. written={total}, skipped={skipped}, tag={tag}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crop ENVI HSI cubes under cube_* directories and write cropped ENVI outputs."
    )
    parser.add_argument(
        "--root",
        default=str(hsm.HSM_CAPTURE_ROOT),
        help="HSM_CAPTURE root directory (contains cube_* folders)",
    )
    parser.add_argument("--crop-percent", type=int, default=10, help="Per-side crop percent (default: 10)")
    parser.add_argument("--hdr-glob", default="*.hdr", help="Which .hdr files inside each cube_ folder")
    parser.add_argument("--tag-prefix", default="cr", help="Crop tag prefix (default: cr -> cr10p)")
    parser.add_argument("--out-subdir", default="", help="Optional subdir to write outputs into")
    parser.add_argument("--limit", type=int, default=0, help="Only process the N newest cube_* folders (0=all)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output .hdr/.img")
    args = parser.parse_args()

    return process_all_cubes(
        Path(args.root),
        crop_percent=args.crop_percent,
        hdr_glob=args.hdr_glob,
        tag_prefix=args.tag_prefix,
        out_subdir=args.out_subdir,
        force=args.force,
        limit=args.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())


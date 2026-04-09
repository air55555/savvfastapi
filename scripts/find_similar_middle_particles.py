from __future__ import annotations

import argparse
from fnmatch import fnmatch
from pathlib import Path
import shutil

import matplotlib.image as mpimg
import numpy as np

DEFAULT_SCAN_DIR = Path(r"C:\Users\1\PycharmProjects\savvfastapi\HSM_detect_2clust\test")
DEFAULT_REFERENCE = "cube_25_02_09_38_02_cr10p_cheese_3_2cluster0p.png"
DEFAULT_WILDCARD = "_2cluster0p"


def matches_wildcard(filename: str, wildcard: str) -> bool:
    # If no glob symbols are provided, treat wildcard as "contains".
    pattern = wildcard
    if not any(ch in wildcard for ch in "*?[]"):
        pattern = f"*{wildcard}*"
    return fnmatch(filename, pattern)


def load_rgb(path: Path) -> np.ndarray:
    arr = mpimg.imread(path)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[-1] >= 4:
        arr = arr[:, :, :3]
    if np.issubdtype(arr.dtype, np.floating):
        arr = np.clip(arr, 0.0, 1.0)
        arr = (arr * 255.0).astype(np.uint8)
    else:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


def center_crop(img: np.ndarray, center_percent: float) -> np.ndarray:
    h, w = img.shape[:2]
    p = max(1.0, min(float(center_percent), 100.0)) / 100.0
    crop_h = max(1, int(round(h * p)))
    crop_w = max(1, int(round(w * p)))
    top = max(0, (h - crop_h) // 2)
    left = max(0, (w - crop_w) // 2)
    return img[top : top + crop_h, left : left + crop_w]


def color_profile_in_center(
    png_path: Path,
    *,
    center_percent: float,
    quant_step: int,
) -> tuple[float, float, float]:
    img = load_rgb(png_path)
    crop = center_crop(img, center_percent=center_percent)
    pix = crop.reshape(-1, 3).astype(np.uint16)

    # Quantize to merge anti-aliased shades into stable color buckets.
    step = max(1, int(quant_step))
    q = (pix // step) * step
    keys = (q[:, 0] << 16) | (q[:, 1] << 8) | q[:, 2]
    _, counts = np.unique(keys, return_counts=True)
    if counts.size == 0:
        return 0.0, 0.0, 0.0

    counts_sorted = np.sort(counts)[::-1]
    dominant = int(counts_sorted[0])
    second = int(counts_sorted[1]) if counts_sorted.size > 1 else 0
    total = int(np.sum(counts))
    other = max(0, total - dominant)
    dominant_pct = (dominant / total) * 100.0
    second_pct = (second / total) * 100.0
    other_pct = (other / total) * 100.0
    return dominant_pct, second_pct, other_pct


def resolve_reference(scan_dir: Path, reference: str) -> Path:
    p = Path(reference)
    if p.is_file():
        return p
    candidate = scan_dir / reference
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"Reference PNG not found: {reference}")


def list_candidate_pngs(scan_dir: Path, wildcard: str) -> list[Path]:
    out: list[Path] = []
    for p in scan_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() != ".png":
            continue
        if not matches_wildcard(p.name, wildcard):
            continue
        out.append(p)
    out.sort(key=lambda x: x.name.lower())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Find PNG files with similar center 'other-color particle' percentage."
        )
    )
    parser.add_argument(
        "--scan-dir",
        default=str(DEFAULT_SCAN_DIR),
        help=f"Directory to scan for PNGs (default: {DEFAULT_SCAN_DIR})",
    )
    parser.add_argument(
        "--reference",
        default=DEFAULT_REFERENCE,
        help=f"Reference PNG path or filename (default: {DEFAULT_REFERENCE})",
    )
    parser.add_argument(
        "--wildcard",
        default=DEFAULT_WILDCARD,
        help=f'Filename wildcard filter (default: "{DEFAULT_WILDCARD}")',
    )
    parser.add_argument(
        "--center-percent",
        type=float,
        default=30.0,
        help="Center crop size in %% of image width/height (default: 30)",
    )
    parser.add_argument(
        "--max-second-percent",
        type=float,
        default=5.0,
        help="Keep files where second color is <= this value (default: 5.0)",
    )
    parser.add_argument(
        "--quant-step",
        type=int,
        default=16,
        help="RGB quantization step for robust color grouping (default: 16)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="Max similar files to print (default: 50)",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print progress every N files while scanning (default: 100)",
    )
    parser.add_argument(
        "--out-subdir",
        default="filtered",
        help='Subdirectory for copied similar files (default: "filtered")',
    )
    args = parser.parse_args()

    scan_dir = Path(args.scan_dir)
    if not scan_dir.is_dir():
        print(f"Scan directory not found: {scan_dir}")
        return 1

    try:
        reference_path = resolve_reference(scan_dir, args.reference)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    candidates = list_candidate_pngs(scan_dir, args.wildcard)
    if not candidates:
        print("No candidate PNG files found with current wildcard.")
        print(f"wildcard: {args.wildcard}")
        print("total files: 0")
        print("total similar files: 0")
        return 0

    ref_dominant, ref_second, ref_other = color_profile_in_center(
        reference_path,
        center_percent=args.center_percent,
        quant_step=args.quant_step,
    )

    rows: list[tuple[Path, float, float, float]] = []
    total = len(candidates)
    step = max(1, int(args.progress_every))
    for idx, p in enumerate(candidates, start=1):
        dominant_pct, second_pct, other_pct = color_profile_in_center(
            p,
            center_percent=args.center_percent,
            quant_step=args.quant_step,
        )
        rows.append((p, dominant_pct, second_pct, other_pct))
        if idx % step == 0 or idx == total:
            print(f"progress: {idx}/{total}")

    similar = [
        r
        for r in rows
        if r[2] <= float(args.max_second_percent)
    ]
    similar.sort(key=lambda x: (x[3], x[2], x[0].name.lower()))

    out_subdir = Path(args.out_subdir)
    out_dir = out_subdir if out_subdir.is_absolute() else (scan_dir / out_subdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for p, _, _, _ in similar:
        shutil.copy2(p, out_dir / p.name)
        copied += 1

    print(f"scan dir: {scan_dir.resolve()}")
    print(f"wildcard: {args.wildcard}")
    print(f"reference: {reference_path.name}")
    print(f"reference dominant percent: {ref_dominant:.3f}%")
    print(f"reference second percent: {ref_second:.3f}%")
    print(f"reference other percent: {ref_other:.3f}%")
    print(f"center percent: {float(args.center_percent):.2f}%")
    print(f"max second percent: {float(args.max_second_percent):.3f}%")
    print(f"total files: {len(candidates)}")
    print(f"total similar files: {len(similar)}")
    print(f"total copied files: {copied}")
    print(f"output dir: {out_dir.resolve()}")
    print("")
    print("similar files:")
    for p, dominant_pct, second_pct, other_pct in similar[: max(0, int(args.top))]:
        print(
            f"{p.name} | dominant={dominant_pct:.3f}% | second={second_pct:.3f}% | other={other_pct:.3f}%"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

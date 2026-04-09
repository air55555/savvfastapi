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

DEFAULT_CENTER_PERCENT = 30.0
DEFAULT_OUT_SUBDIR = "filtered"
DEFAULT_PROGRESS_EVERY = 100


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


def color_stats_in_center(
    png_path: Path,
    *,
    center_percent: float,
) -> tuple[tuple[int, int, int], tuple[int, int, int], float, float, float, set[tuple[int, int, int]]]:
    img = load_rgb(png_path)
    crop = center_crop(img, center_percent=center_percent)
    pix = crop.reshape(-1, 3).astype(np.uint8)
    colors, counts = np.unique(pix, axis=0, return_counts=True)
    if counts.size == 0:
        empty = (0, 0, 0)
        return empty, empty, 0.0, 0.0, 0.0, set()

    order = np.argsort(counts)[::-1]
    colors_sorted = colors[order]
    counts_sorted = counts[order]
    dominant_color = tuple(int(v) for v in colors_sorted[0])
    second_color = tuple(int(v) for v in colors_sorted[1]) if counts_sorted.size > 1 else dominant_color
    dominant = int(counts_sorted[0])
    second = int(counts_sorted[1]) if counts_sorted.size > 1 else 0
    total = int(np.sum(counts))
    other = max(0, total - dominant)
    dominant_pct = (dominant / total) * 100.0
    second_pct = (second / total) * 100.0
    other_pct = (other / total) * 100.0
    color_set = {tuple(int(v) for v in row) for row in colors.tolist()}
    return dominant_color, second_color, dominant_pct, second_pct, other_pct, color_set


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
        description="Filter by dominant background percent (#1 + #2 colors in center)."
    )
    # Single user parameter.
    parser.add_argument(
        "--min-background-percent",
        type=float,
        default=95.0,
        help="Keep files where (color #1 + color #2) >= this value (default: 95.0)",
    )
    args = parser.parse_args()

    scan_dir = DEFAULT_SCAN_DIR
    if not scan_dir.is_dir():
        print(f"Scan directory not found: {scan_dir}")
        return 1

    try:
        reference_path = resolve_reference(scan_dir, DEFAULT_REFERENCE)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    candidates = list_candidate_pngs(scan_dir, DEFAULT_WILDCARD)
    if not candidates:
        print("No candidate PNG files found with current wildcard.")
        print(f"wildcard: {DEFAULT_WILDCARD}")
        print("total files: 0")
        print("total similar files: 0")
        return 0

    (
        ref_dom_color,
        ref_second_color,
        ref_dominant,
        ref_second,
        ref_other,
        ref_color_set,
    ) = color_stats_in_center(
        reference_path,
        center_percent=DEFAULT_CENTER_PERCENT,
    )
    rows: list[tuple[Path, tuple[int, int, int], tuple[int, int, int], float, float, float, float]] = []
    total = len(candidates)
    step = max(1, int(DEFAULT_PROGRESS_EVERY))
    for idx, p in enumerate(candidates, start=1):
        (
            dom_color,
            second_color,
            dominant_pct,
            second_pct,
            other_pct,
            color_set,
        ) = color_stats_in_center(
            p,
            center_percent=DEFAULT_CENTER_PERCENT,
        )
        _ = color_set
        background_pct = dominant_pct + second_pct
        rows.append((p, dom_color, second_color, dominant_pct, second_pct, other_pct, background_pct))
        if idx % step == 0 or idx == total:
            print(f"progress: {idx}/{total}")

    similar = [
        r
        for r in rows
        if r[6] >= float(args.min_background_percent)
    ]
    similar.sort(key=lambda x: (-x[6], x[0].name.lower()))

    out_subdir = Path(DEFAULT_OUT_SUBDIR)
    out_dir = out_subdir if out_subdir.is_absolute() else (scan_dir / out_subdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for p, _, _, _, _, _, _ in similar:
        shutil.copy2(p, out_dir / p.name)
        copied += 1

    print(f"scan dir: {scan_dir.resolve()}")
    print(f"wildcard: {DEFAULT_WILDCARD}")
    print(f"reference: {reference_path.name}")
    print(f"reference dominant color: {ref_dom_color}")
    print(f"reference second color: {ref_second_color}")
    print(f"reference dominant percent: {ref_dominant:.3f}%")
    print(f"reference second percent: {ref_second:.3f}%")
    print(f"reference background percent (#1+#2): {(ref_dominant + ref_second):.3f}%")
    print(f"reference other percent: {ref_other:.3f}%")
    print(f"reference unique colors in center: {len(ref_color_set)}")
    print(f"center percent: {float(DEFAULT_CENTER_PERCENT):.2f}%")
    print(f"min background percent: {float(args.min_background_percent):.3f}%")
    print(f"total files: {len(candidates)}")
    print(f"total similar files: {len(similar)}")
    print(f"total copied files: {copied}")
    print(f"output dir: {out_dir.resolve()}")
    print("")
    print("filtered files (background=#1+#2 >= threshold):")
    for p, dom_color, second_color, dominant_pct, second_pct, other_pct, background_pct in similar:
        print(
            f"{p.name} | color1={dom_color} | color2={second_color} | p1={dominant_pct:.3f}% | p2={second_pct:.3f}% | background={background_pct:.3f}% | dots={other_pct:.3f}%"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

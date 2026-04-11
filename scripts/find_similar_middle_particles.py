from __future__ import annotations

import argparse
from fnmatch import fnmatch
from pathlib import Path
import shutil

import matplotlib.image as mpimg
import numpy as np

DEFAULT_SCAN_DIR = Path(r"C:\Users\1\PycharmProjects\savvfastapi\HSM_detect_2clust\test")
DEFAULT_REFERENCE = "cube_27_03_18_11_16_cr10p_cheese_1_2cluster0p_1.png"
DEFAULT_WILDCARD = "_2cluster0p"
DEFAULT_OUT_SUBDIR = "filtered"
DEFAULT_PROGRESS_EVERY = 100


def matches_wildcard(filename: str, wildcard: str) -> bool:
    pattern = wildcard
    if "*" not in wildcard:
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


def stats_background_and_other(img: np.ndarray) -> tuple[
    tuple[int, int, int],
    float,
    float,
    int,
    float,
    int,
    int,
]:
    """
    Background = single RGB with maximum pixel count.
    Other = all pixels not equal to background (any number of separate colours).

    Returns:
        bg_color,
        bg_percent,
        other_percent,
        n_other_colors (distinct RGB among non-background pixels),
        other_centroid_offset_percent (non-bg centroid vs image centre, %% of half diagonal),
        n_bg,
        n_other,
    """
    h, w = img.shape[:2]
    total = h * w
    pix = img.reshape(-1, 3).astype(np.uint8)
    colors, counts = np.unique(pix, axis=0, return_counts=True)
    if counts.size == 0:
        return (0, 0, 0), 0.0, 0.0, 0, 0.0, 0, 0

    i_max = int(np.argmax(counts))
    bg = tuple(int(x) for x in colors[i_max])
    n_bg = int(counts[i_max])
    n_other = total - n_bg
    bg_pct = (100.0 * n_bg / total) if total else 0.0
    other_pct = (100.0 * n_other / total) if total else 0.0

    bg_arr = np.array(bg, dtype=np.uint8)
    mask_other = np.any(img != bg_arr, axis=2)
    if not np.any(mask_other):
        n_other_colors = 0
        off_pct = 0.0
    else:
        other_pix = img[mask_other]
        n_other_colors = len(np.unique(other_pix.reshape(-1, 3), axis=0))
        ys, xs = np.where(mask_other)
        mx, my = float(xs.mean()), float(ys.mean())
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        dist = float(np.hypot(mx - cx, my - cy))
        half_diag = 0.5 * float(np.hypot(w, h))
        off_pct = (100.0 * dist / half_diag) if half_diag > 0 else 0.0

    return bg, bg_pct, other_pct, n_other_colors, off_pct, n_bg, n_other


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
            "Background = one colour (max pixels). Other = all non-background pixels; "
            "report how many distinct other colours. Filter by other %% and centroid offset."
        )
    )
    parser.add_argument(
        "--max-other-percent",
        type=float,
        default=10.0,
        help="Max %% of pixels that are not background (not the max-count colour).",
    )
    parser.add_argument(
        "--max-other-offset-percent",
        type=float,
        default=35.0,
        help="Max offset of non-background centroid from image centre, %% of half diagonal.",
    )
    parser.add_argument(
        "--scan-dir",
        default=str(DEFAULT_SCAN_DIR),
        help=f"Directory to scan for PNGs (default: {DEFAULT_SCAN_DIR})",
    )
    args = parser.parse_args()

    scan_dir = Path(args.scan_dir)
    if not scan_dir.is_dir():
        print(f"Scan directory not found: {scan_dir}")
        return 1

    try:
        reference_path = resolve_reference(scan_dir, DEFAULT_REFERENCE)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    ref_img = load_rgb(reference_path)
    rh, rw = ref_img.shape[:2]
    (
        ref_bg,
        ref_bg_pct,
        ref_other_pct,
        ref_n_other_colors,
        ref_off,
        ref_n_bg,
        ref_n_other,
    ) = stats_background_and_other(ref_img)
    uniq_all = len(np.unique(ref_img.reshape(-1, 3), axis=0))

    candidates = list_candidate_pngs(scan_dir, DEFAULT_WILDCARD)
    if not candidates:
        print("No candidate PNG files found with current wildcard.")
        print(f"wildcard: {DEFAULT_WILDCARD}")
        return 0

    rows: list[
        tuple[
            Path,
            tuple[int, int, int],
            float,
            float,
            int,
            float,
            int,
            int,
        ]
    ] = []
    total = len(candidates)
    step = max(1, int(DEFAULT_PROGRESS_EVERY))
    for idx, p in enumerate(candidates, start=1):
        img = load_rgb(p)
        bg, bg_pct, o_pct, n_oc, off_pct, n_bg, n_o = stats_background_and_other(img)
        rows.append((p, bg, bg_pct, o_pct, n_oc, off_pct, n_bg, n_o))
        if idx % step == 0 or idx == total:
            print(f"progress: {idx}/{total}")

    similar = [
        r
        for r in rows
        if r[3] <= float(args.max_other_percent)
        and r[5] <= float(args.max_other_offset_percent)
    ]
    similar.sort(key=lambda x: (x[3], x[5], x[0].name.lower()))

    out_dir = Path(DEFAULT_OUT_SUBDIR)
    if not out_dir.is_absolute():
        out_dir = scan_dir / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for p, _, _, _, _, _, _, _ in similar:
        shutil.copy2(p, out_dir / p.name)
        copied += 1

    print("=== reference image ===")
    print(f"path: {reference_path.resolve()}")
    print(f"size: {rw}x{rh} pixels")
    print(f"unique RGB colours (full image): {uniq_all}")
    print("background: one colour with max pixel count")
    print(f"  RGB: {ref_bg}")
    print(f"  pixels: {ref_n_bg}  ({ref_bg_pct:.4f}% of image)")
    print("other: all pixels not equal to background (separate colours counted below)")
    print(f"  pixels: {ref_n_other}  ({ref_other_pct:.4f}% of image)")
    print(f"  distinct other colours: {ref_n_other_colors}")
    print(
        f"  centroid offset from image centre (non-background mass): {ref_off:.4f}% of half diagonal"
    )
    print("")
    print(f"scan dir: {scan_dir.resolve()}")
    print(f"wildcard: {DEFAULT_WILDCARD}")
    print(f"max other %%: {float(args.max_other_percent):.4f}")
    print(f"max other centroid offset %%: {float(args.max_other_offset_percent):.4f}")
    print(f"total files: {len(candidates)}")
    print(f"total similar files: {len(similar)}")
    print(f"total copied files: {copied}")
    print(f"output dir: {out_dir.resolve()}")
    print("")
    print("filtered files:")
    for p, bg, bg_pct, o_pct, n_oc, off_pct, n_bg, n_o in similar:
        print(
            f"{p.name} | bg={bg} bg%%={bg_pct:.4f}% | other%%={o_pct:.4f}% | "
            f"other_clrs={n_oc} | off%%={off_pct:.4f}% | n_bg={n_bg} n_other={n_o}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

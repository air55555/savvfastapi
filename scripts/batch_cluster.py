"""
Lightweight batch clustering utility for RusCoreSpecViewer.

Steps:
1) Load data from .npy / .npz / .json, or ENVI (.hdr / .img).
2) Run k-means via spectral.kmeans (same as app.spectral_ops.analysis.kmeans_spectral_wrapper).
3) Save a colourised cluster map as an image.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import logging
import numpy as np
import spectral as sp

logger = logging.getLogger("batch_cluster")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def _load_array(path: Path) -> np.ndarray:
    """Load numeric data from .npy, .npz, .json, or ENVI (.hdr / .img)."""
    logger.info("Loading data from %s", path)
    suffix = path.suffix.lower()

    if suffix in {".hdr", ".img"}:
        import spectral.io.envi as envi

        hdr_path = path.with_suffix(".hdr") if suffix == ".img" else path
        if not hdr_path.is_file():
            raise FileNotFoundError(f"ENVI header not found: {hdr_path}")
        img = envi.open(str(hdr_path))
        arr = np.asarray(img.load(), dtype=float)
        logger.info("ENVI cube shape: %s", arr.shape)
        return arr

    if suffix in {".npy", ".npz"}:
        data = np.load(path, allow_pickle=False)
        if isinstance(data, np.lib.npyio.NpzFile):
            if "data" in data:
                arr = data["data"]
            else:
                first_key = next(iter(data.files))
                arr = data[first_key]
        else:
            arr = data
        return np.asarray(arr, dtype=float)

    if suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            obj = json.load(f)

        if isinstance(obj, dict) and "data" in obj:
            return np.asarray(obj["data"], dtype=float)

        if isinstance(obj, (list, tuple)):
            arr = np.asarray(obj, dtype=float)
            if arr.ndim not in (2, 3):
                raise ValueError(
                    f"Unsupported data shape {arr.shape}; expected 2D or 3D array."
                )
            return arr

        if isinstance(obj, dict):
            cols = []
            for v in obj.values():
                if isinstance(v, (list, tuple)):
                    try:
                        a = np.asarray(v, dtype=float)
                    except (TypeError, ValueError):
                        continue
                    if a.ndim == 1 and a.size > 1:
                        cols.append(a)
            if not cols:
                raise ValueError(f"No numeric arrays found in {path}")
            min_len = min(c.size for c in cols)
            stacked = np.stack([c[:min_len] for c in cols], axis=1)
            return stacked

        raise ValueError(f"Unsupported JSON structure in {path}")

    raise ValueError(
        f"Unsupported file type: {suffix} "
        "(use .npy, .npz, .json, or ENVI .hdr/.img)."
    )


def _prepare_features(arr: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    if arr.ndim == 3:
        h, w, c = arr.shape
        logger.info("Input cube shape: %s", arr.shape)
        features = arr.reshape(-1, c)
        img_shape = (h, w)
    elif arr.ndim == 2:
        h, w = arr.shape
        logger.info("Input image shape: %s", arr.shape)
        features = arr.reshape(-1, 1)
        img_shape = (h, w)
    else:
        raise ValueError(
            f"Unsupported data shape {arr.shape}; expected 2D or 3D array."
        )

    return features, img_shape


def _crop_window(h: int, w: int, crop_percent: int) -> tuple[int, int, int, int]:
    """
    Return (top, bottom, left, right) for center crop by abs(crop_percent)% each side.
    """
    p = abs(int(crop_percent))
    if p <= 0:
        return 0, h, 0, w
    top = int(h * p / 100.0)
    left = int(w * p / 100.0)
    bottom = h - top
    right = w - left
    if top >= bottom or left >= right:
        logger.warning("Crop percent %s too large for shape (%d, %d); using full frame.", p, h, w)
        return 0, h, 0, w
    return top, bottom, left, right


def _to_rgb(arr: np.ndarray) -> np.ndarray:
    """
    Build an RGB preview in [0..1] from source data.
    - 3D: combine multiple spectral bands into each RGB channel for vivid result
    - 2D: grayscale repeated to RGB
    """
    if arr.ndim == 2:
        rgb = np.repeat(arr[:, :, None], 3, axis=2).astype(float)
    else:
        c = arr.shape[2]
        if c >= 6:
            # Split spectrum into low/mid/high groups and average each group.
            # This usually yields more informative color than simply taking first 3 bands.
            idx = np.array_split(np.arange(c), 3)
            r = np.nanmean(arr[:, :, idx[2]], axis=2)  # higher wavelengths
            g = np.nanmean(arr[:, :, idx[1]], axis=2)  # mid wavelengths
            b = np.nanmean(arr[:, :, idx[0]], axis=2)  # lower wavelengths
            rgb = np.dstack([r, g, b]).astype(float)
        elif c >= 3:
            rgb = arr[:, :, :3].astype(float)
        elif c == 2:
            rgb = np.dstack([arr[:, :, 0], arr[:, :, 1], arr[:, :, 1]]).astype(float)
        else:
            rgb = np.repeat(arr[:, :, :1], 3, axis=2).astype(float)

    # Robust per-channel percentile stretch (better visibility than min-max).
    out = np.zeros_like(rgb, dtype=float)
    for ch in range(3):
        v = rgb[:, :, ch]
        lo = float(np.nanpercentile(v, 2))
        hi = float(np.nanpercentile(v, 98))
        if hi > lo:
            out[:, :, ch] = (v - lo) / (hi - lo)
        else:
            out[:, :, ch] = 0.0
    out = np.clip(out, 0.0, 1.0)

    # Slight gamma lift for dark zones.
    gamma = 0.85
    out = np.power(out, gamma)

    # Small saturation boost via HSV for better color separation.
    hsv = matplotlib.colors.rgb_to_hsv(out)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.25, 0.0, 1.0)
    out = matplotlib.colors.hsv_to_rgb(hsv)
    return np.clip(out, 0.0, 1.0)


def _output_with_tags(output: Path, clusters: int, crop_percent: int) -> Path:
    """
    Append naming tags like: *_5cluster10p.png
    """
    p = abs(int(crop_percent))
    stem = output.stem
    suffix = output.suffix or ".png"
    tagged = f"{stem}_{clusters}cluster{p}p{suffix}"
    return output.with_name(tagged)


def run_clustering(
    features: np.ndarray,
    img_shape: tuple[int, int],
    clusters: int,
    iters: int,
) -> np.ndarray:
    h, w = img_shape
    bands = features.shape[1]
    logger.info(
        "Running kmeans on shape (H=%d, W=%d, Bands=%d), clusters=%d, iters=%d",
        h, w, bands, clusters, iters,
    )
    cube = features.reshape(h, w, bands)
    labels, _ = sp.kmeans(cube, clusters, iters)
    return labels


def save_cluster_image(labels: np.ndarray, output: Path, base_rgb: Optional[np.ndarray] = None) -> None:
    unique, counts = np.unique(labels, return_counts=True)
    class_counts = dict(zip(unique.tolist(), counts.tolist()))
    logger.info("Class pixel counts: %s", class_counts)

    if base_rgb is not None:
        # Overlay cluster colors on valid cluster area only;
        # keep outside area as original RGB.
        valid = labels >= 0
        labels_for_colormap = np.where(valid, labels, 0)
        cluster_rgb = plt.get_cmap("tab20")(labels_for_colormap.astype(float))[:, :, :3]
        img = np.array(base_rgb, copy=True)
        img[valid] = cluster_rgb[valid]
    else:
        img = labels

    fig = plt.figure(figsize=(8, 4.5), dpi=120)
    if base_rgb is not None:
        plt.imshow(img)
    else:
        plt.imshow(img, cmap="tab20")
    plt.axis("off")
    plt.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def run_pipeline(
    input_path: Path,
    output: Path,
    *,
    clusters: int = 5,
    max_iter: int = 100,
    crop_percent: int = -10,
) -> Path:
    """
    One-shot: load dataset, run k-means, save cluster map PNG.
    `input_path` may be ENVI .hdr / .img or .npy / .npz / .json.
    """
    input_path = Path(input_path)
    output = Path(output)
    data = _load_array(input_path)
    base_rgb = _to_rgb(data)
    full_h, full_w = data.shape[0], data.shape[1]
    top, bottom, left, right = _crop_window(full_h, full_w, crop_percent)
    if data.ndim == 2:
        cropped = data[top:bottom, left:right]
    else:
        cropped = data[top:bottom, left:right, :]
    logger.info(
        "Crop window: top=%d bottom=%d left=%d right=%d, cropped shape=%s",
        top, bottom, left, right, cropped.shape,
    )

    features, img_shape = _prepare_features(cropped)
    labels = run_clustering(
        features=features,
        img_shape=img_shape,
        clusters=clusters,
        iters=max_iter,
    )
    # Keep output frame same size: fill edges as "no cluster" (-1),
    # overlay only center clustered window.
    labels_full = np.full((full_h, full_w), -1, dtype=int)
    labels_full[top:bottom, left:right] = labels

    tagged_output = _output_with_tags(output, clusters=clusters, crop_percent=crop_percent)
    save_cluster_image(labels_full, tagged_output, base_rgb=base_rgb)
    logger.info("Saved cluster image to: %s", tagged_output.resolve())
    return tagged_output.resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch cluster a cube and save a label image."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to dataset (.npy/.npz/.json or ENVI .hdr with .img).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("cluster_output.png"),
        help="Output image path (PNG/JPG).",
    )
    parser.add_argument(
        "-k", "--clusters", type=int, default=5, help="Number of clusters."
    )
    parser.add_argument(
        "--max-iter", type=int, default=100, help="Max iterations."
    )
    parser.add_argument(
        "--crop-percent",
        type=int,
        default=-10,
        help="Crop percent on all sides before clustering (default: -10).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (reserved; SPy kmeans may not use it).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(
        args.input,
        args.output,
        clusters=args.clusters,
        max_iter=args.max_iter,
        crop_percent=args.crop_percent,
    )


if __name__ == "__main__":
    main()
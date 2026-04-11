"""
Lightweight batch clustering utility for RusCoreSpecViewer.

Steps:
1) Load data from .npy / .npz / .json, or ENVI (.hdr / .img).
2) Run k-means via spectral.kmeans on the FULL cube (preserves class structure).
3) Save a colourised cluster map; optional crop overlay (edges = RGB preview).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors
import matplotlib.image as mpimg
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
    """Center crop by abs(crop_percent)% from each side. Returns top, bottom, left, right."""
    p = abs(int(crop_percent))
    if p <= 0:
        return 0, h, 0, w
    top = int(h * p / 100.0)
    left = int(w * p / 100.0)
    bottom = h - top
    right = w - left
    if top >= bottom or left >= right:
        logger.warning("Crop %s%% too large for (%d,%d); using full frame.", p, h, w)
        return 0, h, 0, w
    return top, bottom, left, right


def _to_rgb(arr: np.ndarray) -> np.ndarray:
    """HSI -> RGB [0,1] for edge preview: multi-band blend + stretch."""
    if arr.ndim == 2:
        rgb = np.repeat(arr[:, :, None], 3, axis=2).astype(float)
    else:
        c = arr.shape[2]
        if c >= 6:
            idx = np.array_split(np.arange(c), 3)
            r = np.nanmean(arr[:, :, idx[2]], axis=2)
            g = np.nanmean(arr[:, :, idx[1]], axis=2)
            b = np.nanmean(arr[:, :, idx[0]], axis=2)
            rgb = np.dstack([r, g, b]).astype(float)
        elif c >= 3:
            rgb = arr[:, :, :3].astype(float)
        elif c == 2:
            rgb = np.dstack([arr[:, :, 0], arr[:, :, 1], arr[:, :, 1]]).astype(float)
        else:
            rgb = np.repeat(arr[:, :, :1], 3, axis=2).astype(float)

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
    out = np.power(out, 0.85)
    hsv = matplotlib.colors.rgb_to_hsv(out)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.25, 0.0, 1.0)
    out = matplotlib.colors.hsv_to_rgb(hsv)
    return np.clip(out, 0.0, 1.0)


def _output_with_tags(output: Path, clusters: int, crop_percent: int) -> Path:
    """e.g. stem_5cluster10p.png"""
    p = abs(int(crop_percent))
    stem = output.stem
    suf = output.suffix or ".png"
    return output.with_name(f"{stem}_{clusters}cluster{p}p{suf}")


def run_clustering(
    features: np.ndarray,
    img_shape: tuple[int, int],
    clusters: int,
    iters: int,
) -> np.ndarray:
    h, w = img_shape
    bands = features.shape[1]
    logger.info(
        "Running kmeans on FULL frame (H=%d, W=%d, Bands=%d), clusters=%d, iters=%d",
        h, w, bands, clusters, iters,
    )
    cube = features.reshape(h, w, bands)
    labels, _ = sp.kmeans(cube, clusters, iters)
    u = np.unique(labels)
    logger.info("K-means unique label count: %d (requested k=%d)", u.size, clusters)
    return labels


def _discrete_label_rgb(labels: np.ndarray) -> np.ndarray:
    """
    Map each cluster label to one solid RGB (tab20). Output is HxWx3 uint8 —
    only len(unique(labels)) distinct colours, no interpolation.
    """
    uniq = np.unique(labels)
    n = int(uniq.size)
    cmap = plt.get_cmap("tab20")
    palette = np.zeros((n, 3), dtype=np.uint8)
    for i in range(n):
        rgba = cmap(i / max(n - 1, 1)) if n > 1 else cmap(0.0)
        palette[i] = [int(round(rgba[j] * 255.0)) for j in range(3)]

    idx = np.searchsorted(uniq, labels)
    return palette[idx]


def _save_plain_rgb_png(rgb_u8: np.ndarray, output: Path) -> None:
    """Write RGB uint8 array as PNG without matplotlib figure resampling."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if rgb_u8.dtype != np.uint8:
        rgb_u8 = np.clip(rgb_u8, 0, 255).astype(np.uint8)
    mpimg.imsave(str(output), rgb_u8, format="png", pil_kwargs={"compress_level": 1})


def save_cluster_image(labels: np.ndarray, output: Path) -> None:
    unique, counts = np.unique(labels, return_counts=True)
    class_counts = dict(zip(unique.tolist(), counts.tolist()))
    logger.info("Class pixel counts: %s", class_counts)

    rgb = _discrete_label_rgb(labels)
    _save_plain_rgb_png(rgb, output)


def save_crop_overlay(
    labels: np.ndarray,
    base_rgb: np.ndarray,
    crop_percent: int,
    output: Path,
) -> None:
    """Full-size image: cluster colors only in center crop; edges = base_rgb."""
    h, w = labels.shape
    top, bottom, left, right = _crop_window(h, w, crop_percent)
    mask = np.zeros((h, w), dtype=bool)
    mask[top:bottom, left:right] = True

    cluster_rgb = _discrete_label_rgb(labels)
    base_u8 = (np.clip(base_rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    img = base_u8.copy()
    img[mask] = cluster_rgb[mask]

    unique, counts = np.unique(labels, return_counts=True)
    logger.info("Class pixel counts: %s", dict(zip(unique.tolist(), counts.tolist())))
    logger.info(
        "Crop overlay: center region rows [%d:%d] cols [%d:%d] (percent=%d)",
        top, bottom, left, right, abs(int(crop_percent)),
    )

    _save_plain_rgb_png(img, output)


def run_pipeline(
    input_path: Path,
    output: Path,
    *,
    clusters: int = 5,
    max_iter: int = 100,
    crop_percent: int = 10,
) -> Path:
    """
    K-means always uses the full HSI cube (same as classic batch_cluster).
    If crop_percent != 0: save composite with cluster map only in center crop, RGB edges.
    If crop_percent == 0: save classic full cluster map only.
    Output file: {stem}_{k}cluster{p}p.png
    """
    input_path = Path(input_path)
    output = Path(output)
    data = _load_array(input_path)
    features, img_shape = _prepare_features(data)
    labels = run_clustering(
        features=features,
        img_shape=img_shape,
        clusters=clusters,
        iters=max_iter,
    )
    tagged = _output_with_tags(output, clusters=clusters, crop_percent=crop_percent)
    cp = abs(int(crop_percent))
    if cp == 0:
        save_cluster_image(labels, tagged)
    else:
        base_rgb = _to_rgb(data)
        save_crop_overlay(labels, base_rgb, crop_percent, tagged)
    logger.info("Saved cluster image to: %s", tagged.resolve())
    return tagged.resolve()


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
        help="Base output path; final name adds _{k}cluster{p}p before extension.",
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
        default=10,
        help="Crop %% from each side for cluster overlay only (0 = full cluster map, no RGB edges).",
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

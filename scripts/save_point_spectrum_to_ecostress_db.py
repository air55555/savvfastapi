from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import spectral.io.envi as envi


def _parse_coord(value: str) -> tuple[int, int]:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("coords must be in format: x,y")
    try:
        x = int(parts[0])
        y = int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("coords values must be integers: x,y") from exc
    return x, y


def _parse_wavelengths(metadata: dict, bands: int) -> np.ndarray:
    raw = metadata.get("wavelength")
    if isinstance(raw, list) and len(raw) == bands:
        vals: list[float] = []
        for v in raw:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                vals.append(float(len(vals)))
        return np.asarray(vals, dtype=np.float32)
    return np.arange(bands, dtype=np.float32)


def _resolve_hdr_path(cube_path: Path) -> Path:
    hdr_path = cube_path
    if cube_path.suffix.lower() == ".img":
        hdr_path = cube_path.with_suffix(".hdr")
    if not hdr_path.exists():
        raise FileNotFoundError(f"HDR file not found: {hdr_path}")
    return hdr_path


def _load_cube(hdr_path: Path) -> tuple[np.ndarray, np.ndarray]:
    img = envi.open(str(hdr_path))
    cube = np.asarray(img.load(), dtype=np.float32)
    if cube.ndim != 3:
        raise ValueError(f"Expected 3D HSI cube, got shape {cube.shape}")
    _, _, bands = cube.shape
    wavelengths = _parse_wavelengths(getattr(img, "metadata", {}) or {}, bands)
    return cube, wavelengths


def _write_spectrum_to_db(
    db_path: Path,
    name: str,
    description: str,
    measurement: str,
    wavelengths: np.ndarray,
    spectrum: np.ndarray,
    x_unit: str,
    y_unit: str,
) -> tuple[int, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO Samples (Name, Type, Class, SubClass, Description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                "HSI_POINT" if measurement == "point-spectrum" else "HSI_REGION",
                "USER_DATA",
                "POINT_SPECTRUM" if measurement == "point-spectrum" else "REGION_AVERAGE",
                description,
            ),
        )
        sample_id = int(cur.lastrowid)

        cur.execute(
            """
            INSERT INTO Spectra (
                SampleID, SensorCalibrationID, Instrument, Environment, Measurement,
                XUnit, YUnit, MinWavelength, MaxWavelength, NumValues, XData, YData
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample_id,
                0,
                "hsi-cube",
                "unknown",
                measurement,
                x_unit,
                y_unit,
                float(wavelengths.min()) if wavelengths.size else 0.0,
                float(wavelengths.max()) if wavelengths.size else 0.0,
                int(spectrum.size),
                sqlite3.Binary(wavelengths.astype(np.float32).tobytes()),
                sqlite3.Binary(spectrum.astype(np.float32).tobytes()),
            ),
        )
        spectrum_id = int(cur.lastrowid)
        con.commit()
        return sample_id, spectrum_id
    finally:
        con.close()


def save_point_spectrum(
    cube_path: Path,
    db_path: Path,
    x: int,
    y: int,
    sample_name: str | None = None,
    x_unit: str = "micrometers",
    y_unit: str = "reflectance",
) -> tuple[int, int]:
    hdr_path = _resolve_hdr_path(cube_path)
    cube, wavelengths = _load_cube(hdr_path)

    h, w, bands = cube.shape
    if x < 0 or y < 0 or x >= w or y >= h:
        raise ValueError(f"Coordinates out of bounds: x={x}, y={y}, cube size is {w}x{h}")

    spectrum = cube[y, x, :].astype(np.float32)
    name = sample_name or f"{hdr_path.stem}_x{x}_y{y}"
    return _write_spectrum_to_db(
        db_path=db_path,
        name=name,
        description=f"cube={hdr_path.name}; x={x}; y={y}",
        measurement="point-spectrum",
        wavelengths=wavelengths,
        spectrum=spectrum,
        x_unit=x_unit,
        y_unit=y_unit,
    )


def _auto_detect_cube_hdr_from_map(map_path: Path) -> Path:
    if map_path.suffix.lower() != ".png":
        raise ValueError("Map must be a PNG file.")
    cube_dir = map_path.parent.parent
    if not cube_dir.is_dir():
        raise FileNotFoundError(f"Expected cube directory parent for map: {map_path}")

    stem = map_path.stem
    for marker in ("_2cluster", "_3cluster", "_4cluster", "_5cluster", "_6cluster", "_7cluster", "_8cluster", "_9cluster", "_10cluster"):
        if marker in stem:
            stem = stem.split(marker, 1)[0]
            break
    hdr_path = cube_dir / f"{stem}.hdr"
    if hdr_path.exists():
        return hdr_path

    candidates = sorted(cube_dir.glob("*.hdr"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Could not auto-detect cube HDR for map: {map_path}")


def _load_two_color_masks(map_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    arr = mpimg.imread(str(map_path))
    if arr.ndim != 3:
        raise ValueError(f"Expected RGB/RGBA PNG, got shape {arr.shape}")
    rgb = arr[:, :, :3]
    if np.issubdtype(rgb.dtype, np.floating):
        rgb = np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)
    else:
        rgb = rgb.astype(np.uint8)

    flat = rgb.reshape(-1, 3)
    colors, counts = np.unique(flat, axis=0, return_counts=True)
    if colors.shape[0] < 2:
        raise ValueError(f"Expected at least 2 colors in map, got {colors.shape[0]}")
    if colors.shape[0] > 2:
        idx = np.argsort(counts)[::-1][:2]
        colors = colors[idx]
        counts = counts[idx]

    order = np.argsort(counts)[::-1]
    bg_color = colors[order[0]]
    defect_color = colors[order[1]]

    bg_mask = np.all(rgb == bg_color, axis=2)
    defect_mask = np.all(rgb == defect_color, axis=2)
    return bg_mask, defect_mask, bg_color, defect_color


def save_two_region_averages(
    map_path: Path,
    db_path: Path,
    cube_path: Path | None = None,
    x_unit: str = "micrometers",
    y_unit: str = "reflectance",
) -> dict[str, object]:
    map_path = Path(map_path)
    hdr_path = _resolve_hdr_path(Path(cube_path) if cube_path else _auto_detect_cube_hdr_from_map(map_path))
    cube, wavelengths = _load_cube(hdr_path)
    h, w, bands = cube.shape

    bg_mask, defect_mask, bg_color, defect_color = _load_two_color_masks(map_path)
    if bg_mask.shape != (h, w):
        raise ValueError(
            f"Map/cube size mismatch: map={bg_mask.shape[1]}x{bg_mask.shape[0]}, cube={w}x{h}"
        )

    total = h * w
    bg_count = int(bg_mask.sum())
    defect_count = int(defect_mask.sum())
    if bg_count == 0 or defect_count == 0:
        raise ValueError("One of regions has zero pixels; cannot compute two averages.")

    bg_avg = cube[bg_mask].reshape(bg_count, bands).mean(axis=0).astype(np.float32)
    defect_avg = cube[defect_mask].reshape(defect_count, bands).mean(axis=0).astype(np.float32)

    base_name = map_path.stem
    bg_name = f"{base_name}_background_avg"
    defect_name = f"{base_name}_defects_avg"

    bg_sample_id, bg_spectrum_id = _write_spectrum_to_db(
        db_path=db_path,
        name=bg_name,
        description=f"cube={hdr_path.name}; map={map_path.name}; region=background;num = {bg_count}",
        measurement="region-average",
        wavelengths=wavelengths,
        spectrum=bg_avg,
        x_unit=x_unit,
        y_unit=y_unit,
    )
    defect_sample_id, defect_spectrum_id = _write_spectrum_to_db(
        db_path=db_path,
        name=defect_name,
        description=f"cube={hdr_path.name}; map={map_path.name}; region=defects; num = {defect_count}",
        measurement="region-average",
        wavelengths=wavelengths,
        spectrum=defect_avg,
        x_unit=x_unit,
        y_unit=y_unit,
    )

    out_base = map_path.with_name(f"{base_name}_region_averages")
    csv_path = out_base.with_suffix(".csv")
    json_path = out_base.with_suffix(".json")
    log_path = out_base.with_suffix(".log")

    band_labels = [f"band_{i}" for i in range(bands)]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["region", "pixels", "percent", *band_labels])
        wr.writerow(["background", bg_count, (bg_count / total) * 100.0, *[float(v) for v in bg_avg]])
        wr.writerow(["defects", defect_count, (defect_count / total) * 100.0, *[float(v) for v in defect_avg]])

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cube": str(hdr_path),
        "map": str(map_path),
        "shape": {"height": h, "width": w, "bands": bands},
        "regions": {
            "background": {
                "pixels": bg_count,
                "percent": (bg_count / total) * 100.0,
                "color_rgb": [int(x) for x in bg_color.tolist()],
                "sample_id": bg_sample_id,
                "spectrum_id": bg_spectrum_id,
                "avg_spectrum": [float(v) for v in bg_avg],
            },
            "defects": {
                "pixels": defect_count,
                "percent": (defect_count / total) * 100.0,
                "color_rgb": [int(x) for x in defect_color.tolist()],
                "sample_id": defect_sample_id,
                "spectrum_id": defect_spectrum_id,
                "avg_spectrum": [float(v) for v in defect_avg],
            },
        },
    }
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)

    log_text = (
        f"cube={hdr_path}\n"
        f"map={map_path}\n"
        f"db={db_path}\n"
        f"shape={h}x{w}x{bands}\n"
        f"background_pixels={bg_count} ({(bg_count / total) * 100.0:.4f}%) color={bg_color.tolist()}\n"
        f"defects_pixels={defect_count} ({(defect_count / total) * 100.0:.4f}%) color={defect_color.tolist()}\n"
        f"background_sample_id={bg_sample_id}, background_spectrum_id={bg_spectrum_id}\n"
        f"defects_sample_id={defect_sample_id}, defects_spectrum_id={defect_spectrum_id}\n"
        f"csv={csv_path}\n"
        f"json={json_path}\n"
    )
    log_path.write_text(log_text, encoding="utf-8")

    return {
        "cube": str(hdr_path),
        "map": str(map_path),
        "csv": str(csv_path),
        "json": str(json_path),
        "log": str(log_path),
        "background_pixels": bg_count,
        "defects_pixels": defect_count,
        "background_percent": (bg_count / total) * 100.0,
        "defects_percent": (defect_count / total) * 100.0,
        "background_sample_id": bg_sample_id,
        "defects_sample_id": defect_sample_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Save HSI spectra into ECOSTRESS-style SQLite DB.")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_point = sub.add_parser("point", help="Save one spectrum from point x,y.")
    p_point.add_argument("--cube", required=True, type=Path, help="Path to ENVI cube .hdr (or .img).")
    p_point.add_argument("--db", required=True, type=Path, help="Path to SQLite DB.")
    p_point.add_argument("--coords", required=True, type=_parse_coord, help="Point coordinates: x,y")
    p_point.add_argument("--sample-name", default=None, help="Custom sample name.")
    p_point.add_argument("--x-unit", default="micrometers", help="Wavelength unit.")
    p_point.add_argument("--y-unit", default="reflectance", help="Spectral value unit.")

    p_regions = sub.add_parser("regions2", help="Save 2 region-average spectra from 2-color map PNG.")
    p_regions.add_argument("--map", required=True, type=Path, help="Path to 2-color cluster map PNG.")
    p_regions.add_argument("--db", required=True, type=Path, help="Path to SQLite DB.")
    p_regions.add_argument(
        "--cube",
        default=None,
        type=Path,
        help="Optional cube .hdr/.img path. If omitted, auto-detect from map filename.",
    )
    p_regions.add_argument("--x-unit", default="micrometers", help="Wavelength unit.")
    p_regions.add_argument("--y-unit", default="reflectance", help="Spectral value unit.")

    args = parser.parse_args()

    if args.mode == "point":
        x, y = args.coords
        sample_id, spectrum_id = save_point_spectrum(
            cube_path=args.cube,
            db_path=args.db,
            x=x,
            y=y,
            sample_name=args.sample_name,
            x_unit=args.x_unit,
            y_unit=args.y_unit,
        )
        print(
            f"Saved point spectrum: sample_id={sample_id}, spectrum_id={spectrum_id}, "
            f"cube={args.cube}, db={args.db}, coords=({x},{y})"
        )
        return 0

    res = save_two_region_averages(
        map_path=args.map,
        db_path=args.db,
        cube_path=args.cube,
        x_unit=args.x_unit,
        y_unit=args.y_unit,
    )
    print("Saved 2 region averages:")
    print(f"  cube={res['cube']}")
    print(f"  map={res['map']}")
    print(f"  background: pixels={res['background_pixels']} ({res['background_percent']:.4f}%)")
    print(f"  defects: pixels={res['defects_pixels']} ({res['defects_percent']:.4f}%)")
    print(f"  csv={res['csv']}")
    print(f"  json={res['json']}")
    print(f"  log={res['log']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

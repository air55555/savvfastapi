from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import spectral.io.envi as envi

_root = Path(__file__).resolve().parents[1]
_scripts = _root / "scripts"
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

import crop_hsi_cubes as crop  # noqa: E402


def test_compute_crop_window_simple() -> None:
    top, bottom, left, right = crop.compute_crop_window(20, 20, 10)
    assert top == 2
    assert bottom == 18
    assert left == 2
    assert right == 18


def test_make_output_stem_cheese() -> None:
    assert crop.make_output_stem("cube_1_cheese_2", 10) == "cube_1_cr10p_cheese_2"


def test_make_output_stem_non_cheese() -> None:
    assert crop.make_output_stem("cube_1", 10) == "cube_1_cr10p"


def test_crop_and_save_envi_cube_writes_expected_shape(tmp_path: Path) -> None:
    # Create a small ENVI cube so the crop code can load+write a real .hdr/.img pair.
    in_hdr = tmp_path / "cube_1_cheese_2.hdr"
    data = np.arange(20 * 20 * 5, dtype=np.float32).reshape(20, 20, 5)
    envi.save_image(
        str(in_hdr),
        data,
        dtype=np.float32,
        interleave="bil",
        byteorder=0,
        force=True,
    )

    out_hdr = tmp_path / "cube_1_cr10p_cheese_2.hdr"
    crop.crop_and_save_envi_cube(
        in_hdr,
        out_hdr,
        crop_percent=10,
        force=False,
    )

    assert out_hdr.exists()
    out_img = envi.open(str(out_hdr))
    out_arr = out_img.load()
    assert out_arr.shape == (16, 16, 5)


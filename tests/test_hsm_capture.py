"""Tests for HSM capture ingest and testdata creation."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Ensure project root and scripts are importable
_root = Path(__file__).resolve().parents[1]
_scripts = _root / "scripts"
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

import ingest_hsm_capture
import create_hsm_capture_testdata


# --- parse_hdr_sizes ---


def test_parse_hdr_sizes_valid(tmp_path: Path) -> None:
    hdr = tmp_path / "cube_1_cheese_1.hdr"
    hdr.write_text(
        "ENVI\nsamples = 639\nlines = 325\nbands = 114\n",
        encoding="utf-8",
    )
    w, h = ingest_hsm_capture.parse_hdr_sizes(hdr)
    assert w == 639
    assert h == 325


def test_parse_hdr_sizes_missing_values(tmp_path: Path) -> None:
    hdr = tmp_path / "empty.hdr"
    hdr.write_text("ENVI\nbands = 114\n", encoding="utf-8")
    w, h = ingest_hsm_capture.parse_hdr_sizes(hdr)
    assert w is None
    assert h is None


def test_parse_hdr_sizes_case_insensitive(tmp_path: Path) -> None:
    hdr = tmp_path / "x.hdr"
    hdr.write_text("Samples = 100\nLines = 50\n", encoding="utf-8")
    w, h = ingest_hsm_capture.parse_hdr_sizes(hdr)
    assert w == 100
    assert h == 50


# --- folder_timestamp ---


def test_folder_timestamp_valid(tmp_path: Path) -> None:
    folder = tmp_path / "cube_16_03_16_20_22"
    folder.mkdir()
    folder.touch()
    import time
    import os
    ts_ref = datetime(2026, 3, 16, 16, 20, 22)
    os.utime(folder, (ts_ref.timestamp(), ts_ref.timestamp()))
    result = ingest_hsm_capture.folder_timestamp(folder)
    assert result is not None
    assert result.day == 16
    assert result.month == 3
    assert result.hour == 16
    assert result.minute == 20
    assert result.second == 22


def test_folder_timestamp_invalid_name(tmp_path: Path) -> None:
    folder = tmp_path / "not_cube"
    folder.mkdir()
    folder.touch()
    assert ingest_hsm_capture.folder_timestamp(folder) is None


def test_cube_dir_sort_key_prefers_folder_timestamp(tmp_path: Path) -> None:
    """
    The ingester must sort by the timestamp in folder name (DD_MM_HH_MM_SS),
    not by filesystem mtime.
    """
    import os

    feb = tmp_path / "cube_25_02_09_35_56"
    mar24 = tmp_path / "cube_24_03_16_20_37"
    mar25 = tmp_path / "cube_25_03_10_36_04"
    feb.mkdir()
    mar24.mkdir()
    mar25.mkdir()

    # Force filesystem mtimes to be "wrong" (latest mtime on Feb folder).
    base = datetime(2026, 3, 26, 10, 0, 0)
    os.utime(feb, (base.timestamp(), base.timestamp()))
    os.utime(mar25, ((base - timedelta(days=2)).timestamp(), (base - timedelta(days=2)).timestamp()))
    os.utime(mar24, ((base - timedelta(days=1)).timestamp(), (base - timedelta(days=1)).timestamp()))

    # Sorting by key should still put Mar 25 first, then Mar 24, then Feb 25.
    dirs = [feb, mar24, mar25]
    dirs.sort(key=ingest_hsm_capture.cube_dir_sort_key, reverse=True)
    assert dirs[0].name == "cube_25_03_10_36_04"
    assert dirs[1].name == "cube_24_03_16_20_37"
    assert dirs[2].name == "cube_25_02_09_35_56"


# --- nearest_set_pallet_request ---


def test_nearest_set_pallet_request_match(tmp_db_path: Path) -> None:
    import db
    db.set_db_path(tmp_db_path)
    db.init_db()
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO set_pallet_requests(SSCC, IDPoint, Message, Weight, created_at) VALUES(?,?,?,?,?)",
            ("SSCC123", "ID1", "PalletOnID", 100.0, "2026-03-16 16:20:22"),
        )
        conn.commit()
    finally:
        conn.close()

    ts = datetime(2026, 3, 16, 16, 20, 22)
    row = ingest_hsm_capture.nearest_set_pallet_request(ts, tolerance_seconds=5)
    assert row is not None
    assert row["SSCC"] == "SSCC123"
    assert row["IDPoint"] == "ID1"


def test_nearest_set_pallet_request_no_match(tmp_db_path: Path) -> None:
    import db
    db.set_db_path(tmp_db_path)
    db.init_db()
    ts = datetime(2026, 3, 16, 16, 20, 22)
    row = ingest_hsm_capture.nearest_set_pallet_request(ts, tolerance_seconds=5)
    assert row is None


# --- upsert_scan_row ---


def test_upsert_scan_row_insert_then_skip(tmp_db_path: Path) -> None:
    import db
    db.set_db_path(tmp_db_path)
    db.init_db()

    ok1 = ingest_hsm_capture.upsert_scan_row(
        id_point="ID1",
        sscc="SSCC1",
        details="d",
        status="Scanned",
        result="Ok",
        msg="hsm_ingest:cube_1/cheese_1.hdr",
    )
    assert ok1 is True

    ok2 = ingest_hsm_capture.upsert_scan_row(
        id_point="ID1",
        sscc="SSCC1",
        details="d",
        status="Scanned",
        result="Ok",
        msg="hsm_ingest:cube_1/cheese_1.hdr",
    )
    assert ok2 is False


# --- process_folder ---


def test_process_folder_full_flow(tmp_path: Path, tmp_db_path: Path) -> None:
    import db
    db.set_db_path(tmp_db_path)
    db.init_db()

    folder = tmp_path / "cube_16_03_16_20_22"
    folder.mkdir()
    import os
    ts_ref = datetime(2026, 3, 16, 16, 20, 22)
    for p in [folder]:
        p.touch()
        os.utime(p, (ts_ref.timestamp(), ts_ref.timestamp()))

    cheese_hdr = folder / "cube_16_03_16_20_22_cheese_1.hdr"
    cheese_hdr.write_text("samples = 639\nlines = 325\n", encoding="utf-8")
    cheese_hdr.touch()
    os.utime(cheese_hdr, (ts_ref.timestamp(), ts_ref.timestamp()))

    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO set_pallet_requests(SSCC, IDPoint, Message, Weight, created_at) VALUES(?,?,?,?,?)",
            ("MOCKSSCC", "ID2", "PalletOnID", 1.0, "2026-03-16 16:20:22"),
        )
        conn.commit()
    finally:
        conn.close()

    inserted, skipped = ingest_hsm_capture.process_folder(folder, tolerance_seconds=5)

    assert inserted == 1
    assert skipped == 0
    assert (folder / "MOCKSSCC").exists()
    assert (folder / "MOCKSSCC").read_text() == "MOCKSSCC"


# --- create_hsm_capture_testdata ---


def test_create_hsm_folder_name() -> None:
    ts = datetime(2026, 3, 16, 16, 20, 22)
    name = create_hsm_capture_testdata._folder_name(ts)
    assert name == "cube_16_03_16_20_22"


def test_create_hsm_envi_hdr() -> None:
    text = create_hsm_capture_testdata._envi_hdr(639, 325)
    assert "samples = 639" in text
    assert "lines = 325" in text


def test_build_test_data_creates_dirs_and_db(tmp_path: Path, tmp_db_path: Path) -> None:
    import db
    db.set_db_path(tmp_db_path)

    root = tmp_path / "HSM_CAPTURE"
    created = create_hsm_capture_testdata.build_test_data(root, count=2)

    assert len(created) == 2
    for folder, sscc in created:
        assert folder.exists()
        assert folder.is_dir()
        assert (folder / sscc).exists()
        assert (folder / sscc).read_text() == sscc
        cheese = list(folder.glob("*_cheese_*.hdr"))
        assert len(cheese) >= 2

    conn = db.get_connection()
    try:
        rows = conn.execute("SELECT COUNT(*) AS c FROM set_pallet_requests").fetchone()
        assert rows["c"] == 2
    finally:
        conn.close()

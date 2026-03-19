from __future__ import annotations

import db


def test_init_db_creates_tables(tmp_db_path):
	db.set_db_path(tmp_db_path)
	db.init_db()

	conn = db.get_connection()
	try:
		tables = {
			r["name"]
			for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
		}
	finally:
		conn.close()

	assert "request_logs" in tables
	assert "set_pallet_requests" in tables
	assert "set_pallet_responses" in tables
	assert "palletes_scan" in tables
	assert "get_camera_res_requests" in tables
	assert "get_camera_res_responses" in tables


def test_insert_and_fetch_latest_palletes_scan(tmp_db_path):
	db.set_db_path(tmp_db_path)
	db.init_db()

	db.insert_palletes_scan("ID1", "SSCC1", "details", "Scanned", "Ok", "done")
	latest = db.fetch_latest_palletes_scan_by_sscc("SSCC1")

	assert latest is not None
	assert latest["IDPoint"] == "ID1"
	assert latest["SSCC"] == "SSCC1"
	assert latest["Details"] == "details"
	assert latest["Status"] == "Scanned"
	assert latest["Result"] == "Ok"
	assert latest["Msg"] == "done"
	assert latest["created_at"]


def test_request_logs_roundtrip(tmp_db_path):
	db.set_db_path(tmp_db_path)
	db.init_db()

	db.insert_log("GET", "/x", 200, 12.3, "127.0.0.1", "pytest")
	rows = list(db.fetch_logs(limit=10))

	assert rows
	assert rows[0][1] == "GET"
	assert rows[0][2] == "/x"


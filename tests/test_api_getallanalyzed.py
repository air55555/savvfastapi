from __future__ import annotations

import db


def test_getallanalyzed_returns_only_analyzed(app_client, tmp_db_path):
	db.set_db_path(tmp_db_path)
	db.insert_palletes_scan("ID1", "SSCC_A", "d1", "analyzed", "r", "m1")
	db.insert_palletes_scan("ID1", "SSCC_B", "d2", "Scanned", "r", "m2")
	db.insert_palletes_scan("ID1", "SSCC_C", "d3", "analyzed", "r", "m3")

	r = app_client.get("/api/getanalyzed?limit=10&offset=0")
	assert r.status_code == 200
	data = r.json()
	assert data["Count"] == 2
	assert [rec["SSCC"] for rec in data["Records"]] == ["SSCC_C", "SSCC_A"]
	assert [rec["Msg"] for rec in data["Records"]] == ["m3", "m1"]


def test_getallanalyzed_limit_and_offset(app_client, tmp_db_path):
	db.set_db_path(tmp_db_path)
	for i in range(5):
		db.insert_palletes_scan("ID1", f"SSCC{i}", "d", "analyzed", "r", f"m{i}")

	r1 = app_client.get("/api/getanalyzed?limit=2&offset=0")
	assert r1.status_code == 200
	assert r1.json()["Count"] == 2

	r2 = app_client.get("/api/getanalyzed?limit=2&offset=2")
	assert r2.status_code == 200
	assert r2.json()["Count"] == 2


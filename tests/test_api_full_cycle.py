from __future__ import annotations

import db


def test_health(app_client):
	r = app_client.get("/api/health")
	assert r.status_code == 200
	data = r.json()
	assert data["status"] == "healthy"


def test_setpallet_persists_request_and_response(app_client, tmp_db_path):
	payload = {"SSCC": "148102689000000010", "IDPoint": "ID1", "Message": "PalletOnID", "Weight": 12.3}
	r = app_client.post("/api/setpallet", json=payload)
	assert r.status_code == 200
	assert r.json() == {"SSCC": payload["SSCC"], "Status": "Ok"}

	# Verify persistence in DB
	db.set_db_path(tmp_db_path)
	conn = db.get_connection()
	try:
		req_count = conn.execute("SELECT COUNT(*) AS c FROM set_pallet_requests").fetchone()["c"]
		resp_count = conn.execute("SELECT COUNT(*) AS c FROM set_pallet_responses").fetchone()["c"]
	finally:
		conn.close()
	assert req_count == 1
	assert resp_count == 1


def test_getcamerares_uses_latest_scan_result(app_client, tmp_db_path):
	# Seed scan record for this SSCC
	db.set_db_path(tmp_db_path)
	db.insert_palletes_scan("IDX", "111", "good", "Accepted", "Ok", "done")

	r = app_client.post("/api/getcamerares", json={"SSCC": "111"})
	assert r.status_code == 200
	data = r.json()
	assert data["SSCC"] == "111"
	assert data["Result"] == "Ok"
	assert data["Probability"] == "Ok"
	assert data["Degree"] == "Ok"


def test_logs_endpoint_gets_rows(app_client):
	# Generate at least one log row via middleware, then read it
	_ = app_client.get("/api/health")
	r = app_client.get("/api/logs?limit=5")
	assert r.status_code == 200
	rows = r.json()
	assert isinstance(rows, list)
	assert len(rows) >= 1
	assert "created_at" in rows[0]


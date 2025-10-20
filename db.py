import sqlite3
from pathlib import Path
from typing import Iterable, Optional, Tuple


DB_PATH = Path("requests.db")


def get_connection() -> sqlite3.Connection:
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn


def init_db() -> None:
	conn = get_connection()
	try:
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS request_logs (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				method TEXT NOT NULL,
				path TEXT NOT NULL,
				status_code INTEGER NOT NULL,
				duration_ms REAL NOT NULL,
				client_ip TEXT,
				user_agent TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			);
			"""
		)

		# Endpoint-specific persistence tables matching Pydantic models
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS set_pallet_requests (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				SSCC TEXT NOT NULL,
				IDPoint TEXT NOT NULL,
				Message TEXT NOT NULL,
				Weight REAL NOT NULL,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			);
			"""
		)

		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS set_pallet_responses (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				SSCC TEXT NOT NULL,
				Status TEXT NOT NULL,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			);
			"""
		)
		conn.execute(
			"""
            CREATE TABLE IF NOT EXISTS palletes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                SSCC TEXT NOT NULL,
                Status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS get_camera_res_requests (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				SSCC TEXT NOT NULL,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			);
			"""
		)

		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS get_camera_res_responses (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				IDPoint TEXT NOT NULL,
				SSCC TEXT NOT NULL,
				Status TEXT NOT NULL,
				Probability TEXT NOT NULL,
				Degree TEXT NOT NULL,
				Result TEXT NOT NULL,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			);
			"""
		)
		conn.commit()
	finally:
		conn.close()


def insert_log(
	method: str,
	path: str,
	status_code: int,
	duration_ms: float,
	client_ip: Optional[str],
	user_agent: Optional[str],
) -> None:
	conn = get_connection()
	try:
		conn.execute(
			"""
			INSERT INTO request_logs(method, path, status_code, duration_ms, client_ip, user_agent)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(method, path, status_code, duration_ms, client_ip, user_agent),
		)
		conn.commit()
	finally:
		conn.close()


def fetch_logs(limit: int = 50) -> Iterable[Tuple]:
	conn = get_connection()
	try:
		cur = conn.execute(
			"""
			SELECT id, method, path, status_code, duration_ms, client_ip, user_agent, created_at
			FROM request_logs
			ORDER BY id DESC
			LIMIT ?
			""",
			(limit,),
		)
		for row in cur.fetchall():
			yield (
				row["id"],
				row["method"],
				row["path"],
				row["status_code"],
				row["duration_ms"],
				row["client_ip"],
				row["user_agent"],
				row["created_at"],
			)
	finally:
		conn.close()


# Insert helpers for endpoint payloads

def insert_set_pallet_request(sscc: str, id_point: str, message: str, weight: float) -> None:
	conn = get_connection()
	try:
		conn.execute(
			"""
			INSERT INTO set_pallet_requests(SSCC, IDPoint, Message, Weight)
			VALUES(?, ?, ?, ?)
			""",
			(sscc, id_point, message, weight),
		)
		conn.commit()
	finally:
		conn.close()


def insert_set_pallet_response(sscc: str, status: str) -> None:
	conn = get_connection()
	try:
		conn.execute(
			"""
			INSERT INTO set_pallet_responses(SSCC, Status)
			VALUES(?, ?)
			""",
			(sscc, status),
		)
		conn.commit()
	finally:
		conn.close()


def insert_get_camera_res_request(sscc: str) -> None:
	conn = get_connection()
	try:
		conn.execute(
			"""
			INSERT INTO get_camera_res_requests(SSCC)
			VALUES(?)
			""",
			(sscc,),
		)
		conn.commit()
	finally:
		conn.close()


def insert_get_camera_res_response(
	id_point: str,
	sscc: str,
	status: str,
	probability: str,
	degree: str,
	result: str,
) -> None:
	conn = get_connection()
	try:
		conn.execute(
			"""
			INSERT INTO get_camera_res_responses(IDPoint, SSCC, Status, Probability, Degree, Result)
			VALUES(?, ?, ?, ?, ?, ?)
			""",
			(id_point, sscc, status, probability, degree, result),
		)
		conn.commit()
	finally:
		conn.close()


# Database viewer functions
def fetch_set_pallet_requests(limit: int = 100):
	conn = get_connection()
	try:
		cur = conn.execute(
			"SELECT * FROM set_pallet_requests ORDER BY id DESC LIMIT ?",
			(limit,)
		)
		return [dict(row) for row in cur.fetchall()]
	finally:
		conn.close()


def fetch_set_pallet_responses(limit: int = 100):
	conn = get_connection()
	try:
		cur = conn.execute(
			"SELECT * FROM set_pallet_responses ORDER BY id DESC LIMIT ?",
			(limit,)
		)
		return [dict(row) for row in cur.fetchall()]
	finally:
		conn.close()


def fetch_get_camera_res_requests(limit: int = 100):
	conn = get_connection()
	try:
		cur = conn.execute(
			"SELECT * FROM get_camera_res_requests ORDER BY id DESC LIMIT ?",
			(limit,)
		)
		return [dict(row) for row in cur.fetchall()]
	finally:
		conn.close()


def fetch_get_camera_res_responses(limit: int = 100):
	conn = get_connection()
	try:
		cur = conn.execute(
			"SELECT * FROM get_camera_res_responses ORDER BY id DESC LIMIT ?",
			(limit,)
		)
		return [dict(row) for row in cur.fetchall()]
	finally:
		conn.close()



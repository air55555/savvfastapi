import sqlite3
import os
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union


_PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("SAVVFASTAPI_DB_PATH", str(_PROJECT_ROOT / "savvfastapi.db")))


def set_db_path(path: Union[str, Path]) -> None:
	global DB_PATH
	DB_PATH = Path(path)


def get_connection() -> sqlite3.Connection:
	conn = sqlite3.connect(DB_PATH, check_same_thread=False)
	conn.row_factory = sqlite3.Row
	return conn


def _ensure_table_schema(conn: sqlite3.Connection, table: str, create_sql: str) -> None:
	"""
	SQLite doesn't apply schema changes for existing tables when using
	CREATE TABLE IF NOT EXISTS. For this small app, we rebuild tables whose
	columns don't match the expected set.
	"""
	cur = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
	exists = cur.fetchone() is not None
	if not exists:
		conn.execute(create_sql)
		return

	# Compare existing column names to expected column names.
	existing_cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
	expected_cols = []
	for line in create_sql.splitlines():
		line = line.strip()
		if not line or line.upper().startswith("CREATE TABLE"):
			continue
		if line.startswith(");"):
			break
		col = line.split()[0].strip().strip(",")
		if col:
			expected_cols.append(col)

	if existing_cols == expected_cols:
		return

	tmp = f"{table}__old"
	conn.execute(f"ALTER TABLE {table} RENAME TO {tmp}")
	conn.execute(create_sql)

	# Best-effort copy for overlapping columns.
	if expected_cols:
		insert_cols = ", ".join(expected_cols)
		select_exprs = []
		for c in expected_cols:
			if c in existing_cols:
				select_exprs.append(c)
			elif c == "created_at":
				select_exprs.append("datetime('now','localtime')")
			elif c == "id":
				select_exprs.append("NULL")
			else:
				# Provide safe non-null defaults for new NOT NULL TEXT columns.
				select_exprs.append("''")
		select_sql = ", ".join(select_exprs)
		conn.execute(f"INSERT INTO {table} ({insert_cols}) SELECT {select_sql} FROM {tmp}")
	conn.execute(f"DROP TABLE {tmp}")


def init_db() -> None:
	conn = get_connection()
	try:
		_ensure_table_schema(
			conn,
			"request_logs",
			"""
			CREATE TABLE IF NOT EXISTS request_logs (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				method TEXT NOT NULL,
				path TEXT NOT NULL,
				status_code INTEGER NOT NULL,
				duration_ms REAL NOT NULL,
				client_ip TEXT,
				user_agent TEXT,
				created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
			);
			""",
		)

		# Endpoint-specific persistence tables matching Pydantic models
		_ensure_table_schema(
			conn,
			"set_pallet_requests",
			"""
			CREATE TABLE IF NOT EXISTS set_pallet_requests (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				SSCC TEXT NOT NULL,
				IDPoint TEXT NOT NULL,
				Message TEXT NOT NULL,
				Weight REAL NOT NULL,
				created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
			);
			""",
		)

		_ensure_table_schema(
			conn,
			"set_pallet_responses",
			"""
			CREATE TABLE IF NOT EXISTS set_pallet_responses (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				SSCC TEXT NOT NULL,
				Status TEXT NOT NULL,
				created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
			);
			""",
		)

		# Palette scan table (as requested)
		_ensure_table_schema(
			conn,
			"palletes_scan",
			"""
			CREATE TABLE IF NOT EXISTS palletes_scan (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				IDPoint TEXT NOT NULL,
				SSCC TEXT NOT NULL,
				Details TEXT NOT NULL,
				Status TEXT NOT NULL,
				Result TEXT NOT NULL,
				Msg TEXT NOT NULL,
				created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
			);
			""",
		)

		_ensure_table_schema(
			conn,
			"get_camera_res_requests",
			"""
			CREATE TABLE IF NOT EXISTS get_camera_res_requests (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				SSCC TEXT NOT NULL,
				created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
			);
			""",
		)

		_ensure_table_schema(
			conn,
			"get_camera_res_responses",
			"""
			CREATE TABLE IF NOT EXISTS get_camera_res_responses (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				IDPoint TEXT NOT NULL,
				SSCC TEXT NOT NULL,
				Status TEXT NOT NULL,
				Probability TEXT NOT NULL,
				Degree TEXT NOT NULL,
				Result TEXT NOT NULL,
				created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
			);
			""",
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


def insert_palletes_scan(
	id_point: str,
	sscc: str,
	details: str,
	status: str,
	result: str,
	msg: str,
) -> None:
	conn = get_connection()
	try:
		conn.execute(
			"""
			INSERT INTO palletes_scan(IDPoint, SSCC, Details, Status, Result, Msg)
			VALUES(?, ?, ?, ?, ?, ?)
			""",
			(id_point, sscc, details, status, result, msg),
		)
		conn.commit()
	finally:
		conn.close()


# Database viewer functions
def fetch_latest_palletes_scan_by_sscc(sscc: str) -> Optional[dict]:
	conn = get_connection()
	try:
		cur = conn.execute(
			"""
			SELECT id, IDPoint, SSCC, Details, Status, Result, Msg, created_at
			FROM palletes_scan
			WHERE SSCC = ?
			ORDER BY id DESC
			LIMIT 1
			""",
			(sscc,)
		)
		row = cur.fetchone()
		return dict(row) if row else None
	finally:
		conn.close()


def fetch_palletes_scan_by_sscc(sscc: str, limit: int = 50):
	conn = get_connection()
	try:
		cur = conn.execute(
			"""
			SELECT id, IDPoint, SSCC, Details, Status, Result, Msg, created_at
			FROM palletes_scan
			WHERE SSCC = ?
			ORDER BY id DESC
			LIMIT ?
			""",
			(sscc, limit),
		)
		return [dict(row) for row in cur.fetchall()]
	finally:
		conn.close()


def fetch_palletes_scan_analyzed(limit: int = 500, offset: int = 0):
	"""
	Return newest analyzed scan rows (SSCC + Msg only) with pagination.
	"""
	conn = get_connection()
	try:
		cur = conn.execute(
			"""
			SELECT SSCC, Msg
			FROM palletes_scan
			WHERE Status = ?
			ORDER BY id DESC
			LIMIT ? OFFSET ?
			""",
			("analyzed", limit, offset),
		)
		return [dict(row) for row in cur.fetchall()]
	finally:
		conn.close()

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



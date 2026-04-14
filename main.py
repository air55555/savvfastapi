from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Literal
from typing import List
from fastapi import Request
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import json

from db import (
	init_db, 
	insert_set_pallet_request, 
	insert_set_pallet_response, 
	insert_get_camera_res_request, 
	insert_get_camera_res_response, 
	fetch_logs,
	fetch_set_pallet_requests,
	fetch_set_pallet_responses,
	fetch_get_camera_res_requests,
	fetch_get_camera_res_responses,
	fetch_latest_palletes_scan_by_sscc,
	fetch_palletes_scan_by_sscc,
	fetch_palletes_scan_analyzed,
)
from version import get_version_info


def _setup_request_logger() -> logging.Logger:
	logger = logging.getLogger("savvfastapi.requests")
	if logger.handlers:
		return logger

	logger.setLevel(logging.INFO)

	# Log to file (rotating)
	log_dir = Path("logs")
	log_dir.mkdir(parents=True, exist_ok=True)
	file_handler = RotatingFileHandler(
		log_dir / "requests.log",
		maxBytes=2_000_000,
		backupCount=5,
		encoding="utf-8",
	)
	file_handler.setLevel(logging.INFO)

	# More verbose log file for payload/header dumps.
	file_handler_full = RotatingFileHandler(
		log_dir / "requests_full.log",
		maxBytes=5_000_000,
		backupCount=3,
		encoding="utf-8",
	)
	file_handler_full.setLevel(logging.INFO)

	formatter = logging.Formatter(
		fmt="%(asctime)s %(levelname)s %(message)s",
		datefmt="%Y-%m-%d %H:%M:%S",
	)
	file_handler.setFormatter(formatter)
	file_handler_full.setFormatter(formatter)

	# Also log to console
	stream_handler = logging.StreamHandler()
	stream_handler.setLevel(logging.INFO)
	stream_handler.setFormatter(formatter)

	logger.addHandler(file_handler)
	logger.addHandler(file_handler_full)
	logger.addHandler(stream_handler)
	logger.propagate = False
	return logger


request_logger_file = _setup_request_logger()


def _fix_mojibake_text(value: str) -> str:
	"""
	Best-effort fix for UTF-8 text that was decoded as latin-1/cp1252,
	which appears as sequences like 'Ð¡ÑÑ ...'.
	"""
	if not isinstance(value, str):
		return value
	if "Ð" not in value and "Ñ" not in value:
		return value
	try:
		fixed = value.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
		if any("\u0400" <= ch <= "\u04FF" for ch in fixed):
			return fixed
	except Exception:
		pass
	return value

class SetPalletRequest(BaseModel):
	SSCC: str
	IDPoint: str
	Message: Literal["PalletOnID"]
	Weight: float


class SetPalletResponse(BaseModel):
	SSCC: str
	Status: Literal["Ok"]

app = FastAPI(
    title="Vercel + FastAPI",
    description="Vercel + FastAPI",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
	init_db()

@app.get("/api/health")
def health_check():
    version_info = get_version_info()
    return {
        "status": "healthy",
        "version": version_info["version"],
        "semantic_version": version_info["semantic_version"],
        "commit_count": version_info["commit_count"],
        "build_date": version_info["build_date"],
        "git": version_info["git"],
        "api_name": version_info["api_name"]
    }

@app.post("/api/setpallet", response_model=SetPalletResponse)
def set_pallet(payload: SetPalletRequest) -> SetPalletResponse:
	# persist request
	insert_set_pallet_request(payload.SSCC, payload.IDPoint, payload.Message, payload.Weight)
	# build and persist response
	response = SetPalletResponse(SSCC=payload.SSCC, Status="Ok")
	insert_set_pallet_response(response.SSCC, response.Status)
	return response


class GetCameraResRequest(BaseModel):
	SSCC: str


class GetCameraResRecord(BaseModel):
	IDPoint: str
	SSCC: str
	Details: str
	ScanStatus: str
	Result: str
	Msg: str
	created_at: str


class GetCameraResResponse(BaseModel):
	Status: Literal["PalletResult"]
	Count: int
	Records: List[GetCameraResRecord]


class GetAllAnalyzedRecord(BaseModel):
	SSCC: str
	Msg: str


class GetAllAnalyzedResponse(BaseModel):
	Count: int
	Records: List[GetAllAnalyzedRecord]


@app.get("/api/getanalyzed", response_model=GetAllAnalyzedResponse)
def get_analyzed(limit: int = 500, offset: int = 0) -> GetAllAnalyzedResponse:
	# Hard safety caps: DB can contain thousands+ rows.
	if limit < 1:
		limit = 1
	if limit > 5000:
		limit = 5000
	if offset < 0:
		offset = 0

	rows = fetch_palletes_scan_analyzed(limit=limit, offset=offset)
	records = [GetAllAnalyzedRecord(SSCC=row["SSCC"], Msg=_fix_mojibake_text(row["Msg"])) for row in rows]
	return GetAllAnalyzedResponse(Count=len(records), Records=records)


@app.post("/api/getcamerares", response_model=GetCameraResResponse)
async def get_camera_res(payload: GetCameraResRequest) -> GetCameraResResponse:
	# persist request
	insert_get_camera_res_request(payload.SSCC)
	rows = fetch_palletes_scan_by_sscc(payload.SSCC, limit=50)
	records = [
		GetCameraResRecord(
			IDPoint=_fix_mojibake_text(row["IDPoint"]),
			SSCC=row["SSCC"],
			Details=_fix_mojibake_text(row["Details"]),
			ScanStatus=_fix_mojibake_text(row["Status"]),
			Result=_fix_mojibake_text(row["Result"]),
			Msg=_fix_mojibake_text(row["Msg"]),
			created_at=row["created_at"],
		)
		for row in rows
	]

	response = GetCameraResResponse(Status="PalletResult", Count=len(records), Records=records)

	latest_result = records[0].Result if records else "Not found"
	latest_id_point = records[0].IDPoint if records else "ID1"
	insert_get_camera_res_response(
		latest_id_point,
		payload.SSCC,
		response.Status,
		latest_result,
		latest_result,
		latest_result,
	)
	return response


@app.middleware("http")
async def request_logger(request: Request, call_next):
	# Read body early so downstream handlers can still access it (Starlette caches it).
	body_bytes = b""
	try:
		body_bytes = await request.body()
	except Exception:
		body_bytes = b""

	start = time.perf_counter()
	response = await call_next(request)
	duration_ms = (time.perf_counter() - start) * 1000.0
	try:
		from db import insert_log
		client_ip = request.client.host if request.client else None
		user_agent = request.headers.get("user-agent")
		insert_log(request.method, request.url.path, response.status_code, duration_ms, client_ip, user_agent)

		# Human-friendly request timing + file logging
		request_logger_file.info(
			"%s %s status=%s duration_ms=%.2f client_ip=%s ua=%s",
			request.method,
			request.url.path,
			response.status_code,
			duration_ms,
			client_ip,
			user_agent or "",
		)

		# Extended dump (payload + headers + query)
		# - We redact sensitive headers.
		# - We truncate huge bodies to keep logs manageable.
		MAX_BODY_BYTES = 50_000
		body_preview = body_bytes
		truncated = False
		if len(body_bytes) > MAX_BODY_BYTES:
			body_preview = body_bytes[:MAX_BODY_BYTES]
			truncated = True

		body_text = body_preview.decode("utf-8", errors="replace")
		if truncated:
			body_text += "...[TRUNCATED]"

		headers_dump = {}
		for k, v in request.headers.items():
			kl = k.lower()
			if kl in {"authorization", "cookie", "set-cookie"}:
				headers_dump[k] = "REDACTED"
			else:
				headers_dump[k] = v

		query_dump = dict(request.query_params)

		# Attempt to pretty-print JSON bodies if possible.
		body_json = None
		if body_text:
			try:
				body_json = json.loads(body_text)
			except Exception:
				body_json = None

		request_logger_file.info(
			"[IN] %s %s query=%s headers=%s body=%s",
			request.method,
			request.url.path,
			query_dump,
			headers_dump,
			json.dumps(body_json, ensure_ascii=False) if body_json is not None else body_text,
		)
	except Exception:
		# Avoid breaking requests due to logging failure
		pass
	return response


@app.get("/api/logs")
def get_logs(limit: int = 50) -> List[dict]:
	rows = []
	for row in fetch_logs(limit=limit):
		rows.append({
			"id": row[0],
			"method": row[1],
			"path": row[2],
			"status_code": row[3],
			"duration_ms": row[4],
			"client_ip": row[5],
			"user_agent": row[6],
			"created_at": row[7],
		})
	return rows

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title> FastAPI palette cheese API</title>
        <link rel="icon" type="image/x-icon" href="/favicon.ico">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
                background-color: #000000;
                color: #ffffff;
                line-height: 1.6;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                FAST API PALETTE
            }
FAST API PALETTE
            header {
                border-bottom: 1px solid #333333;
                padding: 0;
            }

            

           
        
    </body>
    </html>
    """

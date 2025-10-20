from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Literal
from typing import List
from fastapi import Request
import time

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
)

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
    return {"status": "healthy"}

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


class GetCameraResResponse(BaseModel):
	IDPoint: str
	SSCC: str
	Status: Literal["PalletResult"]
	Probability: str
	Degree: str
	Result: str


@app.post("/api/getcamerares", response_model=GetCameraResResponse)
async def get_camera_res(payload: GetCameraResRequest) -> GetCameraResResponse:
	# persist request
	insert_get_camera_res_request(payload.SSCC)
	# resolve result from the latest palletes_scan row for this SSCC
	row = fetch_latest_palletes_scan_by_sscc(payload.SSCC)
	resolved_result = row["Status"] if row else "Not found"
	# build and persist response
	response = GetCameraResResponse(
		IDPoint="ID1",
		SSCC=payload.SSCC,
		Status="PalletResult",
		Probability=resolved_result,
		Degree=resolved_result,
		Result=resolved_result,
	)
	insert_get_camera_res_response(
		response.IDPoint,
		response.SSCC,
		response.Status,
		response.Probability,
		response.Degree,
		response.Result,
	)
	return response


@app.middleware("http")
async def request_logger(request: Request, call_next):
	start = time.perf_counter()
	response = await call_next(request)
	duration_ms = (time.perf_counter() - start) * 1000.0
	try:
		from db import insert_log
		client_ip = request.client.host if request.client else None
		user_agent = request.headers.get("user-agent")
		insert_log(request.method, request.url.path, response.status_code, duration_ms, client_ip, user_agent)
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

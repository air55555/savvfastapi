from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Literal

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

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/setpallet", response_model=SetPalletResponse)
def set_pallet(payload: SetPalletRequest) -> SetPalletResponse:
	return SetPalletResponse(SSCC=payload.SSCC, Status="Ok")


class GetCameraResRequest(BaseModel):
	SSCC: str


class GetCameraResResponse(BaseModel):
	IDPoint: str
	SSCC: str
	Status: Literal["PalletResult"]
	Probability: str
	Degree: str
	Result: str

@app.get("/api/data")
def get_sample_data():
    return {
        "data": [
            {"id": 1, "name": "Sample Item 1", "value": 100},
            {"id": 2, "name": "Sample Item 2", "value": 200},
            {"id": 3, "name": "Sample Item 3", "value": 300}
        ],
        "total": 3,
        "timestamp": "2024-01-01T00:00:00Z"
    }


@app.get("/api/items/{item_id}")
def get_item(item_id: int):
    return {
        "item": {
            "id": item_id,
            "name": "Sample Item " + str(item_id),
            "value": item_id * 100
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }

@app.post("/api/getcamerares", response_model=GetCameraResResponse)
async def get_camera_res(payload: GetCameraResRequest) -> GetCameraResResponse:
	return GetCameraResResponse(
		IDPoint="ID1",
		SSCC=payload.SSCC,
		Status="PalletResult",
		Probability="98",
		Degree="3",
		Result="Not found",
	)

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

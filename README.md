# FastHTML Boilerplate

Deploy your [FastAPI](https://fastapi.tiangolo.com/) project to Vercel with zero configuration.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/vercel/vercel/tree/main/examples/fastapi&template=fastapi)

_Live Example: https://ai-sdk-preview-python-streaming.vercel.app/_

Visit the [FastAPI documentation](https://fastapi.tiangolo.com/) to learn more.

## Getting Started

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Running Locally

Start the development server on http://0.0.0.0:5001

```bash
uvicorn main:app --reload --port 5001
```

### curl examples

Health check:
```bash
curl -s http://localhost:5001/api/health
```

Set pallet:
```bash
curl -s -X POST http://localhost:5001/api/setpallet \
  -H "Content-Type: application/json" \
  -d '{
    "SSCC": "148102689000000010",
    "IDPoint": "ID1",
    "Message": "PalletOnID",
    "Weight": 123.45
  }'
```

Get camera result:
```bash
curl -s -X POST http://localhost:5001/api/getcamerares \
  -H "Content-Type: application/json" \
  -d '{
    "SSCC": "148102689000000010"
  }'
```

### Camera Result Testing with Different Database Records

The API includes pre-populated test data in the `palletes_scan` table. Here are different test cases:

#### Test Case 1: Good Result (SSCC: "111")
```bash
curl -s -X POST http://localhost:5001/api/getcamerares \
  -H "Content-Type: application/json" \
  -d '{"SSCC": "111"}'
```
**Expected Response:**
```json
{
  "IDPoint": "ID1",
  "SSCC": "111",
  "Status": "PalletResult",
  "Probability": "Ok",
  "Degree": "Ok",
  "Result": "Ok"
}
```

#### Test Case 2: Bad Result (SSCC: "666")
```bash
curl -s -X POST http://localhost:5001/api/getcamerares \
  -H "Content-Type: application/json" \
  -d '{"SSCC": "666"}'
```
**Expected Response:**
```json
{
  "IDPoint": "ID1",
  "SSCC": "666",
  "Status": "PalletResult",
  "Probability": "Bad 66.6 percent",
  "Degree": "Bad 66.6 percent",
  "Result": "Bad 66.6 percent"
}
```

#### Test Case 3: Unknown Result (SSCC: "777")
```bash
curl -s -X POST http://localhost:5001/api/getcamerares \
  -H "Content-Type: application/json" \
  -d '{"SSCC": "777"}'
```
**Expected Response:**
```json
{
  "IDPoint": "ID1",
  "SSCC": "777",
  "Status": "PalletResult",
  "Probability": "Unknown . Not scanned",
  "Degree": "Unknown . Not scanned",
  "Result": "Unknown . Not scanned"
}
```

#### Test Case 4: Not Found (SSCC: "999")
```bash
curl -s -X POST http://localhost:5001/api/getcamerares \
  -H "Content-Type: application/json" \
  -d '{"SSCC": "999"}'
```
**Expected Response:**
```json
{
  "IDPoint": "ID1",
  "SSCC": "999",
  "Status": "PalletResult",
  "Probability": "Not found",
  "Degree": "Not found",
  "Result": "Not found"
}
```

View recent request logs (limit 20):
```bash
curl -s "http://localhost:5001/api/logs?limit=20"
```

#### One-line curl (copy/paste)

Bash (Linux/macOS/Git Bash):
```bash
curl -s http://localhost:5001/api/health
```
```bash
curl -s -X POST http://localhost:5001/api/setpallet -H "Content-Type: application/json" -d '{"SSCC":"148102689000000010","IDPoint":"ID1","Message":"PalletOnID","Weight":123.45}'
```
```bash
curl -s -X POST http://localhost:5001/api/getcamerares -H "Content-Type: application/json" -d '{"SSCC":"148102689000000010"}'
```
```bash
curl -s "http://localhost:5001/api/logs?limit=20"
```

PowerShell (Windows):
```powershell
curl -Method GET "http://localhost:5001/api/health"
```
```powershell
curl -Method POST "http://localhost:5001/api/setpallet" -ContentType "application/json" -Body '{"SSCC":"148102689000000010","IDPoint":"ID1","Message":"PalletOnID","Weight":123.45}'
```

#### PowerShell Camera Result Testing:
```powershell
# Test Case 1: Good Result
curl -Method POST "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body '{"SSCC":"111"}'

# Test Case 2: Bad Result  
curl -Method POST "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body '{"SSCC":"666"}'

# Test Case 3: Unknown Result
curl -Method POST "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body '{"SSCC":"777"}'

# Test Case 4: Not Found
curl -Method POST "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body '{"SSCC":"999"}'
```

```powershell
curl -Method GET "http://localhost:5001/api/logs?limit=20"
```

PowerShell example (Invoke-RestMethod):
```powershell
$body = @{ SSCC = "148102689000000010"; IDPoint = "ID1"; Message = "PalletOnID"; Weight = 123.45 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:5001/api/setpallet" -ContentType "application/json" -Body $body
```
## Database Test Records

The database contains pre-populated test records for different scenarios:

| SSCC | Status | Description |
|------|--------|-------------|
| `111` | `Ok` | Good scan result |
| `666` | `Bad 66.6 percent` | Failed quality check |
| `777` | `Unknown . Not scanned` | Unscanned pallet |

### Quick Test Commands

**Good Result:**
```powershell
curl -Method POST "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body '{"SSCC":"111"}'
```

**Bad Result:**
```powershell
curl -Method POST "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body '{"SSCC":"666"}'
```

**Unknown Result:**
```powershell
curl -Method POST "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body '{"SSCC":"777"}'
```

### Adding New Test Records

To add new test records to the database:
```bash
python add_pallet_record.py --sscc 148102689000000010 --status Found
python add_pallet_record.py --sscc 999 --status "Quality Issue"
```


### 2) Получение результатов исследования аномалий
- POST `/api/getcamerares`

PowerShell example (Invoke-RestMethod):
```powershell
$body = @{ SSCC = "148102689000000010" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body $body
```
---- Integration  tests outside 
plain http browser
https://fastapi-plum-eight.vercel.app/api/health

Powershell
$body = @{ SSCC = "148102689000000010" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "https://fastapi-plum-eight.vercel.app/api/getcamerares" -ContentType "application/json" -Body $body

$body = @{ SSCC = "148102689000000010"; IDPoint = "ID1"; Message = "PalletOnID"; Weight = 123.45 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "https://fastapi-plum-eight.vercel.app/api/setpallet" -ContentType "application/json" -Body $body


Sample response:
```json
{
  "IDPoint": "ID1",
  "SSCC": "148102689000000010",
  "Status": "PalletResult",
  "Probability": "98",
  "Degree": "3",
  "Result": "Not found"
}
```
When you make changes to your project, the server will automatically reload.

## Deploying to Vercel

Deploy your project to Vercel with the following command:

```bash
npm install -g vercel
vercel --prod
```

Or `git push` to your repostory with our [git integration](https://vercel.com/docs/deployments/git).

To view the source code for this template, [visit the example repository](https://github.com/vercel/vercel/tree/main/examples/fastapi).

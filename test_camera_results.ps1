# Test script for getcamerares endpoint
Write-Host "Testing FastAPI getcamerares endpoint..." -ForegroundColor Green

# Test Case 1: Good Result (SSCC: 111)
Write-Host "`n=== Test Case 1: Good Result (SSCC: 111) ===" -ForegroundColor Yellow
$body1 = @{ SSCC = "111" } | ConvertTo-Json
try {
    $result1 = Invoke-RestMethod -Method POST -Uri "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body $body1
    Write-Host "✅ SUCCESS" -ForegroundColor Green
    $result1 | ConvertTo-Json -Depth 3
} catch {
    Write-Host "❌ FAILED: $($_.Exception.Message)" -ForegroundColor Red
}

# Test Case 2: Bad Result (SSCC: 666)
Write-Host "`n=== Test Case 2: Bad Result (SSCC: 666) ===" -ForegroundColor Yellow
$body2 = @{ SSCC = "666" } | ConvertTo-Json
try {
    $result2 = Invoke-RestMethod -Method POST -Uri "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body $body2
    Write-Host "✅ SUCCESS" -ForegroundColor Green
    $result2 | ConvertTo-Json -Depth 3
} catch {
    Write-Host "❌ FAILED: $($_.Exception.Message)" -ForegroundColor Red
}

# Test Case 3: Unknown Result (SSCC: 777)
Write-Host "`n=== Test Case 3: Unknown Result (SSCC: 777) ===" -ForegroundColor Yellow
$body3 = @{ SSCC = "777" } | ConvertTo-Json
try {
    $result3 = Invoke-RestMethod -Method POST -Uri "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body $body3
    Write-Host "✅ SUCCESS" -ForegroundColor Green
    $result3 | ConvertTo-Json -Depth 3
} catch {
    Write-Host "❌ FAILED: $($_.Exception.Message)" -ForegroundColor Red
}

# Test Case 4: Not Found (SSCC: 999)
Write-Host "`n=== Test Case 4: Not Found (SSCC: 999) ===" -ForegroundColor Yellow
$body4 = @{ SSCC = "999" } | ConvertTo-Json
try {
    $result4 = Invoke-RestMethod -Method POST -Uri "http://localhost:5001/api/getcamerares" -ContentType "application/json" -Body $body4
    Write-Host "✅ SUCCESS" -ForegroundColor Green
    $result4 | ConvertTo-Json -Depth 3
} catch {
    Write-Host "❌ FAILED: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== All Tests Completed ===" -ForegroundColor Cyan

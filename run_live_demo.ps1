Write-Host "Starting Autonomous QA Intelligence Platform..." -ForegroundColor Cyan

# 1. Start Backend if not running
$backendPort = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $backendPort) {
    Write-Host "Starting Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
    Start-Process -FilePath "backend\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory "backend" -WindowStyle Hidden
    Start-Sleep -Seconds 3
} else {
    Write-Host "Backend already running on port 8000." -ForegroundColor Green
}

# 2. Open Local App in Browser (Fastest, zero latency)
Start-Process "http://localhost:8000"

# 3. Start Cloudflare Tunnel for public internet access
Write-Host "Starting Cloudflare Public Tunnel..." -ForegroundColor Cyan
Write-Host "Keep this window open to keep the public demo link alive." -ForegroundColor Yellow
.\cloudflared.exe tunnel --url http://127.0.0.1:8000

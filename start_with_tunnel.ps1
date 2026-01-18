# Chronica MCP Server with cloudflared tunnel
# This script starts the HTTP/SSE server and cloudflared tunnel

Write-Host "Starting Chronica MCP Server (HTTP/SSE)..." -ForegroundColor Green

# Start server in background
$serverJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python run_server_http.py
}

# Wait for server to start
Start-Sleep -Seconds 3

Write-Host "Starting cloudflared tunnel..." -ForegroundColor Green
Write-Host "HTTPS URL will be displayed below." -ForegroundColor Yellow
Write-Host "Use the HTTPS URL with /sse endpoint in GPT." -ForegroundColor Yellow
Write-Host ""

# Start cloudflared tunnel
cloudflared tunnel --url http://127.0.0.1:8000

# Clean up
Stop-Job $serverJob
Remove-Job $serverJob

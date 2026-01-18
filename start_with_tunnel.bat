@echo off
REM Chronica MCP Server with cloudflared tunnel
REM This script starts the HTTP/SSE server and cloudflared tunnel

echo Starting Chronica MCP Server (HTTP/SSE)...
start "Chronica Server" python run_server_http.py

REM Wait for server to start
timeout /t 3 /nobreak >nul

echo Starting cloudflared tunnel...
echo HTTPS URL will be displayed below.
echo Use the HTTPS URL with /sse endpoint in GPT.
echo.
cloudflared tunnel --url http://127.0.0.1:8000

pause

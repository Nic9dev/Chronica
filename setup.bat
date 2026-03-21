@echo off
REM Chronica セットアップスクリプト（Windows）
REM setup.ps1 を呼び出します

powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
exit /b %ERRORLEVEL%

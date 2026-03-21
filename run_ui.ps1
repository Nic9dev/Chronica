# Chronica UI起動スクリプト（PowerShell）
Write-Host "Starting Chronica UI..." -ForegroundColor Green

# venv環境を有効化（存在する場合）
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".venv\Scripts\Activate.ps1"
}

# streamlitを起動
python -m streamlit run app.py

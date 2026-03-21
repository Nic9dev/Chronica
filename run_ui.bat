@echo off
REM Chronica UI起動スクリプト（Windows）
echo Starting Chronica UI...

REM venv環境を有効化（存在する場合）
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM streamlitを起動
python -m streamlit run app.py

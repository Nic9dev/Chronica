@echo off
REM Chronica キュレーションUI起動スクリプト（Windows）
echo Starting Chronica Curation UI...

REM venv環境を有効化（存在する場合）
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM streamlitを起動
python -m streamlit run app_curation.py

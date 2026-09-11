@echo off
cd /d %~dp0\..\backend
python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt uvicorn[standard]>=0.30
uvicorn app.main:app --reload --port 8000

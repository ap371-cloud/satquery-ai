@echo off
title SatQuery AI - Full Stack + Cloudflare Tunnel
color 0A

echo ============================================
echo    SatQuery AI - Starting All Services
echo ============================================
echo.

:: -----------------------------------------------
:: 1. Start Backend (FastAPI / Python)
:: -----------------------------------------------
echo [1/3] Starting Backend on port 8000...
start "SatQuery Backend" cmd /k "cd /d %~dp0backend && python -m venv .venv && call .venv\Scripts\activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000"
timeout /t 5 /nobreak >nul

:: -----------------------------------------------
:: 2. Start Frontend (Vite / React)
:: -----------------------------------------------
echo [2/3] Starting Frontend on port 5173...
start "SatQuery Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"
timeout /t 5 /nobreak >nul

:: -----------------------------------------------
:: 3. Start Cloudflare Tunnel
:: -----------------------------------------------
echo [3/3] Starting Cloudflare Tunnel...
echo.
echo --------------------------------------------
echo  Cloudflare tunnel will show a public URL
echo  Copy that URL to share your local app
echo --------------------------------------------
echo.
cloudflared tunnel --url http://localhost:5173

pause

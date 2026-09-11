@echo off
cd /d %~dp0\..\frontend
call npm install
npm run dev

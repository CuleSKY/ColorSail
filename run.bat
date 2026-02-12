@echo off
setlocal

if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)

if "%APP_SECRET_KEY%"=="" (
  echo APP_SECRET_KEY is required
  exit /b 1
)
if "%AGENT_MASTER_URL%"=="" (
  echo AGENT_MASTER_URL is required
  exit /b 1
)
if "%AGENT_SHARED_TOKEN%"=="" (
  echo AGENT_SHARED_TOKEN is required
  exit /b 1
)

python app.py

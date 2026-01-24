$ErrorActionPreference = "Stop"

$env:APP_SECRET_KEY      = "Ss1Ktt7G8c5zusQirc6Ah6dgbuIy3WN4c9DEOMnW5L0="
$env:AGENT_SHARED_TOKEN  = "2004615abc"
$env:WATCHER_SHARED_TOKEN= "2004615abc"
$env:WATCHER_SERVICE_URL = "http://127.0.0.1:5010"

Write-Host "[INFO] Make sure watcher_service\watcher_config.json http.shared_token == WATCHER_SHARED_TOKEN"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\.venv\Scripts\Activate.ps1; python watcher_service\watcher_main.py"

python app.py

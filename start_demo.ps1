# Starts the local CosyVoice worker (own window, loads the model once) and then the demo server.
#   .\start_demo.ps1            normal
#   .\start_demo.ps1 -Debug     also enables the developer audio preview (?dev=1)
param([switch]$Debug)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = (Select-String -Path config.py -Pattern '^COSYVOICE_PYTHON\s*=\s*"(.+)"').Matches[0].Groups[1].Value

if (-not (Test-NetConnection 127.0.0.1 -Port 8765 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "& '$py' workers/cosyvoice_server.py"
    Write-Host "CosyVoice worker starting in a new window (about 25 s to load)."
} else { Write-Host "CosyVoice worker already running." }

if ($Debug) { $env:DEMO_DEBUG = "1" }
Write-Host "Demo at http://localhost:8000   (health: http://localhost:8000/api/health)"
python -m uvicorn server:app --host 127.0.0.1 --port 8000

# Starts the local engine workers (each in its own window, each loads its model once) and then the demo server.
#   .\start_demo.ps1            normal
#   .\start_demo.ps1 -Debug     also enables the developer audio preview (?dev=1)
param([switch]$Debug)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if (Test-Path .venv\Scripts\python.exe) { ".venv\Scripts\python.exe" } else { "python" }

function Get-Setting($name) { (& $py -c "import config; print(config.$name)").Trim() }

$workers = @(
    @{ name = "Qwen3-TTS"; engine = "qwen3tts";  port = 8766; python = (Get-Setting "QWEN_PYTHON");      script = "workers/qwen3tts_server.py" }
)
$enabled = (& $py -c "import config; print(' '.join(config.ENGINES))").Split(" ")
foreach ($w in $workers) {
    if ($enabled -notcontains $w.engine) { continue }
    if (Test-NetConnection 127.0.0.1 -Port $w.port -InformationLevel Quiet -WarningAction SilentlyContinue) {
        Write-Host "$($w.name) worker already running."
    } elseif (-not (Test-Path $w.python)) {
        Write-Host "$($w.name): environment not found at $($w.python). Run python setup.py first." -ForegroundColor Yellow
    } else {
        $env:HF_HOME = (Get-Setting "HF_HOME")
        Start-Process powershell -ArgumentList '-NoExit', '-Command', "& '$($w.python)' $($w.script)"
        Write-Host "$($w.name) worker starting in a new window (about 25 s to load)."
    }
}

if ($Debug) { $env:DEMO_DEBUG = "1" }
Write-Host "Demo at http://localhost:8000   (health: http://localhost:8000/api/health)"
& $py -m uvicorn server:app --host 127.0.0.1 --port 8000

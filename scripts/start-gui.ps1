# Avvia la GUI di Red Giant (detached) e apre il browser. Doppio click e via.
#   scripts\start-gui.ps1 [-Profile severino-sim]
param([string]$Profile = "severino-sim")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Rg = Join-Path $Root ".venv\Scripts\rg.exe"
if (-not (Test-Path $Rg)) { Write-Host "venv mancante: crea .venv e 'pip install -e .'"; exit 1 }

$alive = $false
try { $null = Invoke-WebRequest "http://127.0.0.1:8090/" -TimeoutSec 2 -UseBasicParsing; $alive = $true } catch {}
if (-not $alive) {
    New-Item -ItemType Directory -Force (Join-Path $Root "data") | Out-Null
    Start-Process -WindowStyle Hidden -FilePath $Rg -ArgumentList "serve","--profile",$Profile `
        -WorkingDirectory $Root `
        -RedirectStandardOutput (Join-Path $Root "data\gui-stdout.log") `
        -RedirectStandardError (Join-Path $Root "data\gui-stderr.log")
    foreach ($i in 1..15) { Start-Sleep 1; try { $null = Invoke-WebRequest "http://127.0.0.1:8090/" -TimeoutSec 2 -UseBasicParsing; break } catch {} }
}
Start-Process "http://127.0.0.1:8090/"

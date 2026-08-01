# Scarica i binari llama.cpp PINNATI (D2) in bin/ (gitignored): variante CUDA (dev-fast)
# e variante CPU pura (misure oneste). Idempotente.
# Cambiare il tag = decisione di piattaforma: rifare i bench F0.5 e annotare nell'atlante.
$ErrorActionPreference = "Stop"

$Tag = "b10217"   # pin: config/default.toml e codebase_reference devono citare lo stesso tag
# TRAPPOLA (2026-08-02): la build CUDA richiede le DLL del runtime che stanno in uno
# zip SEPARATO (cudart). Senza, il backend CUDA non si carica e llama.cpp ripiega
# in silenzio sulla CPU — "dev-fast" era un CPU-a-24-thread travestito.
$Assets = @(
    @{ Name = "llama-$Tag-bin-win-cuda-12.4-x64.zip";  Dir = "cuda" },
    @{ Name = "cudart-llama-bin-win-cuda-12.4-x64.zip"; Dir = "cuda" },
    @{ Name = "llama-$Tag-bin-win-cpu-x64.zip";        Dir = "cpu"  }
)

$Root = Split-Path -Parent $PSScriptRoot
$BinRoot = Join-Path $Root "bin\llama-$Tag"

foreach ($a in $Assets) {
    $dest = Join-Path $BinRoot $a.Dir
    $exe  = Join-Path $dest "llama-server.exe"
    $isCudart = $a.Name -like "cudart*"
    $cudartMarker = Join-Path $dest "cudart64_12.dll"
    if (-not $isCudart -and (Test-Path $exe)) { Write-Host ">> $($a.Dir): gia' presente ($exe)"; continue }
    if ($isCudart -and (Test-Path $cudartMarker)) { Write-Host ">> cudart: gia' presente"; continue }
    New-Item -ItemType Directory -Force $dest | Out-Null
    $zip = Join-Path $env:TEMP $a.Name
    $url = "https://github.com/ggml-org/llama.cpp/releases/download/$Tag/$($a.Name)"
    Write-Host ">> Download $url"
    & curl.exe -L --fail --retry 3 -o $zip $url
    if ($LASTEXITCODE -ne 0) { throw "download fallito (curl exit $LASTEXITCODE)" }
    Expand-Archive -Path $zip -DestinationPath $dest -Force
    Remove-Item $zip -Force
    if (-not (Test-Path $exe)) { throw "estratto $($a.Name) ma llama-server.exe non trovato in $dest" }
    Write-Host ">> OK: $exe"
}
Write-Host ">> Binari llama.cpp $Tag pronti."

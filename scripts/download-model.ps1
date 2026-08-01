# Scarica il GGUF di Gemma 4 E2B (QAT, UD-Q4_K_XL) in models/ e ne verifica lo SHA256.
# Idempotente: se il file esiste e l'hash torna, esce senza fare nulla.
#
# Scelta del file (F0.2): variante QAT = quantization-aware training di Google,
# qualita' quasi-BF16 al peso di una Q4 (2.44 GiB). Testo-only per l'MVP: niente mmproj.
$ErrorActionPreference = "Stop"

$Url    = "https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF/resolve/main/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
$Sha256 = "e531007218dfab990486a5de7676a6932d6ea8dea233d1f698d7c21cf8a16889"
$Bytes  = 2620370976

$Root = Split-Path -Parent $PSScriptRoot
$Dest = Join-Path $Root "models\gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
New-Item -ItemType Directory -Force (Split-Path $Dest) | Out-Null

if (Test-Path $Dest) {
    Write-Host ">> File presente, verifico hash..."
    $h = (Get-FileHash -Algorithm SHA256 $Dest).Hash.ToLower()
    if ($h -eq $Sha256) { Write-Host ">> OK: modello gia' scaricato e integro."; exit 0 }
    Write-Host ">> Hash errato ($h), riscarico."
    Remove-Item $Dest -Force
}

Write-Host ">> Download ($([math]::Round($Bytes/1GB,2)) GB): $Url"
& curl.exe -L --fail --retry 3 --retry-delay 5 -o "$Dest.part" $Url
if ($LASTEXITCODE -ne 0) { throw "download fallito (curl exit $LASTEXITCODE)" }
Move-Item "$Dest.part" $Dest -Force

$h = (Get-FileHash -Algorithm SHA256 $Dest).Hash.ToLower()
if ($h -ne $Sha256) { throw "SHA256 mismatch: atteso $Sha256, ottenuto $h" }
Write-Host ">> OK: modello scaricato e verificato."

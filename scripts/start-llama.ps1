# Avvia llama-server per il profilo indicato (piano F0.2, decisioni D2/D6/D7).
#   scripts\start-llama.ps1 -Profile dev-fast [-Ctx 8192] [-Port 8080]
#
# dev-fast     -> CPU-bound, 24 thread (DECISIONE UTENTE 2026-08-02: anche gli smoke
#                 devono sentire il peso della CPU — la GPU non si usa per l'inferenza
#                 del progetto: renderebbe i giudizi troppo ottimisti)
# severino-sim -> delega al Docker compose CPU-only (F0.4)
# severino     -> il server gira SUL box (gestito da li'); qui solo promemoria
param(
    [Parameter(Mandatory)][ValidateSet("dev-fast","severino-sim","severino")] [string]$Profile,
    [int]$Ctx = 8192,
    [int]$Port = 8080
)
$ErrorActionPreference = "Stop"
$Root  = Split-Path -Parent $PSScriptRoot
$Tag   = "b10217"                     # pin condiviso con download-llama.ps1
$Model = Join-Path $Root "models\gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
$Slots = Join-Path $Root "data\slots"
New-Item -ItemType Directory -Force $Slots | Out-Null

switch ($Profile) {
    "severino" {
        Write-Host "Il server del profilo 'severino' gira sul box (deploy F8)."
        Write-Host "Questo PC vi si collega via config/profiles/severino.toml (endpoint Tailscale)."
        exit 0
    }
    "severino-sim" {
        $compose = Join-Path $Root "docker\severino-sim\compose.yml"
        if (-not (Test-Path $compose)) { throw "compose non ancora creato (sottofase F0.4): $compose" }
        docker compose -f $compose up -d
        exit $LASTEXITCODE
    }
    "dev-fast" {
        if (-not (Test-Path $Model)) { throw "modello mancante: esegui scripts\download-model.ps1" }
        $exe = Join-Path $Root "bin\llama-$Tag\cpu\llama-server.exe"
        if (-not (Test-Path $exe)) { throw "binari mancanti: esegui scripts\download-llama.ps1" }
        # --parallel 1 (D7: una inferenza alla volta) · --slot-save-path (predisposto per F0.5/F5)
        # --chat-template gemma: i token BOS/EOS di Gemma differiscono dai default (output
        # corrotto senza template corretto).
        & $exe --model $Model --ctx-size $Ctx --parallel 1 --threads 24 `
               --slot-save-path $Slots --chat-template gemma `
               --host 127.0.0.1 --port $Port
    }
}

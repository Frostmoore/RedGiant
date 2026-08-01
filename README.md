# Red Giant

Sistema agentico per modelli **minuscoli** (Gemma 4 E2B, Q4) su hardware da non-prosumer:
decomposizione, verifica continua, contesto minimo, orchestrazione deterministica.
Il modello resta piccolo; il sistema diventa grande.

- **Specsheet:** [memory/small-model-powerhouse-specsheet.md](memory/small-model-powerhouse-specsheet.md)
- **Piano di sviluppo (contratto):** [memory/plan_red_giant.md](memory/plan_red_giant.md)
- **Atlante della codebase:** [memory/codebase_reference.md](memory/codebase_reference.md)

## Profili di esecuzione (D6)

| Profilo | Cos'è | Uso |
|---|---|---|
| `dev-fast` | llama-server CUDA su questo PC | solo iterazione sul codice, MAI metriche |
| `severino-sim` | Docker CPU-only, 4 core, RAM limitata | metriche ufficiali quotidiane |
| `severino` | il box reale (via Tailscale) | validazione di fase e produzione |

## Setup (sviluppo, Windows)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# modello e server (F0.2):
scripts\download-model.ps1
scripts\start-llama.ps1 -Profile dev-fast
```

## Comandi

```powershell
rg --help          # CLI (i sottocomandi run|status|eval|bench arrivano in F1)
python bench/run_bench.py --profile severino-sim   # baseline (F0.5)
python scripts/check_reference.py                  # verifica atlante <-> codice (F0.7)
```

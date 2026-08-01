# F0.5 — Baseline `severino-sim`

Data: 20260801-130856 UTC · endpoint `http://127.0.0.1:8081` · server `b10200-5f55650a7` · repeats 3

## Prefill freddo

| ctx target | tok/s (media) | dev.std | tempo per prompt pieno |
|---|---|---|---|
| 1024 | 151 | 1 | 6.8s |
| 4096 | 133 | 0 | 30.7s |
| 8192 | 118 | 1 | 69.6s |
| 16384 | 94 | 1 | 173.6s |

## Generazione: **35.8 tok/s** (dev.std 0.2)

## Riuso del prefisso (ctx ~8192)

| scenario | token riprocessati | atteso |
|---|---|---|
| A freddo | 7970 | ~8192 (tutto) |
| B = A+coda | 65 | ~|coda| (pochi) |
| C = byte cambiato a meta' | 7971 | ~meta' di A |

**Prova di D9:** un byte a meta' prompt costa 7971 token riprocessati contro i 65 dell'append puro.

## Slot save/restore: API integra, riuso post-restore NON funzionante (build b10200)

Misure (run dedicata + diagnosi a ctx 2K): save 56-211ms, restore 42-164ms, `n_saved == n_restored`,
~13.4 KB/token su disco (8K token ≈ 107 MB). MA: dopo il restore, lo stesso identico prompt
riprocessa il 100% dei token (872/872), mentre il riuso normale via `cache_prompt` funziona
(1/872 su prompt ripetuto, 59 su append). Diagnosi: il restore ripristina i dati KV ma non il
bookkeeping dei token usato dal matching LCP. **Conseguenza (F0.6):** slot-save inutilizzabile
come skip del prefill sulla build pinnata; da riverificare in F5.4 su build successiva.

Numeri grezzi: `results\raw\baseline_severino-sim_20260801-130856.csv`

# F0.5 — Baseline `dev-fast`

> ⚠️ PROFILO NON UFFICIALE (D6): numeri validi solo come confronto informale.


Data: 20260804-125944 UTC · endpoint `http://127.0.0.1:8080` · server `b10217-ddd4ec142` · repeats 1

## Prefill freddo

| ctx target | tok/s (media) | dev.std | tempo per prompt pieno |
|---|---|---|---|

## Riuso del prefisso (ctx ~4096)

| scenario | token riprocessati | atteso |
|---|---|---|
| A freddo | 4002 | ~4096 (tutto) |
| B = A+coda | 65 | ~|coda| (pochi) |
| C = byte cambiato a meta' | 2001 | ~meta' di A |
| **D = blocco RIMOSSO dal mezzo** | **1390** | dipende da `--cache-reuse` |
| **E = D + coda nuova** | **65** | il caso reale del loop |

**Prova di D9:** un byte a meta' prompt costa 2001 token riprocessati contro i 65 dell'append puro.

**F5.0-ante — il caso della COMPATTAZIONE (D/E).** C cambia un byte *in place*; la compattazione invece **rimuove un blocco** e fa traslare all'indietro tutto cio' che segue. E' la situazione per cui esiste `--cache-reuse N` (riuso via KV shifting, default **0** = spento). Questi due numeri, confrontati fra configurazioni diverse del flag, dicono se il compromesso su cui e' costruita F5 sia reale o un artefatto della nostra configurazione.

## Slot save/restore: saltato

Numeri grezzi: `results\raw\baseline_dev-fast_20260804-125944.csv`

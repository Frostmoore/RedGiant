# A/B ufficiale PS6.2 — plansys vs baseline + ablation (severino-sim)

**Data:** 2026-08-02 sera · **Commit:** `11e3502` (A, B) / `13282de` (B1–B3, solo docs in mezzo, codice identico) · **Profilo:** severino-sim (Docker, 2 core workstation ≈ 4 core target, CPU-only) · **Working tree pulito verificato dallo script** · Report sorgente: `eval_severino-sim_static_20260802-165058.md`, `eval_severino-sim_plansys_20260802-173450.md`, `..._175503.md` (B1), `..._181938.md` (B2), `..._183751.md` (B3).

**Preparazione**: PS6.1 verificata (tutti e tre i task grossi falliscono in baseline; T041 esteso a 3 moduli perché la v1 veniva chiusa dalla baseline — giudice provato soddisfacibile con implementazione di riferimento). Due dry-run GPU preliminari (non ufficiali) hanno scovato e fatto fixare 4 difetti del control plane prima di questa corsa (falsi positivi prosa/package/nomi canonici + budget M2).

## 1. Le metriche cardine

| Metrica | A: baseline naive | B: plansys | Δ |
|---|---|---|---|
| **Verificati** (giudice esterno) | **6/13** | **2/13** | −4 |
| Token totali | 1.143.461 | **635.894** | **−44%** |
| Token utili / totali | 20,8% | 30,2% | +9,4pt |
| Wall clock | 2.610s | 2.632s | ≈ pari |
| Forbice completed≠verified | 0 | **1** (T041, v. §3) | — |

Sui 10 micro-task: baseline 6/10, plansys 2/10. Sui 3 task multi-fase (il target del sistema): **0/3 entrambi** — la baseline brucia 100–200K token a testa per fallire, il plansys muore prima e a costo minore.

**Nota di comparabilità sul 9/10 storico**: il 9/10 della baseline è del rerun F3 della notte precedente su `611d894`. Tra i due commit sono cambiate 3 superfici condivise (card Worker regola 12, esclusioni `_repo_listing`, `syntax_hint`): su CPU deterministica i task marginali (T008–T010) hanno cambiato traiettoria. Il confronto di QUESTO report è interno allo stesso commit ed è quello valido. La bisection della regressione baseline è debito dichiarato (§5).

## 2. Ablation per componente (T040–T042, tutti 0/3 in ogni braccio)

| Braccio | Token (3 task) | vs B completo (192K) | Verdetto componente |
|---|---|---|---|
| B completo | 192.237 | — | — |
| B1 senza oracle gate | 289.960 | **+51%** | **RESTA** — non compra verificati qui, ma contiene il costo: senza, T041 brucia 140K/627s inseguendo test non qualificati (vs 20K/138s con gate). Nei batch storici ha azzerato le famiglie di test-truffa |
| B2 senza ledger | 338.238 | **+76%** | **RESTA** — il costo peggiore: senza memoria esterna il compiler ri-esplora (T041: 20K→160K) |
| B3 senza entry gate | 287.560 | +50% | **RESTA CON RISERVA** — il costo cresce, ma su questo set nessuna fase viene mai ri-provata (lo scenario fasi-ridondanti non si materializza); il valore pieno è dimostrato solo nei piloti. Da ri-misurare su task che completano più fasi |

**Conclusione ablation: nessuna componente compra verificati sul set difficile; tutte e tre comprano contenimento del costo dei fallimenti (+50%…+76% di token senza).** Con un tasso di successo ancora basso, il contenimento È il valore.

## 3. Tassonomia delle morti (run B, 13 task, dal DB)

| Famiglia | Task | Lettura |
|---|---|---|
| ✅ Verificati | T004, T005 | piani 1-fase puliti, proof verdi, giudice verde |
| ⚠️ **Forbice** (completed≠verified) | T041 | **under-scoping del Senior**: criteri = solo stats.py, hist/summary mai pianificati; coverage interno verde, giudice `No module named 'hist'`. Il gap si è spostato A MONTE: nessun gate confronta i criteri con la richiesta. La richiesta NOMINA i tre file → check deterministico possibile (fix §5.1) |
| **Synthesis gate su suite piena** | T007, T010, T040 | **difetto strutturale scoperto**: `synthesis_cmds=pytest` esegue TUTTA la suite fornita alla chiusura di P1 — su task multi-fase i test delle fasi future sono rossi per definizione → morte inevitabile anche con P1 perfetta (fix §5.2) |
| Oracle gate respinge (costo, non bug) | T001, T002 | characterization sbagliate uccise in compilazione: morti economiche e oneste |
| M3/M4 residui | T003 (test.php: l'eccezione "file esistente" dei nomi canonici tiene un file NON-py — fix §5.3), T006 (targets), T008 (M2 coverage) | famiglie note, code residue |
| J sui proof | T009, T042 | il muro F18, invariato |

## 4. Verdetto PS6.3 (D11, onesto)

**Il sistema NON si è guadagnato l'accensione di default.** Con 2/13 contro 6/13 la risposta alla domanda del piano è **no, e si documenta perché**: (a) sui micro-task la governance resta un sovrapprezzo che il 2B non ripaga; (b) sui task larghi — il suo target — il sistema non converte ancora, e tre delle cause sono difetti di control plane appena scoperti e fixabili (§5), non limiti del modello; (c) la forbice-zero, l'invariante fondante, ha retto ovunque tranne il nuovo gap S (anch'esso chiudibile deterministicamente).

**Cosa il sistema ha comprato, coi numeri**: fallimenti che costano metà (636K vs 1.143K), token utili +9pt, diagnosi attribuibile per stadio di ogni morte, e ~50 regole deterministiche che hanno azzerato intere famiglie di errore. Il plansys resta **gated** (`[plansys] enabled=false`), il verdetto si riapre dopo: i fix di §5 + l'esperimento thinking T-SM (`plan_thinking_ab.md`) — che i dati di stasera motivano direttamente (le morti di testa: under-scoping S, characterization sbagliate di M).

## 5. Fix identificati da questa corsa (post-verdetto, in ordine)

1. **Copertura della richiesta**: i file nominati esplicitamente nella richiesta devono comparire negli artifacts di qualche fase del MacroPlan — gate deterministico su S (chiude la famiglia forbice-T041).
2. **Synthesis gate scoped**: la sintesi di fase esegue i proof della fase + i test delle fasi GIÀ chiuse, mai i test di fasi future; la suite piena resta al coverage gate finale (chiude T007/T010/T040-synthesis).
3. **Eccezione nomi canonici solo per `test_*.py` esistenti** (chiude T003).
4. **`test_author_max_tokens` 3072→4096** (p95 = cap, audit budget dal DB) + regola permanente: cap ≥ 1,5× p95 misurato dopo ogni run ufficiale.
5. Bisection della regressione baseline 9/10→6/10 (card regola 12 / repo_listing / syntax_hint, una alla volta su `611d894`).

## 6. Metriche PS-D9 (dal DB e dai log)

- **Test deboli respinti dall'oracle gate**: 5 morti-compile per qualificazione fallita nelle run ufficiali (T001/T002 B + 3 nelle ablation) — tutte prima che J spendesse un token.
- **Retry fotocopia bloccati**: 6 blocchi photocopy nelle run ufficiali (B+ablation) — ciascuno risparmia ~1 sessione J identica.
- **Token di governance**: ~7 chiamate M+S per fase (medie ruoli: S 418, M1 404, M2 219, M3 159, M4 415 gen-token/chiamata).
- **Criteri coperti**: coverage interno 100% nei 3 completed; il caso T041 dimostra che "coperto" ≠ "richiesto" (fix §5.1).
- **Lavoro duplicato**: non osservato nelle run B (l'ownership esclusiva lo rende irrappresentabile).

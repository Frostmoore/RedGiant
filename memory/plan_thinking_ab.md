# Piano: A/B Thinking Mode su Gemma 4 E2B (esperimento TH)

**Stato:** 📋 pianificato — prerequisito: PS6 chiusa (il braccio di controllo è il suo run B ufficiale).
**Decisione utente (2026-08-02):** PS6 si chiude nella condizione storica no-thinking; POI il thinking
si misura con un batch dedicato comparabile, per determinare la differenza di prestazioni e di
token/tempo. Questo documento è la specsheet di quell'esperimento.

---

## 0. Il fatto di partenza (da mettere a verbale, era implicito)

**In tutto Red Giant, dal F0 a PS6 incluso, il thinking mode NON è mai stato attivo — per
costruzione, non per scelta documentata:**

1. `redgiant/prompts/assemble.py` costruisce il prompt A MANO con i marcatori di turno Gemma
   (`_TURN_OPEN = "<start_of_turn>user\n"`, `_TURN_CLOSE = "\n<end_of_turn>\n<start_of_turn>model\n"`)
   e `LlamaClient.complete` chiama l'endpoint raw `/completion`: qualunque attivazione del thinking
   che passi dal chat template del server non viene mai emessa.
2. Ogni chiamata è grammar-constrained (GBNF da JSON Schema): il primo token generato DEVE aprire
   il JSON. Un preambolo di pensiero è grammaticalmente irrappresentabile.

**Perché è coerente col progetto** (e quindi il default resta no-thinking anche dopo l'esperimento,
salvo verdetto contrario): su Severino la generazione corre a 35,8 tok/s — una traccia di pensiero
da N token costa N/35,8 secondi PER CHIAMATA; la specsheet §3 impone "la verbosità non è
ragionamento" (il `thought` di J è cappato a 300 caratteri per questo).

**Perché comunque va misurato**: due classi di fallimento candidate, in ordine di priorità:
1. **S e M sbagliano le decisioni di testa** (ipotesi PRIMARIA, decisione utente 2026-08-02 dopo il
   blocco B ufficiale di PS6: 5 micro-task morti a zero tool call in compilazione, più la forbice
   T041 da under-scoping del Senior — criteri che coprivano un terzo della richiesta). S e M fanno
   decisioni compresse single-shot: è il caso d'uso classico del reasoning esplicito, e il costo è
   limitato (S parla 1 volta per task, M 4 per fase — mai dentro il loop di J).
2. **Il muro F18 di J** (ipotesi secondaria): J non riproduce i formati esatti dei proof (~metà
   delle morti residue quando la compilazione regge).
Crederci o non crederci è vietato dal metodo: si misura (D-metodo di F3: "le run ufficiali solo da
codice committato", "ogni ruolo si guadagna il posto con un A/B").

---

## Rituale di fine fase (OBBLIGATORIO, prima del tracking)

Alla fine di OGNI fase TH*n*:
1. Aggiornare QUESTO documento (checkbox + esiti numerici nella fase).
2. Aggiornare `memory/codebase_reference.md` (nuove firme/colonne/trappole) e far passare
   `python scripts/check_reference.py`.
3. Messaggio ESTREMAMENTE dettagliato: stato, checkbox di fase e sottofasi, commento generale.
4. Commit e push su branch versionato (origin=Gitea E github), tabella versioni sotto.

| Fine fase | Branch | Entità |
|---|---|---|
| TH0 (meccanica) | `v4.1.0` | media |
| TH1 (compliance GPU) | `v4.1.1` | piccola |
| TH2 (A/B ufficiale severino-sim) | `v4.1.2` | piccola |
| TH3 (verdetto + docs) | `v4.2.0` | media |

(Numerazione fissata allo scheduling, 2026-08-03: la campagna TH parte subito dopo `v4.0.0`
per decisione utente, quindi PRIMA di F3-bis — che slitta a `v4.3.0`; la riconciliazione del
piano padre si fa al rituale TH3.)

---

## Tracking

- [x] **TH0 — Meccanica del thinking (two-call protocol)** ✅ 2026-08-03, `v4.1.0`
  - [x] TH0.1 client: `complete()` con `think: int | None`
  - [x] TH0.2 store: colonne `thinking_tokens`/`thinking_ms` su `llm_calls` (migrazione additiva idempotente; `budget_used` le conta una volta)
  - [x] TH0.3 leva d'esperimento `RG_THINKING_ROLES` + `RG_THINKING_BUDGET` (`plansys.thinking_roles()/thinking_budget()`; call-site: `_SingleShot.run`, `SeniorPlanner.run`, `Worker`)
  - [x] TH0.4 unit (7 test nuovi, suite a 92) + smoke GPU: sonda diretta col canale che produce ragionamento strutturato vero (200 tok/914ms) e pilota fast con S+M1+M2+M3 tutti pensanti (256 tok/ruolo, ~1.15s l'uno su GPU)

  **REVISIONE TH0 (dai fatti del GGUF, non dai docs — trap TH-1 rispettata):**
  1. **Marcatori veri, estratti dal chat template INCORPORATO nel GGUF pinnato** (parser
     dell'header scritto ad hoc; `/props` di questa build espone solo l'alias "gemma" e
     `/tokenize` non onora i token speciali): il pensiero di Gemma 4 vive in un CANALE
     testuale `<|channel>thought\n … \n<channel|>` dentro il turno model; l'interruttore
     nativo è il token di controllo `<|think|>` (id 98) in testa al system turn.
  2. **Niente variante S7** (il piano ipotizzava la sostituzione dell'istruzione): la
     chiamata 1 apre direttamente il canale — `prompt + think_open`, stop a `think_close`.
     Più semplice, byte-stabile, e non serve l'interruttore `<|think|>` (il canale lo
     apriamo noi; se TH1 mostrasse pensieri di bassa qualità, provare l'interruttore è la
     prima variante da testare).
  3. **La TH-D2 è cablata nel modello stesso**: il template incorporato ha `strip_thinking`
     che RIMUOVE i canali thought dai turni precedenti + un reasoning guard — la linea
     guida "mai ripassare il ragionamento" è il comportamento nativo, il nostro two-call
     la rispetta per costruzione.
  4. **Valori della leva = nomi ruolo reali del DB** (`senior_planner`, non `senior`):
     T-SM = `RG_THINKING_ROLES=senior_planner,phase_analyst,work_decomposer,verification_designer,test_author`.
  5. **REVISIONE (decisione utente, 2026-08-03): il budget è un FUSIBILE, non un
     bersaglio.** L'osservazione iniziale ("il modello non chiude mai il canale") era un
     artefatto del budget 256 troppo stretto: misurato con budget largo, il modello
     **chiude da solo, sempre** — 322 tok (piano semplice), 543 (piano largo), 506
     (debug). Default alzato a 1536 (non scatta mai in condizioni normali; caso
     patologico ≤ ~43s su severino — F12: l'uscita esiste sempre) e il client clampa il
     pensiero allo spazio reale del contesto riservando SEMPRE i max_tokens della
     risposta. Costo atteso reale su severino: ~9-15s di pensiero per chiamata pensante.
  6. **Scoperta collaterale (a debito, NON si tocca ora)**: i marcatori di turno nativi di
     questo GGUF sono i token di controllo `<|turn>`/`<turn|>` (105/106) — il nostro
     `<start_of_turn>` tokenizza come 7 token NON speciali. Funziona (misurato da F0 in
     poi), ma il protocollo nativo è un altro: A/B futuro, registrato nell'atlante §10.
- [ ] **TH1 — Compliance GPU (famiglie, non numeri)**
  - [x] TH1 round 1 (T-SM): **0/20** @`a2076ab` — famiglia nuova "phase_id drift di M2 pensante" (5/20, fixata: identità imposta in `_norm`); **amplificazione delle morti J** (M3 pensante progetta obblighi O1-O3 per micro, J non pensante ne fallisce di più: onestà su, conversione giù); costo 2,4× token / 2,3× wall.
  - [ ] TH1 round 2 (T-SM post-fix phase_id): in corsa @`4dfc05f`.
  - [ ] **TH1 round 3 (T-J, decisione utente 2026-08-03): pensiero SOLO a J** (`RG_THINKING_ROLES=worker`), stesso protocollo. Razionale: le morti dominanti sono di J e sono "di testa" (formati esatti); il round 1 mostra che migliorare solo il verificatore peggiora la conversione — prima di TH2 va misurato il braccio dell'esecutore. Attenzione al costo: J pensa A OGNI STEP (10-30 per micro) — su GPU è tollerabile, il numero severino si stima dai token.
- [ ] **TH2 — A/B ufficiale severino-sim (i numeri)**
- [ ] **TH3 — Verdetto, decision rule, documentazione**

---

## TH0 — Meccanica: il protocollo a due chiamate

### TH-D1 (decisione architetturale): il thinking NON entra nella grammatica — due chiamate

**Scelta:** thinking e output strutturato restano due generazioni separate, in sequenza, sulla
stessa sessione di cache:

1. **Chiamata di pensiero** — stesso prompt del ruolo + istruzione S7 sostituita da una variante
   "reason step by step about the task; be brief and factual" — SENZA grammatica, con
   `n_predict = think_budget` e stop al marcatore di chiusura del template thinking del modello.
2. **Chiamata di output** — prompt = stesso prefisso + `[THINKING]\n<testo di 1>` appeso al
   volatile + istruzione S7 originale — CON la grammatica di sempre.

**Alternative scartate e perché:**
- *Grammatica che ammette un prefisso libero poi il JSON* (`<think> .* </think> json`): un loop
  di caratteri liberi dentro il GBNF indebolisce il vincolo proprio dove serve (F4: le derive si
  eliminano per costruzione) e non dà un budget separato per il pensiero — un derail penserebbe
  all'infinito dentro una chiamata sola, invisibile.
- *Chat template del server con thinking nativo*: butterebbe la convenzione S1→S7 e la stabilità
  byte-a-byte dei prefissi (F10: un byte cambiato = ~120× di prefill), cioè l'architettura di cache.

**Perché il two-call è KV-friendly**: la chiamata 2 condivide con la 1 l'intero prefisso
(append-only) — il costo aggiuntivo di prefill è SOLO il testo di pensiero (F10). Il costo vero è
la generazione del pensiero: `think_budget/35,8 s` per chiamata su severino-sim — ed è esattamente
una delle due grandezze che l'esperimento deve misurare.

### TH-D2 (vincolo Gemma 4, indicazione utente 2026-08-02): il ragionamento NON entra mai nella catena duratura

Le linee guida di Gemma 4 impongono di **non ripassare il ragionamento nel contesto** dei turni
successivi. Regola meccanica, non fiduciaria:

- **Il pensiero vive SOLO dentro la sua coppia think→emit**: compare nel prompt della chiamata 2
  (il modello deve vederlo per usarlo — è il comportamento nativo entro il turno) e in nessun
  altro prompt, mai. Non nel ledger, non nella projection, non nel volatile dei passi successivi,
  non nei retry.
- **Per S e M** il vincolo è soddisfatto per costruzione: ogni passo è single-shot con prompt
  proprio; la coppia think→emit nasce e muore lì.
- **Per J (braccio T-J)** serve il **fork della cache**: sia `P` il prompt canonico append-only
  dello step N. Chiamata 1 = `P + invito a pensare` → pensiero `T` (ramo usa-e-getta). Chiamata 2
  = `P + [THINKING]T + S7` → JSON (secondo ramo, riusa il prefisso `P`). La **catena canonica
  prosegue da `P + JSON + tool result`**: lo step N+1 condivide con la storia il prefisso fino a
  `P` e ri-prefilla solo il proprio output JSON (piccolo) — `T` non entra MAI nella catena.
  Costo extra per step: prefill di `T` una volta (chiamata 2) + re-prefill del JSON allo step
  successivo. Niente strappi di byte a metà prefisso (F10), niente ragionamento trascinato
  (linee guida Gemma 4).
- Implementazione: `complete(think=N)` NON altera `parts` per il chiamante — i due prompt
  arricchiti sono costruiti e scartati dentro il client; il chiamante riceve solo `LlmResult`
  (con `thinking_text` a scopo di LOG, mai di contesto).

### TH0.1 — Client

`redgiant/llm/client.py`:

```python
def complete(self, parts: PromptParts, *, role: str,
             schema: type[BaseModel] | None = None,
             max_tokens: int, temperature: float | None = None,
             task_id: str | None = None, subtask_id: str | None = None,
             cache_prompt: bool = True,
             grammar_schema: dict | None = None,
             think: int | None = None) -> LlmResult
```

- `think=None` (default): comportamento IDENTICO a oggi, byte per byte — il braccio di controllo
  non deve cambiare di un token.
- `think=N`: esegue il two-call protocol. La chiamata 1 usa
  `payload = {prompt, n_predict=N, seed=42, cache_prompt, temperature}` SENZA `json_schema`,
  con `"stop": [cfg.think_close]`; troncamento a N NON è errore (il pensiero troncato si usa
  com'è: è un budget, non un contratto). La chiamata 2 è l'attuale `complete`, con
  `parts.volatile_context + "\n[THINKING]\n" + testo1` e stessa firma di logging.
- `LlmResult` guadagna: `thinking_tokens: int = 0`, `thinking_ms: float = 0.0`,
  `thinking_text: str = ""` (il testo si logga per l'analisi qualitativa dei fallimenti, mai
  ri-iniettato altrove: il pensiero è usa-e-getta per non sporcare i prefissi stabili).
- Config `[llm]` per-profilo: `think_open: str`, `think_close: str` (i marcatori del template
  thinking di Gemma 4 E2B — da verificare in TH0.4 contro il GGUF pinnato: PRIMA si stampa il
  chat template del modello via `/props` del server, POI si cablano; mai fidarsi della memoria).

### TH0.2 — Store

`redgiant/state/store.py`: migrazione additiva `ALTER TABLE llm_calls ADD COLUMN thinking_tokens
INTEGER NOT NULL DEFAULT 0` (+ `thinking_ms REAL NOT NULL DEFAULT 0`). `budget_used` conta i
thinking token nel totale (sono costo vero); il report eval li espone come colonna separata.

### TH0.3 — La leva d'esperimento

Come `RG_PLANSYS_ABLATE` (leva di solo-A/B, mai contratto config):
`RG_THINKING_ROLES` ∈ sottoinsiemi di `{worker, senior, phase_analyst, work_decomposer,
verification_designer, test_author}` + `RG_THINKING_BUDGET` (default 256).
Helper `redgiant/plansys/ablate.py::thinking_roles() -> set[str]`. I ruoli la leggono nel punto
UNICO in cui chiamano `complete` (Worker: `redgiant/core/worker.py`; M/S: `roles.py::_SingleShot.run`
e `SeniorPlanner.run`) passando `think=budget if role in thinking_roles() else None`.

### TH0.4 — Accettazione TH0

- Unit: (1) `think=None` produce payload identico a oggi (spia sul transport); (2) two-call con
  stop e budget; (3) troncamento del pensiero non alza `LlmTruncated`; (4) `[THINKING]` appeso al
  volatile della chiamata 2; (5) migrazione DB idempotente; (6) **TH-D2**: `parts` del chiamante
  intatte dopo `complete(think=N)` e il prompt dello step successivo di J NON contiene
  `[THINKING]`. Suite intera verde.
- Smoke GPU: 1 task pilota con `RG_THINKING_ROLES=worker` — nel log si vedono le coppie di
  chiamate, i thinking_tokens nel DB, e il template markers verificati contro `/props`.

---

## TH1 — Compliance GPU (famiglie, non numeri)

Protocollo BATCH20 identico ai batch n.1–8 (stesso `pilot_ps5_batch20.py`, stesso task, codice
committato, snapshot): **20 run con l'`RG_THINKING_ROLES` del braccio primario T-SM
(senior + i 4 passi M), budget 256**. Confronto di
FAMIGLIE contro i batch storici (la GPU non dà numeri, dà tassonomie — F17):
- Le morti J sui proof (photocopy/retries) calano, crescono o cambiano forma?
- Compaiono famiglie nuove (pensiero che avvelena il contesto della chiamata 2, derive S7)?
- Costo: token e wall per run vs batch n.8.
Esito TH1 = tabella famiglie prima/dopo + le trappole nuove fixate (se di control plane).

## TH2 — A/B ufficiale (severino-sim, codice committato)

Bracci, in quest'ordine (il controllo esiste già):
- **T-0 (controllo)**: il run B di PS6.2 — plansys no-thinking sui 13 task. NON si riesegue: si
  riusa il report committato (stesso commit-range, stessa condizione — se nel frattempo il codice
  plansys è cambiato, si riesegue T-0 sul commit nuovo: comparabilità > risparmio).
- **T-SM (PRIMARIO, decisione utente)**: plansys +
  `RG_THINKING_ROLES=senior,phase_analyst,work_decomposer,verification_designer,test_author`,
  TUTTI i 13 task. Il thinking è attivo per il Senior quando scrive il piano e per i passi M
  quando compilano la fase — i due punti di fallimento più rilevanti osservati nel run ufficiale
  PS6 (morti a zero tool call + under-scoping T041). Mai per J: il costo resterebbe fuori dal
  loop di esecuzione.
- **T-J (secondario)**: plansys + `RG_THINKING_ROLES=worker`, SOLO T040–T042. (L'ipotesi F18:
  il thinking serve a J sui formati esatti. Costa a ogni step: si misura sul set piccolo.)
- **T-SMJ** (solo se T-SM e T-J migliorano entrambi): tutti i ruoli, T040–T042.
TH1 (compliance GPU) usa di conseguenza `RG_THINKING_ROLES` di T-SM, non piu' solo worker.
Budget: 256 di default; se TH1 mostra troncamenti sistematici del pensiero, UNA sola variante di
budget (512) su T-J, dichiarata nel report.

Metriche (per braccio, nel report `bench/results/`): verified/13, token totali, **thinking token**
(colonna separata), wall clock, useful%, e la tassonomia per stadio delle morti. La metrica di
paragone chiave: **Δverified vs Δcosto** (token E secondi) rispetto a T-0.

## TH3 — Verdetto e decision rule

Decision rule FISSATA PRIMA di vedere i numeri (anti-cherry-picking):
- Il thinking entra in produzione per un ruolo SOLO se nel suo braccio: `verified ≥ T-0 + 2`
  (su 13) E `wall ≤ 2× T-0` E forbice completed≠verified = 0.
- Se migliora ma sotto soglia → resta leva sperimentale documentata, OFF di default.
- Se non migliora → si documenta il numero e si chiude (come il Planner in F3: un verdetto
  negativo onesto è un risultato).
Documentazione: questo piano aggiornato, atlante (firme + trappole), README (nuova finding F19
"thinking mode misurato" qualunque sia il verdetto — coi numeri), memoria di progetto.

---

## Trappole prevedibili (da vegliare in TH0/TH1)

1. **I marcatori del template thinking sono modello-specifici**: verificarli contro il GGUF
   pinnato via `/props`, MAI dai docs generici (lezione F0.3: il template sbagliato produce
   nonsense ben formato).
2. **Il pensiero nel volatile sposta i byte**: `[THINKING]` va SEMPRE in coda al volatile (S6),
   mai prima — il prefisso stabile S1→S5 non deve cambiare di un byte (F10). E per TH-D2 il
   pensiero resta nel ramo usa-e-getta: la catena canonica di J non lo contiene MAI (unit
   dedicato in TH0.4: il prompt dello step N+1 non contiene `[THINKING]`).
3. **Seed e two-call**: la chiamata 1 consuma stato del sampler? No (seed per-richiesta, F1.11),
   ma va provato nello smoke: due run identiche → stesso pensiero, stesso output.
4. **Il thinking troncato che finisce a metà frase** può indurre la chiamata 2 a completarlo
   invece di produrre il JSON: la grammatica lo impedisce strutturalmente, ma la QUALITÀ può
   soffrire — osservarlo in TH1, eventualmente chiudere il blocco con "\n[END THINKING]".
5. **Doppio conteggio budget**: i thinking token entrano UNA volta in `budget_used` (dalla
   chiamata 1), la chiamata 2 conta solo il proprio delta di prefill (già clampato, F9).

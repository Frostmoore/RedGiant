# Red Giant — Tutti i dati raccolti

Registro completo di **ogni misura** effettuata sul progetto: coding e non-coding, CPU e GPU,
con e senza fix, con e senza thinking. Ogni numero qui dentro viene da un report committato in
[`bench/results/`](bench/results/) o da un log di run archiviato; le righe segnate *(non
ufficiale)* non hanno valore di verdetto (v. §1.3).

> **Ultimo aggiornamento:** 2026-08-03 · **Prossimo:** dopo il run ufficiale della ladder su
> severino-sim (B2+B4 col codice fixato), che chiuderà la campagna in corso.

---

## 1. Come si leggono questi dati

### 1.1 I due profili hardware

| Profilo | Cos'è | A cosa serve |
|---|---|---|
| **`severino-sim`** | Docker, 2 core workstation ≈ 4 core del target, 10 GB, CPU-only | **L'UNICO profilo ufficiale.** Ogni verdetto viene da qui |
| **`dev-fast`** | server CUDA sulla workstation (RTX 4080S) | Solo iterazione: classifica *famiglie di errore*, mai tassi di successo (F17) |

### 1.2 I quattro blocchi di misura (la matrice)

Regola di metodo permanente: ogni batteria si misura su quattro blocchi, con le **ablazioni
obbligatorie** nei due blocchi col workflow.

| | senza thinking | con thinking |
|---|---|---|
| **Nudo** (materiali inline, 1 completion, zero tool/loop/retry) | **B1** | **B3** |
| **Workflow** (loop agentico, tool, verifica) | **B2** + ablazioni | **B4** + le stesse ablazioni |

- **B1** isola la capacità del modello · **B2** isola quanto sale il pavimento e *quale pezzo*
  lo paga · **B3** isola il ragionamento senza impalcatura · **B4** risponde a *"il
  ragionamento sostituisce un componente mancante?"*
- **Ablazioni disponibili**: percorso Worker `RG_WORKER_ABLATE` ∈ {`search`, `verify`,
  `retry`, `calc`} · plan compiler `RG_PLANSYS_ABLATE` ∈ {`oracle`, `ledger`, `entry`}.

### 1.3 Bande di rumore misurate (perché serve la statistica)

| Ambiente | Banda osservata | Causa |
|---|---|---|
| GPU (`dev-fast`) | fino a **2↔7 verdi su 20** a codice identico | batching CUDA non deterministico (llama.cpp #7052) |
| CPU (`severino-sim`) | **±2 su 13** a codice identico | stato della cache del server (llama.cpp #2838) |

**Conseguenza operativa:** i verdetti si traggono da **run multiple mediate**. Le run singole
presenti in questo documento sono marcate come tali e non fondano conclusioni.

### 1.4 Metriche

`verified` = il **giudice esterno** del task (script indipendente) dà exit 0 — mai
l'autodichiarazione del modello. `completed` = il sistema dice di aver finito. La **forbice**
`completed ≠ verified` è la metrica anti-bugia: deve essere 0.

---

## 2. Fondamenta hardware e runtime (F0)

Profilo `severino-sim`. Report: [`bench/results/f0_baseline_severino-sim.md`](bench/results/).

| Misura | Valore | Perché conta |
|---|---|---|
| Prefill a freddo @1K ctx | 6.8 s | |
| Prefill a freddo @4K ctx | 30.7 s | |
| Prefill a freddo @8K ctx | 69.6 s | il contesto di lavoro standard |
| Prefill a freddo @16K ctx | **173.6 s** | leggere 16K token costa **3 minuti**: i contesti piccoli sono fisica, non gusto |
| Generazione | 35.8 tok/s | memory-bound (24 thread arrivano solo a 42) |
| Riuso prefisso (8K), append-only | **65** token riprocessati | |
| Riuso prefisso (8K), **un byte cambiato a metà** | **7.971** token (~120×) | la stabilità del prefisso è architettura, non stile |
| Overhead della grammatica | 0.4–9.8% sulla generazione | il prezzo del decoding vincolato |

**Sonda del decoding vincolato** (60 generazioni): **0/60** semanticamente utilizzabili con
grammatica attiva ma schema assente dal prompt → **60/60** con lo schema nel prompt.

---

## 3. Campagne coding

### 3.1 F1–F2 (fondamenta e GUI)

| Misura | Valore |
|---|---|
| Task sintetici risolti e verificati (F1) | **4/6** su profilo capped, zero false dichiarazioni |
| Interfaccia di edit: diff unificati → sostituzione esatta | da **20+ chiamate fallite** a **5–6 pulite** per lo stesso fix |
| Difetti trovati nello shakedown GUI (3 giri utente + batteria) | **15**, tutti chiusi |
| Recupero strutturale dai derail (unioni discriminate) | **8/8** sonde |
| Loop patologici osservati (poi cappati) | 60 chiamate (derail da virgoletta), 49 riscritture dello stesso file, 15 edit no-op |

### 3.2 F3 — A/B ufficiale del Planner in-loop (`@611d894`, severino-sim)

| Braccio | Verificati | Token | Wall | Note |
|---|---|---|---|---|
| Baseline statica | **9/10** | 710.000 | ~44 min | il piano "ingenuo" deterministico |
| Planner in-loop | **2/10** | 814.646 | — | ~10× chiamate LLM sui task equivalenti |

**Verdetto D11:** Planner OFF di default, dietro gate di config. *(Una prima run fu invalidata
per working tree sporco → regola permanente: run ufficiali solo da codice committato.)*

### 3.3 Planner system — batch di compliance su GPU *(non ufficiali)*

20 run per batch, stesso task, snapshot committato prima di ciascuno. Servono a classificare
famiglie di errore mentre si costruiva il sistema.

| Batch | Verdi | Fasi verdi medie | Token medi | Wall medio | Fix introdotto dopo |
|---|---|---|---|---|---|
| n.1 | 3/20 | — | — | — | enum dinamici (M1 inventava file: 6/20) |
| n.2 | 1/20 | — | — | — | nomi canonici |
| n.3 | 1/20 | — | — | — | riconciliazione nomi (11/20 morti per mismatch) |
| n.4 | **7/20** | — | — | — | pruning test non legati |
| n.5 | 2/20 | — | — | — | dedup covers, determinismo dei prompt |
| n.6 | 5/20 | 1.4 | 5.060 | 31 s | budget patch, retry informato |
| n.7 | 2/20 | 0.9 | 4.464 | 27 s | import top-level obbligatorio |
| n.8 | 3/20 | 0.9 | 5.403 | 33 s | *(riferimento della griglia thinking)* |

**Famiglie azzerate lungo la campagna:** file inventati 6/20 → **0** · nomi disallineati 11/20
→ **0** · test che ingannano l'oracolo 5/20 → **0** · `phase_id` sbagliato 5/20 → **0**.

### 3.4 PS5.5 — piloti end-to-end su severino-sim

| Tentativo | Esito | Wall | Difetto scoperto (e fixato) |
|---|---|---|---|
| 1 | ko | 998 s | micro ordinate col deposito invertito → sort topologico |
| 2 | ko | 375 s | Giano importava moduli non ancora esistenti → lista IMPORTS nel work order |
| 3 | ko | 409 s | proof con import irrisolvibili → check ghost-imports |
| 4 | ko | 606 s | prosa del contratto fuori perimetro → validatore sulla prosa |
| **5** | **VERDE** | **569 s** | 3 fasi, coverage totale, giudice esterno exit 0, **7.845 token**, 20 tool call |

### 3.5 PS6.1 — taratura dei task larghi (baseline naive, severino-sim `@d8b080a`)

| Task | Verificato | Token | Wall | Lettura |
|---|---|---|---|---|
| T040 multiphase | ✗ | 140.146 | 311 s | taglia giusta |
| T041 no-tests (v1) | **✓** | 99.803 | 353 s | **troppo facile** → esteso a 3 moduli |
| T042 brownfield | ✗ | 153.975 | 288 s | taglia giusta |
| T041 esteso (ricontrollo) | ✗ | 190.628 | 1.062 s | metro tarato |

### 3.6 PS6.2 — A/B ufficiale del plan compiler (`@11e3502`, severino-sim)

**Bracci principali, 13 task ciascuno:**

| Braccio | Verificati | Token | Utili % | Wall | Forbice |
|---|---|---|---|---|---|
| A — baseline naive | **6/13** | 1.143.461 | 20.8% | 2.610 s | 0 |
| B — plan compiler | 2/13 | **635.894 (−44%)** | **30.2%** | 2.632 s | **1** (T041) |

**Dettaglio per task** (T = verificato):

| Task | A baseline | A token | A wall | B compiler | B token | B wall |
|---|---|---|---|---|---|---|
| T001 | ✓ | 19.039 | 46.6 s | ✗ | 13.066 | 118.6 s |
| T002 | ✗ | 119.220 | 275.7 s | ✗ | 15.703 | 118.6 s |
| T003 | ✓ | 11.087 | 30.2 s | ✗ | 12.695 | 93.9 s |
| T004 | ✓ | 19.591 | 50.3 s | **✓** | 25.761 | 164.1 s |
| T005 | ✓ | 14.958 | 54.8 s | **✓** | 49.573 | 203.2 s |
| T006 | ✓ | 20.580 | 52.0 s | ✗ | 16.633 | 114.7 s |
| T007 | ✓ | 152.257 | 306.5 s | ✗ | 52.805 | 216.2 s |
| T008 | ✗ | 169.265 | 336.9 s | ✗ | 16.654 | 121.2 s |
| T009 | ✗ | 104.416 | 218.5 s | ✗ | 147.597 | 391.2 s |
| T010 | ✗ | 126.260 | 256.8 s | ✗ | 93.170 | 271.1 s |
| T040 | ✗ | 108.605 | 296.2 s | ✗ | 25.698 | 149.5 s |
| T041 | ✗ | 78.796 | 297.2 s | ⚠️ *completed ma non verified* | 19.999 | 138.5 s |
| T042 | ✗ | 199.387 | 335.7 s | ✗ | 146.540 | 528.9 s |

**Ablazioni del compiler** (solo T040–T042, tutti 0/3 → il confronto è sul *costo del fallire*):

| Configurazione | Token | vs sistema completo | Wall |
|---|---|---|---|
| Compiler completo | 192.237 | — | — |
| − oracle qualification gate | 289.960 | **+51%** | 1.212 s |
| − task ledger | 338.238 | **+76%** | 1.476 s |
| − phase entry gate | 287.560 | **+50%** | 1.093 s |

### 3.7 PS6-bis — ri-misura dopo 4 fix del control plane (`@80fe6fe`, severino-sim)

| Braccio | Verificati | Token | Wall | Forbice |
|---|---|---|---|---|
| A2 — baseline | **8/13** | 1.177.963 | 2.688 s | 0 |
| B2 — compiler | 2/13 | 857.217 | 3.136 s | **0** *(la forbice di T041 è stata chiusa dal fix)* |

**Il dato metodologico:** la baseline è passata da 6/13 a 8/13 **a codice identico** (i fix
toccavano solo il percorso compiler) → è così che è stata scoperta la banda di rumore CPU
di ±2/13. Effetto dei fix sul compiler: le morti si spostano in profondità — task che
morivano a **0 tool call** ora ne eseguono **20–38** con **80–93% di token utili** anche
fallendo.

### 3.8 Dry-run GPU del protocollo PS6 *(non ufficiali)*

Servivano a scovare difetti prima di spendere ore di CPU: ne hanno trovati 4.

| Giro | A baseline | B compiler | −oracle | −ledger | −entry |
|---|---|---|---|---|---|
| 1 (`@44c5916`) | 6/13 · 1.148K · 554 s | 2/13 · 450K · 339 s | 0/3 · 126K | 0/3 · 177K | 0/3 · 233K |
| 2 (`@3eb3ec5`, post-fix) | 7/13 · 1.107K · 545 s | 2/13 · 486K · 530 s | 0/3 · 290K | 0/3 · 204K | 0/3 · 295K |

---

## 4. Campagna thinking

### 4.1 TH0 — misure di meccanica

| Misura | Valore |
|---|---|
| Chiusura naturale del canale di pensiero | **322 / 543 / 506 token** (piano semplice / piano largo / debugging) |
| Chiusura col budget a 256 | mai — **tutte** le chiamate tagliate a metà frase (artefatto del cap) |
| Costo del pensiero su GPU | ~1.15 s per chiamata (256 tok) · ~914 ms (200 tok) |
| Fusibile adottato | **1536** token (non scatta mai in condizioni normali; caso patologico ≤ ~43 s su CPU) |

### 4.2 TH1 — griglia di collocazione, 7 bracci × 20 run *(GPU, non ufficiale)*

| Braccio (chi pensa) | Verdi | Morti di Giano | Fasi verdi medie | Token/run | Wall/run |
|---|---|---|---|---|---|
| nessuno (riferimento, batch n.8) | 3/20 | 10/20 | 0.9 | 5.4K | 33 s |
| Sirio + tutti gli M (r1) | 0/20 | 11/20 | 0.9 | 13.2K | 70 s |
| Sirio + tutti gli M (r2, post-fix) | 2/20 | ~10/20 | 1.4 | 17.4K | 95 s |
| **solo Giano (r3)** | **4/20** | **5/20** | 1.3 | **8.5K** | 50 s |
| tutti (r4) | 1/20 | 7–8/20 | 1.1 | 16.9K | 88 s |
| Sirio + Giano (r5) | 2/20 | 9/20* | **1.9** | 14.1K | 87 s |
| **Sirio + Mizar + Giano (r6)** | **4/20** | 6/20* | **1.9** | 16.5K | 95 s |
| Mizar + Giano (r7) | 2/20 | 4/20 (14 morti in compilazione) | 0.8 | 10.8K | 62 s |

\* *Le morti di Giano non sono comparabili a profondità diverse: nei bracci con Sirio molte più
run sopravvivono alla compilazione e lo raggiungono, quindi la sua esposizione raddoppia.*

### 4.3 TH2 — A/B ufficiale del thinking (severino-sim, 2 batterie per braccio)

| Braccio | Batteria 1 | Batteria 2 | Media | Token | Wall |
|---|---|---|---|---|---|
| T-J (Giano pensa) | 2/13 · 977.102 tok · 9.111 s* | 1/13 · 596.661 tok · 5.183 s | **1.5/13** | ~787K | 1.9× il controllo |
| T-0 (controllo) | 2/13 | 1/13 · 447.559 tok · 2.345 s | **1.5/13** | ~652K | — |

\* *contaminata da carico parallelo sull'host, dichiarato.*

**Δ verificati = 0** (la decision rule pre-registrata chiedeva ≥ +2) → **thinking OFF di
default, verdetto lasciato aperto** (misurato solo su coding sintetico senza router).
Nota: la batteria 1 ha risolto **T002**, il task-trappola di ragionamento mai passato nella
storia del progetto — ma **non riprodotto** nella batteria 2: reale, dentro il rumore.

---

## 5. Domini non-coding (F3-bis)

### 5.1 Batteria multi-dominio (severino-sim `@17d274d`)

| Task | Dominio | Verificato | Token | Utili % | Wall | Retry |
|---|---|---|---|---|---|---|
| T030 analisi documenti | research_local | **✓** | 21.835 | 100% | 68.2 s | 0 |
| T031 chiamata API (`http_get` live) | api | **✓** | 18.103 | 100% | **44.8 s** | 0 |
| T032 documento → CSV esatto | docs | **✓** | 140.603 | 100% | 279.0 s | 1 |
| | | **3/3** | 180.541 | | 392 s | forbice 0 |

### 5.2 Braccio di controllo nudo — la lezione

| Task | Workflow | **Modello nudo** (3 run) |
|---|---|---|
| T030 | ✓ | **3/3** |
| T031 | ✓ | **3/3** |
| T032 | ✓ | **3/3** |

**Attribuzione onesta:** su questi task la **cognizione è tutta del modello**; il workflow
compra autonomia end-to-end, onestà e sicurezza — **non capacità** — e a caro prezzo (T032:
140K token nel loop contro **<1K nudo**). Da qui la ladder: *se il nudo passa, il task non
misura il workflow*.

---

## 6. La LADDER (campagna in corso)

### 6.1 Il disegno

Corpus generato con seed fisso ([`bench/ladder/generate.py`](bench/ladder/generate.py)),
rigenerabile identico. Asse: **ampiezza**, a cognizione per-fatto costante. Ogni gradino
chiede la stessa cosa banale ("il `listen_port` del servizio X è N"); cresce solo il pagliaio.

| Gradino | Documenti | Parole | Token stimati | Fatti | Extra | Budget passi |
|---|---|---|---|---|---|---|
| L1 | 5 | 237 | 319 | 2 | — | 20 |
| L2 | 15 | 724 | 977 | 3 | — | 20 |
| L3 | 40 | 1.872 | 2.527 | 4 | — | 20 |
| L4 | 90 | 4.261 | 5.752 | 5 | — | 33 |
| L5 | 90 | 4.252 | 5.740 | 5 | **somma** | 33 |
| L6 | 200 | 9.428 | 12.727 | 6 | — | 58 |
| L7 | 400 | 18.773 | 25.343 | 8 | **somma** | 60 |

### 6.2 B1 e B3 — il modello nudo (severino-sim, 3 run per gradino)

| Gradino | **B1** nudo | Troncamento B1 | **B3** nudo+thinking | Troncamento B3 |
|---|---|---|---|---|
| L1 | **3/3** | — | **3/3** | — |
| L2 | **3/3** | — | **3/3** | — |
| L3 | **3/3** | — | **3/3** | — |
| L4 | **3/3** | 8.047 → 7.536 (−6%) | **3/3** | 8.047 → 6.000 (−25%) |
| L5 | **0/3** | 8.036 → 7.536 | **0/3** ¹ | 8.036 → 6.000 |
| L6 | **0/3** | 17.737 → 7.536 (−57%) | **0/3** | 17.737 → 6.000 (−66%) |
| L7 | **0/3** | 35.263 → 7.536 (−79%) | **0/3** | 35.263 → 6.000 (−83%) |

¹ **Confondimento risolto a metà** (severino-sim, 3 run): ripetuto con budget di pensiero 256, il
troncamento torna a **7.280 token** — alla pari col braccio nudo (7.536, −3%) — e il risultato
resta **0/3**. Il fallimento di L5 col thinking **non** era dovuto al contesto rubato.

⚠️ **Ma resta una cella mai misurata** (obiezione dell'utente, 2026-08-04): entrambe le prove
tengono costante *una* variabile sacrificando l'altra — o pensiero pieno e materiale ridotto, o
materiale pieno e pensiero **mutilato**. Con 256 token un esito nullo non distingue *"il
ragionamento non serve"* da *"256 token non bastano per ragionare"*. La quarta configurazione —
**pensiero 1536 E materiale 7.536**, che richiede `ctx_size ≈ 9728`, fuori dal vincolo D8 — è
**LAD.14** nel piano. Serve perché i due esiti danno verdetti di natura diversa: 0/3 rende TH3
definitivo su questo asse; un passaggio lo riqualifica da *"il thinking non paga"* a **"il
thinking paga e non ci sta in 8192"** — un verdetto sull'hardware, non sul modello, che
cambierebbe l'obiettivo di F5.

**Conclusione su L5, con tutte le configurazioni misurate:**

| Configurazione | L5 | Materiale visto |
|---|---|---|
| nudo | 0/3 | 7.536 tok |
| nudo + thinking (fusibile 1536) | 0/3 | 6.000 tok |
| nudo + thinking (fusibile 256) | **0/3** | 7.280 tok (alla pari, ma pensiero mutilato) |
| nudo + thinking (fusibile 1536, ctx 9728) | **da misurare — LAD.14** | 7.536 tok (pieno) |
| workflow **con** `calc` | **4/5** | lettura selettiva |
| workflow **senza** `calc` | 0/5 | lettura selettiva |

**Il ragionamento esplicito non compra l'aritmetica; un tool deterministico sì.** Tre
configurazioni di pensiero falliscono, una calcolatrice AST da poche righe risolve il gradino.

**Il pavimento nudo del modello su questo asse: ~5.8K token di materiale, 5 fatti, nessuna
aggregazione.** Sopra: zero.

### 6.3 B2 — workflow, **prima** dei fix (severino-sim, 1 run per braccio — sotto lo standard)

| Braccio | L5 | L6 | L7 | Verificati | Forbice | Token | Wall |
|---|---|---|---|---|---|---|---|
| full | ✗ | **✓** | ✗ | 1/3 | 0 | 375.759 | 744 s |
| −search | ✗ | ✗ | ✗ | 0/3 | 0 | **507.513 (+35%)** | 916 s |
| −verify | ✗ | ✗ *(dichiarato fatto!)* | ✗ | 0/3 | **1** ⚠️ | 346.303 | 675 s |
| −retry | ✗ | ✗ | ✗ | 0/3 | 0 | **153.932 (−59%)** | 297 s |

### 6.4 La diagnosi che ha prodotto i fix

Analisi degli artefatti realmente prodotti:

| Gradino | Cosa ha prodotto | Causa reale |
|---|---|---|
| **L5** | `fornax=693 · draco=228 · sagitta=196 · dorado=428 · hydra=247 · **total=1892**` — **5 fatti su 5 corretti**, somma vera 1792 | **aritmetica**, non comprensione: sbagliata l'addizione di 100 |
| **L7** | *nessun `answer.txt`* nella maggioranza delle run | **budget di passi**: 20 mosse non bastano per 8 fatti in 400 documenti |

**Fix introdotti** (entrambi ablabili, come impone la matrice): tool `calc` deterministico
(AST-only) · `worker_max_steps` proporzionale alla taglia del task.

### 6.5 B2 — workflow, **dopo** i fix *(GPU, 5 run per gradino — non ufficiale)*

| Braccio | L5 (somma) | L6 (200 doc) | L7 (400 doc) | Wall |
|---|---|---|---|---|
| **full** | **4/5** | **4/5** | 0/5 | 491 s |
| **−calc** | **0/5** ⬅ crolla | **4/5** ⬅ intatto | 0/5 | 492 s |
| −search | *in corso* | | | |
| −verify | *in corso* | | | |

**Prima lettura:** i fix convertono due gradini su tre da **0/3 nudo** a **4/5 con workflow**;
L7 resta un muro anche con 60 passi.

**Attribuzione chirurgica (`−calc`):** togliere la calcolatrice azzera **solo** il gradino
dell'aritmetica (L5: 4/5 → 0/5) e lascia **intatto** quello del recupero (L6: 4/5 → 4/5), a
parità di costo (492 s vs 491 s). È la dimostrazione che il componente fa **esattamente** ciò
per cui è stato aggiunto, né più né meno — il tipo di attribuzione che senza ablazioni sarebbe
stato impossibile affermare.

### 6.6 B4 — workflow + thinking

| Stato | Nota |
|---|---|
| Bracci lanciati su severino-sim **col codice pre-fix** | non comparabili col B2 post-fix: **da rifare** |
| `think` (pre-fix, severino-sim) | 0/3 · 376.990 token · **1.980 s** |

---

## 7. Letture trasversali

### 7.1 Dove il pavimento è dimostrabilmente salito

| Leva | Senza | Con | Fonte |
|---|---|---|---|
| Schema nel prompt (con grammatica attiva) | 0/60 utilizzabili | **60/60** | §2 |
| Interfaccia di edit adattata al modello | 20+ chiamate fallite | **5–6 pulite** | §3.1 |
| Recupero dai derail (unioni discriminate) | loop da 60 chiamate | **8/8 recuperi** | §3.1 |
| Prefisso stabile (loop append-only) | 7.971 token riprocessati | **65** | §2 |
| Identità al control plane | 6/20 · 11/20 · 5/20 famiglie di errore | **0 · 0 · 0** | §3.3 |
| **Ricerca selettiva** (ladder L6) | **0/3 nudo** | **4/5 workflow** | §6.2, §6.5 |
| **Aritmetica offloadata** (ladder L5) | **0/3 nudo** | **4/5 workflow** | §6.4, §6.5 |

### 7.2 Dove NON è salito (e va detto)

| Situazione | Numero |
|---|---|
| Pianificazione sui micro-task (2 A/B indipendenti) | 2/10 vs 9/10 · 2/13 vs 6–8/13 |
| Task larghi multi-sessione (T040–T042) | **0/3 in ogni braccio**, con e senza compiler |
| Thinking a tempo pieno, profilo ufficiale | Δ verificati **= 0** a 1.4× token |
| Ladder L7 (400 documenti, 8 fatti + somma) | **0/5** anche col workflow fixato |

### 7.3 Il prezzo dell'onestà (l'unico numero di questo tipo)

**La forbice `completed ≠ verified` è stata ≠ 0 solo due volte in tutta la storia del
progetto**, ed entrambe sono spiegate:

| Dove | Causa | Esito |
|---|---|---|
| PS6.2, task T041 | il Senior pianificava un terzo della richiesta | fixato lo stesso giorno (gate copertura-richiesta) |
| Ladder, braccio **−verify** | **la verifica era stata disattivata di proposito** | è la dimostrazione sperimentale: senza oracolo il sistema mente |

### 7.4 Costo delle campagne (ordine di grandezza)

| Campagna | Run end-to-end | Note |
|---|---|---|
| Planner system (batch GPU + piloti) | ~180 | 8 batch da 20 + piloti |
| PS6 + PS6-bis + dry-run (ufficiali e non) | ~100 | 13 task × più bracci |
| Thinking (TH1 griglia + TH2) | ~192 | 7 bracci × 20 + 4 batterie da 13 |
| F3-bis + probe nudo | 12 | |
| Ladder (B1, B3, B2 pre/post fix) | ~90 | in crescita |
| **Totale strumentato** | **oltre 550** | |

---

## 7.5 LADDER — l'esperimento sull'obbedienza a una regola (2026-08-03, GPU)

Diagnosi: su L5 il modello estrae **5 fatti su 5 corretti** e sbaglia solo il totale, sempre
allo stesso modo — unità e decine giuste, centinaia sbagliate (`1592` è esattamente la somma
col **riporto dimenticato**). Analisi degli artefatti su 43 run: **solo 7 invocavano lo
strumento di calcolo** pur avendolo disponibile; 13 su 43 sprecavano metà del budget chiamando
tool inesistenti (`tool_name_placeholder`).

Tre livelli di persuasione testuale, misurati in sequenza:

| Intervento | Uso dello strumento | L5 verificati |
|---|---|---|
| strumento presente, nessuna regola | 7/43 (16%) | 4/5 → 2/5 |
| + regola numerata nella card (con il *perché* misurato) | ~40% | 2/5 |
| + nome pieno `calculator` + descrizione **MANDATORY** + giudice che non regala la risposta | **2/5 (40%)** | **2/5** · ablato: 1/5 |

**Il 60% delle run continua a calcolare a mente.** Un'istruzione procedurale esplicita, ripetuta
su tre livelli, non produce comportamento affidabile in questo regime — e l'ablazione dello
strumento non morde (2/5 vs 1/5) proprio perché lo strumento non viene invocato.

**Difetti di misura scoperti e corretti lungo il percorso** (entrambi invalidavano il gradino):
il corpus marcava i bersagli in grassetto markdown, rompendo le ricerche naturali **solo** nel
braccio workflow; e il giudice stampava `expected 1792, got 1892`, cioè **regalava la
risposta** a chiunque eseguisse il check — il task misurava la lettura di un messaggio d'errore.

**Conclusione operativa:** dove esiste un oracolo deterministico, l'operazione non va
*suggerita* al modello ma **tolta dalle sue mani** (il totale non è significato, è identità
derivata → appartiene al control plane). Prossimo passo misurato: guardia deterministica che
rende l'incoerenza aritmetica irrappresentabile invece di sconsigliata.

## 7.6 LADDER — togliere l'operazione dalle mani del modello (2026-08-03, GPU)

Seguito diretto di §7.5. Se un'istruzione non produce obbedienza, l'operazione va resa
**irrappresentabile**: `redgiant/tools/coherence.py` verifica, *prima* che il file tocchi il
disco, che un totale dichiarato sia coerente coi valori che il modello stesso ha scritto; se
non lo è, la scrittura è rifiutata con il numero corretto nel messaggio. È il principio F4 del
progetto (*rendi l'output incoerente impossibile da generare, invece di validarlo a
posteriori*), applicato per la prima volta ai **contenuti** e non alla sintassi.

**Cosa NON è:** non è un oracolo sul task. Somma ciò che il modello ha scritto, non ciò che è
vero — se i fatti sono sbagliati certifica una somma sbagliata. Coerenza interna, non
correttezza: nessun leak come quello del giudice (§7.5).

**Nota di metodo:** il prompt **non è stato toccato**. Nessuna nuova regola testuale, nessuna
menzione della guardia nella card — così il delta è attribuibile solo al meccanismo, e il
confronto con le tornate di §7.5 resta pulito.

### 7.6.1 A/B su L5 (`@da8df90`, dev-fast, **20 run per braccio**)

| Braccio | L5 verificati | Tempo totale |
|---|---|---|
| `full` (guardia attiva) | **18/20 = 90%** | 500 s |
| `−coherence` (guardia ablata) | **9/20 = 45%** | 797 s |

**45 punti di differenza, Fisher esatto bilaterale p = 0.0057.** Riferimento di §7.5, stesso
gradino e stesso hardware, prima della guardia: 2/5.

Il braccio con la guardia è anche **il 37% più veloce**: un rifiuto immediato costa una
riscrittura, mentre un artefatto incoerente costa un giro completo di verifica fallita più il
rientro nella ricerca da zero.

**⚠️ Lezione di metodo, pagata sul campo — 5 run non bastano su questo gradino.** I primi
blocchi erano a n=5 e hanno prodotto, su codice funzionalmente identico, `−coherence` = **1/5**
e poi **5/5**; `full` = 2/5, 3/5, 5/5. Su quella base avevo scritto un'attribuzione che i dati
non sostenevano, e l'ho ritirata. La causa è che il comportamento del modello oscilla per
blocchi interi (l'uso della calcolatrice è stato 0 volte in 5 run e poi continuo nelle 5
successive), quindi la varianza reale è molto più larga della banda di rumore hardware di §1.3.
**Regola operativa: sulla ladder, nessuna conclusione sotto le 20 run per braccio**, e il
numero va accompagnato da un test esatto, non da un'impressione.

### 7.6.2 Il meccanismo, run per run (log dei tool, braccio `full`)

*(blocco a n=5: la meccanica è osservata direttamente sui log dei tool e non dipende dalla
statistica, ma i punteggi di questa tabella sì — v. l'avvertenza in §7.6.1.)*

| Run | Morsi della guardia | Cosa è successo dopo | Esito |
|---|---|---|---|
| 1 | 1 (`total=1392`) | riscrive `total=1792` alla chiamata successiva | ✅ |
| 2 | 1 (`total=1202`) | va a `run_tests` **credendo di aver scritto**, poi ricomincia a cercare | ❌ |
| 3 | 1 (`total=1532`) | chiama `edit_file` su un file **mai creato**, due volte | ❌ |
| 4 | 1 | riscrive `total=1792` | ✅ |
| 5 | 0 | totale giusto al primo colpo | ✅ |

**La guardia ha morso in 4 run su 5** — cioè l'errore aritmetico è quasi universale su questo
gradino, molto più di quanto suggerisse il punteggio. Ma solo **2 morsi su 4** si sono
convertiti.

### 7.6.3 Il difetto scoperto dal fallimento (e il fix)

Le due run perse condividono la stessa causa, e **non riguarda l'aritmetica**: *un rifiuto di
scrittura non diceva al modello che il file non esisteva*. Il modello trattava il rifiuto come
un successo e proseguiva su un mondo immaginario — chiamando `edit_file` su un file assente o
verificando un artefatto mai scritto.

Fix (`fs.refusal_state`, `@63f55eb`): ogni hint di rifiuto ora dichiara lo stato reale del
disco — *"answer.txt does NOT exist: nothing was written. Call write_file again with the full
content — edit_file cannot work, there is no file to edit yet"* oppure *"still has its
PREVIOUS content"*. Applicato anche a `syntax_error`, che aveva sempre avuto la stessa
trappola senza che nessuno l'avesse notata.

**Lezione trasversale, la più riusabile di questa tornata:** un errore che dice *cosa era
sbagliato* ma non *com'è rimasto il mondo* lascia il modello a ragionare su uno stato che non
esiste. Vale per ogni gate che rifiuta un'azione, non solo per questo.

### 7.6.4 Progressione dell'intervento

| Configurazione | L5 verificati | Note |
|---|---|---|
| workflow, solo la regola nel prompt (§7.5) | 2/5 | lo strumento non veniva invocato |
| + guardia di coerenza in scrittura | 3/5 *(n=5, non concludente)* | 2 morsi convertiti su 4 |
| + il rifiuto dichiara lo stato del disco | 5/5 *(n=5, non concludente)* | 4 su 4 |
| **misura vera, n=20:** `full` | **18/20** | p = 0.0057 vs ablato |
| **misura vera, n=20:** `−coherence` | **9/20** | |

Il gradino resta il primo che il modello nudo non vede in **nessuna** configurazione
(B1 0/3, B3 0/3): il 90% è interamente merito dell'impalcatura.

**Il dato più istruttivo:** nei blocchi in cui il gradino passa, il modello spesso **non invoca
mai la calcolatrice**. Il totale finisce corretto perché il control plane rifiuta l'incoerenza
e restituisce il numero — al modello resta la trascrizione. È PS-D11 applicato all'aritmetica:
*il modello crea il significato, il control plane crea l'identità.*

**Riserve dichiarate:** GPU (`dev-fast`), non `severino-sim`; il numero ufficiale è LAD.7.

### 7.6.5 Cosa dicono i log integrali (e non i punteggi)

Letti i log completi delle ultime 40 run, emergono **due modi di fallire che nessun punteggio
mostrava**, entrambi più grossi del problema aritmetico che stavamo inseguendo.

**(a) Il finish fantasma — 31 tentativi su 78 (40%).** Il Worker dichiara `done` **senza aver
mai chiamato `write_file`, `edit_file` o `write_patch`**. Esempio integrale: trova tutti e 5 i
fatti, calcola col tool passo per passo (`693+228=921`, `921+196=1117`, `1117+428=1545`,
`1545+247=1792`, esatto) e allo step 12 chiude `done`. Il file non esiste. Il tentativo prima
aveva fatto lo stesso, con il *thought* che diceva *"Now I need to compile the results into
answer.txt"*. Di questi 31, **17 al primo tentativo**; 6 run su 40 lo fanno due o più volte.

Il sistema **glielo dice già**: `verify` propaga lo stdout del giudice (`FAIL: answer.txt
missing`) nel blocco `[PREVIOUS ATTEMPT FAILED]` del tentativo successivo. Il modello lo legge
e ripete. **Terza conferma indipendente che l'istruzione non produce obbedienza** (le prime
due: §7.5 e la regola 8 della card, che dice esattamente questo dal F1).

Il costo è la parte peggiore: un finish fantasma brucia un **tentativo intero** — si rilistano
90 file e si rifanno tutte e 5 le ricerche — quando al modello sarebbe bastato **un passo**,
con il contesto ancora caldo.

**(b) La calcolatrice fallisce sull'interfaccia, non sull'aritmetica — 27 chiamate su 67
(40%) con `expression=None`.** Il router risponde `bad_args` col dettaglio pydantic grezzo e il
modello ci cicla dentro: cinque step consecutivi, poi *"I have exhausted all attempts to use the
calculator tool correctly"* → `blocked`. **Questo riscrive in parte §7.5:** non tutto quel "60%
calcola a mente" era rifiuto dello strumento — una fetta era il modello che *provava* a usarlo e
veniva respinto da un errore che non nominava l'argomento mancante. Quando la chiamata passa, il
risultato è sempre giusto.

**Conseguenza operativa:** entrambi si affrontano con lo stesso principio già validato due
volte (guardia di coerenza, `refusal_state`) — struttura invece di istruzione, ed errori che
dicono cosa fare e com'è rimasto il mondo. Vedi LAD.9 e LAD.10 nel piano.

## 7.7 LAD.9 — il gate sul finish: risultato NULLO, e perché è comunque utile saperlo

Il gate (`Worker._finish_gate`) rifiuta un `done` dichiarato quando l'artefatto promesso non
esiste, o quando il tentativo non ha mutato nulla e l'oracolo è rosso. Bersaglio: il **finish
fantasma** di §7.6.5, misurato al 40% dei tentativi.

### 7.7.1 La misura (dev-fast, 20 run per braccio, `@699ed56`)

| Gradino | `full` (gate acceso) | ablato | Fisher bilaterale |
|---|---|---|---|
| **L5** | 18/20 · 725 s | 16/20 · 633 s | **p = 0.66** |
| **L7** | 11/20 · 629 s | 11/20 · 623 s | **p = 1.00** |

**Nessun effetto su nessuno dei due gradini, e un costo del +15% in tempo su L5.**

**Perché — ed è questo il vero risultato:** *il loop di retry pagava già per il finish
fantasma.* La verifica esterna lo intercetta e il tentativo successivo di solito scrive il file.
Abbiamo trovato una patologia reale che l'architettura **tollerava già**. Il gate è ridondante
rispetto a un componente che esisteva.

**Verdetto: SPENTO di default** (`RG_FINISH_GATE=1` per accenderlo), stesso trattamento di D11
(planner) e TH3 (thinking) — costruito, misurato, spento, verdetto **aperto**. Condizione di
retest scritta: sui task coding larghi un tentativo sprecato costa **100K+ token** invece di 25
secondi (T032 ha bruciato 140K token in loop), e lì convertirlo in un passo potrebbe pagare. Va
rimisurato su T040–T042 prima di dichiararlo inutile.

**Corollario di metodo:** una patologia frequente non è automaticamente una patologia costosa.
Il 40% di finish fantasma sembrava enorme, ma il sistema aveva già chi lo assorbiva. Prima di
costruire una difesa, va misurato **chi sta già pagando** per il problema.

### 7.7.2 LAD.8 risolto: L7 non finisce i passi, finisce il CONTESTO

L'A/B su L7 ha prodotto la diagnosi che cercavamo da giorni, e non è né correttezza né
completamento:

```
llm error: prompt of 9323 tokens exceeds budget (ctx_size=8192)
```

Su 92 tentativi di L7, i tentativi usano **8,5 passi di media e al massimo 18** su 60
disponibili: **nessuno esaurisce il budget di passi**. Muoiono perché la catena append-only dei
risultati sfonda la finestra di contesto. Ogni risultato di ricerca su 400 documenti pesa fino
a `_RESULT_MAX_CHARS = 6000` caratteri (~1500 token): cinque o sei bastano a saturare 8192.

*(Nota di onestà: una prima classificazione automatica aveva letto quei blocked come "budget di
passi esaurito" — il grep matchava `exceeds budget`. La diagnosi corretta è arrivata leggendo
le motivazioni per esteso, non i conteggi.)*

**Conseguenza:** L7 è un problema di **capienza**, non di intelligenza né di disciplina. È il
territorio di **F5 "Dwarf Star"** (contesto e KV cache) — che la ladder ha ora motivato dal
basso con un numero invece che con un'intuizione. Le leve candidate: risultati di ricerca più
stretti, compattazione dei risultati vecchi (che però rompe il riuso append-only della KV
cache: F0.5, 65 token contro 7971 — è un compromesso da misurare, non da assumere), oppure far
scaricare al modello i fatti trovati su un artefatto di appoggio.

**Numero secondario ma notevole:** L7 con il codice attuale passa **11/20**, contro il rosso in
ogni braccio delle misure precedenti e lo 0/3 nudo. Il merito non è di LAD.9 (identico nei due
bracci): è dei fix precedenti — corpus uniforme, giudice che non regala la risposta, guardia di
coerenza, `refusal_state`, budget di passi proporzionale alla taglia.

## 8. Cosa manca (aggiornamento previsto)

- [ ] Ladder B2 post-fix: ablazioni `−calc`, `−search`, `−verify`, `−coherence` su GPU (L5 fatto a n=20: §7.6.1; mancano L6 e L7)
- [ ] L5 con la guardia su `severino-sim` (il 18/20 è GPU, va confermato sul profilo ufficiale)
- [x] ~~Gate sul finish in-loop (LAD.9)~~ — **fatto e spento**: risultato nullo, §7.7
- [ ] `bad_args` che insegna (LAD.10) — il secondo modo di fallire di §7.6.5, non ancora affrontato
- [ ] LAD.13: `calculator` merita il catalogo? A/B a n=20 **dopo** LAD.10 — è l'unico componente acceso senza prove
- [ ] Retest di LAD.9 sui task coding larghi T040–T042 (dove un tentativo sprecato costa 100K+ token)
- [ ] **F5**: L7 muore per contesto pieno (§7.7.2) — la ladder ha motivato la fase dal basso
- [ ] Ladder B4 post-fix (workflow + thinking, con le stesse ablazioni) — il blocco pre-fix è da buttare
- [ ] **Ladder ufficiale su severino-sim**: B2 + B4 col codice fixato, run multiple → i numeri che andranno nel README
- [ ] Diagnosi di L7 (perché 60 passi non bastano)
- [x] ~~Disambiguazione del confondimento B3/L5 (budget di pensiero 256)~~ — fatta, §6.2 nota 1
- [ ] **LAD.14**: pensiero PIENO (1536) con materiale PIENO (ctx 9728) — la cella mai misurata, §6.2
- [ ] Retest dei verdetti aperti (planner e thinking) col router attivo, post-F6/F7
- [ ] Benchmark pubblici a fine progetto (valori comparabili con la letteratura)

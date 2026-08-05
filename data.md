# Red Giant — Tutti i dati raccolti

Registro completo di **ogni misura** effettuata sul progetto: coding e non-coding, CPU e GPU,
con e senza fix, con e senza thinking. Ogni numero qui dentro viene da un report committato in
[`bench/results/`](bench/results/) o da un log di run archiviato; le righe segnate *(non
ufficiale)* non hanno valore di verdetto (v. §1.3).

> **Ultimo aggiornamento:** 2026-08-04 · **Prossimo:** dopo il run ufficiale della ladder su
> severino-sim (B2+B4 col codice fixato), che chiuderà la campagna in corso.

---

## 0. IL BILANCIO — cosa migliora, cosa no, cosa è ancora incerto

*Le tre tabelle di sintesi. Ogni riga rimanda alla sezione con i dati completi; qui c'è solo il
verdetto, il numero che lo sostiene e la ragione tecnica.*
**Criterio di collocazione:** una riga sta in §0.1 o §0.2 solo se ha un A/B con bracci
comparabili e numerosità adeguata; tutto ciò che è stato *osservato* ma non *isolato* sta in
§0.3. Un miglioramento plausibile ma non misurato non è un miglioramento.

### 0.1 Cose che migliorano il sistema — DIMOSTRATE

| # | Leva | Senza | Con | Perché funziona | Fonte |
|---|---|---|---|---|---|
| 1 | **Grammatica + schema nel prompt** | 0/60 output utilizzabili | **60/60** | il ramo malformato non è *generabile*, non viene corretto dopo | §2 |
| 2 | **Prefisso stabile / loop append-only** | 7.971 token riprocessati | **65** (**122×**) | la KV cache si riusa solo se il prefisso non cambia mai (D9) | §2 |
| 3 | **`edit_file` al posto dei diff unificati** | 20+ chiamate fallite per un fix | **5–6 pulite** | i diff sono ostili a un 2B: la sostituzione esatta con unicità garantita no | §3.1 |
| 4 | **Unioni discriminate sugli step** | loop da 60 chiamate dopo un derail | **8/8 recuperi** | dopo un apice non escapato non esiste più un'uscita sintattica incoerente | §3.1 |
| 5 | **Identità gestita dal control plane** | 6/20 file inventati · 11/20 nomi disallineati · 5/20 `phase_id` errati | **0 · 0 · 0** | il modello crea il significato, il control plane crea l'identità (PS-D11) | §3.3 |
| 6 | **Ricerca selettiva** (`search_code`) | **0/5** su *tutti* i gradini, replicato **3×** su due corpus, spendendo **+35%** di token | 4/5 → 18/20 | è l'unico componente la cui rimozione perde il gradino conquistato: compra **capacità** | §6.5, §7.1 |
| 7 | **Verifica deterministica** | **8 false dichiarazioni in 5 run** | 1 sola in **550+** run verificate | compra **onestà**, non throughput: è il trust boundary (D10) | §6.5, §7.3 |
| 8 | **Retry (2 tentativi)** | 0/3, muore **veloce e a buon mercato** (−59% token) | — | è il **carburante**: assorbe i fallimenti transitori, incluso il finish fantasma | §6.5, §7.7 |
| 9 | **Guardia di coerenza aritmetica** | **9/20 (45%)** · 797 s | **18/20 (90%)** · 500 s | **Fisher p = 0,0057**; e **−37% di tempo**: rifiutare presto costa meno che fallire tardi | §7.6 |
| 10 | **Budget di passi proporzionale alla taglia** | L7 moriva senza mai scrivere il file | L7 **11/20** | 20 passi non bastano per 8 fatti in 400 documenti: non era incapacità, era budget | §7.7.2 |
| 11 | **Pensiero a budget pieno, materiale intero** | **0/20** | **20/20** | **p = 1,45×10⁻¹¹** — ma solo dove materiale e pensiero **ci stanno insieme** in 8192: sul gradino vero il materiale verrebbe troncato e il guadagno sparisce. Verdetto sull'**hardware** | §7.8 |
| 12 | **Errori azionabili** (`bad_args` LAD.10, `refusal_state` LAD.6) | spirali fino a **6 passi consecutivi**, **7 sequenze fatali** | **max 1 passo**, **0 fatali**, recupero **100%** | non riducono gli sbagli (18% di chiamate ancora malformate): **tolgono le spirali che gli sbagli causavano**. Agiscono sul *costo* del fallire, non sulla frequenza | §7.9.2 |
| 13 | **Flag di runtime** (`--swa-full --cache-reuse`) | **2.748** token per rimuovere un blocco dal mezzo | **1** | Gemma è sliding-window: con la cache SWA parziale il runtime non riusa nulla dopo una divergenza. Costa memoria → adottato solo su GPU | §7.11 |
| 14 | **Compattazione della catena volatile** (F5.0-bis) | L7 **12/40 = 30%**, tentativi morti a **7,7 passi**, **731** token riprocessati per chiamata | **22/40 = 55%**, **13,2 passi**, **550** per chiamata | **p = 0,0411**, campione dimensionato *prima* di guardare. Il +53% di tempo è il costo di **non morire** — e il riuso della KV **migliora** (89,3% contro 85,8%): l'ondata lascia un prompt più corto | §7.13.4, §7.13.5 |
| 15 | **La card del Worker** (scoperto ablandola) | card ridotta: L7 **1/20**, e il modello **legge** invece di cercare (440 `read_file` contro 169 `search_code`) | card intera: **15/20**, 294 ricerche contro 146 letture | **p = 1,0×10⁻⁵**. Non serviva a dire regole: **orienta la scelta dello strumento**, e solo dove il recupero selettivo è indispensabile (su L5 nessuna differenza). **Bisezionata (§7.16.2):** l'effetto sta nelle regole di **perimetro/focus** (9/20, p = 0,0084 contro la ridotta), non in quelle di disciplina d'azione (4/20, indistinguibile dalla ridotta) | §7.16.1, §7.16.2 |
| 16 | **Il pensiero sui task a recupero largo** | L7 **12/20**, 15,7 passi/tentativo, 59 ondate di compattazione | L7 **20/20**, 12,4 passi, **13 ondate** | **p = 0,0033**. Non aggiunge contesto: **riduce il bisogno di contesto** — 168 ricerche contro 5 letture. Ribalta la tesi dei "sostituti": complementari dove il collo di bottiglia è la *strategia di recupero* | §7.17 |

**Il filo comune delle 10 righe:** nessuna insegna qualcosa al modello. Otto rendono
*impossibile* un errore, due gli danno più spazio o più tentativi per lo stesso lavoro.

### 0.2 Cose che NON migliorano il sistema — verdetto con numeri

⚠️ *"Irrevocabile" va inteso come: **dimostrato falso nel regime misurato**. Tre di queste
quattro righe hanno una condizione di riapertura scritta, perché il regime cambierà (router,
domini non-coding, task larghi). Nessuna è stata chiusa per opinione.*

| # | Leva | Numeri | Perché non funziona | Riapertura |
|---|---|---|---|---|
| 1 | **Planner in-loop** (D11) | **2/10 contro 9/10** (baseline statica) · 815K contro 710K token · ~10× chiamate LLM | su task piccoli pianificare **costa più di quanto renda**: il piano diventa un'altra cosa che può sbagliare | col router attivo, F6 |
| 2 | **Plan compiler** (PS-D9) | **2/13 contro 6/13**, e **2/13 contro 8/13** nella ri-misura · −44% token e +9,4 punti di token utili, ma i verdi non salgono | i gate spostano le morti **in profondità** (da 0 tool call a 20–38 con 80–93% di token utili) senza convertirle in verdi | task larghi multi-sessione, F6 |
| 3 | **Thinking DENTRO il workflow, sul CODING** (TH2 + LAD.11) | Δ = 0 su 4 batterie coding · su L5/L6 **43/60 contro 47/60**, p = 0,528, +55% tempo | dove il collo di bottiglia è l'**aritmetica**, la guardia di coerenza l'ha già chiuso e il pensiero non aggiunge nulla: lì sono **sostituti** | ⚠️ **NON estendere ai task a recupero largo**: su L7 il pensiero fa **20/20 contro 12/20** (§0.1 riga 16). La riapertura è già avvenuta |
| ~~4~~ | ~~**Thinking sull'aritmetica**~~ | ⛔ **VERDETTO RIBALTATO il 2026-08-04** — v. §0.1 riga 11 e §7.8 | le tre prove precedenti erano confondute | — |
| 5 | **Calcolatrice deterministica** (LAD.13) | `full` **16/20** contro `−calc` **17/20**, **Fisher p = 1,000** — e non per mancato uso: **27 chiamate riuscite** nel braccio completo | **la guardia di coerenza l'ha resa superflua**: due percorsi allo stesso esito, e quello deterministico non dipende da una scelta del modello | domini di F7 (matematica, everyday), dove la guardia non si applica |
| ~~6~~ | ~~`bad_args` che insegna~~ | ✅ **SPOSTATA fra le dimostrate** — v. §0.1 riga 12: la metrica pre-registrata era quella sbagliata, l'effetto c'è ed è sulle **spirali** | — | — |
| 4 | **Gate sul finish in-loop** (LAD.9) | L5 **18/20 contro 16/20**, **p = 0,66** · L7 **11/20 contro 11/20**, **p = 1,00** · **+15% di tempo** | ⚠️ **NON dimostrato inutile: A/B sotto-potenziato** (rettifica 2026-08-04). +10 punti richiedono ~200 run per braccio. La spiegazione originale — "il retry pagava già" — è stata **smentita** dai log: le 7 run fallite di LAD.13 sono 7/7 finish fantasma in tutti e tre i tentativi | ~200 run per braccio · e su T040–T042, dove un tentativo sprecato costa 100K+ token |

**La lezione che unisce le prime tre:** tutto ciò che abbiamo spento è "intelligente"
(pianificare, compilare piani, ragionare, sorvegliarsi). Tutto ciò che è acceso in §0.1 è
meccanico (cercare, verificare, riprovare, rifiutare l'incoerente).
**La quarta insegna un'altra cosa:** una patologia *frequente* non è automaticamente *costosa* —
prima di costruire una difesa, misurare **chi sta già pagando** per il problema.

### 0.3 Decisioni prese ma NON ancora certe

| # | Cosa | Stato della prova | Cosa manca | Rischio se sbagliata |
|---|---|---|---|---|
| 1 | **`refusal_state`** — il rifiuto dichiara lo stato del disco | meccanismo **osservato** sui log: recuperi da **2 su 4** a **4 su 4**; e la causa è certa (`edit_file` su un file mai creato, due volte nella stessa run). Rafforzata da LAD.10, che ha lo stesso profilo su un campione più grande (§0.1 riga 12) | mai isolato con un A/B suo: il 18/20 di §0.1 riga 9 è stato misurato **coi due fix insieme** | bassa: costa nulla e non può nuocere, ma il merito attribuito alla guardia potrebbe essere in parte suo |
| 8 | **Il gate sul finish è davvero inutile?** | ⚠️ **il suo A/B era sotto-potenziato** (§7.7): 18/20 contro 16/20, e +10 punti richiedono ~200 run per braccio. L'evidenza meccanicistica gli è **favorevole**: colpisce il 100% dei fallimenti residui di L5 (7 su 7 finish fantasma) | un A/B dimensionato sull'effetto, o su un gradino dove il fenomeno è più frequente | **media**: è spento un componente che potrebbe valere ~10 punti sul gradino conquistato |
| ~~2~~ | ~~**`calculator` nel catalogo**~~ | ✅ **RISOLTA il 2026-08-04** (§7.9): **p = 1,000** a n=20 — spenta di default. Il sospetto era fondato: la guardia di coerenza l'aveva resa superflua | resta da rimisurare nei domini di F7, dove la guardia non si applica | — |
| 3 | **Tutti i numeri della ladder** | GPU `dev-fast`, non `severino-sim` | **LAD.7**: run ufficiale su CPU, 20 run per braccio | media: la direzione è solida, l'ampiezza no (IC 95% del 18/20: **70–97%**) |
| 4 | **L7 = 11/20** | misurato a n=20 su GPU | attribuzione: è il cumulo di 5 fix, nessuno isolato | bassa sul numero, alta sull'interpretazione |
| ~~5~~ | ~~Il verdetto TH3 su L5~~ | ✅ **RISOLTA il 2026-08-04, ed era sbagliata** (§7.8): il pensiero pieno con materiale intero fa **20/20 contro 0/20**. Il rischio che avevo dichiarato "alto" si è materializzato: è un verdetto sull'**hardware**, e F5 cambia obiettivo | resta da confermare su `severino-sim` | — |
| ~~6~~ | ~~Buco nella matrice: B4~~ | ✅ **CHIUSO il 2026-08-04** (§7.10): B2 e B4 rimisurati sullo **stesso commit**, 20 run per gradino. La matrice 2×2 della ladder è completa | — | — |
| 7 | **Syntax gate, `no_op_edit`, hint su `unknown_tool`** | validati da piloti e collaudi (es. 13 task su 43 sprecavano passi su nomi inventati; 15 edit no-op consecutivi osservati) | mai passati dalla ladder con bracci ablati | bassa: patologie documentate e costo nullo |

### 0.4 Le conclusioni, nella forma in cui reggono davvero

*Scritte il 2026-08-04, dopo la campagna ladder. Ogni frase qui sotto è stata potata fino a
quello che i numeri sostengono — le versioni più ambiziose sono state provate e sono cadute.*

**1. L'impalcatura funziona, ma non fa quello che sembra.**
A livello di singolo passo il sistema trasforma un modello inutilizzabile in un esecutore
affidabile: output strutturati da 0/60 a 60/60, un'interfaccia di modifica che passa da 20+
chiamate fallite a 5-6, intere famiglie di errore azzerate. Questo è il risultato più solido del
progetto e non è in discussione.
Ma **non lo rende più intelligente**. Delle tredici leve che funzionano, dieci rendono un errore
*impossibile da commettere* e tre danno solo più spazio o più tentativi. **Nessuna leva che si
limita a chiedere qualcosa al modello ha mai funzionato**, e ne abbiamo provate quattro.

**2. Converte solo dove esiste un modo economico di verificare la risposta.**
Dove c'è un oracolo deterministico e il modello nudo cade per ampiezza o incoerenza, la
conversione è netta: il gradino dell'aggregazione passa da **0/20 a 19/20**. Dove l'oracolo non
c'è — i task di ingegneria del software multi-sessione — siamo a **0 su 3 in ogni braccio**, con
e senza pianificatore, con e senza ragionamento. È il fallimento aperto del progetto, e nessuno
dei componenti costruiti finora lo tocca nemmeno di striscio.

**3. Il valore dell'impalcatura è relativo, non assoluto.**
È la scoperta che ridimensiona di più la tesi originale. Sul gradino dell'aritmetica il
ragionamento **da solo**, senza alcun workflow, fa **20/20**. Dentro il workflow non aggiunge
nulla. Impalcatura e ragionamento **risolvono lo stesso collo di bottiglia**: chi arriva primo
prende tutto. Quindi la domanda giusta non è *"quanto vale la nostra impalcatura?"* ma **"quanto
vale rispetto a ciò che risolverebbe lo stesso problema in un altro modo?"**.

**4. Il vincolo che morde non è l'intelligenza: è la finestra di contesto.**
Due misure indipendenti puntano lì. Il gradino più duro non esaurisce i passi — ne usa 8,5 su 60
— muore perché il contesto si riempie. E il ragionamento, che risolverebbe l'aritmetica, **non ci
sta in 8192 token insieme al materiale**. Il contesto non è una voce di costo: è la risorsa che
decide **quali capacità sono raggiungibili**.

**5. Quello che non possiamo ancora dire.**
Quasi tutti i numeri recenti vengono dalla GPU, su task **sintetici**, con giudici scritti da
noi. Il profilo ufficiale su CPU non ha ancora visto nessuno di questi fix. Finché quella
campagna non gira, **tutto ciò che c'è sopra è una direzione solida, non una misura definitiva**.
E l'onestà impone di aggiungere che in due giorni abbiamo trovato **cinque difetti di misura**
(un formato sleale, un giudice che regalava la risposta, marcatori che bocciavano risposte
esatte, un campione insufficiente letto come verdetto, un vincolo mai rimisurato): nessuno era
visibile nei punteggi, tutti trovati leggendo artefatti e log. È ragionevole assumere che ce ne
siano altri.

---

**La tesi, riformulata in modo che regga:**

> Su hardware modesto, un control plane deterministico rende un modello da 2 miliardi di
> parametri **affidabile** — non più capace — nei compiti in cui esiste un modo economico di
> verificare il risultato. Non alza l'intelligenza del modello: **riduce i punti in cui serve
> intelligenza**. Dove quel modo economico di verificare non esiste, non abbiamo ancora niente
> da mostrare. E il tetto che oggi ci limita non è il modello: è quanto contesto entra nella
> macchina.

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

### 6.2 B1 e B3 — il modello nudo

#### 6.2.1 La misura definitiva (LAD.15 — dev-fast, **20 run per gradino**, `@9f075a9`)

Rifatta da zero col fix dei marcatori di template (§7.8) e a potenza statistica piena. È
**questa** la tabella da citare; quella a 3 run qui sotto è conservata solo per la storia.

| Gradino | Compito | **B1** nudo | **B3** + pensiero | Materiale visto (B1 / B3) |
|---|---|---|---|---|
| L1 | 2 fatti | **20/20** | **20/20** | intero / intero |
| L2 | 3 fatti | **20/20** | **20/20** | intero / intero |
| L3 | 4 fatti | **20/20** | **20/20** | intero / intero |
| L4 | 5 fatti | **20/20** | **20/20** | 7.536 (−6%) / 6.000 (−25%) |
| **L5** | **5 fatti + somma** | **0/20** | **0/20** | 7.536 / 6.000 — *entrambi troncati* |
| L6 | 6 fatti | **0/20** | **0/20** | 7.536 (−57%) / 6.000 (−66%) |
| L7 | 8 fatti + somma | **0/20** | **0/20** | 7.536 (−79%) / 6.000 (−83%) |
| **L5c** | **5 fatti + somma** | **0/20** | **20/20** | **3.587 / 3.587 — nessun troncamento** |

**Le due righe da leggere insieme sono L5 e L5c: sono lo STESSO COMPITO.** Cinque fatti più la
somma; cambia solo l'ampiezza del pagliaio (90 documenti contro 40), cioè **se il materiale
entra nella finestra accanto al pensiero**. Il braccio col ragionamento passa da **0/20 a 20/20**
non perché il task diventi più facile — il braccio nudo resta **0/20 in entrambi** — ma perché
smette di essere troncato.

**Due conclusioni indipendenti, entrambe a n=20:**
1. **Il soffitto del modello nudo è confermato**, e più solido di prima: 5 fatti sì, la somma
   no, indipendentemente dall'ampiezza (L5c ha *meno* materiale di L4 e resta 0/20).
2. **Il ragionamento supera quel soffitto quando ci sta.** Non è una questione di capacità del
   modello: è una questione di capienza della finestra.

*(Nota di validità: questa serie ha anche chiuso il dubbio aperto da LAD.15 — i numeri
precedenti erano stati presi col difetto dei marcatori attivo. L'esito è **identico**: i
gradini che passavano passano, quelli che cadevano cadono. Le fondamenta reggono.)*

#### 6.2.2 La misura originale (severino-sim, 3 run per gradino) — *storica*

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

> ~~**Il ragionamento esplicito non compra l'aritmetica; un tool deterministico sì.**~~
> ⛔ **AFFERMAZIONE FALSIFICATA il 2026-08-04 da LAD.14 (§7.8).** Era vera solo *nel regime
> misurato*: tutte e tre le configurazioni sopra erano confondute — o pensiero pieno e materiale
> troncato, o materiale intero e pensiero mutilato. Con **pensiero pieno E materiale intero** il
> gradino passa **20/20 contro 0/20**, p = 1,45×10⁻¹¹. La formulazione corretta è: *il
> ragionamento compra l'aritmetica, ma non entra in 8192 token insieme al materiale.*

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
| Ladder (B1, B3, B2 pre/post fix) | ~90 | |
| Ladder — A/B a n=20 (coerenza L5, gate sul finish L5 e L7) + blocchi a n=5 | ~150 | §7.6, §7.7 |
| **Totale strumentato** | **oltre 700** | |

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

**Nessuna differenza rilevabile a n=20, e un costo del +15% in tempo su L5.**

> ### ⚠️ RETTIFICA (2026-08-04) — la spiegazione qui sotto era SBAGLIATA
>
> Avevo scritto: *"il loop di retry pagava già per il finish fantasma; il gate è ridondante
> rispetto a un componente che esisteva"*. **I log di LAD.13 la smentiscono** (§7.9.4): le 7
> run fallite di quella campagna sono **7 su 7 finish fantasma, in tutti e tre i tentativi**.
> Il retry non paga affatto — dà tre occasioni e il modello le spreca tutte allo stesso modo.
>
> **La lettura corretta di p = 0,66 è un'altra:** gate acceso **18/20**, spento **16/20**. È un
> effetto di **+10 punti**; per distinguerlo dal rumore a quella dimensione servono circa
> **200 run per braccio**, non 20. Ho scambiato *"non l'ho misurato"* per *"non c'è"* — e a n=20
> quell'A/B era semplicemente **sotto-potenziato**, non conclusivo.
>
> **Il gate resta spento**, ma il motivo cambia: non perché sia ridondante, ma perché **il suo
> effetto non è ancora dimostrato**. E l'evidenza meccanicistica ora gli è *favorevole*: colpisce
> il 100% dei fallimenti residui di L5.

**Verdetto: SPENTO di default** (`RG_FINISH_GATE=1` per accenderlo), stesso trattamento di D11
(planner) e TH2 (thinking) — costruito, misurato, spento, verdetto **aperto**. Due condizioni di
retest, entrambe scritte:
1. **A n adeguato** per l'effetto in gioco (~200 run per braccio, o su un gradino dove il
   fenomeno è più frequente): l'A/B fatto non poteva vedere +10 punti.
2. **Sui task coding larghi** (T040–T042), dove un tentativo sprecato costa **100K+ token**
   invece di 25 secondi (T032 ha bruciato 140K token in loop).

**Corollario di metodo — anche questo va corretto.** Avevo tratto: *"una patologia frequente non
è automaticamente costosa; prima di costruire una difesa, misura chi sta già pagando"*. La
seconda metà resta valida come domanda da porsi; la **prima è stata smentita dai dati**: quella
patologia *era* costosa, ed è oggi l'unico modo di fallire rimasto su L5. La lezione vera è
un'altra e più scomoda: **un A/B nullo su un effetto piccolo non è un verdetto, è un campione
insufficiente** — e avevo appena scritto la regola delle 20 run senza chiedermi *20 run per
quale ampiezza d'effetto*.

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

## 7.8 LAD.14 — il pensiero a budget pieno E materiale pieno: **verdetto ribaltato**

*(2026-08-04, dev-fast, 20 run per braccio, `@81179c3`. Origine: obiezione dell'utente —
"non ha senso RIDURRE i token del pensiero, bisogna AUMENTARE i token di contesto".)*

### 7.8.1 Il disegno

Le due prove precedenti erano **entrambe confondute**, in direzioni opposte: pensiero pieno con
materiale troncato (6.000 contro 7.536), oppure materiale alla pari con pensiero **mutilato**
(256 token, che TH0 aveva già misurato come *"mai una chiusura naturale, tutte le chiamate
tagliate a metà frase"*). Un esito nullo a 256 token non distingue *"il ragionamento non serve"*
da *"256 token non bastano per ragionare"*.

Allargare il contesto avrebbe richiesto di riavviare `llama-server` fuori dal vincolo D8.
Disegno alternativo: **rimpicciolire il materiale** invece di allargare il contesto — gradino
**L5c** (`T058`), stesso compito di L5 (5 fatti **+ somma**) su 40 documenti.

**Condizione di validità, verificata col tokenizer del modello prima di leggere gli esiti:**

| | Budget materiale | Materiale reale | Troncamento |
|---|---|---|---|
| B1 nudo | 7.536 | **3.587** | NO |
| B3 nudo + pensiero 1536 | 6.000 | **3.587** | NO (margine 2.413) |

I due bracci vedono **esattamente lo stesso materiale**. L'unica differenza è il canale di
pensiero.

### 7.8.2 Il risultato

| Braccio | L5c verificati |
|---|---|
| **B1** — nudo | **0/20** |
| **B3** — nudo + pensiero pieno | **20/20** |

**Fisher esatto bilaterale p = 1,45 × 10⁻¹¹.** Costo: ~3 s per run contro <1 s.

Il braccio nudo sbaglia la somma in modo stabile (`total=1104`, `1054`, `1144` contro 1913
vero); quello col pensiero la azzecca **venti volte su venti**.

### 7.8.3 Cosa viene ribaltato, e cosa no

**RIBALTATO** — la tesi *"il ragionamento esplicito non compra l'aritmetica"*, che avevo scritto
in `data.md` §6.2, nel README e nel whitepaper (§6.4). Era vera **solo nel regime misurato**, e
il regime era il confondimento stesso.

**NON ribaltato** — il verdetto **TH2** sulla batteria ufficiale di coding (Δ verificati = 0 su
4 batterie, 1,9× tempo): è un altro dominio e un'altra misura. Il thinking resta spento di
default lì.

**La formulazione corretta:** *il ragionamento compra l'aritmetica, ma non entra in 8192 token
insieme al materiale.* È un verdetto sull'**hardware**, non sul modello — esattamente il ramo
che avevo pre-registrato come "se passa, cambia natura" (§0.3 riga 5).

### 7.8.4 Le due soluzioni allo stesso gradino, e quale è spedibile

Ora abbiamo **due** vie indipendenti per l'aritmetica, e occupano regimi diversi:

| Via | Dove funziona | Dove no |
|---|---|---|
| **Guardia di coerenza** (§7.6) | L5 vero, 90 documenti, **18/20** a ctx 8192 | — |
| **Pensiero pieno** (qui) | L5c, materiale ≤ ~4K token, **20/20** | su L5 vero il materiale verrebbe troncato a 6.000 → il gradino ridiventa 0/3 |

**La guardia è la soluzione spedibile oggi; il pensiero è quella che chiede un contesto più
grande.** Non sono alternative: sono due punti diversi della stessa curva costo/capienza — ed è
la curva che F5 deve ottimizzare.

### 7.8.5 Conseguenze operative

1. **F5 acquista un secondo obiettivo**: fare spazio *anche al ragionamento*, non solo al
   materiale. Prima era una fase di prestazioni, ora è una fase di capacità.
2. **LAD.11 (blocco B4) diventa molto più interessante**: se il pensiero paga da solo su un
   gradino che ci sta, cosa fa *dentro* il workflow?
3. **Da rimisurare su `severino-sim`** prima di essere ufficiale (regola D6: la GPU classifica,
   non decide).
4. **Lezione di metodo, la terza di questa campagna:** un controllo che *mutila* la variabile
   invece di isolarla non è un controllo — produce un nullo illeggibile che sembra una conferma.
   Il 256 sembrava rigore; era il confondimento speculare.

## 7.9 LAD.13 e LAD.10 — la calcolatrice esce dal catalogo, e il quarto no

*(2026-08-04, dev-fast, 20 run per braccio, `@a6f7ed2`)*

### 7.9.1 LAD.13 — lo strumento non paga

| Braccio su L5 | Verificati | Tempo |
|---|---|---|
| `full` (calcolatrice presente) | **16/20** | 611 s |
| `−calc` (ablata) | **17/20** | 577 s |

**Fisher esatto bilaterale p = 1,000.** L'ablazione è persino nominalmente migliore.

Il punto decisivo: **non è che lo strumento non venga chiamato.** Nel braccio completo ci sono
**27 chiamate riuscite** con l'espressione giusta (`693+228+196+428+247`) — e il risultato è lo
stesso di quando lo strumento non c'è.

**Causa: la guardia di coerenza l'ha resa superflua.** Il totale finisce corretto perché il
control plane rifiuta l'incoerenza e restituisce il numero. Sono due percorsi verso lo stesso
esito, e quello deterministico non dipende da una scelta del modello — che è esattamente la
proprietà che ci interessa.

**Verdetto: fuori dal catalogo di default** (`RG_CALCULATOR=1` per riaccenderla), stesso
trattamento di D11, TH2 e LAD.9. **APERTO**: la guardia copre solo i *totali in file di testo*;
nei domini di F7 (matematica, everyday) l'aritmetica non ha quella forma e la guardia non si
applica — lì la calcolatrice potrebbe essere l'unico meccanismo.

**Beneficio concreto della rimozione:** la sua voce nella card dei tool era pagata a **ogni step
di ogni task**. Un test permanente asserisce che la card si accorcia quando è spenta.

### 7.9.2 LAD.10 — la previsione era sbagliata, ma il fix funziona meglio di così

Avevo pre-registrato: *"il tasso di `bad_args` su `calculator` dev'essere ~0"*. **La previsione
non è centrata — e la metrica che avevo scelto era quella sbagliata.**

⚠️ *(I primi numeri che avevo calcolato — "40% → 27%" — erano su un campione **contaminato**:
mescolavano i due bracci di LAD.13 e più campagne. Nel braccio `−calc` le chiamate a
`calculator` tornano `unknown_tool`, non `bad_args`, e non possono per definizione riprendersi:
includerle falsava sia il tasso sia il recupero. Il confronto qui sotto è ristretto ai soli task
in cui lo strumento **era** nel catalogo.)*

| | Prima del fix | Dopo il fix |
|---|---|---|
| Chiamate malformate | 78 su 240 — **32%** | 6 su 33 — **18%** |
| Sequenze consecutive di fallimenti, **lunghezza max** | **6** | **1** |
| Sequenze **fatali** (nessun recupero nel task) | **7** | **0** |
| Recupero | 85% | **100%** |

**Il messaggio azionabile non impedisce l'errore: elimina la spirale.** Il modello continua a
mandare argomenti vuoti nel 18% dei casi, ma prima un errore poteva costare **sei passi
consecutivi** e uccidere il tentativo, mentre ora ne costa **esattamente uno** — e la chiamata
successiva riesce, 6 volte su 6.

**Regola generale, che vale per tutta la famiglia** (`refusal_state` si comportò allo stesso
modo: recuperi da 2 su 4 a 4 su 4): **gli errori azionabili non riducono gli sbagli, tolgono le
spirali che gli sbagli causavano.** È un effetto sul *costo* del fallire, non sulla sua
frequenza — e quindi va cercato nella lunghezza delle sequenze, non nel tasso di errore. La
metrica che avevo pre-registrato non poteva vederlo.

### 7.9.3 Lettura d'insieme delle due

**Su questo modello l'unica leva che cambia gli esiti è togliere la scelta, non facilitarla.**
La guardia di coerenza — che non chiede nulla al modello — vale 45 punti; la calcolatrice — che
gliela chiede — vale zero, anche quando la usa.

Ma le due famiglie non sono in concorrenza: **agiscono su assi diversi.** I gate deterministici
cambiano *quanto spesso si riesce*; gli errori azionabili cambiano *quanto costa sbagliare*.
Confonderli è ciò che mi ha portato a pre-registrare la metrica sbagliata per LAD.10.

### 7.9.4 Il meccanismo di LAD.13, letto sui log (e ciò che ha smentito)

| | `full` | `−calc` |
|---|---|---|
| Morsi della guardia di coerenza | **13** | **17** |
| …di cui la run poi scrive 1792 | 12 | 16 |
| Chiamate riuscite alla calcolatrice | 27 | 0 |
| Tentativi di chiamare uno strumento assente | 3 | **8** |
| **Artefatti finali col totale SBAGLIATO** | **0** | **0** |
| Run senza artefatto | 4 | 3 |

**La guardia morde di più quando la calcolatrice non c'è** (17 contro 13): raccoglie esattamente
il lavoro che l'altra non fa. È la sostituzione, misurata direttamente sui log invece che dedotta
dal punteggio.

**Il dato che vale più del p-value: zero artefatti sbagliati su 40 run, in entrambi i bracci.**
Su L5 l'aritmetica non è "migliorata": è **chiusa**. Nessuna run scrive più un totale errato.

**E quindi tutti i fallimenti residui sono un'altra cosa.** Ho letto i log integrali delle 7 run
fallite: **7 su 7 sono il finish fantasma**, e non in un tentativo — in **tutti e tre**. È questo
che ha smentito la spiegazione di §7.7 (*"il retry pagava già"*): il retry dà tre occasioni e il
modello le spreca tutte allo stesso modo.

**Nota minore ma indicativa:** nel braccio `−calc` il modello prova comunque a chiamare la
calcolatrice **8 volte** su 20 run, ricevendo `unknown_tool`. Toglierla dalla card non lo
dissuade del tutto — costa ~0,4 passi per run, e non cambia l'esito.

## 7.10 LAD.11 — il blocco B4: il pensiero DENTRO il workflow

*(2026-08-04, dev-fast, 20 run per gradino per braccio, **stesso commit per i due bracci**
`@42ba6cc` — il B2 è stato rifatto apposta invece di riusare quello di LAD.9, che girava su
codice precedente alla rimozione della calcolatrice e al fix di `bad_args`.)*

### 7.10.1 La misura

| Gradino | **B2** workflow | **B4** workflow + pensiero | Fisher bilaterale | Δ |
|---|---|---|---|---|
| L5 (5 fatti + somma) | **19/20** | 16/20 | p = 0,342 | **−3** |
| L6 (200 documenti) | 16/20 | **19/20** | p = 0,342 | **+3** |
| L7 (400 documenti) | 8/20 | **12/20** | p = 0,343 | **+4** |
| **aggregato** | **43/60** | **47/60** | **p = 0,528** | +4 |
| tempo totale | **1.794 s** | 2.772 s | — | **+55%** |

**I segni si alternano e i p-value sono identici a tre cifre: è rumore attorno allo zero.**
Il ragionamento dentro il workflow **non paga**, e costa il 55% di tempo in più.

### 7.10.2 La previsione registrata era sbagliata — e il perché è interessante

Avevo scritto nel piano, **prima di misurare**: *"su L7, che muore per capienza, il pensiero
dovrebbe PEGGIORARE l'esito, perché sottrae 1536 token a un contesto già saturo"*. Risultato:
**12/20 contro 8/20**, nominalmente il contrario.

La previsione poggiava su un modello mentale sbagliato — che il budget di pensiero fosse
sottratto al **contesto durevole**. Due misure lo smentiscono:

1. **Il pensiero non si comprime al crescere del prompt** (137 → 452 token medi per fascia da
   1K di prompt): si chiude naturalmente ben sotto il fusibile da 1536, coerente con TH0.
2. **Il ragionamento non entra MAI nella catena append-only** — è il protocollo **TH-D2**,
   adottato per tenere pulita la catena durevole. Viene generato e **scartato a ogni chiamata**.

Quindi il costo del pensiero è **per chiamata, non cumulativo**: il contesto che sfonda su L7 è
fatto di *risultati dei tool*, identici con o senza pensiero. **Una decisione architetturale
presa per un motivo (purezza della catena) protegge da un fallimento identificato molto dopo.**

### 7.10.3 Cosa risponde davvero questo blocco

È la domanda per cui la matrice 2×2 esiste — *il ragionamento sostituisce un componente
mancante?* — e ora ha una risposta a due facce:

| Confronto | Effetto del pensiero |
|---|---|
| **B3 − B1** (modello nudo, gradino controllato) | **0/20 → 20/20**, p = 1,45×10⁻¹¹ (§7.8) |
| **B4 − B2** (dentro il workflow) | **zero**, p = 0,528 |

**Il workflow e il ragionamento risolvono lo stesso collo di bottiglia: chi arriva primo prende
tutto.** Da solo, il pensiero fa l'aritmetica che il modello nudo non sa fare. Dentro il
workflow non aggiunge nulla, perché la guardia di coerenza quell'aritmetica l'ha già chiusa
(§7.9.4: zero artefatti sbagliati su 40 run). **Sono sostituti, non complementi.**

Il che rafforza il verdetto TH2 dandogli una spiegazione: il thinking non è inutile in assoluto
— è inutile *sopra un'impalcatura che copre già il suo contributo*.

### 7.10.4 Riserva dichiarata

L7 resta l'unico gradino dove entrambi i bracci sono lontani dal soffitto (8/20 e 12/20, IC 95%
rispettivamente 22-61% e 39-78%: si sovrappongono ampiamente). È anche l'unico dove il
collo di bottiglia — la capienza — **non è coperto da nessuno dei due**. Se F5 lo rimuove, il
confronto B2/B4 su L7 va rifatto: potrebbe essere l'unico posto dove i due smettono di essere
sostituti.

## 7.11 F5.0-ante — il vincolo che struttura F5 era un artefatto della nostra configurazione

*(2026-08-04, dev-fast, ctx 4096, server riavviato pulito prima di ogni cella.)*

Prima di scrivere una riga di F5 abbiamo fatto due cose: una **ricerca sullo stato dell'arte**
(su richiesta dell'utente) e la **rimisura del numero che struttura l'intera fase**. La ricerca
ha rivelato che `llama-server` ha un flag, `--cache-reuse`, che riusa la KV **via shifting**
quando il prefisso cambia a metà — e che **non lo stavamo usando** (default 0). Il numero di
F0.5 che rende "proibitiva" la compattazione (**65 token contro 7.971**) era quindi misurato col
meccanismo di mitigazione **spento**.

### 7.11.1 La sonda che mancava

Lo scenario storico **C** cambia **un byte *in place***: era la prova di D9 (stabilità del
prefisso), non il nostro caso. La compattazione **rimuove un blocco** e fa traslare all'indietro
tutto ciò che segue. Aggiunti a `bench/run_bench.py`: **D** (blocco rimosso dal mezzo) ed **E**
(D più una coda nuova — il caso vero del loop).

**Due trappole di disegno, entrambe scoperte misurando e ora documentate nel codice:**
1. tagliare a un offset di **carattere** arbitrario spezza la tokenizzazione alla sutura: il
   suffisso non è più token-identico e **nessun riuso è possibile, flag o non flag**;
2. il prompt base era **la stessa frase ripetuta** → rimuoverne il centro produce un testo
   identico a un suo **prefisso**, e misureremmo un troncamento invece di uno shift. Da qui
   `_mk_blocks`, che genera blocchi numerati eterogenei.

### 7.11.2 La matrice 2×2 dei flag

| Configurazione | C (byte cambiato) | **D (blocco RIMOSSO)** | E |
|---|---|---|---|
| `--cache-reuse 0`, SWA parziale ← **la nostra** | 4003 | **2748** | 65 |
| `--cache-reuse 256`, SWA parziale | 4003 | **2748** | 70 |
| `--cache-reuse 0` + `--swa-full` | **2001** | **1390** | 65 |
| **`--cache-reuse 256` + `--swa-full`** | **2001** | **1** | 65 |

**Rimuovere un blocco dal mezzo passa da 2.748 token riprocessati a UNO.**

**Perché, e la spiegazione regge in tutte e quattro le celle:**
- **`--swa-full` è il prerequisito.** Gemma è un modello a *sliding-window attention*: con la
  cache SWA parziale llama.cpp non riusa nulla dopo una divergenza. Con la cache piena il
  prefisso comune torna riusabile — e infatti C si **dimezza** (4003 → 2001), che è esattamente
  ciò che la teoria prevede quando il riuso parziale funziona.
- **`--cache-reuse` aggiunge lo shifting del suffisso.** Con `--swa-full` da solo, D riusa solo
  il primo terzo (1390 riprocessati ≈ i due terzi restanti); con entrambi, il suffisso viene
  **traslato invece che ricalcolato**.

### 7.11.3 Conseguenze

1. **La leva dello sfratto torna in gioco alla pari.** Era esclusa da un numero misurato con
   entrambi i flag spenti.
2. **`--swa-full` costa memoria** (cache SWA piena). Su `dev-fast` irrilevante e **adottato**;
   su `severino-sim` (10 GB, CPU, ctx 16384) **non ancora**: prima vanno misurati RAM e prefill.
3. **L'avvertimento della letteratura resta corretto in generale** ("la compattazione invalida
   la cache") **ma dipende dal runtime**: questo runtime sa fare shifting, se glielo si chiede.

**Lezione di metodo, la quinta della campagna:** *un vincolo che struttura un'intera fase va
rimisurato prima di progettarci intorno* — specialmente se il numero che lo sostiene è vecchio e
nato per rispondere a un'altra domanda. Il 65-contro-7.971 era corretto per D9 e **non
trasferibile** al caso della rimozione.

## 7.12 F5.0 — di cosa si riempiono gli 8192 token

*(2026-08-04, dev-fast, 140 chiamate su 5 run di L7, `@3b6ab12`.)*

La composizione del prompt è ora rilevata **a ogni chiamata** e persistita in
`llm_calls.sections` (prima il calcolo esisteva ma finiva solo dentro il messaggio d'errore).
Costo misurato prima di decidere: **0,5–6,3 ms per sezione** contro step da 1–3 s, cioè ~0,5% —
quindi nessun flag.

### 7.12.1 La tabella

| Step | CONTEXT | OUTPUT | PREAMBLE | ROLE | STATE | TASK | TOOLS | **Totale** |
|---|---|---|---|---|---|---|---|---|
| 1 | 284 | 18 | 314 | 1521 | 88 | 272 | 317 | **2.871** |
| 5 | 3.352 | 18 | 314 | 1521 | 88 | 272 | 317 | **5.939** |
| 10 | 3.225 | 18 | 314 | 1521 | 88 | 272 | 317 | **5.812** |
| 15 | 4.077 | 18 | 314 | 1521 | 88 | 272 | 317 | **6.664** |
| **al tetto** | **4.600** | 18 | 314 | 1521 | 88 | 272 | 317 | **7.186** |

### 7.12.2 Le due cose che dice

**1. La leva di F5.0-bis è puntata bene.** `CONTEXT` — la catena append-only dei risultati dei
tool — è l'unica sezione che cresce, e al tetto vale **4.600 token, il 65% del prompt**. Tutto
il resto è **costante**.

**2. Ma c'è un secondo bersaglio che nessuno aveva in lista: il costo FISSO.** Le sei sezioni
costanti sommano **2.530 token = il 31% della finestra**, pagati a *ogni* chiamata prima che il
sistema faccia qualunque cosa. Dentro, la voce più grossa è `ROLE` con **1.521 token**, che si
scompone così:

| Voce | Token | Natura |
|---|---|---|
| Schema di output (`WorkerStep`) | ~684 | **portante** — è la leva meglio misurata del progetto (0/60 → 60/60) |
| Card `worker.md` | **837** | **discrezionale** — 55 righe di regole numerate |

### 7.12.3 Il bug che è saltato fuori

La regola 13 della card imponeva: *"NEVER compute arithmetic yourself: any sum … goes through
the calculator tool, ALWAYS"*. Ma **LAD.13 aveva tolto `calculator` dal catalogo**. Il modello
riceveva l'ordine di usare uno strumento che non poteva vedere, **a ogni passo, per ~59 token a
chiamata** — e questo spiega le **8 chiamate a `calculator` inesistente** che avevo registrato
in §7.9.4 come curiosità.

Regola rimossa; e siccome è una classe di errore che si ripresenterà a **ogni** componente che
spegniamo, ora un test permanente (`test_card_consistency.py`) verifica che nessuna card citi
strumenti fuori dal catalogo di default. Verificato che il test **cattura** il bug rimettendo il
codice vecchio.

**Costo delle regole che abbiamo misurato come inefficaci:** ~59 token (calcolatrice, rimossa),
~68 (nomi esatti), ~70 (dire ≠ fare). Non sono cifre enormi da sole, ma sono pagate **su ogni
chiamata di ogni run**, e la campagna ha dimostrato che quelle regole non producono obbedienza.
**Da qui F5.0-ter nel piano**: misurare la card, invece di continuare ad aggiungerci righe.

## 7.13 F5.0-bis — compattazione della catena volatile: il pilota

*(2026-08-04, dev-fast, 20 run per braccio su L7, `@27f9cbc`. **Pilota**, non verdetto: v.
§7.13.3.)*

### 7.13.1 Il meccanismo

Quando la catena volatile supera il **55% del contesto**, i risultati dei tool più vecchi
vengono sostituiti dalla loro **`evidence`** — la riga di verità deterministica che ogni tool
produce già da sé (*"read x:1-40 (40 lines of 120)"*, *"search 'foo' → 12 matches"*). Gli ultimi
3 restano interi, la testa della catena (spec della sottofase, `[PREVIOUS ATTEMPT FAILED]`) non
si tocca mai, e il modello viene avvisato che è successo.

**Nessun riassunto generato dal modello.** Un riassunto allucinato dentro la catena di verità
sarebbe peggio del testo lungo — la stessa ragione per cui lo StateCompressor di F5.5 valida
contro il DB.

**A ondate, non a ogni passo.** Riscrivere il prefisso costa **1 token** con `--swa-full
--cache-reuse` e il riprocessamento completo senza (§7.11): un'ondata lo paga una volta sola,
uno sfratto continuo lo pagherebbe sempre. È anche la differenza che la letteratura indica fra
compattazione ed eviction incrementale.

### 7.13.2 I numeri del pilota

| Braccio | L7 verificati | Tempo | **Passi per tentativo** |
|---|---|---|---|
| `full` (compattazione attiva) | **11/20** | 1.028 s | **14,2** |
| `−compact` (ablata) | **6/20** | 679 s | **7,0** |

**Fisher bilaterale p = 0,200** — IC 95%: 34-74% contro 15-52%, ampiamente sovrapposti.

**Il dato meccanicistico è più forte del punteggio: i passi per tentativo raddoppiano.** I 7,0
del braccio ablato coincidono con la diagnosi di LAD.8 (8,5 passi di media, morte per contesto
pieno); con la compattazione i tentativi arrivano a **14,2**. Il **+51% di tempo è il costo di
NON morire** — la stessa forma di `−retry`, che era veloce perché falliva subito.

### 7.13.3 Perché questo NON è un verdetto

`p = 0,200` non risolve niente, ed è **esattamente la situazione in cui ho sbagliato con LAD.9**
leggendo un nullo sotto-potenziato come "non funziona". Stavolta il calcolo è stato fatto prima
di parlare:

| Run per braccio | 55% contro 30% | p |
|---|---|---|
| 20 | 11/20 vs 6/20 | 0,200 |
| 30 | 16/30 vs 9/30 | 0,115 |
| **40** | 22/40 vs 12/40 | **0,041** ✅ |
| 60 | 33/60 vs 18/60 | 0,009 |

**Servono 40 run per braccio.** E le prime 20 **non si possono estendere**: aggiungere run dopo
aver guardato l'esito è *optional stopping*, che gonfia il falso positivo. Quindi le 20 restano
un **pilota che serve solo a dimensionare**, e il verdetto viene da un campione nuovo da 40.

### 7.13.4 Il verdetto — campione confermativo (40 run per braccio)

| Braccio | L7 verificati | IC 95% | Tempo | Passi/tentativo | Ondate |
|---|---|---|---|---|---|
| `full` (compattazione) | **22/40 = 55%** | 40-69% | 1.917 s | **13,2** | 66 |
| `−compact` (ablata) | **12/40 = 30%** | 18-45% | 1.253 s | 7,7 | 0 |

**Fisher esatto bilaterale p = 0,0411.** Pilota e confermativo concordano esattamente — 55%
contro 30% in entrambi — e la dimensione del campione era **decisa prima di guardare**.

**Il gradino che resisteva a tutto si muove.** L7 — 400 documenti, 25K token di materiale, tre
volte la finestra — passa dal 30% al 55%. Era rosso in ogni braccio delle campagne precedenti e
0/3 nudo.

**Il costo è reale e va detto: +53% di tempo.** Ma non è overhead della compattazione: è il
costo di **non morire**. I passi per tentativo passano da 7,7 a 13,2, e i 7,7 del braccio ablato
coincidono con la morte per contesto pieno diagnosticata da LAD.8. Il braccio senza
compattazione è veloce come lo era `−retry`: perché fallisce prima.

**Nota di metodo — è il primo risultato della campagna fatto come si deve.** Pilota per
dimensionare, calcolo di potenza dichiarato, campione confermativo nuovo, nessun *optional
stopping*. È la lezione di LAD.9 applicata invece che ripetuta.

### 7.13.5 Condizione (b) — quanto costa in riuso della KV: **niente**

L'accettazione di F5.0-bis richiedeva anche il conto opposto: la compattazione riscrive il
prefisso, quindi *quanto paga* in riuso? Misurato con la contabilità corretta (§7.14), su dati
nuovi, 10 run per braccio:

| Braccio | Chiamate | Riuso medio | Token riprocessati **per chiamata** | Prefill medio |
|---|---|---|---|---|
| `full` (compattazione) | 290 | **89,3%** | **550** | **63 ms** |
| `−compact` (ablata) | 187 | 85,8% | 731 | 81 ms |

**Non costa: rende.** Con `--swa-full --cache-reuse` l'ondata costa ~1 token (§7.11) e lascia un
prompt **più corto**, quindi ogni passo successivo ne processa meno: **−25% di token
riprocessati per chiamata** e prefill medio più basso.

**Curva per posizione dello step** (la firma dell'append-only di D20): parte bassa allo step 1
— prefisso freddo — e sale a **90-95%** dal terzo passo in poi, in entrambi i bracci. D20
funziona come progettato, e la compattazione non la rompe.

⚠️ **Vale su GPU, dove i flag ci sono.** Su `severino-sim`, senza `--swa-full`, la riscrittura
costerebbe il riprocessamento completo e questo conto andrebbe rifatto da zero. **La leva è
ACCETTATA sul profilo di sviluppo e resta da validare su quello ufficiale.**

## 7.14 Il sesto difetto di misura: `tokens_cached` non è il riuso

Trovato costruendo la strumentazione di F5.2: il riuso risultava del **102%**. Un rapporto sopra
1 significa che il numeratore non è quello che si crede, quindi ho interrogato il server invece
di aggiustare la formula.

| Scenario | Prompt reale | `tokens_cached` | `timings.prompt_n` |
|---|---|---|---|
| freddo | 721 | 722 | **721** |
| identico | 721 | 722 | **1** |
| append | 724 | 725 | **4** |

`tokens_cached` è **quanti token stanno nella cache dopo la chiamata** — prompt+1, identico a
freddo e a caldo. Il numero vero è `timings.prompt_n`.

**Conseguenza, ed è seria:** in `budget_used` la sottrazione `MAX(prompt_tokens - cached_tokens,
0)` valeva **sempre 0**. Il budget dei task **ha contato solo la generazione, mai il prefill**,
da F1.2 a oggi. Corretto: `cached = max(n_prompt - timings.prompt_n, 0)`.

*Nota che salva i numeri storici:* il bench F0.5 usava già `prompt_n` ed era corretto — per
questo il 65-contro-7.971 reggeva. Il difetto stava **solo** nella contabilità di runtime, non
nelle misure di riuso pubblicate.

**Sesto difetto in pochi giorni, e come i precedenti non era visibile in nessun punteggio.** Si
è rivelato solo perché una metrica derivata è finita fuori dal suo intervallo ammissibile — che
è un buon argomento per calcolare sempre quantità che *hanno* un intervallo ammissibile.

## 7.15 F5.3 — audit dei prefissi: nessuna violazione

*(2026-08-04. La cache è byte-level, quindi l'audit lo è.)*

**`avg_reuse_ratio` del Worker: 89,3%**, contro la soglia di **0,6** fissata in F0.6. D9 regge
in produzione e non solo in teoria — la curva per posizione dello step parte bassa (prefisso
freddo) e sale a **90-95% dal terzo passo**.

Tre vie restavano scoperte dai test esistenti, tutte verificate pulite: card degli strumenti
**deterministica**; **stabile al rimescolamento** del catalogo (che viene costruito da liste
filtrate da ablazioni e interruttori, quindi l'ordine non deve dipendere dal dict); **preambolo
condiviso** e mai duplicato dalle card. Aggiunto anche un presidio contro i **valori volatili**
(date, orari) dentro S1–S4: uno solo azzererebbe il riuso a ogni chiamata.

⚠️ **Lo strumento di diff previsto dal piano NON è stato costruito, di proposito.** Serviva a
inseguire un `reuse_ratio` anomalo: non ce n'è. Resta come debito **con la sua condizione di
innesco** — si costruisce al primo riuso fuori norma. Costruirlo ora sarebbe aggiungere un pezzo
che nessuna misura ha richiesto, cioè la cosa che questa campagna ha imparato a non fare.

## 7.16 F5.0-ter — la card del Worker: 414 token a ogni chiamata

*(2026-08-04. A/B in corso al momento della scrittura: qui c'è il progetto e il risparmio
misurato, il verdetto arriva dopo.)*

La card costa **776 token a ogni chiamata di ogni run** ed è **la più grande di tutte** (3.114
caratteri contro i 2.250 della seconda). La variante ridotta ne costa **362**: **414 token
liberati per chiamata, il 5,1% dell'intera finestra**.

**Non è un taglio a gusto: ogni regola tolta cita il motivo.** Tre categorie:

| Categoria | Regole tolte | Perché |
|---|---|---|
| **Già imposte dalla struttura** | una azione per passo · pensiero ≤300 char · confini di scope | l'unione discriminata, `Field(max_length=300)` e `Scope.check_write` le rendono **non violabili**: ripeterle a parole non aggiunge nulla |
| **Misurate inefficaci o inerti** | "dire non è fare" · "altre sottofasi" · "later subtasks own the rest" | la prima è violata nel **40% dei tentativi** (§7.6.5); le altre due parlano di sottofasi che **col planner spento non esistono** |
| **Duplicate da un errore azionabile** | nomi esatti dei tool · f-string | ora il router suggerisce il nome vicino e `syntax_hint` arriva **al momento del fallimento** — e gli errori azionabili li abbiamo misurati funzionare (§7.9.2) |

**Cosa resta, e perché:** descrizione del compito, semantica `done`/`blocked`, contratto di
`edit_file` (l'evidenza più forte del progetto: 20+ chiamate fallite → 5-6) e scoperta dei
comandi di test.

**Limite dichiarato prima di vedere i numeri:** a 20 run per braccio si vedono differenze di
~40 punti, non di 5. Se l'A/B darà "nessuna differenza", la conclusione lecita sarà **"nessun
danno grande rilevabile"**, non "equivalenti". Con un beneficio *certo* (414 token) e un danno
*non rilevabile*, l'adozione è ragionevole — ma va detta così.

### 7.16.1 L'esito: la card ridotta è RESPINTA, e ha insegnato più di una promossa

| Gradino | `full` | `card-min` | Fisher |
|---|---|---|---|
| L5 (90 documenti) | **20/20** | 18/20 | p = 0,487 |
| **L7 (400 documenti)** | **15/20** | **1/20** | **p = 1,0 × 10⁻⁵** |

Non serviva il limite che avevo dichiarato: l'effetto è enorme e va nella direzione opposta a
quella che mi aspettavo. **La card ridotta distrugge il gradino largo.**

**La causa, letta sui log dei tool — e non è una regola, è un comportamento:**

| Strumento | `card-min` | `full` |
|---|---|---|
| `read_file` | **440** | 146 |
| `search_code` | **169** | 294 |
| `write_file` | **2** | 46 |

**Con la card ridotta il modello legge invece di cercare.** Su 400 documenti scorrere i file uno
per uno è senza speranza: è *esattamente* il comportamento del braccio `−search`, che avevamo
misurato a **0/5 su tutti i gradini**. E infatti non arriva quasi mai a scrivere la risposta
(2 scritture contro 46).

**Cosa abbiamo imparato, e non lo sapevamo:** la card **non serviva solo a dire regole — orienta
la scelta dello strumento**. Su corpus piccoli non conta (L5: nessuna differenza); conta
esattamente dove il recupero selettivo è indispensabile. È la stessa cosa che le ablazioni
avevano eletto a componente portante, e scopriamo ora che **la card aiuta il modello a usarla**.

**Il mio ragionamento a priori era plausibile e sbagliato.** Avevo classificato le regole in
"già imposte dalla struttura", "misurate inefficaci" e "duplicate da un errore azionabile" —
tre argomenti solidi, nessuno dei quali era una misura. Il fatto che una regola sia *non
violabile* per costruzione non dice niente su cosa faccia la sua **presenza nel testo**.

**Verdetto: la variante ridotta resta nel repo, spenta**, come banco di prova per il passo
successivo. `RG_WORKER_CARD` resta su `full`.

**Prossimo passo (LAD-style, non a intuito):** bisezione. Si rimettono i gruppi di regole uno
alla volta e si guarda quando L7 risale — così sapremo *quale* pezzo orienta la ricerca, invece
di indovinarlo. I 414 token restano sul tavolo: ora sappiamo che non sono gratis, non che siano
intoccabili.

### 7.16.2 F5.0-quater — la bisezione: è il PERIMETRO che orienta, non la disciplina d'azione

*(2026-08-05, notte, dev-fast, **20 run per braccio** su L7, `@4467073`/`@da21184` — stesso
codice; ogni braccio girato in due blocchi da 10, sommati. Log timestampati, prima applicazione
della regola dell'utente sui log.)*

Le 9 regole che `minimal` toglie, divise in due gruppi disgiunti, un braccio ciascuno:

- **A** (`worker.bisect-a.md`) — *disciplina d'azione e strumenti*: one action per step · leggi
  l'errore e non ripetere identico · solo le tool call cambiano il mondo · nomi ESATTI dei tool.
- **B** (`worker.bisect-b.md`) — *perimetro, focus, stile*: thought ≤300 · non uscire dallo
  scope · fai SOLO il tuo obiettivo (il TASK è sfondo) · fuori confine → finish done · stile
  delle stringhe.

| Braccio | Verde | IC 95% | vs `card-min` | vs `card-full` |
|---|---|---|---|---|
| `card-min` (ancora) | 1/20 = 5% | 1-24% | — | p = 0,0002 |
| **`card-bisA`** | **4/20 = 20%** | 8-42% | p = 0,342 | **p = 0,0225** |
| **`card-bisB`** | **9/20 = 45%** | 26-66% | **p = 0,0084** | p = 0,527 |
| `card-full` (ancora) | 12/20 = 60% | 39-78% | p = 0,0002 | — |

**Il gruppo B porta il grosso dell'effetto; il gruppo A non è distinguibile dalla card ridotta.**
Le regole che spingono a *cercare invece di leggere* sono quelle che **delimitano il perimetro
del compito**, non quelle che disciplinano l'uso degli strumenti. Interpretazione (non misurata):
dire al modello *"il TASK è sfondo, fai SOLO il tuo obiettivo"* gli impedisce di trattare il
corpus come materiale da studiare; le regole sui tool gli dicono *come* agire, non *su cosa*.

**Tre riserve dichiarate, perché il risultato non è più forte di quanto i dati permettano:**

1. **La bisezione non è pulita: i gruppi non si sommano.** 20% + 45% contro il 60% della card
   intera. B basta quasi da solo, A da solo non basta.
2. **"A non rilevabile" ≠ "A inutile".** 4/20 contro 1/20 è un effetto da ~15 punti e 20 run per
   braccio sono cieche sotto i ~30 (§ regola 1 della disciplina di misura). Per condannare A
   servirebbero ~100+ run per braccio. **Non lo condanniamo.**
3. **La previsione registrata era sbagliata** — la terza su quattro. Avevo scritto *prima* di
   misurare: *"le regole che orientano stanno nel gruppo A, candidata principale la regola
   'one action per step'"*. È uscito l'opposto quasi esatto. È anche la ragione per cui la
   previsione si registra: senza, avrei spiegato il gruppo B con la stessa disinvoltura con cui
   avevo previsto il gruppo A.

**Errore di lettura commesso e corretto in diretta:** guardando il parziale del secondo blocco di
bisA (cinque sconfitte di fila) avevo commentato *"è l'oscillazione a blocchi in diretta"*. I due
blocchi, 3/10 e 1/10, sono **compatibili con rumore binomiale** (p = 0,582), come lo sono quelli
di bisB (6/10 vs 3/10, p = 0,370). Vedere un fenomeno in un campione ancora aperto è esattamente
ciò che il divieto di *optional stopping* previene: la regola è stata rispettata nei fatti (il
giudizio è arrivato solo a campione pieno) e violata a voce.

**Conseguenza operativa — candidata, NON adottata:** la sola `bisect-b` dà 45% contro 60% a
prompt più corto. Se i token risparmiati valgano 3/20 è una decisione di progetto che **richiede
potenza adeguata**: `RG_WORKER_CARD` resta su `full`.

**Prossimo passo possibile:** bisezione di 2° livello dentro B, per isolare la singola regola.
Candidate a posteriori (mai misurate, da trattare come tali): la regola 10 (*"il TASK è
sfondo"*) e la 2 (*thought ≤300*).

### 7.16.3 Lettura dei log della bisezione — non è "cercare di più", è **non mettersi a leggere**

*(2026-08-05, analisi **ESPLORATIVA** dei log dei bracci `card-bisA` e `card-bisB`, 40 run,
`@4467073`/`@da21184`. Nessuna ipotesi pre-specificata: genera ipotesi, non le verifica.)*

La mappatura run→braccio è venuta dai **log timestampati con il percorso del report** introdotti
poche ore prima: `eval_runs.report_path` incrocia il log della sessione, e i conteggi tornano
esatti (20 e 20, 4/20 e 9/20 come dal runner). **Primo dividendo della regola sui log.**

**Scomposizione delle chiamate per esito, dentro lo stesso braccio:**

| Braccio / esito | run | `search_code`/run | `read_file`/run | s/r |
|---|---|---|---|---|
| `bisA` vinte | 4 | 10,2 | 19,8 | 0,52 |
| `bisA` perse | 16 | 14,1 | 46,0 | 0,31 |
| **`bisB` vinte** | 9 | **11,8** | **2,1** | **5,58** |
| **`bisB` perse** | 11 | **11,5** | **42,1** | 0,27 |

**Il numero di ricerche è praticamente identico fra run vinte e perse** (11,8 contro 11,5 in
bisB; in bisA le vinte cercano perfino *meno*). A cambiare di **venti volte** è il numero di
letture. La variabile non è *"cerca di più"*: è **"non si mette a leggere"**.

**Il test che separa causa da conseguenza** — l'obiezione ovvia è che leggere 42 file sia la
*conseguenza* di una run che sta andando male, non la causa. Guardando **solo i primi 5 passi**,
prima che l'esito sia determinato (bisA+bisB in pool, n = 40):

| Nei primi 5 passi… | vinte | perse | tasso di successo |
|---|---|---|---|
| **legge** almeno un file | 3 | 17 | **15%** |
| **non legge** | 10 | 10 | **50%** |

**Fisher esatto bilaterale p = 0,0407.** Chi apre leggendo perde tre volte su quattro; chi apre
senza leggere vince una volta su due. Il bias di sopravvivenza è **ridotto ma non azzerato**:
una run che legge presto potrebbe essere già in difficoltà per un'altra causa. È però
significativo che il totale delle chiamate distingua nettamente vinte e perse (bisB: 22,9 contro
62,0 per run) mentre **le ricerche restino piatte**: se fosse solo sopravvivenza, dovrebbero
crescere entrambe.

**Conseguenza sulla tesi del progetto.** La sintesi di §7.17.4 dice *"la variabile che predice il
successo è se il modello cerca o legge"*. Va **riformulata più precisamente**: cercare è quasi
una costante; ciò che discrimina è **se il modello scivola nella lettura**. Non è una sfumatura
lessicale, cambia l'intervento implicato: non serve spingerlo a cercare di più (lo fa già), serve
**rendergli difficile o costoso leggere** su corpus larghi — che è un intervento *strutturale*,
in linea con tutto ciò che in questo progetto ha funzionato, invece di un intervento persuasivo.

⚠️ **Statuto di questo risultato: esplorativo.** Analisi decisa *dopo* aver visto gli esiti, su
un pool di due bracci con card diverse, con p = 0,0407 vicino alla soglia e senza correzione per
molteplicità. **Non è un verdetto.** Il test che lo deciderebbe è quello già specificato per la
campagna fattoriale: registri per-run della strategia nei primi passi, su **istanze generate
indipendentemente**, con la finestra "primi N passi" fissata *prima* di guardare.

**Reperto minore, nella stessa analisi:** le chiamate a tool inesistenti (`tool_name`,
`tool_call_spec_id_1`, `tool_name_placeholder`) valgono 1,1/run in `bisA` — che **contiene** la
regola 13 sui nomi esatti — contro 1,6/run in `bisB`, che **non la contiene**, e 0,4/run in
`card-no10` (che la contiene). Indizio debole che la regola 13 dimezzi le chiamate fantasma
**senza convertirle in successi**: coerente con §7.9.2, dove gli errori azionabili agivano sul
*costo* del fallire e non sulla *frequenza*.

## 7.17 F5.6a — il pensiero fa 20/20 su L7, e tre scoperte diventano una sola

*(2026-08-04, dev-fast, 20 run per braccio, `@018e5a7` — codice con le ondate riarmabili.)*

### 7.17.1 Il difetto che ha invalidato la prima misura

Il primo tentativo di F5.6a è stato buttato, e per una ragione trovata **leggendo i log durante
l'attesa**: la compattazione scattava **una volta sola per tentativo**.

```
ondate per tentativo:  0 → 48 tentativi   ·   1 → 89   ·   2 o più → MAI
dei 89 tentativi che avevano compattato, 44 (49%) morti per contesto pieno LO STESSO
```

Il flag disarmava il meccanismo dopo la prima ondata; la catena ricresceva e risaturava la
finestra. **Errore di ragionamento, non di codice:** *"a ondate e non a ogni passo"* giustifica
il non compattare a ogni passo, **non** il compattare una volta e basta. E la riscrittura costa
~1 token (§7.11), quindi un'ondata in più è quasi gratis.

Corretto con un contatore e una condizione di riarmo (*la catena risupera la soglia* **e** *c'è
almeno un risultato nuovo da collassare* — il secondo vincolo è ciò che evita di ricadere nello
sfratto continuo). Verifica meccanica dopo il fix: **0 su 12 tentativi compattati muore per
contesto pieno**, contro il 49% di prima.

**Conseguenza sulla misura:** la previsione registrata assumeva *"ora la capienza è coperta"*, e
non lo era. L'esperimento non testava ciò che intendeva → rifatto da zero.

### 7.17.2 Il risultato

| Braccio su L7 | Verificati | IC 95% | Tentativi | Passi/tentativo | Ondate |
|---|---|---|---|---|---|
| `full` | 12/20 = 60% | 39-78% | 48 | 15,7 | 59 |
| **`think`** | **20/20 = 100%** | **84-100%** | **27** | **12,4** | **13** |

**Fisher esatto bilaterale p = 0,0033.** Il gradino più duro della ladder — 400 documenti, 25K
token, tre volte la finestra — passa **venti volte su venti** col ragionamento attivo.

### 7.17.3 La previsione registrata era sbagliata, e la tesi dei sostituti va ristretta

Avevo scritto, **prima di misurare**: *"se la tesi dei sostituti regge, il vantaggio del
pensiero deve sparire ora che la compattazione copre la capienza"*. È successo il contrario: il
vantaggio è **cresciuto** (+4 in LAD.11 → **+8** adesso, con il braccio col pensiero al 100%).

**Impalcatura e ragionamento non sono sostituti in generale.** Lo sono dove il collo di
bottiglia è l'**aritmetica** (L5: la guardia di coerenza lo copre, e il pensiero non aggiunge
nulla). Sono **complementari** dove il collo di bottiglia è la **strategia di recupero su larga
scala** (L7).

### 7.17.4 Il meccanismo — e qui tre scoperte separate diventano una

Il pensiero **non aggiunge contesto: riduce il bisogno di contesto.**

| | `full` | `think` |
|---|---|---|
| `search_code` | 109 | **168** |
| `read_file` | 23 | **5** |

Cerca invece di leggere. Quindi trova prima, spende meno passi, chiude in metà dei tentativi e
**non si avvicina mai al tetto** — 13 ondate di compattazione contro 59.

**E questa è la stessa variabile di altre due scoperte:**

| Scoperta | Effetto sul comportamento | Esito |
|---|---|---|
| Ablare `search_code` (§6.5) | costretto a leggere | **0/5 su ogni gradino** |
| Ridurre la card (§7.16.1) | 440 letture contro 169 ricerche | **L7 1/20** |
| Aggiungere il pensiero (qui) | 168 ricerche contro 5 letture | **L7 20/20** |

> **Su corpus larghi, la variabile che predice il successo è una sola: se il modello cerca o
> legge.** Tre interventi indipendenti — un tool, un pezzo di prosa, un canale di ragionamento —
> agiscono tutti su quella stessa leva, e i loro esiti si ordinano esattamente come l'intensità
> con cui ce lo spingono.

### 7.17.5 Conseguenza operativa: una regola di routing misurata

TH2 aveva spento il thinking sul **coding**; LAD.11 non l'aveva visto pagare su L5/L6. Qui paga
in modo schiacciante. **Non è una contraddizione: sono compiti diversi.** Il ragionamento paga
dove serve una *strategia di recupero*, non dove serve ragionare in astratto.

È la prima regola di routing del progetto che nasce da una misura invece che da un'intuizione, e
va portata in **F6**: *thinking ON per i task a recupero largo, OFF per il coding.*

## 7.18 F5.6b — la sintesi regge: il pensiero sostituisce la card

*(2026-08-04, dev-fast, 20 run, `@64843a1`. **Prima previsione registrata che risulta corretta**,
su tre.)*

| L7 | card intera | card ridotta |
|---|---|---|
| **senza pensiero** | 12/20 | **1/20** |
| **con pensiero** | **20/20** | **19/20** |

**La card conta enormemente quando il pensiero è spento (12 contro 1), e quasi nulla quando è
acceso (20 contro 19).** Le due leve agiscono sulla stessa variabile — *cercare invece di
leggere* — e sono **largamente intercambiabili**.

**Conseguenza di progetto:** col pensiero attivo si possono liberare i **414 token** della card
al prezzo di 1/20. Si può *pagare in ragionamento* invece che in token di prompt — ed è una
scelta, non un vincolo.

**Conseguenza sulla teoria:** la sintesi di §7.17.4 regge nella forma forte. Tre interventi
indipendenti (un tool, un pezzo di prosa, un canale di ragionamento) non solo spingono la stessa
leva: **si sostituiscono a vicenda**. Dove uno è presente, gli altri smettono di contare.

## 7.19 Audit di novità: quanto di tutto questo era già noto

*(2026-08-04, sette ricerche mirate. **Risposta: praticamente tutto, sul piano concettuale.**)*

Erano state elencate cinque scoperte come "non trovate in letteratura". Cercandole **una per
una**, sono state trovate **tutte e cinque**, più una sesta che non era nemmeno in lista:

| Nostra "scoperta" | Stato reale |
|---|---|
| Il nudo come controllo: *"se il modello nudo passa, il task non misura l'impalcatura"* | **Noto** — [*Baselines Before Architecture*](https://arxiv.org/html/2607.13085) lo enuncia nel titolo |
| Ablare le regole del prompt e misurarne l'esito | **Noto** — [RubricRefine](https://arxiv.org/pdf/2605.09730) quantifica l'impatto per categoria di regola |
| Cercare contro leggere come variabile del successo | **Noto** — [*Is Grep All You Need?*](https://arxiv.org/html/2605.15184v1) e la letteratura sulla *direct corpus interaction* |
| Ragionamento condizionato al dominio | **Noto come concetto** (routing base/CoT). ⚠️ Ma il canone dice che il CoT aiuta l'**aritmetica** e ReAct il **recupero**: il nostro dato va nella direzione opposta |
| La forbice `completed ≠ verified` | **Noto**, con lo stesso nome: [*Characterizing False Success in LLM Agents*](https://arxiv.org/pdf/2606.09863), e lo stesso rimedio (controllore deterministico) |
| Guardia di coerenza in scrittura | **Noto** — è il pattern *reject-and-regenerate* dei guardrail di output, applicato a totali e somme |
| Il pensiero **compensa** una card indebolita (§7.18) | **Noto** — [*Cross-Component Interference*](https://arxiv.org/html/2605.05716) studia le interazioni fra componenti; [*Select-then-Solve*](https://arxiv.org/pdf/2604.06753) formula l'**ipotesi della compensazione**: la struttura di ragionamento compensa i divari di capacità e vale **di più quanto più il modello è debole** (CoT: Qwen3-30B da 18% a 64%, **GPT-5 −15 punti**) |

### ⚠️ La lacuna che il campo dichiara, e che ci riguarda

Dal primo di quei due lavori, sul limite dello stato dell'arte:

> *«Il lavoro precedente usa nel migliore dei casi ablazioni una-alla-volta, **mai disegni
> fattoriali completi** che rivelino interazioni di ordine superiore.»*

**È esattamente la campagna completa proposta dall'utente** (~22 h, tutti i bracci × tutte le
famiglie × tutte le leve). Il campo dichiara che manca, e noi siamo in posizione di farla **su
un regime che nessuno misura**. Non cambia l'ordine — prima si capisce, poi si misura (§tesi e
fase) — ma dice **perché** quella misura varrà la pena: non per convincere noi, ma perché è il
pezzo che manca a tutti.

E l'altra metà della loro conclusione è il nostro F6, enunciato da fuori:
> *«I default da agente massimamente equipaggiato andrebbero sostituiti da una selezione di
> sottoinsiemi specifica per task.»*

E la decomposizione che stiamo facendo esiste già, fatta meglio su alcuni assi:
[*Where Does Agent Reliability Come From?*](https://arxiv.org/html/2607.17044) misura
**struttura +9,5pp contro verifica +1,5pp** su SpreadsheetBench — **la nostra stessa conclusione**,
raggiunta indipendentemente.

### Cosa resta davvero nostro

Non i concetti. **Il regime e i numeri.**

1. **Un solo modello da 2B fa tutto, su 15 W, in locale.** La letteratura più vicina usa un
   modello di frontiera come generatore più piccoli specialisti, e misura economia di serving
   cloud — dichiara esplicitamente di **non** riportare inferenza su hardware vincolato.
2. **Il numero**: 0/20 → 20/20 su 400 documenti, con quel modello e quell'hardware.
3. **La tabella di attribuzione** delle sette leve sulla stessa famiglia di task, allo stesso
   commit — che è ciò che ancora non abbiamo, ed è il vero prodotto della fase.
4. **Il catalogo dei risultati negativi** con regole di decisione pre-registrate.

**Conseguenza editoriale, non negoziabile:** il whitepaper va riscritto **citando** questi
lavori e posizionandosi rispetto a essi. Pubblicare una decomposizione senza citarli ci farebbe
sembrare disinformati o disonesti — e su alcuni assi loro l'hanno fatta meglio.

### 7.19.1 Esito editoriale: white paper riscritto (2026-08-04)

✅ **Fatto.** `white_paper.md` riscritto alla luce di **tutte** le fonti raccolte in sessione,
non solo quelle dell'audit finale. Bibliografia da **12 a 46 voci**, raggruppate per famiglia
(decomposizione dell'affidabilità · strategia di recupero · falso successo · ragionamento
condizionato · compattazione del contesto · KV cache e runtime · critici e specification-driven).
Verifica meccanica: **0 citazioni senza voce, 0 voci mai citate**.

Modifiche sostanziali, non solo aggiunta di riferimenti:

| Sezione | Cosa è cambiato |
|---|---|
| Abstract | nuovo paragrafo di posizionamento: sette meccanismi su sette già noti; ciò che rivendichiamo è **regime, numeri, tabella di attribuzione a un commit, negativi pre-registrati, sostituzione fra leve** |
| §1.3 Contributi | riscritti da 4 a 6 voci, **tutte più strette di prima**: nessun meccanismo rivendicato come nuovo |
| §2.3 (nuova) | l'audit di priorità come tabella: nostra scoperta → arte nota → verdetto |
| §2.4 (nuova) | cosa resta nostro, con il confronto esplicito a 2607.17044 e 2602.00887 sul regime |
| §2.5 (nuova) | la lacuna dichiarata dal campo (niente disegni fattoriali) come obiettivo del progetto |
| §0.1 | aggiunte le righe **15 (card)** e **16 (pensiero su recupero largo, 12/20 → 20/20, p = 0,0033)** |
| §0.2 riga 3 | il rifiuto del pensiero **ristretto a coding e gradini stretti**: la condizione di riapertura è scattata ed è risultata positiva |
| §6.4-quater | riscritta: da *"sostituti"* a **sostituti sul collo di bottiglia condiviso, complementari altrove**, con la 2×2 card × pensiero e la sintesi cercare-contro-leggere |
| §6.1 | riconciliazione col +1,5pp di 2607.17044: numero giusto, metrica incompleta |
| §8 | la campagna **fattoriale completa** promossa a lavoro principale pianificato, con la motivazione presa dai nostri stessi dati |

**Motivo per cui §6.4-quater andava comunque riscritta, a prescindere dalle citazioni:** il
paper affermava ancora *"sostituti, non complementi"*, tesi che **F5.6a ha falsificato** su L7.
Era un'affermazione sbagliata rimasta nel documento pubblico.

### 7.19.2 Revisione da peer review esterna (2026-08-05)

Il white paper è stato sottoposto a una review esterna (GPT 5.6) e revisionato sui punti accolti:

1. **Provenienza CPU/GPU esplicitata ovunque** — box di provenienza in testa al documento,
   caveat in §0, §8 corretta (diceva *"every number in §5 and §6 was obtained on the GPU"*, ed
   era **falso per eccesso**: §5.1–5.7 sono severino-sim CPU; solo la ladder è dev-fast GPU).
2. **"Single-commit attribution table" ritirata come claim** — è una sintesi storica di
   ablazioni una-alla-volta a commit diversi; la tabella simultanea è il *prodotto atteso*
   della campagna fattoriale, e ora il paper lo dice.
3. **Unità sperimentale dichiarata** — nuova §4.5: n=20 = 20 esecuzioni della **stessa istanza**
   deterministica sotto non-determinismo del server, non 20 problemi indipendenti; inferenza
   limitata all'istanza; multi-istanza rimandata alla campagna fattoriale.
4. **Confermativo/esplorativo separati** (§4.5): solo la compattazione ha protocollo pienamente
   confermativo (pilota per dimensionare + campione nuovo); il resto è pre-specificato
   mono-campione o esplorativo. **"pre-registered" → "pre-specified"** ovunque (regole in git
   con timestamp verificabili, ma nessun registro esterno).
5. **Interazione card × pensiero formalizzata per quanto possibile**: test stratificati
   calcolati — effetto card **p = 4,3×10⁻⁴ senza pensiero, p = 1,0 con** (e simmetrici
   5,8×10⁻⁹ / 0,0033); modello logistico con termine d'interazione rimandato ai dati
   multi-istanza. Corretta anche la terminologia: è un'interazione **a due fattori**, non
   "higher-order".
6. **"La variabile unica che predice il successo" declassata a ipotesi di mediazione** con i
   confondenti dichiarati (i conteggi aggregati sono in parte conseguenza del successo).
7. **Denominatori dell'onestà separati**: 8 claim su 5 run (livello claim) vs 1 run su 550+
   (livello run) — presentati come bound, non come rapporto; "lie" → "false completion claim"
   nei punti assertivi.
8. **Ladder ridescritta come matrice a 3 assi** (ampiezza, fatti, aggregazione) campionata su
   una diagonale, non scala monodimensionale.
9. **Pass di coerenza sulle conclusioni stratificate**: l'abstract e §9 usavano ancora il
   finish gate (p=0,66, sottodimensionato) come controesempio — sostituito col **calcolatore**
   (p=1,000, assorbito dalla guardia di coerenza, meccanismo verificato); corretta anche la
   frase in §8 sul trade-off compattazione/cache (già smentito da §7.11/§7.13) e la riga step
   budget in §0.1 (sequenza: budget vincolante a 20, capienza vincolante a 60).
10. **§7 Threats**: aggiunte unità/indipendenza e molteplicità. **Bibliografia**: una fonte
    per voce (sotto-lettere), anni e date d'accesso. **Appendice A**: dove stanno commit hash,
    SHA del modello, pin di llama.cpp; dichiarato ciò che ancora manca (DOI, raw archives,
    script statistici).

**Punti della review NON accolti (con motivo):** la ristrutturazione completa in 11 sezioni e
il taglio del 30-40% sono rimandati a **dopo la campagna CPU** — la review stessa dice di
riscrivere l'abstract *"dopo aver congelato i risultati"*, e i risultati non sono congelati:
ristrutturare ora significherebbe farlo due volte. La cronaca delle correzioni resta nel testo
principale **di proposito** (nota in testa a §6): in un working paper è contenuto di metodo;
migrerà in appendice nella versione da submission.

## 8. Cosa manca (aggiornamento previsto)

- [ ] Ladder B2 post-fix: ablazioni `−calc`, `−search`, `−verify`, `−coherence` su GPU (L5 fatto a n=20: §7.6.1; mancano L6 e L7)
- [x] ~~L5 con la guardia su `severino-sim`~~ — **ANNULLATA 2026-08-05 (utente)**, come ogni
      conferma ladder su severino-sim: i numeri assoluti ufficiali verranno dai **benchmark
      pubblici su Severino vero** (v. piano, sezione benchmark); la GPU resta per iterazione e
      delta interni
- [x] ~~Gate sul finish in-loop (LAD.9)~~ — **fatto e spento**: risultato nullo, §7.7
- [ ] `bad_args` che insegna (LAD.10) — il secondo modo di fallire di §7.6.5, non ancora affrontato
- [x] ~~LAD.13: `calculator` merita il catalogo?~~ — **no**: p = 1,000, spenta di default (§7.9)
- [ ] Rimisurare la calcolatrice nei domini di F7 (matematica/everyday), dove la guardia di coerenza non si applica
- [ ] Retest di LAD.9 sui task coding larghi T040–T042 (dove un tentativo sprecato costa 100K+ token)
- [ ] **F5**: L7 muore per contesto pieno (§7.7.2) — la ladder ha motivato la fase dal basso
- [ ] `--swa-full` su `severino-sim`: misurare RAM e prefill prima di adottarlo (§7.11.3)
- [ ] **Rifare TUTTA la ladder** (B1-B4, ablazioni, thinking on/off) dopo F5 — decisione utente
      2026-08-04: i test attuali non sono invalidi ma vanno rifatti per sicurezza dopo i fix
- [x] ~~Ladder B4 post-fix~~ — **fatto** (§7.10): B2 43/60 contro B4 47/60, p = 0,528, +55% tempo
- [ ] B4 **con le ablazioni** (simmetria della matrice): finora solo il braccio `think` completo
- [x] ~~**Ladder ufficiale su severino-sim**~~ — **ANNULLATA 2026-08-05 (utente)**: sostituita dai benchmark pubblici su Severino vero. I numeri per il README saranno quelli
- [ ] Diagnosi di L7 (perché 60 passi non bastano)
- [x] ~~Disambiguazione del confondimento B3/L5 (budget di pensiero 256)~~ — fatta, §6.2 nota 1
- [x] ~~**LAD.14**: pensiero PIENO con materiale PIENO~~ — **fatto, e ha ribaltato il verdetto**: 20/20 contro 0/20, §7.8
- [x] ~~LAD.14 su `severino-sim`~~ — **ANNULLATA 2026-08-05 (utente)**: stessa decisione di cui sopra
- [ ] **F5 con il secondo obiettivo**: fare spazio al ragionamento oltre che al materiale (§7.8.5)
- [ ] Retest dei verdetti aperti (planner e thinking) col router attivo, post-F6/F7
- [ ] Benchmark pubblici a fine progetto (valori comparabili con la letteratura)

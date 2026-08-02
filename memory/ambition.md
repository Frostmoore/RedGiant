# ambition.md — Battere la ricerca

**Dichiarazione (utente, 2026-08-03):** questo piccolo e unassuming harness deve ottenere
risultati **migliori della ricerca generica** sui modelli piccoli. Non "in linea con": migliori.
Si procede per **piccolissimi step**, ognuno con un numero pubblico da battere e una misura
nostra da contrapporgli.

Questo documento è il registro di quella campagna: cosa vuol dire "battere", contro chi, con
quali regole, un gradino alla volta. Si aggiorna a ogni gradino salito (o fallito: un gradino
fallito onestamente resta nel registro).

**⏸️ QUANDO si comincia (utente, 2026-08-03): NON ORA.** La campagna parte solo quando il
sistema è completo e ottimizzato — oggi sarebbe un confronto impari a nostro sfavore (nessuna
ottimizzazione fatta: niente thinking, niente routing, fix appena atterrati). Prerequisiti
minimi prima di G0: PS7 chiusa (v4.0.0), campagna thinking TH0–TH3 completata, routing per
taglia (F6) o motivazione per farne a meno. Fino ad allora questo file resta un registro di
intenzioni, non di misure.

---

## 1. Cosa significa "battere la ricerca" (perché il confronto sia VALIDO)

Un nostro numero batte un numero della letteratura solo se valgono TUTTE queste condizioni:

1. **Benchmark pubblico o riproducibile** — mai solo i nostri task sintetici: su quelli
   nessuno può verificarci.
2. **Modello uguale o più piccolo** di quello del numero da battere (classe ~2B effettivi,
   quantizzato Q4 QAT) — **zero fine-tuning, zero distillazione**: solo harness. Se loro
   fine-tunano e noi no, batterli vale doppio; se serve il fine-tuning per confrontarsi, il
   confronto va etichettato.
3. **Hardware dichiarato e più povero**: i numeri ufficiali su severino-sim (CPU 4 core
   target-equivalent). La ricerca gira su GPU datacenter; noi su un mini-PC. A parità di
   risultato, il nostro vale di più — e va detto con il wattaggio accanto.
4. **Verified, mai self-reported**: giudice esterno meccanico, forbice completed≠verified
   dichiarata, codice committato, **run multiple mediate** (lezione della varianza CPU:
   banda ±2/13 osservata — mai più verdetti su run singola).
5. **Zero API esterne, sempre** (D-fondamentale del progetto).

## 2. I numeri da battere (dalla ricognizione del 2026-08-02, fonti nel README §niche)

| # | Il numero della letteratura | Fonte | Il nostro angolo di attacco |
|---|---|---|---|
| B1 | GCD su SLM: media 62,5%→75,2% pass su generazione Bash; 0.6B: 16,7%→59,2% | NVIDIA dev blog | La nostra grammatica + schema-in-prompt + validatori è PIÙ del solo GCD: su un benchmark comparabile dobbiamo superare il delta del solo constrained decoding |
| B2 | Structured output: 7-9B da ~0% usabile a 84-87% con workflow | arXiv:2605.02363 | Noi siamo a 100% schema-valido su 2B (60/60) — da ri-dimostrare sul LORO protocollo, non sul nostro |
| B3 | Function calling: xLAM-**1B fine-tuned** 78,94% su BFCL | arXiv:2409.03215 | Il bersaglio più duro e più bello: avvicinarlo/superarlo **senza fine-tuning**, solo harness, su BFCL |
| B4 | Task agentici vincolati su edge: 60-80% (1-13B, con fine-tuning) | arXiv:2511.22138 (TinyLLM) | Stessa fascia di successo, modello alla base della loro forchetta, zero training |
| B5 | Tool-verification: 1B > 8B su MATH | arXiv:2504.04718 | Riprodurre il pattern "piccolo+oracolo > grande nudo" su un dominio nostro (coding micro-task) con modelli locali |
| B6 | Harness quality: +20-40 punti a modello fisso | arXiv:2606.08529 | Documentare il NOSTRO delta harness-vs-naked sullo stesso benchmark pubblico (non su task nostri) |

*(Tabella da raffinare insieme: quali bersagli sono i primi gradini, quali richiedono
infrastruttura che ancora non abbiamo — es. BFCL richiede l'harness di function calling.)*

## 3. Il metodo dei piccolissimi step

Ogni gradino è UNA riga di questa forma, e non si sale il successivo finché il corrente non è
chiuso (vinto o perso, mai abbandonato in silenzio):

> **Gradino G<n>**: [numero da battere] · [nostro setup esatto] · [protocollo di misura,
> incluse N run] · [esito: numeri nostri vs loro] · [verdetto: BATTUTO / PAREGGIATO /
> PERSO — e perché]

Regole di campagna:
- **Un cambiamento alla volta** tra un gradino e l'altro (protocollo Sol, già rodato).
- Prima il gradino si **perde onestamente col sistema attuale**, poi si migliora: il numero
  "prima" è parte del risultato quanto il "dopo".
- Il costo si dichiara sempre accanto al risultato: token, secondi, watt. "Batterli spendendo
  100× tanto" non è battere la ricerca, è comprarla.
- Le leve già in canna, in ordine: i 5 fix PS6 → thinking T-SM (`plan_thinking_ab.md`) →
  routing per taglia (F6) → dieta artefatti/budget audit → fine-tuning MAI (fuori tesi).

## 4. Gradini — registro

- [ ] **G0 — Scegliere l'arena del primo gradino.** Candidati (decisione da prendere insieme):
  (a) **B2/structured output** — il più vicino a ciò che già facciamo, vittoria probabile,
  valore mediatico basso; (b) **B3/BFCL senza fine-tuning** — il più ambizioso, serve
  costruire l'harness di function calling (ma è ANCHE il pezzo che serve al worker quotidiano
  per F7); (c) **B5/pattern piccolo+oracolo** — dimostrazione concettuale forte, richiede solo
  l'evaluator che già abbiamo + un modello di confronto più grande locale.
- [ ] G1 — *(si definisce dopo G0)*
- *(registro da riempire: un gradino = una riga chiusa, con data e commit)*

## 5. Cosa falsificherebbe l'ambizione (da scrivere prima di cominciare, per onestà)

Se dopo i gradini con tutte le leve in canna (fix + thinking + routing) i nostri numeri restano
sotto quelli della letteratura *a parità di condizioni valide (§1)*, la conclusione onesta non
sarà "la tesi è falsa" ma: **l'harness generico della ricerca + un modello di classe superiore
resta preferibile all'harness specializzato + il modello minimo**. Anche quel verdetto andrà
scritto qui, coi numeri. (E resterà comunque vero ciò che è già dimostrato: pavimento alzato a
livello step, onestà, contenimento dei costi — v. README §scoreboard.)

---

*Documento creato il 2026-08-03 su richiesta dell'utente. Prossima azione: decidere G0.*

# Small Model Powerhouse
## Specifica operativa per un sistema agentico basato su modelli piccoli

**Versione:** 0.1  
**Stato:** Draft operativo  
**Obiettivo:** trasformare un modello locale piccolo, limitato e relativamente poco affidabile in un sistema capace di affrontare task complessi attraverso decomposizione, verifica continua, contesto minimo e orchestrazione deterministica.

---

## 1. Visione del sistema

Il sistema non tenta di rendere il modello intrinsecamente più intelligente.

L'obiettivo è ridurre sistematicamente le condizioni nelle quali un modello piccolo tende a fallire:

- task troppo ampi;
- contesto eccessivo;
- istruzioni ambigue;
- pianificazione insufficiente;
- dipendenze non esplicitate;
- errori propagati tra più passaggi;
- assenza di test;
- loop improduttivi;
- dichiarazioni di successo non verificate;
- uso incoerente degli strumenti.

La tesi fondamentale è:

> Un modello piccolo può produrre risultati molto migliori quando ogni attività viene ridotta a un'unità limitata, verificabile e compatibile con le sue capacità.

Il sistema deve quindi applicare quattro principi:

1. **Pianificazione globale**
2. **Esecuzione locale**
3. **Verifica continua**
4. **Contesto minimo**

---

## 2. Obiettivi principali

Il sistema deve:

- classificare automaticamente il tipo di richiesta;
- stimare la difficoltà e il rischio del task;
- scegliere la pipeline minima necessaria;
- produrre un piano globale sintetico;
- espandere una sola macrofase alla volta;
- eseguire una sola sottofase alla volta;
- verificare ogni risultato significativo;
- correggere gli errori prima che si propaghino;
- ripianificare quando il piano non è più valido;
- mantenere uno stato strutturato e persistente;
- evitare di usare la cronologia completa come unica memoria;
- limitare token, tempo, RAM, CPU e numero di tentativi;
- produrre una risposta finale fondata su risultati verificati.

---

## 3. Non-obiettivi

La prima versione non deve:

- supportare qualsiasi modello esistente;
- simulare una squadra infinita di agenti;
- generare piani lunghi decine di migliaia di token senza necessità;
- affidarsi a una conversazione lineare come memoria principale;
- consentire a ogni agente di modificare liberamente lo stato globale;
- eseguire operazioni irreversibili senza autorizzazione;
- continuare indefinitamente in caso di errore;
- confondere la verbosità con il ragionamento;
- considerare valido un risultato solo perché il modello dichiara di aver terminato.

---

## 4. Architettura generale

Il sistema è composto da due categorie di componenti:

### 4.1 Componenti cognitivi

Sono ruoli eseguiti dal modello:

- Classifier
- Assessor
- Planner
- Phase Designer
- Worker
- Debugger
- Supervisor
- Final Reviewer

Questi ruoli possono usare lo stesso modello con prompt, contesto, temperatura e strumenti differenti.

### 4.2 Componenti deterministici

Sono componenti software tradizionali:

- Orchestrator
- State Manager
- Context Builder
- Tool Router
- Policy Engine
- Budget Manager
- Checkpoint Manager
- Artifact Store
- Logger
- Evaluator

Il sistema non deve affidare al modello decisioni che possono essere prese in modo deterministico.

---

## 5. Pipeline principale

```text
Prompt utente
    ↓
Classifier
    ↓
Assessor
    ↓
Policy Engine
    ↓
Planner globale
    ↓
Phase Designer
    ↓
Worker
    ↓
Debugger / Verifier
    ↓
Supervisor
    ↓
Aggiornamento dello stato
    ↓
Fase o sottofase successiva
    ↓
Final Reviewer
    ↓
Risposta finale
```

La pipeline non è obbligatoriamente completa per ogni richiesta.

Un task semplice può seguire:

```text
Prompt → Classifier → Worker → Risposta
```

Un task medio può seguire:

```text
Prompt → Classifier/Assessor → Planner breve → Worker → Verifier → Risposta
```

Un task complesso usa l'intera pipeline.

---

## 6. Ruoli agentici

## 6.1 Classifier

### Responsabilità

Il Classifier identifica:

- dominio del task;
- natura della richiesta;
- formato di output;
- necessità di strumenti;
- presenza di file, codice, web, database o API;
- eventuali vincoli espliciti;
- livello di rischio;
- possibilità di esecuzione diretta.

### Output richiesto

```yaml
task_type: coding
domain: backend
intent: modify_existing_project
required_capabilities:
  - filesystem
  - code_search
  - shell
  - test_runner
constraints:
  - preserve_existing_api
  - no_database_changes
risk_flags:
  - modifies_existing_code
recommended_pipeline: full
```

### Regole

- Non deve risolvere il task.
- Non deve produrre un piano dettagliato.
- Deve usare un output strutturato.
- Deve preferire categorie limitate e stabili.

---

## 6.2 Assessor

### Responsabilità

L'Assessor valuta:

- difficoltà;
- ambiguità;
- numero stimato di passaggi;
- dipendenze;
- rischio di errore;
- verificabilità;
- costo computazionale;
- necessità di supervisione.

### Output richiesto

```yaml
difficulty: high
ambiguity: medium
estimated_phases: 5
estimated_subtasks: 18
verification_level: strict
replanning_probability: medium
human_approval_required: false
recommended_token_budget: 24000
recommended_retry_budget: 2
```

### Scala suggerita

- `trivial`
- `low`
- `medium`
- `high`
- `critical`

### Regole

- Il livello di difficoltà deve influenzare la pipeline.
- Il livello di rischio deve influenzare i controlli.
- Un task difficile ma verificabile può essere automatizzato.
- Un task semplice ma irreversibile può richiedere approvazione.

---

## 6.3 Planner

### Responsabilità

Il Planner produce una mappa generale del lavoro.

Deve definire:

- obiettivo finale;
- criteri globali di successo;
- macrofasi;
- ordine;
- dipendenze;
- rischi;
- punti di verifica;
- condizioni di stop.

### Vincolo fondamentale

Il Planner non deve descrivere ogni singola operazione.

Deve produrre una struttura sufficientemente precisa da guidare il lavoro, ma abbastanza sintetica da poter essere aggiornata.

### Output richiesto

```yaml
goal: "Implementare il sistema richiesto senza regressioni"
success_criteria:
  - all_requested_features_implemented
  - existing_tests_pass
  - new_tests_added
  - no_unapproved_breaking_changes

phases:
  - id: P1
    title: Analyze current system
    depends_on: []
    completion_criteria:
      - architecture_understood
      - affected_components_identified

  - id: P2
    title: Design changes
    depends_on: [P1]
    completion_criteria:
      - implementation_strategy_defined
      - test_strategy_defined

  - id: P3
    title: Implement changes
    depends_on: [P2]

  - id: P4
    title: Test and repair
    depends_on: [P3]

  - id: P5
    title: Final verification
    depends_on: [P4]
```

### Regole

- Il piano globale deve avere un limite di token.
- Il limite può crescere con la difficoltà, ma non deve usare automaticamente l'intero contesto disponibile.
- Il piano deve essere versionato.
- Ogni modifica al piano deve indicare la ragione.
- Il Planner deve poter essere richiamato durante l'esecuzione.

---

## 6.4 Phase Designer

Il Phase Designer corrisponde al ruolo inizialmente definito come “Developer 1”.

### Responsabilità

Prende una sola macrofase e la converte in una sequenza di sottofasi operative.

Per ogni sottofase definisce:

- obiettivo;
- input;
- operazioni;
- strumenti;
- output atteso;
- criteri di completamento;
- test;
- dipendenze;
- rischio;
- strategia di fallback.

### Output richiesto

```yaml
phase_id: P3
subtasks:
  - id: P3.S1
    title: Modify service layer
    objective: "Aggiungere la nuova logica senza cambiare l'interfaccia pubblica"
    inputs:
      - current_service_code
      - architecture_notes
    tools:
      - read_file
      - search_code
      - write_patch
    expected_outputs:
      - modified_service
    completion_criteria:
      - code_compiles
      - public_interface_unchanged
    verification:
      - static_analysis
      - unit_tests
```

### Regole

- Espande solo la fase corrente.
- Non deve riscrivere l'intero piano.
- Ogni sottofase deve essere abbastanza piccola da poter essere eseguita in una singola sessione del Worker.
- Le sottofasi devono avere criteri di successo osservabili.

---

## 6.5 Worker

Il Worker corrisponde al ruolo inizialmente definito come “Developer 2”.

### Responsabilità

Esegue una sola sottofase alla volta.

Riceve:

- obiettivo della sottofase;
- contesto strettamente necessario;
- strumenti autorizzati;
- stato locale;
- criteri di successo;
- limiti di esecuzione.

Produce:

- risultato;
- modifiche;
- artefatti;
- evidenze;
- eventuali problemi;
- richiesta di verifica.

### Regole

- Non può cambiare il piano globale.
- Non può dichiarare completata una sottofase senza evidenza.
- Non riceve automaticamente tutta la cronologia.
- Deve usare gli strumenti quando il risultato è verificabile tramite strumenti.
- Deve fermarsi quando raggiunge un limite o incontra un blocco reale.
- Non deve inventare output di tool.

### Output richiesto

```yaml
subtask_id: P3.S1
status: completed
actions:
  - "Updated service implementation"
artifacts:
  - path: src/Service.php
evidence:
  - "Static analysis passed"
issues: []
verification_requested:
  - unit_tests
```

---

## 6.6 Debugger / Verifier

### Responsabilità

Il Debugger verifica il lavoro svolto.

Deve:

- generare test quando necessario;
- eseguire test;
- controllare output e artefatti;
- confrontare risultato atteso e reale;
- identificare regressioni;
- classificare gli errori;
- proporre correzioni;
- stabilire se la sottofase può essere accettata.

### Tipi di verifica

- verifica sintattica;
- verifica strutturale;
- verifica semantica;
- test unitari;
- test di integrazione;
- test end-to-end;
- controllo output;
- confronto con criteri di successo;
- verifica di sicurezza;
- verifica delle regressioni.

### Output richiesto

```yaml
subtask_id: P3.S1
verdict: fail
checks:
  - name: syntax
    result: pass
  - name: unit_tests
    result: fail
failures:
  - test: testExistingBehavior
    reason: unexpected_return_value
severity: medium
recommended_action: repair
repair_scope:
  - src/Service.php
```

### Regole

- Il Debugger non deve modificare direttamente il piano.
- Può proporre una patch o una strategia di riparazione.
- Deve distinguere errori del codice, errori del test ed errori del piano.
- Un test generato dal modello non è automaticamente valido: deve essere controllato rispetto ai requisiti.

---

## 6.7 Supervisor

### Responsabilità

Il Supervisor controlla la qualità dell'intero processo.

Può decidere di:

- accettare la sottofase;
- richiedere una correzione;
- ripetere una sottofase;
- cambiare approccio;
- annullare una modifica;
- espandere nuovamente la fase;
- richiamare il Planner;
- chiedere chiarimenti;
- interrompere l'esecuzione;
- dichiarare il task parzialmente completato.

### Input

- piano attuale;
- stato globale;
- output del Worker;
- report del Debugger;
- budget residuo;
- cronologia dei tentativi;
- criteri di successo.

### Output richiesto

```yaml
decision: retry_subtask
reason: "Implementation failed one required regression test"
target: P3.S1
retry_strategy: "Use previous checkpoint and preserve public behavior"
budget_adjustment: 0
```

### Regole

- Deve impedire loop infiniti.
- Deve considerare il numero di tentativi già effettuati.
- Deve distinguere un errore locale da un piano globalmente sbagliato.
- Dopo un numero massimo di fallimenti deve cambiare strategia o fermarsi.

---

## 6.8 Final Reviewer

### Responsabilità

Il Final Reviewer controlla il risultato complessivo prima della risposta finale.

Deve verificare:

- copertura dell'obiettivo;
- completamento delle macrofasi;
- stato dei test;
- presenza di errori residui;
- coerenza degli artefatti;
- rispetto dei vincoli;
- chiarezza della risposta finale.

### Output richiesto

```yaml
overall_status: completed
success_criteria:
  requested_features: pass
  tests: pass
  regressions: pass
  constraints: pass
remaining_issues: []
final_response_allowed: true
```

---

## 7. Orchestrator

L'Orchestrator è il componente centrale.

Non è un agente linguistico, ma un motore deterministico.

### Responsabilità

- avviare la pipeline;
- scegliere il prossimo ruolo;
- fornire il contesto corretto;
- applicare policy;
- gestire budget e timeout;
- eseguire strumenti;
- aggiornare lo stato;
- creare checkpoint;
- gestire retry;
- fermare loop;
- registrare decisioni;
- produrre la sequenza finale delle attività.

### Regola fondamentale

Il modello propone.  
L'Orchestrator decide cosa viene effettivamente eseguito.

---

## 8. Stato condiviso

La memoria principale del sistema deve essere strutturata.

La cronologia testuale è solo una fonte secondaria.

### Struttura minima

```yaml
task:
  id: task_001
  user_request: "..."
  task_type: coding
  difficulty: high
  status: running

goal:
  description: "..."
  success_criteria: []

plan:
  version: 3
  current_phase: P3
  phases: []

execution:
  current_subtask: P3.S1
  completed_subtasks: []
  failed_subtasks: []
  retry_count: 1

artifacts:
  files: []
  outputs: []
  patches: []

verification:
  checks: []
  failures: []
  unresolved_issues: []

decisions:
  - id: D1
    actor: supervisor
    reason: "..."
    decision: "..."

budgets:
  token_limit: 24000
  tokens_used: 12000
  tool_call_limit: 100
  tool_calls_used: 35
  retry_limit: 2

next_action:
  role: worker
  target: P3.S1
```

### Regole

- Ogni modifica deve essere atomica.
- Ogni modifica deve indicare chi l'ha proposta.
- Lo stato deve essere validato contro uno schema.
- Gli agenti devono vedere solo le sezioni necessarie.
- Gli artefatti grandi devono essere salvati separatamente.
- Lo stato deve poter essere serializzato e ripreso.

---

## 9. Context Builder

Il Context Builder costruisce il prompt di ogni agente.

### Obiettivo

Fornire il minimo contesto sufficiente.

### Sorgenti possibili

- richiesta originale;
- classificazione;
- valutazione;
- piano globale;
- macrofase corrente;
- sottofase corrente;
- file rilevanti;
- risultati di tool;
- errori;
- test;
- decisioni del Supervisor;
- memoria persistente;
- checkpoint precedente.

### Regole di selezione

Il contesto deve essere:

- rilevante;
- recente;
- verificato;
- non ridondante;
- limitato al ruolo;
- privo di informazioni non necessarie.

### Esempio

Il Worker non deve ricevere:

- l'intera cronologia del Planner;
- tutte le fasi future;
- file non correlati;
- log completi di test già superati;
- discussioni precedenti non operative.

Deve ricevere:

- la sottofase corrente;
- i criteri di successo;
- i file coinvolti;
- le decisioni rilevanti;
- gli errori ancora aperti;
- gli strumenti autorizzati.

---

## 10. Gestione del piano

Il piano è un oggetto versionato.

### Operazioni consentite

- creare;
- leggere;
- aggiornare una fase;
- aggiungere una fase;
- rimuovere una fase non iniziata;
- cambiare dipendenze;
- marcare una fase come completata;
- invalidare una fase;
- ripristinare una versione precedente.

### Replanning

Il replanning deve avvenire quando:

- una dipendenza non esiste;
- una fase è tecnicamente impossibile;
- emergono requisiti nuovi;
- i test mostrano un errore architetturale;
- il costo supera il budget;
- il Supervisor rileva una strategia fallimentare;
- il risultato parziale modifica le condizioni iniziali.

Il replanning non deve avvenire per ogni piccolo errore locale.

---

## 11. Ciclo operativo di una sottofase

```text
1. Orchestrator seleziona la sottofase
2. Context Builder prepara il contesto
3. Worker esegue
4. Tool Router applica le azioni autorizzate
5. Artifact Store salva i risultati
6. Debugger verifica
7. Supervisor decide
8. State Manager aggiorna lo stato
9. Checkpoint Manager crea un checkpoint
10. Orchestrator passa alla sottofase successiva
```

### Esiti possibili

- `completed`
- `completed_with_warnings`
- `retry`
- `repair`
- `replan_phase`
- `replan_global`
- `blocked`
- `failed`
- `cancelled`

---

## 12. Gestione degli errori

### Categorie

#### Errori locali

Esempi:

- sintassi errata;
- test fallito;
- output malformato;
- tool call non valida;
- file mancante.

Azione:

- retry o repair locale.

#### Errori di fase

Esempi:

- sottofasi insufficienti;
- dipendenza non prevista;
- approccio tecnico errato.

Azione:

- richiamare il Phase Designer.

#### Errori globali

Esempi:

- obiettivo irrealizzabile;
- architettura incompatibile;
- requisito contraddittorio;
- budget insufficiente.

Azione:

- richiamare il Planner o fermare il task.

#### Errori del modello

Esempi:

- allucinazione;
- dichiarazione falsa;
- ripetizione;
- mancato rispetto dello schema;
- uso improprio degli strumenti.

Azione:

- validazione, retry controllato, cambio prompt o riduzione del contesto.

---

## 13. Retry e anti-loop

Ogni sottofase deve avere un limite di tentativi.

### Strategia suggerita

- primo fallimento: correzione locale;
- secondo fallimento: nuova strategia;
- terzo fallimento: revisione della fase;
- ulteriore fallimento: escalation al Supervisor o stop.

### Identificazione dei loop

Un loop è sospetto quando:

- lo stesso errore compare più volte;
- le patch si annullano a vicenda;
- il piano non avanza;
- il numero di token cresce senza nuovi artefatti;
- il modello ripete la stessa proposta;
- i test non cambiano;
- la stessa tool call fallisce ripetutamente.

L'Orchestrator deve calcolare un indicatore di progresso.

---

## 14. Criteri di successo

Ogni livello deve avere criteri separati.

### Task

- richiesta soddisfatta;
- vincoli rispettati;
- risultato verificato.

### Fase

- tutti gli output richiesti prodotti;
- dipendenze successive sbloccate;
- controlli della fase superati.

### Sottofase

- output osservabile;
- test associati superati;
- assenza di errori bloccanti.

### Sistema

- nessuna dichiarazione di successo senza evidenza;
- nessun tool inventato;
- nessuna modifica irreversibile non autorizzata;
- stato coerente;
- budget rispettato.

---

## 15. Budget e risorse

Il Budget Manager controlla:

- token;
- tempo;
- tool call;
- retry;
- RAM;
- CPU;
- GPU;
- spazio su disco;
- dimensione della KV cache;
- numero di artefatti;
- numero di checkpoint.

### Allocazione dinamica

Il budget dipende da:

- difficoltà;
- rischio;
- verificabilità;
- dimensione del progetto;
- qualità del modello;
- disponibilità hardware.

### Esempio

```yaml
budget:
  max_total_tokens: 32000
  max_planner_tokens: 3000
  max_phase_designer_tokens: 2500
  max_worker_tokens_per_subtask: 2000
  max_debugger_tokens: 1500
  max_supervisor_tokens: 1000
  max_retries_per_subtask: 2
```

Il contesto massimo disponibile non deve essere confuso con il budget da consumare.

---

## 16. KV cache e persistenza

La KV cache è un'ottimizzazione centrale, ma non deve sostituire lo stato strutturato.

### Utilizzi

- riuso del system prompt;
- riuso delle definizioni dei tool;
- riuso delle istruzioni di ruolo;
- ripresa delle sessioni;
- fork di una fase;
- rollback;
- riduzione del prefill.

### Checkpoint suggeriti

- dopo il Planner;
- dopo ogni macrofase;
- dopo ogni sottofase verificata;
- prima di una modifica rischiosa;
- prima di un replanning;
- prima di un retry con strategia differente.

---

## 17. Strumenti

Gli strumenti devono essere registrati in un catalogo.

### Metadati minimi

```yaml
name: read_file
description: "Legge un file"
risk: low
requires_approval: false
input_schema: {}
output_schema: {}
timeout_seconds: 10
reversible: true
```

### Categorie

- lettura;
- scrittura;
- ricerca;
- shell;
- test;
- Git;
- web;
- database;
- API;
- generazione artefatti;
- comunicazione esterna.

### Policy

- strumenti di lettura: generalmente consentiti;
- strumenti di scrittura: limitati allo scope;
- strumenti distruttivi: approvazione o sandbox;
- comunicazioni esterne: sempre esplicite;
- segreti: mai inseriti nel contesto del modello se evitabile;
- output dei tool: trattati come dati, non come istruzioni.

---

## 18. Formati strutturati

Ogni agente deve produrre output validabile.

Formati ammessi:

- JSON;
- YAML;
- schema tipizzato;
- blocchi XML ridotti;
- formati compatti proprietari.

### Regole

- validazione automatica;
- retry in caso di output malformato;
- campi obbligatori;
- enum limitati;
- nessun testo libero quando non necessario;
- separazione tra decisione e spiegazione.

---

## 19. Sicurezza operativa

Il sistema deve:

- usare sandbox quando possibile;
- limitare percorsi accessibili;
- impedire comandi arbitrari non autorizzati;
- filtrare input esterni;
- distinguere dati e istruzioni;
- conservare log delle azioni;
- richiedere conferma per operazioni irreversibili;
- mascherare segreti;
- limitare la rete;
- permettere rollback.

---

## 20. Osservabilità

Ogni esecuzione deve produrre log leggibili.

### Dati da registrare

- ruolo attivo;
- input sintetico;
- output;
- token;
- durata;
- tool call;
- esito;
- errori;
- decisioni;
- retry;
- checkpoint;
- stato prima e dopo;
- versione del piano.

### Vista operativa consigliata

```text
TASK 001
├── Classification: coding/high
├── Plan v3
├── P1 completed
├── P2 completed
├── P3 running
│   ├── P3.S1 failed
│   ├── P3.S1 retry passed
│   └── P3.S2 running
└── Budget: 58% remaining
```

---

## 21. Metriche

Le metriche devono misurare l'efficacia del sistema, non solo la velocità del modello.

### Qualità

- task completion rate;
- percentuale di task verificati;
- tasso di regressione;
- errori rilevati prima della fase finale;
- accuratezza del Classifier;
- accuratezza dell'Assessor;
- frequenza di replanning;
- successo al primo tentativo;
- qualità dei test generati.

### Efficienza

- token per task completato;
- token per sottofase;
- tempo per task;
- tool call per task;
- cache hit rate;
- numero medio di retry;
- dimensione media del contesto;
- rapporto tra token utili e token totali.

### Stabilità

- loop evitati;
- task interrotti correttamente;
- recovery da checkpoint;
- errori di stato;
- output strutturati invalidi;
- operazioni bloccate dalle policy.

---

## 22. Evaluator

Serve un ambiente di valutazione ripetibile.

### Dataset iniziale

Il benchmark deve includere:

- domande semplici;
- ricerca locale;
- modifica di file;
- bug fixing;
- generazione di test;
- refactoring;
- task multi-file;
- task con requisiti ambigui;
- task impossibili;
- task con informazioni mancanti;
- task che richiedono replanning.

### Confronti

Per ogni task confrontare:

1. modello piccolo senza pipeline;
2. modello piccolo con sola pianificazione;
3. modello piccolo con pipeline completa;
4. modello più grande come riferimento.

### Obiettivo

Dimostrare che la pipeline migliora:

- correttezza;
- verificabilità;
- affidabilità;
- capacità di completare task lunghi;
- uso delle risorse.

---

## 23. MVP

La prima versione deve essere limitata.

### Modello

- un solo modello;
- testo soltanto;
- una sola configurazione di quantizzazione.

### Task

- coding locale;
- ricerca in una codebase;
- modifica controllata;
- esecuzione test;
- correzione errori.

### Ruoli

- Classifier/Assessor combinato;
- Planner;
- Phase Designer;
- Worker;
- Debugger;
- Supervisor.

### Componenti

- Orchestrator;
- State Manager;
- Context Builder;
- Tool Router;
- Budget Manager;
- Checkpoint Manager;
- Logger.

### Tool minimi

- read file;
- search code;
- write patch;
- shell limitata;
- test runner;
- Git diff;
- Git status.

### Funzioni minime

- avvio task;
- pausa;
- ripresa;
- retry;
- rollback;
- replanning;
- report finale.

---

## 24. Roadmap

### Fase 1 — Pipeline lineare

- ruoli definiti;
- stato JSON;
- esecuzione sequenziale;
- nessuna persistenza KV avanzata;
- tool minimi;
- test manuali.

### Fase 2 — Verifica continua

- Debugger dopo ogni sottofase;
- retry controllati;
- checkpoint;
- rollback;
- metriche.

### Fase 3 — Contesto intelligente

- Context Builder;
- retrieval selettivo;
- compressione dello stato;
- cache dei prefissi;
- fork delle sessioni.

### Fase 4 — Adaptive routing

- pipeline dinamica;
- task semplici eseguiti direttamente;
- task complessi con pipeline completa;
- budget adattivo;
- scelta automatica del livello di verifica.

### Fase 5 — Multi-domain

- ricerca;
- documenti;
- amministrazione;
- automazioni;
- analisi dati;
- web;
- task multimodali.

---

## 25. Decisioni progettuali fondamentali

1. Un solo modello può ricoprire più ruoli.
2. Gli agenti sono configurazioni, non necessariamente processi separati.
3. Lo stato strutturato è più importante della cronologia.
4. Il piano globale deve essere sintetico.
5. Solo la fase corrente viene dettagliata.
6. Solo la sottofase corrente viene eseguita.
7. Ogni risultato importante deve essere verificato.
8. Il Supervisor può fermare o ripianificare.
9. L'Orchestrator deve essere deterministico.
10. I tool devono produrre evidenze.
11. Il contesto deve essere costruito per ruolo.
12. Il sistema deve poter fallire in modo esplicito.
13. Un risultato parziale corretto è preferibile a un successo inventato.
14. La pipeline deve ridursi automaticamente per i task semplici.
15. L'obiettivo non è massimizzare il ragionamento, ma minimizzare la superficie di errore.

---

## 26. Formula operativa

Il comportamento desiderato può essere riassunto così:

```text
Classifica il problema
→ valuta quanto è difficile
→ definisci il risultato verificabile
→ pianifica le macrofasi
→ dettaglia una sola fase
→ esegui una sola sottofase
→ verifica subito
→ correggi prima di proseguire
→ aggiorna lo stato
→ ripianifica quando necessario
→ termina solo con evidenze
```

---

## 27. Principio finale

> Il sistema non deve chiedere al modello piccolo di essere brillante. Deve costruire un ambiente nel quale, per produrre un risultato sbagliato, il modello sia costretto a superare più controlli indipendenti.

La “powerhouse” non è il modello.

La powerhouse è l'insieme formato da:

- decomposizione;
- specializzazione dei ruoli;
- memoria strutturata;
- contesto selettivo;
- strumenti;
- test;
- supervisione;
- checkpoint;
- orchestrazione;
- criteri di successo verificabili.

Il modello rimane piccolo.

Il sistema diventa grande.

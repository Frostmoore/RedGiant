# plan_planner_system.md — Il sistema di pianificazione: S/M/J + Control Plane

**Versione piano:** 1.0 (espansione ossessiva del seed v0 del 2026-08-02)
**Data:** 2026-08-03
**Piano padre:** [plan_red_giant.md](plan_red_giant.md) — IN PAUSA da ESITO F3; questo sistema è a sé stante e ha il suo ciclo di vita. Al completamento (PS7) il piano padre riprende da F3-bis.
**Atlante:** [codebase_reference.md](codebase_reference.md) — le firme di questo piano vi confluiscono fase per fase, verificate da `scripts/check_reference.py`.
**Stato:** 🟢 **PS4 completata** (2026-08-03, `v3.5.0`) — prossima azione: **PS5** (Engine: J + gate di esecuzione).

> **La regola che comanda questo documento:**
> *The Senior defines what must be achieved. The Mid decides how to decompose it and how
> correctness will be demonstrated. The Junior implements one proven contract at a time.
> Deterministic code governs every transition but makes no creative design decision.*
>
> Ogni volta che il control plane comincia a "scegliere come progettare", o M viene ridotto
> a riempitore di template, il sistema sta violando la propria architettura.

---

## Come si legge questo documento

Stesse regole del piano padre, che qui si richiamano per contratto:

1. **Le firme sono vincolanti** — direzione unica piano → codice; se una firma deve cambiare, si cambia PRIMA qui con la ragione scritta accanto.
2. **Ogni sottofase è un'unità chiusa**: obiettivo, motivazione, implementazione, casi limite, accettazione.
3. **Il piano è autosufficiente per costruzione**: un implementatore senza alcun altro contesto deve poter sviluppare leggendo solo questo documento + l'atlante per lo stato corrente della codebase + la specsheet per la visione.
4. Le decisioni vincolanti di questo sistema sono **PS-D1…PS-D10** (sotto); in caso di conflitto con le D1–D21 del piano padre, **le D del padre prevalgono** (questo sistema vive dentro Red Giant: D3 constrained decoding, D6 metriche CPU-only, D8 contesto piccolo, D11 A/B, D16 mai API esterne, D21 schemi piccoli valgono qui identiche).

**Origine del design (2026-08-02/03):** il verdetto D11 su F3 (baseline 9/10 vs Planner in-loop 2/10) più la diagnosi condivisa con l'utente: *il thrashing era dei GATE, non del proponente*. L'obiettivo dichiarato dall'utente: **il motore deve replicare la sua working pipeline** — `plan_*.md` → implementazione → gate di fine fase → `codebase_reference.md` — con gate più pesanti e contesti più piccoli, perché con un 2B il baricentro della qualità si sposta dal plan (debole) ai gate (forti). Ispirazioni esterne verificate: GitHub Spec Kit (constitution→specify→plan→tasks→implement), Kiro (requirements/design/tasks come unit of work), MetaGPT (catena di montaggio di artefatti strutturati validati), ricerca TDD+LLM (test come vincoli di processo: red-baseline, mutation probe; ai modelli piccoli serve contesto su *quali* test, non istruzioni su *come* fare TDD).

---

## PS-D — Decisioni vincolanti del sistema

### PS-D1 — Tre ruoli creativi, un control plane deterministico

- **Enunciato:** la tabella sotto è VINCOLANTE. Ciò che è "creativo" lo fa il modello (Gemma 4 E2B, constrained); ciò che è "deterministico" è codice Python senza alcuna chiamata LLM. Nessun componente cambia colonna senza revisione di questo piano.

| Componente | Responsabilità | Natura |
|---|---|---|
| **S — Senior Planner** | MacroPlan: goal, criteri globali C1..Cn, macrofasi con dipendenze e copertura | Creativa (1 chiamata per task) |
| **M — Phase Compiler** (4 passi: M1 analisi, M2 decomposizione, M3 design della verifica, M4 stesura test) | Blueprint della SOLA fase corrente + prove | Creativa (≤4+4 chiamate per fase, correttive incluse) |
| **J — Junior Worker** | Implementa UN work order provato alla volta | Creativa locale (il `Worker` esistente, invariato) |
| **Control Plane** | Valida, materializza, esegue i gate, registra, limita, decide le transizioni | Deterministica |
| **Gate Runner** | Esegue gli oracoli scelti da M (test runner, AST check, red-baseline) | Deterministica |
| **Ledger Builder** | Ricostruisce lo stato da DB + AST + esiti gate; proietta il contesto per fase | Deterministica |
| **Renderer** | DB → documenti Markdown greppabili | Deterministica |

- **Perché:** l'errore concettuale da evitare è "M è deterministico". M è il punto di massima intelligenza del sistema; il deterministico lo *restringe e controlla*, non lo sostituisce. E il simmetrico: il control plane non prende MAI decisioni di design (se serve una scelta, è un choice point PS-D8).
- **Violazione tipica:** "il gate corregge il blueprint da solo" (il gate BOCCIA, la correzione è una PhaseBlueprintPatch di M); "il template del prompt decide la struttura delle microfasi" (la decide M2 dentro i vincoli).

### PS-D2 — Prima gli artefatti, poi i prompt

- **Enunciato:** ogni oggetto scambiato tra ruoli è un artefatto tipizzato (Pydantic, §PS-A2), persistito e versionato in `ps_artifacts` (DDL §PS-A3), con: chi lo produce, chi può modificarlo, come si valida, quale versione sostituisce, cosa può leggerne il ruolo successivo. **Il DB è la fonte di verità; i Markdown renderizzati sono viste greppabili** in `data/tasks/<id>/plan/`. I prompt (card) si scrivono DOPO che gli schemi sono fissati.
- **Perché:** altrimenti si finisce a progettare l'architettura inseguendo ciò che il modello riesce casualmente a generare. È la stessa regola piano→codice del progetto, applicata al runtime.

### PS-D3 — M è una pipeline di compilazione, non una chiamata

- **Enunciato:** M sono 4 invocazioni dello stesso modello con 4 schemi PICCOLI distinti (D21), in sequenza fissa M1→M2→M3→M4, ciascuna validata deterministicamente prima della successiva, con UNA richiamata correttiva che CITA la regola violata (lezione F3: elencare i sintomi non basta), poi fallimento esplicito. Devono sembrare passaggi di compilazione, non agenti che discutono.
- **Violazione tipica:** "già che c'è, M2 scriva anche i test" — il mega-oggetto è esattamente ciò che ha ucciso il Designer di F3 (troncamenti a 2048, sottofasi-analisi artificiali).

### PS-D4 — Work contract ≠ Proof contract, entrambi immutabili per J

- **Enunciato:** ogni microfase ha due blocchi distinti: il **work contract** (cosa modificare, perimetro, firme, input, output, invarianti) e il **proof contract** (comportamento da dimostrare, test/oracolo, comando, stato atteso prima/dopo, evidenza necessaria). J li riceve entrambi e **non può modificarli** — né i test (che sono già materializzati e qualificati prima che J parta).
- **Perché:** perimetro=verifica (F3.2-REVISIONE) portato a sistema: J non è mai giudicato da oracoli fuori dal suo contratto, e non può ammorbidire l'oracolo che lo giudica.

### PS-D5 — Oracle Qualification Gate: si qualifica l'oracolo, non solo il codice

- **Enunciato:** nessun work order parte se le sue prove non sono QUALIFICATE dal gate deterministico (§PS4.2): test raccolto dal runner, **red-baseline** (un test `new_behavior` DEVE fallire prima dell'implementazione; un `characterization` DEVE passare sulla baseline), asserzioni reali presenti (AST), riferimento reale al simbolo/file bersaglio, dentro lo scope della microfase, comando eseguibile, ogni criterio coperto da ≥1 obbligo. Mutation probe leggero opzionale (config) sui test marcati critici.
- **Perché:** il failure mode peggiore dell'intero design è M che scrive test deboli e J che li soddisfa perfettamente. La ricerca TDD+LLM conferma: i test vanno trattati come vincoli di processo *verificati meccanicamente*, non come suggerimenti; e la qualificazione la fa il codice, non il modello.

### PS-D6 — Correzione = patch dell'artefatto, mai rigenerazione

- **Enunciato:** quando una validazione o un gate bocciano, M riceve la violazione e restituisce una **patch tipizzata** (`BlueprintPatch`) che tocca SOLO la parte violata; il control plane la applica e rivalida. Rigenerare l'artefatto intero è vietato (salvo patch impossibile: 1 sola rigenerazione, poi fallimento esplicito).
- **Perché:** meno token, meno regressioni, niente cambiamenti cosmetici che distruggono parti già buone; e la KV cache ringrazia (il contesto della correzione è un delta, non un ricominciare).

### PS-D7 — Il ledger è preparato per M, non buttato nel prompt

- **Enunciato:** M non riceve mai l'atlante intero né lo storico grezzo. Il Ledger Builder costruisce deterministicamente il `TaskLedger` (da DB, esiti gate, AST dei file toccati) e per ogni fase produce una **Phase Context Projection** budgetata (componenti rilevanti, firme reali, test esistenti, decisioni applicabili, artefatti delle fasi precedenti, failure già visti, criteri della macrofase). Il ledger completo resta ricercabile via tool (`read_file`/`search_code` su `data/tasks/<id>/plan/ledger.md`); il prompt contiene la proiezione minima + gli ID da approfondire.
- **Perché:** è il principio della pipeline umana — la memoria vive nei documenti, il ruolo corrente riceve solo ciò che gli serve — ed è D8/D18: contesto piccolo, prefisso stabile, pagare una volta.

### PS-D8 — Choice point espliciti, mai arbitrio nascosto

- **Enunciato:** ogni decisione progettuale di M appare in `PhaseAnalysis.decisions` (decisione, alternative scartate, vincolo determinante, conseguenze). Quando né codebase né piano determinano una scelta, M emette `decision_required` (domanda, opzioni con conseguenze, raccomandazione): il control plane la instrada sul canale clarification ESISTENTE (tabella `approvals`, kind `clarification`, GUI F2.3) — l'utente risponde, la risposta diventa una decisione registrata. M non inventa mai in silenzio.
- **Perché:** il Junior che riceve contratti "precisi" basati su decisioni invisibili non può correggerle senza riscrivere tutto; e l'utente ha già un canale di consenso rodato — si riusa, non si duplica.
- **Policy per run non presidiate (aggiunta PS5, dal pilota):** nell'eval (`RG_PLANSYS_AUTODECIDE=recommended`) il choice point si auto-decide sulla RACCOMANDATA di M1, registrata in `decisions` (actor `policy:autodecide`) e nel canale approvals come clarification già risposta — mai silenziosa, max 2 per fase poi blocked vero. È il "default versionato" previsto da questa decisione.

### PS-D9 — D11 vale anche qui: A/B su task multi-fase, con ablation

- **Enunciato:** il sistema resta `enabled=false` finché non batte la baseline (piano ingenuo, 9/10 su T001–T010) sul SUO terreno: la serie **T040+**, task progettati per NON stare in una singola sessione Worker. L'Evaluator misura sistema completo E ablation per componente (§PS6). Metriche: le 5 cardine + token di governance, task duplicati, test deboli respinti dal gate, retry fotocopia bloccati, criteri globali coperti.
- **Perché:** il primo Planner è stato misurato su task per cui pianificare era strutturalmente inutile — errore di disegno sperimentale da non ripetere. E l'ablation dice QUALE livello di astrazione produce valore, non solo "il tutto insieme".

### PS-D10 — Granularità delle microfasi: criteri osservabili, non regole rigide

- **Enunciato:** una microfase è abbastanza piccola quando TUTTE: sta in una sessione Worker (`worker.max_steps`); ha ownership chiara e unica dei file; non richiede una nuova decisione architetturale; possiede una verifica locale qualificabile; non dipende da artefatti futuri; ha output singolo o fortemente coeso; il suo fallimento restituisce informazione utile. "Una microfase per classe/metodo" è un orientamento: una classe banale può essere una microfase, un metodo complesso può richiederne tre. Il validatore di M2 applica i criteri meccanici (ownership, dipendenze, tetto ≤6); il resto è responsabilità creativa di M2 dentro la card.

---

## PS-A. Architettura di riferimento

### PS-A1. Albero dei file (tutto nuovo salvo dove indicato)

```text
redgiant/plansys/
├── __init__.py                PS0
├── artifacts.py               PS0 — tutti gli schemi Pydantic degli artefatti
├── render.py                  PS0 — renderer deterministico DB → Markdown greppabile
├── ledger.py                  PS1 — TaskLedger, build deterministico, proiezioni per fase
├── gates.py                   PS2+ — tutti i gate deterministici (entry, oracle, micro, synthesis, coverage, retry)
├── roles.py                   PS2/PS3/PS4 — SeniorPlanner, PhaseAnalyst, WorkDecomposer,
│                                             VerificationDesigner, TestAuthor + validatori
├── compiler.py                PS3/PS4 — PhaseCompiler (pipeline M1→M4 con patch correttive)
└── engine.py                  PS5 — PlanSysEngine (il driver: S → fasi → M → gate → J → ledger)
redgiant/prompts/roles/
├── senior_planner.md          PS2
├── phase_analyst.md           PS3
├── work_decomposer.md         PS3
├── verification_designer.md   PS4
└── test_author.md             PS4
redgiant/eval/tasks/
├── T040_multiphase_package/   PS6 — pacchetto 3 moduli + CLI, test forniti (multi-sessione)
├── T041_no_tests_given/       PS6 — feature SENZA test forniti: M4 li scrive, il giudice esterno decide
└── T042_brownfield_extend/    PS6 — estensione di codebase esistente ~15 file (ledger obbligatorio)
tests/unit/
├── test_plansys_artifacts.py  PS0
├── test_plansys_ledger.py     PS1
├── test_plansys_gates.py      PS2/PS4/PS5
└── test_plansys_compiler.py   PS3/PS4
data/tasks/<id>/plan/          runtime — viste renderizzate: macro_plan.md, P<k>.blueprint.md, ledger.md
```

Riuso (INVARIATI): `roles/worker.py` (J), `core/verify.py`, `tools/*` (incl. syntax gate e `run_tests`), `llm/client.py`, `prompts/assemble.py` (S1→S7), `state/store.py` (+ metodi nuovi sotto), GUI F2 per approvals/clarifications. L'`Orchestrator` del piano padre resta com'è (gate D11 incluso): `PlanSysEngine` è un driver PARALLELO, selezionato via config.

### PS-A2. Gli artefatti (`redgiant/plansys/artifacts.py`) — firme vincolanti

Tutti con `model_config = ConfigDict(extra="forbid")`. Limiti = contratto di grammatica (D21).

```python
# ── S: il MacroPlan ──────────────────────────────────────────────────────────
class Criterion(BaseModel):
    id: str                                  # "C1".."C8", stabile
    text: str = Field(max_length=200)        # osservabile, mai "il codice è buono"
class MacroPhase(BaseModel):
    id: str                                  # "P1".."P6", stabile
    title: str = Field(max_length=80)
    intent: str = Field(max_length=300)      # COSA deve ottenere, mai COME
    depends_on: list[str] = Field(max_length=5)
    covers: list[str] = Field(min_length=1, max_length=8)   # id di Criterion (matrice di copertura)
class MacroPlan(BaseModel):
    goal: str = Field(max_length=300)
    criteria: list[Criterion] = Field(min_length=1, max_length=8)
    phases: list[MacroPhase] = Field(min_length=1, max_length=6)

# ── M1: analisi di fase ──────────────────────────────────────────────────────
class DesignDecision(BaseModel):
    id: str                                  # "P2.D1"
    decision: str = Field(max_length=200)
    alternatives: list[str] = Field(max_length=3)
    constraint: str = Field(max_length=200)  # il vincolo che l'ha determinata
class ChoicePoint(BaseModel):
    question: str = Field(max_length=200)
    options: list[str] = Field(min_length=2, max_length=3)
    recommended: str = Field(max_length=80)
    reason: str = Field(max_length=200)
class PhaseAnalysis(BaseModel):
    phase_id: str
    objective: str = Field(max_length=300)
    involved: list[str] = Field(max_length=10)      # file/simboli ESISTENTI coinvolti (dal ledger, mai inventati)
    artifacts: list[str] = Field(max_length=10)     # file da creare/modificare
    decisions: list[DesignDecision] = Field(max_length=4)
    risks: list[str] = Field(max_length=4)
    decision_required: ChoicePoint | None = None    # PS-D8: se presente, il control plane si ferma e chiede

# ── M2: decomposizione ───────────────────────────────────────────────────────
class WorkContract(BaseModel):
    goal: str = Field(max_length=300)
    boundary: str = Field(max_length=300)           # cosa NON fa (appartiene ad altre micro)
    files_owned: list[str] = Field(min_length=1, max_length=4)   # ownership ESCLUSIVA nella fase
    signatures: list[str] = Field(max_length=6)     # firme proposte, verbatim dal ledger dove esistenti
    inputs: list[str] = Field(max_length=6)
    outputs: list[str] = Field(max_length=4)
class MicroPhase(BaseModel):
    id: str                                  # "P2.S1"
    title: str = Field(max_length=80)
    work: WorkContract
    proves: list[str] = Field(max_length=8)  # id di Criterion a cui contribuisce
                                             # (REVISIONE fast #5: 4→8 — con la coverage_chain
                                             # una micro sola deve poter provare tutti i criteri
                                             # di una fase, che possono essere fino a 8)
class PhaseBlueprint(BaseModel):
    phase_id: str
    micro: list[MicroPhase] = Field(min_length=1, max_length=6)

# ── M3: design della verifica ────────────────────────────────────────────────
class ProofObligation(BaseModel):
    id: str                                  # "P2.S1.O1"
    micro_id: str
    kind: Literal["new_behavior", "characterization"]
    behavior: str = Field(max_length=300)    # il comportamento da dimostrare, in parole
    test_file: str                           # path del test che lo dimostra
    test_name: str                           # nome esatto della funzione di test
    cmd_id: str                              # comando registrato (run_tests)
class VerificationBlueprint(BaseModel):
    phase_id: str
    obligations: list[ProofObligation] = Field(min_length=1, max_length=12)
    synthesis_cmds: list[str] = Field(min_length=1, max_length=3)   # cmd_id del gate di sintesi fase

# ── M4: stesura test ─────────────────────────────────────────────────────────
class TestArtifact(BaseModel):
    path: str
    content: str                             # materializzato dal control plane (syntax gate incluso), NON da J
class TestBundle(BaseModel):
    phase_id: str
    artifacts: list[TestArtifact] = Field(min_length=1, max_length=8)

# ── Correzioni (PS-D6) ───────────────────────────────────────────────────────
class PatchOp(BaseModel):
    op: Literal["replace", "add", "remove"]
    target: str                              # id dell'elemento (micro, obligation, decision)
    payload_json: str                        # il NUOVO elemento serializzato (vuoto per remove).
                                             # REVISIONE PS4.3: niente max_length — maxLength=4000
                                             # produce una ripetizione GBNF {0,4000} che llama-server
                                             # rifiuta con 400; il tetto vero e' il budget di generazione
class BlueprintPatch(BaseModel):
    phase_id: str
    ops: list[PatchOp] = Field(min_length=1, max_length=6)

# ── Gate (prodotti dal control plane, mai dal modello) ───────────────────────
class GateReport(BaseModel):
    gate: Literal["macro_validation", "phase_entry", "oracle_qualification",
                  "micro", "phase_synthesis", "plan_coverage", "retry"]
    target: str
    ok: bool
    checks: list[CheckResult]                # riuso di core.verify.CheckResult
```

**Ownership degli artefatti** (chi produce / chi può modificare): `MacroPlan` S / solo S via replan versionato (fuori slice v1) · `PhaseAnalysis` M1 / M via patch · `PhaseBlueprint` M2 / M via patch · `VerificationBlueprint` M3 / M via patch · `TestBundle` M4 / M via patch PRIMA della qualificazione, POI immutabile · `GateReport` control plane / nessuno · `TaskLedger` Ledger Builder / nessuno.

### PS-A3. Persistenza (migrazione additiva in `state/store.py::_DDL`)

```sql
CREATE TABLE IF NOT EXISTS ps_artifacts (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('macro_plan','phase_analysis','phase_blueprint',
                                           'verification_blueprint','test_bundle','ledger_snapshot')),
  ref        TEXT NOT NULL,                 -- '' per macro_plan, 'P2' per artefatti di fase
  version    INTEGER NOT NULL,              -- 1+; la patch applicata produce version+1
  actor      TEXT NOT NULL,                 -- 'senior' | 'phase_compiler' | 'ledger'
  json       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (task_id, kind, ref, version)
);
CREATE TABLE IF NOT EXISTS ps_gates (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  gate       TEXT NOT NULL,
  target     TEXT NOT NULL,
  ok         INTEGER NOT NULL,
  checks     TEXT NOT NULL,                 -- JSON list[CheckResult]
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ps_artifacts ON ps_artifacts(task_id, kind, ref);
CREATE INDEX IF NOT EXISTS idx_ps_gates     ON ps_gates(task_id, gate);
```

Metodi nuovi di `StateStore` (stesse regole: transazioni, actor obbligatorio, mai SQL fuori da store.py):

```python
def save_ps_artifact(self, task_id: str, *, kind: str, ref: str, payload_json: str, actor: str) -> int   # ritorna la version assegnata
def load_ps_artifact(self, task_id: str, kind: str, ref: str = "", version: int | None = None) -> dict   # ultima se version=None; KeyError se assente
def list_ps_artifacts(self, task_id: str, kind: str | None = None) -> list[dict]
def log_ps_gate(self, task_id: str, *, gate: str, target: str, ok: bool, checks_json: str) -> None
def ps_gate_history(self, task_id: str, gate: str | None = None) -> list[dict]
```

### PS-A4. Configurazione (sezione nuova in `config/default.toml` + `_KNOWN_KEYS`)

```toml
[plansys]
enabled = false                  # PS-D9: si accende solo per A/B espliciti finché non vince
max_phases = 6
max_micro_per_phase = 6
projection_max_tokens = 2500     # budget della Phase Context Projection (dentro D8)
m_pass_max_tokens = 1536         # M1/M2/M3 (schemi piccoli; 1024 troncava M2 con
                                 # piu' microfasi — smoke PS4.3)
test_author_max_tokens = 3072    # M4 scrive file interi (2048 troncava al primo
                                 # smoke PS4.3: il JSON con newline escapati gonfia;
                                 # ~86s di gen a 35.8 tok/s, accettabile una volta a fase)
mutation_probe = false           # PS-D5: probe leggero opzionale (costa run di test extra)
```

`Config` guadagna: `plansys_enabled: bool` + dataclass `PlansysCfg(max_phases, max_micro_per_phase, projection_max_tokens, m_pass_max_tokens, test_author_max_tokens, mutation_probe)` come campo `plansys: PlansysCfg`.

### PS-A5. Il flusso end-to-end (la vertical slice, normativa)

```text
richiesta larga (rg eval --plansys / engine diretto)
  → [S] MacroPlan (1 chiamata) → macro_validation gate (copertura C, acicliche, id, tetti)
  → render macro_plan.md
  → loop macrofasi eleggibili (dipendenze completate, ordine piano):
      → phase_entry gate: criteri della fase GIÀ verdi? → fase completata a costo zero
      → Ledger Builder: build + Phase Context Projection (budget PS-A4)
      → [M1] PhaseAnalysis  → validazione (simboli esistenti nel ledger, decisioni esplicite)
        └─ decision_required? → clarification (canale F2.3), attesa risposta, ri-M1 col verdetto
      → [M2] PhaseBlueprint → validazione (ownership esclusiva, tetti, PS-D10 meccanici)
      → [M3] VerificationBlueprint → validazione (ogni micro ≥1 obbligo, cmd noti, kind coerenti)
      → [M4] TestBundle → materializzazione dal control plane (Scope + syntax gate)
      → ORACLE QUALIFICATION GATE (PS-D5) — bocciatura → violazioni a M → BlueprintPatch → riqualifica
      → render P<k>.blueprint.md
      → loop microfasi in ordine:
          → work order = work contract + proof contract (immutabili) → [J] Worker.run
          → micro gate: verify_subtask + obblighi della micro TUTTI verdi (after=green)
          → fail → retry gate: il retry DEVE differire (istruzioni emendate dai check falliti;
                   fotocopia = vietata) entro max_retries → micro failed → fase failed → stop onesto
                   (replanning di macrofase = fuori slice v1, registrato come debito PS8)
          → ledger update (deterministico) dopo ogni micro chiusa
      → phase_synthesis gate: synthesis_cmds tutti verdi + obblighi di fase ri-eseguiti
      → render ledger.md aggiornato
  → plan_coverage gate: ogni Criterion coperto da ≥1 obbligo provato in fasi completate
  → finalize (completed/partial/failed con evidenze — semantica identica al padre)
```

Costi per costruzione: S=1 chiamata per task; M≤8 per fase (4 passi + ≤4 correttive/patch); J=come oggi; **tutti i gate e il ledger = 0 token**.

---

## Rituale di fine fase (di QUESTO piano — prima della sezione di tracking)

Identico nella sostanza al piano padre, adattato nei riferimenti. Al completamento dell'ultima sottofase 🔎 di ogni PS-fase, nell'ordine, ognuno bloccante per il successivo:

1. **Aggiornare questo file**: checkbox della fase e sottofasi; campo **Stato** in testa; se una firma è cambiata in corso d'opera, la modifica è già QUI con la ragione (direzione piano → codice).
2. **Aggiornare `codebase_reference.md`**: sezione dedicata `redgiant/plansys/` (classi, firme complete, DDL, config, test con cosa dimostra ciascuno), trappole nuove in §9 con causa tecnica, debito in §10.
3. **README.md**: obbligatorio a PS6 (i numeri dell'A/B, aggiornamento della finding F8) e PS7 (integrazione); facoltativo prima SOLO se una scoperta merita il catalogo findings.
4. **Verifica meccanica:** `python scripts/check_reference.py` — exit ≠ 0 → il rituale si ferma.
5. **Messaggio ESTREMAMENTE DETTAGLIATO** all'utente: stato, checkbox, commento generale + di fase, numeri se prodotti.
6. **Commit e push su branch versionato, ENTRAMBE le remote.** Tabella versioni:

| Evento | Versione | Entità |
|---|---|---|
| Questo piano (v1.0) | `v3.0.1` | piccola (documentale) |
| Fine PS0 | `v3.1.0` | media |
| Fine PS1 | `v3.2.0` | media |
| Fine PS2 | `v3.3.0` | media |
| Fine PS3 | `v3.4.0` | media |
| Fine PS4 | `v3.5.0` | media |
| Fine PS5 (slice completa) | `v3.6.0` | media |
| Fine PS6 (A/B + verdetto) | `v3.7.0` | media |
| Fine PS7 (integrazione) | `v4.0.0` | **grande → merge in `main`** |

⚠️ **Nota di riconciliazione col piano padre:** la tabella del padre assegnava `v3.1.0` a F3-bis e `v4.0.0` a F4. Alla chiusura di PS7 la tabella del padre va aggiornata (F3-bis → `v4.1.0`, F4 → `v5.0.0`, e a scalare) con questa nota come ragione. I commit intermedi durante una PS-fase: `+0.0.1` piccoli / `+0.1.0` medi, come sempre; `redgiant/__init__.py::__version__` allineata nello stesso commit.

---

## Mappa delle fasi e gate d'ingresso

| Fase | Titolo | Dipende da | Gate d'ingresso |
|---|---|---|---|
| PS0 | Artefatti, persistenza, renderer, config | — | questo piano committato |
| PS1 | Ledger Builder + proiezioni | PS0 | schemi e DDL verdi (unit) |
| PS2 | Senior Planner + macro validation | PS0 | renderer funzionante |
| PS3 | Phase Compiler M1–M2 + patch | PS1, PS2 | proiezione di fase disponibile |
| PS4 | Verification Compiler M3–M4 + Oracle Qualification | PS3 | blueprint validato su fixture |
| PS5 | Engine: J + gate di esecuzione (vertical slice) | PS4 | test qualificati su fixture |
| PS6 | Evaluator: T040+ e A/B con ablation | PS5 | slice verde su 1 task pilota |
| PS7 | Integrazione in Red Giant | PS6 | verdetto D11 favorevole (o decisione utente) |

---

## Fase PS0 — Artefatti, persistenza, renderer, config → `v3.1.0`

🎯 **Scope:** tutto ciò che è dato-e-contratto, zero intelligenza: schemi PS-A2, DDL PS-A3, config PS-A4, renderer Markdown.
🧭 **Perché prima:** PS-D2 — prima gli artefatti, poi i prompt. Ogni fase successiva importa questi tipi; la loro forma È l'architettura.

#### PS0.1 — Schemi degli artefatti

- [x] 🤖 **Obiettivo:** `redgiant/plansys/artifacts.py` esattamente come PS-A2.
- **Implementazione:** copiare le firme di PS-A2 (sono normative); `CheckResult` importato da `redgiant.core.verify`. Ogni classe con docstring di una riga: chi la produce, chi la modifica.
- **Accettazione:** unit `test_plansys_artifacts.py`: round-trip JSON di ogni artefatto; `extra="forbid"` respinge campi ignoti; i tetti (`max_length`/`min_length`) mordono; `BlueprintPatch` con op `remove` e payload vuoto valida.

#### PS0.2 — Persistenza

- [x] 🤖 **Obiettivo:** tabelle `ps_artifacts`/`ps_gates` + i 5 metodi di `StateStore` (PS-A3).
- **Implementazione:** DDL additivo in `_DDL`; `save_ps_artifact` calcola `version = MAX(version)+1` per (task, kind, ref) in transazione; `load_ps_artifact` senza version → l'ultima.
- **Accettazione:** unit: versioni monotone; UNIQUE violata impossibile per costruzione; `load` di artefatto assente → `KeyError` col riferimento.

#### PS0.3 — Renderer deterministico

- [x] 🤖 **Obiettivo:** `redgiant/plansys/render.py` — DB → Markdown greppabile, struttura FISSA.
- **Implementazione:**
  ```python
  def render_macro_plan(plan: MacroPlan) -> str
  def render_blueprint(bp: PhaseBlueprint, vbp: VerificationBlueprint | None,
                       analysis: PhaseAnalysis | None) -> str
  def write_plan_doc(tasks_dir: Path, task_id: str, name: str, content: str) -> Path
      # data/tasks/<id>/plan/<name>.md, scrittura atomica (tmp+replace), LF
  ```
  Formato normativo (greppabile da un modello piccino E da rg): intestazioni `## P<k> — <titolo>`, `### P<k>.S<n> — <titolo>`, blocchi etichettati `**Work:**` / `**Proof:**` / `**Decisions:**`, criteri come checkbox `- [ ] C<i>: <testo>` spuntati dai gate. MAI contenuto libero del modello nelle intestazioni (gli id sono la struttura).
- **Accettazione:** unit: render di fixture → contiene le intestazioni attese; due render dello stesso artefatto → byte-identici (determinismo); `rg "P2.S1"` sul file trova la microfase.

#### PS0.4 — Config

- [x] 🤖 **Obiettivo:** sezione `[plansys]` (PS-A4) in `config.py` (+`_KNOWN_KEYS`) e `default.toml`.
- **Accettazione:** `Config.load("dev-fast")` espone `plansys.enabled is False` e i default; chiave ignota in `[plansys]` → ValueError.

#### PS0.5 — 🔎 Verifica di fase

- [x] Unit di PS0 tutti verdi; `check_reference.py` verde con le firme nuove documentate nell'atlante (sezione plansys creata); nessun modulo di plansys importa `llm` (la fase è a zero intelligenza per costruzione — un import di `LlamaClient` qui è una violazione di PS-D1). *(fatto: 60/60 unit, atlante verde, plansys senza import llm)*

**Rituale** → `v3.1.0`.

---

## Fase PS1 — Ledger Builder + proiezioni → `v3.2.0`

🎯 **Scope:** la memoria esterna deterministica: `TaskLedger`, build da DB+AST+gate, proiezione budgetata per fase.
🧭 **Perché ora:** M (PS3) senza ledger riceverebbe o troppo o niente — è il prerequisito del contesto piccolo.

#### PS1.1 — TaskLedger e build

- [x] 🤖 **Obiettivo:** `redgiant/plansys/ledger.py`: *(fatto; aggiunta in corso d'opera: `StateStore.list_decisions(task_id) -> list[dict]` — lettura pura richiesta dal builder, registrata in atlante)*
  ```python
  class LedgerEntry(BaseModel):
      kind: Literal["signature", "test", "artifact", "decision", "failure", "fact"]
      ref: str            # path/simbolo/id
      text: str = Field(max_length=300)
  class TaskLedger(BaseModel):
      task_id: str
      entries: list[LedgerEntry]
  def build_ledger(store: StateStore, scope: Scope, task_id: str) -> TaskLedger
  def render_ledger(ledger: TaskLedger) -> str        # per data/tasks/<id>/plan/ledger.md
  ```
  `build_ledger`, tutto deterministico: firme reali via AST (riuso di `scripts/check_reference.py::extract_signatures` — spostare la funzione in un modulo importabile `redgiant/plansys/astscan.py` e far importare lo script da lì, SENZA cambiarne il comportamento) sui file dentro lo Scope toccati dal task (da `tool_calls`) + su `inputs` dei contratti; test esistenti (`discover_test_commands` + collect dei file `test_*`); decisioni da `decisions` e da `PhaseAnalysis.decisions` persistite; fallimenti dai `ps_gates` non-ok (firma corta); artefatti dalle micro completate.
- **Casi limite:** file cancellato dopo l'uso → entry `fact` "deleted"; AST che non parsa → entry `failure` col path (mai crash).
- **Accettazione:** unit con repo fixture: il ledger contiene le firme vere (confronto con AST diretto); ri-build su stato invariato → identico (determinismo).

#### PS1.2 — Phase Context Projection

- [x] 🤖 **Obiettivo:** la proiezione minima per M (PS-D7):
  ```python
  def project_for_phase(ledger: TaskLedger, plan: MacroPlan, phase_id: str,
                        max_tokens: int, count: Callable[[str], int]) -> str
  ```
  Ordine di riempimento a budget (normativo): (1) criteri coperti dalla fase (verbatim); (2) intent e vincoli della fase; (3) firme/test degli elementi citati da fasi precedenti completate; (4) decisioni applicabili; (5) failure pertinenti; (6) il resto per rilevanza (match sui termini dell'intent), troncando CON dichiarazione (`[LEDGER TRUNCATED — search ledger.md via tools for more]`).
- **Accettazione:** unit: la proiezione sta nel budget (conteggio vero via callable); gli obbligatori (1)(2) presenti anche con budget minimo; oltre-budget → gli opzionali cadono, mai gli obbligatori.

#### PS1.3 — 🔎 Verifica di fase

- [x] Ledger e proiezione verdi su fixture; `ledger.md` renderizzato e greppabile; determinismo dimostrato (due build identiche); atlante aggiornato. *(63/63 unit; astscan unico estrattore, check_reference importa da lì)*

**Rituale** → `v3.2.0`.

---

## Fase PS2 — Senior Planner + macro validation → `v3.3.0`

🎯 **Scope:** S scrive il MacroPlan UNA volta; il control plane lo valida e lo renderizza; poi S esce di scena.

#### PS2.1 — Card e ruolo

- [x] 🤖 **Obiettivo:** `redgiant/prompts/roles/senior_planner.md` + in `roles.py`:
  ```python
  class SeniorPlanner(Role):
      name = "senior_planner"; output_model = MacroPlan
      def run(self, ctx: RoleContext, *, max_tokens: int = 1024) -> MacroPlan
  ```
  Card (EN, regole — lezione F6 del README: ogni regola del validatore ha la sua frase): phases describe OUTCOMES, never operations; criteria are observable facts with stable ids C1..; every phase covers ≥1 criterion; depends_on lists ONLY phase ids from THIS plan, root = []; no ceremony phases; copy identifiers verbatim from CONTEXT, never invent (contract anchoring: la proiezione iniziale contiene il listato repo + estratti dei test se esistono).
- **Accettazione:** su fixture di richiesta larga, output valido alle validazioni sotto in ≤2 chiamate (1 correttiva ammessa). *(REVISIONE fast #4: correttive del Senior 1→2 — la coverage è l'errore più meccanicamente correggibile e una sola richiamata perdeva task interi sulle code di instabilità; costo marginale solo quando serve)*

#### PS2.2 — Macro validation gate

- [x] 🤖 **Obiettivo:** in `gates.py`:
  ```python
  def macro_validation_gate(plan: MacroPlan) -> GateReport
  ```
  Check (tutti, sempre): id fase/criterio univoci e nel formato; dipendenze esistenti, acicliche (riuso della DFS di `roles/planner.py::validate_plan_logic` — estrarla in helper condiviso), root presente; **copertura totale: ogni Criterion coperto da ≥1 fase** (la matrice PS-D9/13); sentinelli riparati con la `normalize_plan` esistente (estesa ai MacroPhase). Violazione → UNA richiamata correttiva che cita la regola, poi fallimento esplicito.
- **Accettazione:** unit: piano con C2 scoperto → bocciato col check giusto; auto-dipendenza riparata; ciclo → bocciato.

#### PS2.3 — 🔎 Verifica di fase

- [x] S su 3 richieste-fixture produce MacroPlan validi e renderizzati (`macro_plan.md` greppabile); gate coperto da unit; zero chiamate LLM fuori da `SeniorPlanner.run` (grep su plansys: `llm.complete` solo in roles.py/compiler.py). *(smoke live severino-sim 3/3: 34s/12s/18s, copertura totale sempre; 67/67 unit)*

**Rituale** → `v3.3.0`.

---

## Fase PS3 — Phase Compiler: M1 analisi + M2 decomposizione → `v3.4.0`

🎯 **Scope:** la prima metà della compilazione di fase: analisi con decisioni esplicite, decomposizione con ownership, correzioni a patch.

#### PS3.1 — M1 Phase Analyst

- [x] 🤖 **Obiettivo:** card `phase_analyst.md` + `PhaseAnalyst(Role)` (`output_model = PhaseAnalysis`), input = proiezione di fase (S6) + MacroPhase corrente. *(firma estesa in implementazione: `validate_analysis(analysis, projection, phase_id)` — il check di coerenza dell'id sta nel validatore, non nel compiler; ragione: tutti i check nello stesso posto)*
  Card: analyse ONLY this phase; `involved` MUST quote identifiers that appear in CONTEXT (ledger projection) — never invent; every design choice goes in `decisions` with the constraint that forced it; if the codebase and plan do not determine a choice, emit `decision_required` instead of choosing silently.
- **Validazione deterministica** (`gates.py::validate_analysis(analysis, projection) -> list[str]`): `involved` ⊆ simboli/path presenti nella proiezione o nel ledger (anti-invenzione meccanica); `decisions` senza duplicati; `decision_required` → il compiler si ferma (PS-D8) e scrive la clarification.
- **Accettazione:** su fixture con simbolo inventato → bocciato con la voce esatta; con choice point → riga `approvals` kind clarification creata e compilazione sospesa.

#### PS3.2 — M2 Work Decomposer

- [x] 🤖 **Obiettivo:** card `work_decomposer.md` + `WorkDecomposer(Role)` (`output_model = PhaseBlueprint`), input = proiezione + PhaseAnalysis validata. *(firma estesa: `validate_blueprint(bp, analysis, covers)` — il check `proves ⊆ covers` richiede i criteri della fase)*
  Card: one micro-phase per coherent artifact (PS-D10 come guida, non regola); each micro OWNS its files exclusively; boundary states what it does NOT do; signatures verbatim from analysis/ledger; ≤6 micro.
- **Validazione** (`validate_blueprint(bp, analysis) -> list[str]`): ownership dei file ESCLUSIVA tra micro della fase (il difetto "fasi ridondanti" di F3, reso impossibile); ogni `files_owned` ⊆ `analysis.artifacts ∪ analysis.involved`; id `P<k>.S<n>` ordinati; tetti; ogni micro `proves` ⊆ criteri coperti dalla fase.
- **Accettazione:** fixture con ownership duplicata → bocciata; blueprint valido → renderizzato.

#### PS3.3 — PhaseCompiler (prima metà) + patch

- [x] 🤖 **Obiettivo:** `compiler.py`: *(in corso d'opera: aggiunto `projection(task_id, plan, phase) -> str` — il compiler costruisce da sé ledger+proiezione, l'engine chiama solo compile; e il ledger ora include il listato repo come fact, max 40: a task fresco è l'unico ancoraggio per gli involved)*
  ```python
  class PhaseCompiler:
      def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient,
                   assembler: PromptAssembler, router: ToolRouter, scope: Scope) -> None
      def compile_phase(self, task_id: str, plan: MacroPlan, phase: MacroPhase,
                        log: TaskLog) -> tuple[PhaseBlueprint, VerificationBlueprint, TestBundle]
      def _request_patch(self, task_id: str, role: Role, violations: list[str],
                        current_json: str, log: TaskLog) -> BlueprintPatch
      def _apply_patch(self, artifact_json: str, patch: BlueprintPatch) -> str   # deterministico
  ```
  Politica correzioni (PS-D6): violazione → `_request_patch` (il ruolo riceve SOLO le violazioni + l'artefatto corrente, schema `BlueprintPatch`) → `_apply_patch` → rivalidazione; max 2 patch per passo, poi 1 rigenerazione intera, poi fallimento esplicito. Ogni versione persistita (`save_ps_artifact`).
- **Accettazione:** unit con LLM mock: il flusso patch→apply→revalidate funziona; la patch che non tocca la violazione → conteggiata e ritentata; esaurimento → eccezione esplicita `CompileFailed(violations)`.

#### PS3.4 — 🔎 Verifica di fase

- [x] M1+M2 end-to-end su fixture reale (severino-sim, smoke CPU-bound): blueprint valido per una macrofase di T040-bozza, con decisioni esplicite e ownership pulita; `P<k>.blueprint.md` renderizzato; unit compiler verdi. *(smoke live: M1 25s con involved ancorati ai file veri, M2 20s, 0 patch necessarie; 72/72 unit)*

**Rituale** → `v3.4.0`.

---

## Fase PS4 — Verification Compiler: M3 + M4 + Oracle Qualification → `v3.5.0`

🎯 **Scope:** la seconda metà: obblighi di prova, test materializzati, e il gioiello — la qualificazione deterministica dell'oracolo.

#### PS4.1 — M3 Verification Designer + M4 Test Author

- [x] 🤖 **Obiettivo:** card `verification_designer.md` (+`VerificationDesigner(Role)`, output `VerificationBlueprint`) e `test_author.md` (+`TestAuthor(Role)`, output `TestBundle`). *(in corso d'opera: guardia anti-perdita test in materializzazione + `[EXISTING TEST FILE]` a M4; troncamento gestito come dato in `_SingleShot`)*
  Card M3: every micro gets ≥1 proof obligation; `new_behavior` = will FAIL before implementation; `characterization` = passes NOW and must keep passing; obligations name real test files/names; synthesis_cmds = the phase-wide commands. Card M4: write COMPLETE test files for the obligations, nothing else; use ONLY symbols from the blueprint contracts; tests must be meaningful (assert observable behaviour, not tautologies) — sapendo che un gate meccanico li BOCCERÀ se non lo sono.
  **Materializzazione (control plane, non J):** i `TestArtifact` sono scritti via `Scope.check_write` + syntax gate + LF, path sotto i `files_owned`... NO: i test vivono in file PROPRI (`test_*`), dichiarati negli obblighi; lo Scope del task deve includerli nei writable_globs (il control plane li aggiunge esplicitamente, loggandolo).
- **Validazione M3** (`validate_verification(vbp, bp, known_cmd_ids) -> list[str]`): ogni micro ha ≥1 obbligo; `cmd_id` ∈ known (la regola che ha ucciso F3, qui e nella card); `test_file` coerente col naming del runner; kind ∈ {new_behavior, characterization}.
- **Accettazione:** su blueprint fixture, M3+M4 producono bundle sintatticamente valido e materializzato.

#### PS4.2 — ⚠️ Oracle Qualification Gate

- [x] 🤖 **Obiettivo:** `gates.py::oracle_qualification_gate` — il gate che qualifica le PROVE prima che J esista:
  ```python
  def oracle_qualification_gate(vbp: VerificationBlueprint, bundle: TestBundle,
                                bp: PhaseBlueprint, scope: Scope, router: ToolRouter,
                                task_id: str, *, mutation_probe: bool = False) -> GateReport
  ```
  Check deterministici, tutti, nell'ordine: (1) **collezione**: ogni `test_name` è raccolto dal runner (`pytest --collect-only -q` via `run_tests` con cmd dedicato registrato dal control plane); (2) **red-baseline**: ogni obbligo `new_behavior` eseguito ORA fallisce (un test nuovo che passa prima dell'implementazione non prova niente); (3) **green-baseline**: ogni `characterization` eseguito ORA passa; (4) **asserzioni reali**: AST del test — ≥1 assert osservabile, corpo non vuoto, niente `assert True`; (5) **aggancio al bersaglio**: il sorgente del test riferisce ≥1 simbolo/path dai contratti della micro (anti test-scollegato); (6) **scope**: il test non scrive fuori dai propri file (AST: niente open/write su path dei `files_owned` altrui); (7) **copertura**: ogni criterio `proves` della fase ha ≥1 obbligo. (8) **mutation probe** (se config): per gli obblighi marcati... v1: SKIP dichiarato — registrato come estensione PS8 (il probe serio richiede il codice implementato: qui si può solo sondare i characterization invertendo un assert via AST e verificando che diventi rosso — implementare SOLO questa forma).
  Bocciatura → violazioni al `PhaseCompiler._request_patch` (M3 o M4 secondo il check), riqualifica; esaurimento patch → fase failed esplicita.
- **Motivazione:** ogni singolo check corrisponde a un modo REALE in cui M può produrre un oracolo inutile; il gate costa run di test (secondi), non token.
- **Accettazione:** unit con test-trappola: tautologia bocciata (4), test che passa già per un new_behavior bocciato (2), test che non cita il bersaglio bocciato (5); fixture pulita → qualificata.

#### PS4.3 — 🔎 Verifica di fase

- [x] Su una macrofase fixture completa: M1→M4 → qualificazione VERDE con almeno una bocciatura intermedia corretta via patch (dimostrare il ciclo, non solo il caso felice); tutti gli artefatti versionati in `ps_artifacts`; blueprint.md finale include il Verification blueprint. *(smoke finale: compile_phase 134s, qualificazione verde; il ciclo patch/rigenerazione è scattato LIVE nei run precedenti su M2 e M4 — 5 trappole nuove pagate e registrate in atlante §9, batch PS4; 77/77 unit)*

**Rituale** → `v3.5.0`.

---

## Fase PS5 — Engine: J + gate di esecuzione (vertical slice completa) → `v3.6.0`

🎯 **Scope:** il driver che chiude il cerchio: S → fasi → M → qualificazione → J → micro gate → sintesi → ledger → fase successiva.

#### PS5.1 — Work order per J

- [x] 🤖 **Obiettivo:** la conversione MicroPhase+obblighi → `SubtaskSpec` ESISTENTE (J non cambia):
  ```python
  # engine.py
  def work_order(micro: MicroPhase, vbp: VerificationBlueprint) -> SubtaskSpec
      # id=micro.id, objective=work.goal+boundary (col blocco "PROOF:" testuale),
      # inputs=work.inputs, expected_outputs=work.outputs+files_owned,
      # verification=[o.cmd_id degli obblighi della micro]  ← perimetro=verifica by design
  ```
  La card del Worker resta invariata (regole 10-11 già coprono boundary e test fuori perimetro).
- **Accettazione:** unit: la spec generata passa `verify_subtask` con un report fixture; gli obblighi della micro sono ESATTAMENTE i suoi `verification`.

#### PS5.2 — Micro gate + retry gate

- [x] 🤖 **Obiettivo:** in `gates.py`:
  ```python
  def micro_gate(verdict_ok: bool, target: str, checks: list[CheckResult]) -> GateReport
  def failure_signature(failed_checks: list[str], summary: str) -> str
  def retry_gate(prev_sig: str | None, new_sig: str) -> GateReport
  ```
  **REVISIONE PS5 (firma cambiata QUI prima del codice, regola di direzione):** il retry gate
  confronta le **firme di fallimento consecutive** (check falliti + sintesi normalizzata),
  non le istruzioni emendate — misura l'ESITO, non l'intenzione: stessa firma due volte di
  fila = fotocopia vietata → micro `failed` esplicita. L'emendamento informativo del contesto
  ([PREVIOUS ATTEMPT FAILED] + check) è già prodotto da `_execute_subtask` ereditato. `micro_gate`
  è l'involucro del Verdict di `verify_subtask` (che l'engine ottiene via `_execute_subtask`).
  L'emendamento è deterministico in v1 (template dai check falliti: quali file, quale assert, quale exit code — informazione, non strategia); la strategia generata è del Supervisor del piano padre (F4), non di questo sistema.
- **Accettazione:** unit: retry identico bloccato; retry emendato passa; micro con obbligo rosso → gate ko coi check.

#### PS5.3 — PlanSysEngine

- [x] 🤖 **Obiettivo:** `engine.py`: *(implementato come SOTTOCLASSE dell'Orchestrator — eredita ripresa orfani, esecuzione sottofase con resume in-place, budget-consenso e finalize: il collaudato di F1/F2 non si riscrive)*
  ```python
  class PlanSysEngine:
      def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient,
                   router: ToolRouter, assembler: PromptAssembler) -> None
      def run_task(self, task_id: str) -> TaskState        # il flusso PS-A5, bloccante
      def _eligible_phase(self, plan: MacroPlan, task_id: str) -> MacroPhase | None
      def _phase_entry_gate(self, phase: MacroPhase, vbp_prev: list[VerificationBlueprint],
                            router: ToolRouter, task_id: str) -> GateReport
      def _phase_synthesis_gate(self, phase: MacroPhase, vbp: VerificationBlueprint,
                                router: ToolRouter, task_id: str) -> GateReport
      def _plan_coverage_gate(self, plan: MacroPlan, task_id: str) -> GateReport
  ```
  Semantiche: entry gate = se TUTTI i criteri `covers` della fase risultano già provati da obblighi verdi di fasi completate → fase `completed` a zero LLM (il killer delle fasi ridondanti); synthesis = `synthesis_cmds` + ri-run degli obblighi di fase; coverage = a fine piano, ogni C provato ≥1 volta. Ledger ricostruito e renderizzato dopo ogni micro chiusa e a ogni fine fase. Stati/budget/ripresa: STESSE semantiche del padre (riuso `BudgetTracker`, orphan reclaim, resume file di J). Fuori slice v1 (fallimento esplicito, non silenzio): replanning di macrofase, descope, rollback.
- **Accettazione:** unit con LLM mock per S/M: il flusso completo su fixture attraversa i gate nei punti giusti (spia sugli ordini di chiamata); entry gate salta una fase già provata.

#### PS5.4 — CLI

- [x] 🤖 **Obiettivo:** `rg eval --plansys` (harness: `dataclasses.replace(cfg, plansys_enabled=True)` + engine al posto dell'orchestrator quando attivo) e `rg run --plansys` per il pilota manuale. *(+ leva ablation PS6.2 via env `RG_PLANSYS_ABLATE`, solo A/B)*
- **Accettazione:** `rg eval --plansys --only T040` parte e usa l'engine (verificabile dal log: righe `senior`/`compiler`/`gate`).

#### PS5.5 — 🔎 Verifica di fase

- [ ] **Il task pilota:** una richiesta larga su repo fixture (bozza di T040) completa end-to-end su severino-sim: MacroPlan → ≥2 macrofasi → test qualificati → micro implementate da J → sintesi verde → coverage verde; `data/tasks/<id>/plan/` contiene macro_plan.md, blueprint per fase, ledger.md coerenti con il DB; forbice completed≠verified = 0.

**Rituale** → `v3.6.0`.

---

## Fase PS6 — Evaluator: T040+ e A/B con ablation → `v3.7.0`

🎯 **Scope:** il giudizio. Task multi-fase veri, confronto contro la baseline 9/10, ablation per componente.

#### PS6.1 — La serie T040+

- [ ] 🤖 **Obiettivo:** 3 task PROGETTATI per eccedere una singola sessione Worker (il difetto di disegno sperimentale di F3.5, corretto):
  - **T040_multiphase_package** — costruire un pacchetto Python a 3 moduli (parser → trasformazione → report CLI) con suite di test FORNITA (~18 test su 3 file) che copre le interfacce tra moduli; il giudice esterno è la suite piena. Un Worker singolo con `max_steps=20` non può chiuderlo (stimato ≥45 step di lavoro).
  - **T041_no_tests_given** — feature su repo esistente SENZA test forniti: prompt descrive il comportamento; M4 DEVE scrivere i test (la qualificazione lavora davvero); giudice esterno = script indipendente che esercita il comportamento (non i test di M4: il giudice non si fida dell'imputato).
  - **T042_brownfield_extend** — repo fixture di ~15 file con convenzioni sue: estendere rispettandole; misura il ledger/projection (senza, il modello ri-esplora; con, consulta). Giudice = suite fornita + check convenzioni via script.
  Formato: `task.toml` standard (`expected_outcome="verified"`, `success_cmd` esterno); i repo sono nel repo di Red Giant, versionati (D18: si estendono, non si ammorbidiscono).
- **Accettazione:** i 3 task girano nell'harness in modalità baseline (naive) e producono il loro (prevedibile) fallimento o successo parziale — QUESTO è il punto: se la baseline li chiude, sono troppo piccoli e vanno rifatti.

#### PS6.2 — 📌 A/B + ablation

- [ ] 🤖 **Obiettivo:** run ufficiali (severino-sim, codice committato, regola F3): (A) baseline naive su T001–T010 + T040–T042; (B) plansys completo, stesso set; ablation su T040–T042: (B1) senza oracle qualification (gate bypass, flag di test); (B2) senza ledger/projection (proiezione = listato repo grezzo); (B3) senza phase entry gate. *(meccanica ablation decisa in implementazione: env var `RG_PLANSYS_ABLATE` ∈ {oracle, ledger, entry}, helper `plansys.ablated()` — leva di solo-A/B, mai in produzione: non tocca il contratto config)* Report con le 5 metriche cardine + le metriche PS-D9 (token di governance, test deboli respinti, retry fotocopia bloccati, criteri coperti, lavoro duplicato).
- **Accettazione:** report committato in `bench/results/` con conclusione scritta per componente (resta / esce / resta con riserva); atlante §8-bis aggiornato; **README aggiornato** (finding F8 riscritta coi numeri nuovi, qualunque essi siano).

#### PS6.3 — 🔎 Verifica di fase

- [ ] Verdetto D11 scritto nell'ESITO PS6 di questo file: il sistema si è guadagnato l'accensione di default sui task larghi? (Le opzioni oneste: sì sui multi-fase con routing per taglia; no e si documenta perché; dati insufficienti e si dice cosa manca.) Forbice = 0 su tutte le run.

**Rituale** → `v3.7.0`.

---

## Fase PS7 — Integrazione in Red Giant → `v4.0.0` (major, merge in `main`)

🎯 **Scope:** il sistema smette di essere un esperimento parallelo.

- [ ] **PS7.1** 🤖 Selezione del driver in config: `[plansys] enabled=true` → i task GUI/CLI senza piano statico usano `PlanSysEngine` (il gate D11 del vecchio Planner resta com'è: quel Planner rimane OFF e deprecato, la rimozione fisica si decide con l'utente); `enabled=false` → tutto come oggi. Routing per taglia (quando pianificare) = resta materia di F6 del padre, con i dati di PS6 come input.
- [ ] **PS7.2** 🤖 GUI: la pagina task mostra i documenti di piano (`macro_plan.md`, blueprint, ledger) come tab read-only (sono file: `GET /tasks/{id}/plan/{name}` con tail, riuso del pattern log); i gate compaiono nell'albero come righe (✓/✗ con link ai check).
- [ ] **PS7.3** 🤖 Piano padre: aggiornare Stato + tabella versioni (nota di riconciliazione) + riga in F6 (routing usa PS6) + ESITO di questo interludio; memoria di progetto aggiornata.
- [ ] **PS7.4** 🔎 Un task reale dalla GUI con plansys attivo completa end-to-end; `check_reference` verde; 55+ unit verdi; il piano padre riprende da F3-bis.

**Rituale** → `v4.0.0` + merge `main` su entrambe le remote.

---

## Rischi aperti e mitigazioni

| Rischio | Prob. | Mitigazione attiva |
|---|---|---|
| M4 scrive test che il gate boccia in loop | media | patch mirate (PS-D6) con violazioni citate; max 2+1; il fallimento esplicito è un esito accettabile (D16-spirito) |
| Il costo di M (≤8 chiamate/fase) mangia il vantaggio | media | entry gate a zero token; proiezioni budgetate; A/B PS6 misura i token di governance separatamente — se non paga, lo dice il report |
| Red-baseline lenta (run di test per ogni qualifica) | bassa | i test di una fase si qualificano in UN run collect + UN run execute; su fixture ~secondi |
| T040+ mal calibrati (troppo piccoli/grandi) | media | PS6.1 accettazione: se la baseline li chiude, si rifanno PRIMA dell'A/B |
| Ownership esclusiva troppo rigida (file condivisi reali) | media | PS-D10: la si rilassa SOLO via revisione di questo piano con caso reale documentato |
| Il ledger AST è lento su repo grandi | bassa | scan limitato ai file toccati/inputs; T042 lo misura; cache per mtime se serve (debito dichiarato) |
| Slice v1 senza replanning si incaglia su piani sbagliati | media | fallimento esplicito con ESITO leggibile + rilancio guidato (F2.4-bis) — replanning versionato = PS8 futura, da aprire coi dati |

## Cosa NON esiste in questo sistema (per non cercarlo invano)

Replanning/descope di macrofase (fallimento esplicito in v1) · mutation testing completo (solo probe assert-flip sui characterization) · Supervisor/Debugger (restano F4 del padre; il retry qui è emendato deterministicamente) · compressione del ledger (il budget della proiezione basta in v1) · multi-dominio (coding-only fino a prova PS6; l'estensione segue F3-bis/F7 del padre) · parallelismo (D7 padre, sempre).

# Red Giant — Codebase Reference (atlante)

**Aggiornato al:** 2026-08-03 · **Versione repo:** `v4.4.0` · **Fase completata:** F3-bis (domini non-coding) + planner system (PS0–PS6) + campagna thinking (TH0–TH3) + ladder di attribuzione
**Regola:** questo documento descrive **il codice che esiste**, non quello pianificato (per quello c'è [plan_red_giant.md](plan_red_giant.md)). Verifica meccanica: `python scripts/check_reference.py` — bloccante nel rituale di fine fase.

---

## 1. Indice "dove sta cosa"

| Cerchi… | Vai in… |
|---|---|
| GUI web (coda, approvazioni/grant, metriche) | `redgiant/web/` — avvio: `rg serve` o `scripts/start-gui.ps1` |
| Collaudo end-to-end riproducibile della GUI | `scripts/collaudo-gui.py --task T007 [--approve]` |
| Visione e requisiti | [small-model-powerhouse-specsheet.md](small-model-powerhouse-specsheet.md) |
| Decisioni vincolanti (D1–D21) e piano | [plan_red_giant.md](plan_red_giant.md) |
| Numeri di baseline F0 e decisioni derivate | §8-bis + `config/default.toml` + `bench/results/` |
| Configurazione e profili | `redgiant/config.py` + `config/*.toml` |
| Stato persistente (modelli + SQLite) | `redgiant/state/` |
| Client del modello (guided decoding, timings) | `redgiant/llm/` |
| Prompt S1→S7, preambolo, card | `redgiant/prompts/` |
| Tool (Scope, catalogo, router) | `redgiant/tools/` |
| Ruoli cognitivi (Worker) | `redgiant/roles/` |
| Orchestrator, verifica, budget, task log | `redgiant/core/` |
| Evaluator e task sintetici T001–T057 | `redgiant/eval/` |
| CLI di sviluppo (`rg`) | `redgiant/cli.py` |
| Planner system (artefatti, gate, compilatore, ledger) | `redgiant/plansys/` |
| Leve di ablazione (attribuzione dei componenti) | `redgiant/core/ablate.py` + `redgiant/plansys/__init__.py::ablated` |
| Guardia aritmetica in scrittura (F4 sui contenuti) | `redgiant/tools/coherence.py` |
| Thinking mode (protocollo a due chiamate TH-D1/TH-D2) | `redgiant/llm/client.py::complete(..., think=)` |
| Ladder di difficoltà crescente (generatore + runner) | `bench/ladder/` |
| Tutti i dati mai raccolti, con tabelle | [../data.md](../data.md) |
| Whitepaper scientifico | [../white_paper.md](../white_paper.md) |

## 2. Albero dei file (reale, a v4.4.0)

```text
RedGiant/
├── pyproject.toml / requirements.lock / LICENSE (MIT+attribution) / README.md / logo.png
├── data.md (registro di tutte le misure) / white_paper.md
├── config/{default.toml, profiles/{dev-fast,severino-sim,severino}.toml}
├── docker/severino-sim/compose.yml     # 2 core (≈4 di Severino), 10g, digest-pinned b10200
├── scripts/{download-llama,download-model,start-llama}.ps1, check_reference.py, collaudo-gui.py
├── bench/
│   ├── schemas_probe.py · run_bench.py · naked_probe.py · results/
│   └── ladder/{generate.py, run_naked.py, run_agentic.py}
├── memory/{plan_red_giant.md, plan_planner_system.md, plan_thinking_ab.md, codebase_reference.md}
├── redgiant/
│   ├── __init__.py (__version__) · config.py · cli.py
│   ├── state/{models.py, store.py}
│   ├── llm/{client.py, schema.py}
│   ├── prompts/{assemble.py, preamble.md, roles/*.md}
│   ├── tools/{base.py, fs.py, search.py, proc.py, router.py, calc.py, coherence.py, web.py}
│   ├── roles/{base.py, worker.py, planner.py, phase_designer.py}
│   ├── plansys/{artifacts.py, astscan.py, compiler.py, engine.py, gates.py, ledger.py, render.py, roles.py}
│   ├── core/{orchestrator.py, verify.py, budget.py, ablate.py}
│   ├── web/{app.py, jobs.py}
│   └── eval/{harness.py, tasks/T001..T010,T030..T032,T040..T042,T051..T057}
└── tests/unit/  (15 file, 126 test)
```

## 3. Classi e metodi

### `redgiant/config.py` — caricamento configurazione (F0.1)

Dataclass frozen per sezione TOML; merge default+profilo; chiave sconosciuta → `ValueError` col nome; profilo inesistente → `FileNotFoundError`.

```python
class LlmProfileCfg      # base_url, ctx_size, timeout_s, temperature, max_tokens_default
class PathsCfg           # db, models_dir, tasks_dir, slots_dir, ripgrep
class BudgetCfg          # max_total_tokens, max_tool_calls, max_retries_per_subtask, max_wall_s
class WebCfg             # host, port
class SecurityCfg        # writable_globs, shell_whitelist (tuple)
class Config
    def load(cls, profile_name: str, config_dir: Path | None = None) -> "Config"
```

### `redgiant/cli.py` — CLI di sviluppo (F1.9)

```python
def main(argv: list[str] | None = None) -> int   # rg run|status|eval|bench
```

### `redgiant/state/models.py` — modelli dello stato (F1.1)

Tutti Pydantic `extra="forbid"`. Enum: `TaskStatus` (7 stati), `SubtaskStatus` (9 stati, specsheet §11).

```python
class Budget        # max_total_tokens, max_tool_calls, max_retries_per_subtask, max_wall_s
class BudgetUsed    # tokens, tool_calls, wall_s
class SubtaskSpec   # id, phase_id, title, objective, inputs, tools, expected_outputs,
                    # completion_criteria, verification (nomi check per verify.py)
class PhaseSpec     # id, title, depends_on, completion_criteria
class Plan          # version, goal, success_criteria, phases
class TaskState     # id, request, target_dir, domain, status, plan, current_phase,
                    # current_subtask, budget, used
class LlmCallRow    # riga llm_calls (scritta dal client)
class ToolCallRow   # riga tool_calls (scritta dal router)
```

### `redgiant/state/store.py` — StateStore (F1.1)

Unico punto di accesso al DB (DDL §4). Connessione per-operazione (WAL), mutazioni in transazione con `actor`. `load_task` deriva current_phase/subtask dalla tabella subtasks (unica fonte di verità) ed è LA funzione di ripresa. `budget_used` aggrega dal DB: mai contatori in RAM.

```python
def _ulid() -> str                     # 48bit timestamp + 80bit random, Crockford base32
class StateStore
    def __init__(self, db_path: Path) -> None
    def init_schema(self) -> None
    def create_task(self, request: str, target_dir: str, profile: str, budget: Budget) -> str
    def load_task(self, task_id: str) -> TaskState
    def list_tasks(self, limit: int = 50) -> list[dict]
    def set_task_status(self, task_id: str, status: TaskStatus, *, actor: str, error: str | None = None) -> None
    def save_plan(self, task_id: str, plan: Plan, *, actor: str, reason: str) -> None
    def upsert_subtask(self, task_id: str, spec: SubtaskSpec, *, actor: str) -> None
    def get_subtask(self, task_id: str, subtask_id: str) -> tuple[SubtaskSpec, SubtaskStatus, int]
    def list_subtasks(self, task_id: str) -> list[dict]
    def set_subtask_status(self, task_id: str, subtask_id: str, status: SubtaskStatus, *, actor: str, result: dict | None = None) -> None
    def add_approval(self, task_id: str, *, kind: str, payload: str) -> int
    def pending_approvals(self, task_id: str | None = None) -> list[dict]
    def answer_approval(self, approval_id: int, answer: str) -> str
    def list_grants(self, task_id: str | None = None) -> list[dict]
    def override_approval(self, approval_id: int, answer: str | None) -> str
    def consume_matching_approval(self, task_id: str, tool: str, args_json: str) -> str | None
    def latest_clarification_answer(self, task_id: str) -> str | None
    def extend_budget(self, task_id: str, key: str, add: int) -> None
    def take_budget_extension(self, task_id: str) -> tuple[str, str, int] | None
    def list_decisions(self, task_id: str) -> list[dict]
    def save_ps_artifact(self, task_id: str, *, kind: str, ref: str, payload_json: str, actor: str) -> int
    def load_ps_artifact(self, task_id: str, kind: str, ref: str = "", version: int | None = None) -> dict
    def list_ps_artifacts(self, task_id: str, kind: str | None = None) -> list[dict]
    def log_ps_gate(self, task_id: str, *, gate: str, target: str, ok: bool, checks_json: str) -> None
    def ps_gate_history(self, task_id: str, gate: str | None = None) -> list[dict]
    def add_decision(self, task_id: str, *, actor: str, decision: str, reason: str, target: str | None = None) -> None
    def log_llm_call(self, task_id: str, row: LlmCallRow) -> None
    def log_tool_call(self, task_id: str, row: ToolCallRow) -> None
    def budget_used(self, task_id: str) -> BudgetUsed
```

### `redgiant/llm/schema.py` + `redgiant/llm/client.py` — model client (F1.2)

Unico punto che parla con llama-server. Guided decoding su ogni chiamata con schema + rivalidazione Pydantic (fallita = `outcome='invalid'`, MAI retry). Stop `limit` → `LlmTruncated`. `ContextOverflow` PRIMA di chiamare, coi token per sezione. Seed fisso 42 (riproducibilità). Retry SOLO su errori di trasporto (2×, 2s).

```python
def to_llama_schema(model: type[BaseModel]) -> dict
class LlmError
class LlmTimeout
class LlmTruncated
class LlmInvalidOutput
class ContextOverflow
    def __init__(self, prompt_tokens: int, ctx_size: int, sections: dict[str, int]) -> None
class LlmResult     # text, parsed, prompt_tokens, cached_tokens, gen_tokens, prefill_ms, gen_ms, raw_timings
class LlamaClient
    def __init__(self, cfg: LlmProfileCfg, store: StateStore | None = None) -> None
    def complete(self, parts: PromptParts, *, role: str, schema: type[BaseModel] | None = None, max_tokens: int, temperature: float | None = None, task_id: str | None = None, subtask_id: str | None = None, cache_prompt: bool = True, grammar_schema: dict | None = None, think: int | None = None) -> LlmResult  # grammar_schema: schema SPECIALIZZATO (enum dinamici); think (TH0): budget del canale di pensiero, two-call protocol TH-D1/TH-D2 — chiamata 1 = prompt+think_open senza grammatica con stop=[think_close] (troncamento NON errore), chiamata 2 = prompt+canale+JSON grammaticato; parts MAI mutate; LlmResult guadagna thinking_tokens/thinking_ms/thinking_text (testo solo per log)
    def count_tokens(self, text: str) -> int
    def health(self) -> bool
    def props(self) -> dict
```

### `redgiant/prompts/assemble.py` — convenzione S1→S7 (F1.3, §A4)

Ordine fisso, separatori byte-stabili, turn markers Gemma sempre presenti. Lo schema di output completo sta in S2 (statica → cachata); S7 resta corta. `with_appended_context` = append-only su S6 (D20).

```python
class PromptParts
    def render(self) -> str
    def section_tokens(self, counter: Callable[[str], int]) -> dict[str, int]
    def static_prefix_len(self) -> int
    def with_appended_context(self, block: str) -> "PromptParts"
class PromptAssembler
    def __init__(self, prompts_dir: Path) -> None
    def build(self, role: str, *, task: TaskState, subtask: SubtaskSpec | None, tools: Sequence["ToolSpec"], volatile: str, output_schema: dict | None = None, schema_name: str | None = None) -> PromptParts
```

### `redgiant/tools/base.py` — fondamenta tool (F1.4)

```python
class ScopeError
class Scope
    def __init__(self, root: Path, writable_globs: list[str]) -> None
    def check_read(self, p: str) -> Path
    def check_write(self, p: str) -> Path
class ToolResult    # ok, data, evidence, error
class ToolSpec      # name, description, risk, reversible, requires_approval, timeout_s, input_model, handler
```

### `redgiant/tools/fs.py` — filesystem (F1.4 + F1.11)

`edit_file` è lo strumento di editing PRIMARIO (i diff unificati sono ostili agli E2B — evidenza F1.11); normalizza i prefissi `N<TAB>` che i modelli copiano da `read_file`; un edit con `old_string == new_string` (post-normalizzazione) è respinto con `no_op_edit` (A/B 2026-08-02: il no-op "riusciva" e il modello lo ripeteva fino a esaurire gli step). `write_file` crea file nuovi. `write_patch` resta per edit multi-punto, con matching tollerante (prefissi numerici, whitespace, code `-` vuote spurie).

**Syntax gate (post-F1, richiesta utente):** ogni writer verifica la sintassi del contenuto risultante PRIMA della scrittura atomica (`.py` ast.parse, `.php` php -l se disponibile, `.json`, `.toml`); sintassi rotta = scrittura rifiutata con `syntax_error` + dettaglio riga — un file rotto non esiste mai su disco.

**Coherence gate (2026-08-03, F4 sui CONTENUTI):** gli stessi tre writer chiamano `coherence_check` sul testo risultante; un artefatto testuale con un totale incoerente rispetto ai valori che dichiara è rifiutato con `incoherent_arithmetic` e il numero corretto nell'hint. Logica in [`redgiant/tools/coherence.py`](#redgianttoolscoherencepy--guardia-di-coerenza-aritmetica-f4-sui-contenuti); `coherence_check` è il solo wrapper che applica l'ablazione `RG_WORKER_ABLATE=coherence`.

**Stato del mondo nei rifiuti (`refusal_state`, 2026-08-03) — TRAPPOLA DISINNESCATA:** ogni hint di rifiuto (`incoherent_arithmetic` **e** `syntax_error`) dichiara ora com'è rimasto il disco: *"… does NOT exist: nothing was written. Call write_file again with the full content — edit_file cannot work, there is no file to edit yet"* oppure *"still has its PREVIOUS content"*. **Causa tecnica:** misurato su L5 (`data.md` §7.6), su 4 write rifiutati 2 run morivano perché il modello trattava il rifiuto come un successo — una chiamava `edit_file` su un file mai creato (due volte), l'altra andava a `run_tests` su un artefatto inesistente. La regola generale, valida per **ogni gate futuro che rifiuta un'azione**: un errore che dice *cosa* era sbagliato ma non *com'è rimasto il mondo* lascia il modello a ragionare su uno stato che non esiste.

```python
class ReadFileArgs
class ListFilesArgs
class WritePatchArgs
class EditFileArgs
class WriteFileArgs
def syntax_check(path: Path, content: str) -> str | None
def coherence_check(path: Path, content: str) -> str | None  # None se ablato; delega a coherence.arithmetic_check
def refusal_state(real: Path, path: str) -> str  # stato REALE del disco, accodato a ogni hint di rifiuto
def syntax_hint(detail: str) -> str  # hint mirato accodato ai syntax_error (f-string annidati → .format/concat, pilota PS5)
def read_file(scope: Scope, path: str, start_line: int = 1, end_line: int | None = None) -> ToolResult
def list_files(scope: Scope, glob: str, max_results: int = 200) -> ToolResult
def edit_file(scope: Scope, path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult
def write_file(scope: Scope, path: str, content: str) -> ToolResult
def write_patch(scope: Scope, path: str, unified_diff: str) -> ToolResult
```

### `redgiant/tools/coherence.py` — guardia di coerenza aritmetica (F4 sui contenuti)

**Perché esiste:** l'esperimento sull'obbedienza (`data.md` §7.5) ha misurato che *un'istruzione non produce obbedienza* — tre livelli di persuasione testuale hanno portato l'invocazione della calcolatrice dal 16% al 40% e il gradino L5 è rimasto a 2/5, con i 5 fatti su 5 giusti e la sola somma sbagliata. Quindi l'operazione si toglie dalle mani del modello: un totale non è significato, è **identità derivata** dai valori che il modello stesso ha scritto, e l'identità appartiene al control plane (PS-D11).

**Cosa NON è:** non è un oracolo sul task. Somma ciò che il modello ha scritto, non ciò che è vero: se i fatti sono sbagliati, certifica una somma sbagliata. Verifica coerenza interna, non correttezza — così non ripete il leak del giudice della ladder (§7.5).

**Condizioni di attivazione (deliberatamente conservative — un falso positivo blocca lavoro legittimo, molto peggio di un mancato aiuto):** suffisso in `{"", ".txt", ".md", ".text", ".answer", ".out"}` (mai codice o config: là un `total = 100` è un valore indipendente); riga di totale riconosciuta per chiave (`total/totale/sum/somma/grand_total/…`); il totale dev'essere l'**ultima** assegnazione numerica del file; almeno 2 addendi; **una sola** riga di totale. Regex `_ASSIGN`: `chiave = numero` da sola sulla riga, niente unità o commenti in coda.

```python
_TEXTUAL: set[str]      # suffissi su cui la guardia è applicabile
_TOTAL_KEYS: set[str]   # chiavi riconosciute come totale
_ASSIGN: re.Pattern     # ^ [-*]? chiave [=:] numero [,.;]? $
_TOL = 1e-9
def _fmt(v: float) -> str
def arithmetic_check(path: Path, content: str) -> str | None   # messaggio azionabile o None
```

Il messaggio contiene il numero corretto e l'espressione (`693 + 228 + … = 1792`, addendi troncati a 12): il giro successivo il modello trascrive invece di calcolare. Ablabile con `RG_WORKER_ABLATE=coherence` (l'ablazione è applicata da `fs.coherence_check`, non qui: `arithmetic_check` resta una funzione pura e testabile).

### `redgiant/tools/calc.py` — calcolatrice deterministica (F4)

AST-only: costanti numeriche e `+ - * / // % **`, niente nomi, chiamate, indexing o lambda (non è un `eval` travestito); `2**99999` e la divisione per zero sono errori-dato, non eccezioni. Registrata nel catalogo come `calculator` (rinominata da `calc` su richiesta utente 2026-08-03), descrizione "MANDATORY for every sum…". **Nota di misura:** il tool funziona ma viene invocato nel ~40% delle run — per questo esiste la guardia di coerenza qui sopra.

```python
class CalcArgs
def calc(expression: str) -> ToolResult   # data["result"]; error: division_by_zero | bad_expression:<dettaglio>
```

### `redgiant/tools/web.py` — HTTP minimale (F3b.1, anticipo di F7.2)

Whitelist da config (`security.http_allowed_domains`, default VUOTA = niente rete), solo http(s), timeout 15s, size-cap 200KB, guardia sui redirect (destinazione ri-verificata), CACHE per-task in `.rg_http_cache/` dentro la workdir (la verifica rilegge LA copia vista dal modello; dir esclusa da `_repo_listing`, `build_ledger` e quindi dai prompt). Registrato nel catalogo come `http_get` (approval-free, "medium").

```python
CACHE_DIR = ".rg_http_cache"
class HttpGetArgs
def _host_allowed(host: str, allowed: tuple[str, ...]) -> bool
def http_get(scope: Scope, allowed_domains: tuple[str, ...], url: str) -> ToolResult
```

### `redgiant/tools/search.py` — ricerca (F1.4)

`resolve_ripgrep` salta gli Scripts del venv (omonimia col nostro entry point); `search_python` è il fallback puro Python quando ripgrep manca (stesso contratto).

```python
class SearchCodeArgs
def resolve_ripgrep(configured: str) -> str
def search_python(scope: Scope, pattern: str, glob: str | None = None, max_results: int = 50) -> ToolResult
def search_code(scope: Scope, rg_bin: str, pattern: str, glob: str | None = None, max_results: int = 50) -> ToolResult
```

### `redgiant/tools/proc.py` — processi (F1.4)

`run_tests` esegue SOLO `cmd_id` registrati; `pytest`/`python` risolti sull'interprete di Red Giant (l'ambiente dei tool == quello dell'harness).

I comandi di test li trova il SISTEMA (richiesta utente, F2): `discover_test_commands` deterministica all'avvio di ogni job (test_*.py⇒pytest, test.php⇒php, composer scripts.test⇒composer; config utente vince) + tool `register_test_command` per il Worker (guardia: eseguibile in `shell_whitelist`, persistito in task_config.json).

```python
class RunTestsArgs
class GitStatusArgs
class GitDiffArgs
class RegisterTestCommandArgs
def discover_test_commands(root, shell_whitelist: tuple[str, ...]) -> dict[str, list[str]]
def run_tests(scope: Scope, test_commands: dict[str, list[str]], shell_whitelist: tuple[str, ...], cmd_id: str, timeout_s: float = 300.0) -> ToolResult
def git_status(scope: Scope) -> ToolResult
def git_diff(scope: Scope, ref: str = "HEAD") -> ToolResult
```

### `redgiant/tools/router.py` — ToolRouter (F1.4)

`dispatch`: unknown/bad_args/awaiting_approval/eccezioni = tutti DATI per il modello, mai crash; tutto loggato su tool_calls. Tollera l'echo `"tool"` negli args. `requires_approval` → riga approvals + task blocked.

```python
def default_catalog(cfg: Config, scope: Scope, test_commands: dict[str, list[str]], persist_test_commands=None) -> dict[str, ToolSpec]
class ToolRouter
    def __init__(self, catalog: dict[str, ToolSpec], scope: Scope, store: StateStore) -> None
    def allowed_for(self, role: str, domain: str) -> list[ToolSpec]
    def render_tool_card(self, specs: list[ToolSpec]) -> str
    def dispatch(self, task_id: str, subtask_id: str, name: str, args: dict) -> ToolResult
```

### `redgiant/roles/base.py` + `redgiant/roles/worker.py` — Worker (F1.5, D20)

ReAct a passo singolo vincolato: un `WorkerStep` per step, contesto in append puro (KV cache riusata). L'incoerenza action↔payload NON è un validator (la grammatica non può esprimerla): è un dato gestito nel loop. Il `finish` non chiude la sottofase: la chiude la verifica. Guard cumulativo per (tool, errore) nel tentativo: advice a 3/5, aborto a 8; esclusi i `run_tests`→`tests_failed` (l'oracolo che parla non è un tool rotto); le chiamate identiche consecutive contano come fallimento `identical_repeat` anche se "riuscite" (A/B 2026-08-02: 15 edit no-op di fila), con `run_tests` ESENTATO (rerun stesso giorno: rieseguire l'oracolo è lecito — il guard abortiva le sottofasi di sola analisi a 8 pytest identici).

```python
class RoleContext   # task, subtask, volatile
class Role
    def __init__(self, llm: LlamaClient, assembler: PromptAssembler, router: ToolRouter) -> None
class ToolCallSpec  # tool, args
class FinishReport  # status done|blocked, summary<=600, evidence, verification_requested
class WorkerToolStep    # thought<=300, action="tool", tool_call OBBLIGATORIO
class WorkerFinishStep  # thought<=300, action="finish", finish OBBLIGATORIO
class WorkerStep    # RootModel: union DISCRIMINATA dei due — il ramo incompleto
                    # (finish:null) non e' generabile ne' validabile (fix F2.5:
                    # il derail da apice non escapato non ha piu' un'uscita incoerente)
class Worker
    def run(self, ctx: RoleContext, *, max_steps: int, step_max_tokens: int = 512, step_log=None, resume_file=None) -> FinishReport
```

### `redgiant/roles/planner.py` + `redgiant/roles/phase_designer.py` — pianificazione (F3)

Planner: mappa sintetica (≤7 fasi), la LOGICA validata deterministicamente (id univoci, dipendenze acicliche, root presente, fasi completate conservate al replanning) con UNA richiamata correttiva (che CITA le regole violate, non solo i sintomi — A/B 2026-08-02) poi `PlanRejected`. `normalize_plan` ripara i sentinelli inequivoci in `depends_on` ("none"/"null"/"n/a"/"-"/"" e l'auto-dipendenza `dep == p.id` → rimossi) prima di ogni validazione; le allucinazioni vere (es. nomi di file) restano al validatore. PhaseDesigner: espande solo la fase corrente (≤6 sottofasi, id `P<x>.S<n>`); D10: ogni sottofase deve avere verifica eseguibile O expected_outputs (l'esistenza è un oracolo); i cmd di verifica devono essere registrati.

```python
class PlannerOutput      # goal<=300, success_criteria<=6, phases<=7
def normalize_plan(out: PlannerOutput) -> PlannerOutput
def validate_plan_logic(out: PlannerOutput, required_phase_ids: list[str] | None = None) -> list[str]
class Planner
    def run(self, ctx: RoleContext, *, max_tokens: int = 1536, required_phase_ids: list[str] | None = None) -> PlannerOutput
class PlanRejected
    def __init__(self, problems: list[str]) -> None
class PhaseDesign        # phase_id, subtasks<=6
def validate_design_logic(out: PhaseDesign, current_phase_id: str, known_cmd_ids: set[str]) -> list[str]
class PhaseDesigner
    def run(self, ctx: RoleContext, *, current_phase_id: str, known_cmd_ids: set[str], max_tokens: int = 2048) -> PhaseDesign
class DesignRejected
    def __init__(self, problems: list[str]) -> None
```

Orchestrator v1 (F3.3/F3.4): piano generato se assente, espansione lazy della sola fase eleggibile, sottofase fallita oltre i retry → **replanning** (max 2; fasi completate immutabili, sottofasi orfane → skipped) → poi `failed` esplicito.

### `redgiant/plansys/` — il sistema di pianificazione S/M/J (piano: `plan_planner_system.md`)

**Cast (nomi utente, id tecnici invariati):** Sirio=`senior_planner` · Mira=`phase_analyst` · Mizar=`work_decomposer` · Vega=`verification_designer` · Altair=`test_author` · Giano=`worker`.

Sistema a sé stante (PS-D1: LLM solo in roles.py/compiler.py, il resto deterministico). PS0: artefatti tipizzati (versionati in `ps_artifacts`), renderer DB→Markdown greppabile (`data/tasks/<id>/plan/`, byte-deterministico, scrittura atomica LF), config `[plansys]` (default OFF, PS-D9). Tabelle: `ps_artifacts` (task_id, kind∈{macro_plan, phase_analysis, phase_blueprint, verification_blueprint, test_bundle, ledger_snapshot}, ref, version UNIQUE auto-incrementata per (task,kind,ref), actor, json, created_at) e `ps_gates` (gate, target, ok, checks JSON).

```python
class Criterion       # id C1.., text<=200 — prodotto da S, immutabile
class MacroPhase      # id P1.., intent (mai operazioni), depends_on<=5, covers>=1
class MacroPlan       # goal, criteria 1..8, phases 1..6
class DesignDecision  # id, decision, alternatives<=3, constraint (PS-D8: esplicita)
class ChoicePoint     # question, options 2..3, recommended, reason
class PhaseAnalysis   # phase_id, objective, involved<=10, artifacts<=10, decisions<=4, risks<=4, decision_required?
class WorkContract    # goal, boundary, files_owned 1..4 (ownership esclusiva), signatures<=6, inputs, outputs
class MicroPhase      # id P<k>.S<n>, title, work, proves<=4
class PhaseBlueprint  # phase_id, micro 1..6
class ProofObligation # id, micro_id, kind new_behavior|characterization, behavior, test_file, test_name, cmd_id
class VerificationBlueprint  # phase_id, obligations 1..12, synthesis_cmds 1..3
class TestArtifact    # path, content — materializzato dal control plane, MAI da J
class TestBundle      # phase_id, artifacts 1..8
class PatchOp         # op replace|add|remove, target, payload_json SENZA tetto (maxLength→GBNF {0,N} = 400 dal server, trappola PS4.3)
class BlueprintPatch  # phase_id, ops 1..6 (PS-D6: correzione=patch)
class GateReport      # gate enum a 7 valori, target, ok, checks (riusa CheckResult)
class PlansysCfg      # (in config.py) max_phases, max_micro_per_phase, projection_max_tokens, m_pass_max_tokens, test_author_max_tokens, mutation_probe
def render_macro_plan(plan: MacroPlan) -> str
def render_blueprint(bp: PhaseBlueprint, vbp: VerificationBlueprint | None, analysis: PhaseAnalysis | None) -> str
def write_plan_doc(tasks_dir: Path, task_id: str, name: str, content: str) -> Path
def normalize_signature(sig: str) -> str
def file_signatures(path: Path) -> list[str]
def extract_signatures(pkg_dir: Path) -> dict[str, list[str]]
class LedgerEntry   # kind signature|test|artifact|decision|failure|fact, ref, text<=300
class TaskLedger    # task_id, entries
def build_ledger(store: StateStore, scope: Scope, task_id: str) -> TaskLedger
def render_ledger(ledger: TaskLedger) -> str
def project_for_phase(ledger: TaskLedger, plan: MacroPlan, phase_id: str, max_tokens: int, count: Callable[[str], int]) -> str
def ablated(component: str) -> bool   # PS6.2: RG_PLANSYS_ABLATE="oracle,ledger,entry" (solo A/B)
def thinking_roles() -> set[str]      # TH0.3: RG_THINKING_ROLES=nomi ruolo DB (senior_planner,...,worker) — leva di solo esperimento
def thinking_budget() -> int          # TH0.3: RG_THINKING_BUDGET (default 256)
def dag_problems(pairs: list[tuple[str, list[str]]]) -> list[str]
def normalize_macro(plan: MacroPlan) -> MacroPlan
def macro_validation_gate(plan: MacroPlan, request: str | None = None) -> GateReport  # request: check copertura-richiesta (file .py nominati => criteri/intent, forbice T041)
class MacroRejected
    def __init__(self, problems: list[str]) -> None
class SeniorPlanner
    def run(self, ctx: RoleContext, *, max_tokens: int = 1024) -> MacroPlan
def parse_artifact(model: type[BaseModel], payload_json: str) -> BaseModel
class _SingleShot     # base di M1..M4: una chiamata, un parse (correzioni = patch nel compiler) + 1 retry su troncamento
    def run(self, ctx: RoleContext, *, max_tokens: int = 1024, grammar_schema: dict | None = None) -> BaseModel
class PhaseAnalyst    # M1 — single-shot, output PhaseAnalysis
class WorkDecomposer  # M2 — single-shot, output PhaseBlueprint
def validate_analysis(analysis: PhaseAnalysis, projection: str, phase_id: str) -> list[str]
def validate_blueprint(bp: PhaseBlueprint, analysis: PhaseAnalysis, covers: list[str], existing: set[str] | None = None) -> list[str]  # + prosa nel perimetro, 1 file nuovo/micro, coverage chain
class VerificationDesigner  # M3 — single-shot, output VerificationBlueprint
class TestAuthor            # M4 — single-shot, output TestBundle (budget dedicato 3072)
def validate_verification(vbp: VerificationBlueprint, bp: PhaseBlueprint, known_cmd_ids: set[str]) -> list[str]
def _top_imports(imports_src: str) -> set[str]  # primo segmento dei moduli importati top-level
def validate_bundle(bundle: TestBundle, vbp: VerificationBlueprint, bp: PhaseBlueprint | None = None, existing: set[str] | None = None) -> list[str]  # + aggancio al bersaglio, import top-level nei new_behavior, ghost imports
def oracle_qualification_gate(vbp: VerificationBlueprint, bundle: TestBundle, bp: PhaseBlueprint, scope: Scope, router, task_id: str, *, mutation_probe: bool = False) -> GateReport
class CompileFailed
    def __init__(self, step: str, problems: list[str]) -> None
class NeedsDecision
    def __init__(self, phase_id: str, choice: ChoicePoint) -> None
class PhaseAlreadySatisfied  # entry-check in compile_phase: proofs verdi E files_owned esistenti → fase chiusa a zero J
    def __init__(self, phase_id: str) -> None
class PhaseCompiler
    def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient, assembler: PromptAssembler, router: ToolRouter, scope: Scope) -> None
    def projection(self, task_id: str, plan: MacroPlan, phase: MacroPhase) -> str
    def analyze(self, task_id: str, plan: MacroPlan, phase: MacroPhase, projection: str, log) -> PhaseAnalysis
    def decompose(self, task_id: str, phase: MacroPhase, analysis: PhaseAnalysis, projection: str, log) -> PhaseBlueprint
    def design_verification(self, task_id: str, phase: MacroPhase, bp: PhaseBlueprint, projection: str, log) -> VerificationBlueprint
    def author_tests(self, task_id: str, phase: MacroPhase, bp: PhaseBlueprint, vbp: VerificationBlueprint, projection: str, log) -> TestBundle
    def materialize_tests(self, bundle: TestBundle, log) -> None
    def compile_phase(self, task_id: str, plan: MacroPlan, phase: MacroPhase, log) -> tuple[PhaseBlueprint, VerificationBlueprint, TestBundle]
def micro_gate(verdict_ok: bool, target: str, checks: list[CheckResult]) -> GateReport
def failure_signature(failed_checks: list[str], summary: str) -> str
def retry_gate(prev_sig: str | None, new_sig: str) -> GateReport
def work_order(micro: MicroPhase, vbp: VerificationBlueprint, importable: list[str] | None = None) -> SubtaskSpec  # importable = moduli locali esistenti al momento della micro (fatto del control plane)
class PlanSysEngine
    def run_task(self, task_id: str) -> TaskState
    def _load_or_create_macro_plan(self, task_id: str, log: TaskLog) -> MacroPlan | TaskState
    def _eligible_macro_phase(self, task_id: str, plan: MacroPlan) -> MacroPhase | None
    def _phase_entry_gate(self, task_id: str, plan: MacroPlan, phase: MacroPhase) -> GateReport
    def _phase_synthesis_gate(self, task_id: str, phase: MacroPhase, vbp: VerificationBlueprint, plan: MacroPlan | None = None) -> GateReport  # SCOPED: suite piena solo all'ultima fase; regression = proof delle fasi chiuse
    def _register_proof_commands(self, vbp: VerificationBlueprint) -> None
    def _run_micro(self, task_id: str, micro: MicroPhase, vbp: VerificationBlueprint, worker: Worker, tracker: BudgetTracker, log: TaskLog) -> TaskState | None
```

**PS5 (Engine):** `PlanSysEngine` EREDITA dall'Orchestrator il collaudato di F1/F2 (`_reclaim_orphans`, `_execute_subtask` con resume in-place, `_handle_budget_exhaustion` = budget-consenso, `_finalize`). `work_order` = perimetro=verifica by design: `verification` della micro sono SOLO i suoi `proof:<obligation_id>` (comandi pytest `file::test` registrati dal control plane nel catalogo run_tests via `_register_proof_commands`) — mai la suite intera; la suite gira solo nel `phase_synthesis` gate. Fasi "done" = ps_gates ok (`phase_synthesis` o `phase_entry`); entry gate = ri-esecuzione delle prove dei criteri coperti (fase già provata → chiusa a zero LLM); coverage gate a fine piano (criterio provato = ≥1 obbligo verde ADESSO, ri-eseguito mai creduto). Retry gate: firme di fallimento consecutive identiche = fotocopia vietata → micro failed esplicita (niente replanning in v1). `NeedsDecision` → clarification sul canale approvals F2.3, task blocked; per run non presidiate `RG_PLANSYS_AUTODECIDE=recommended` auto-decide sulla raccomandata di M1 (max 2/fase, actor `policy:autodecide`). Accensione: `rg run --plansys`, `rg eval --plansys` (`run_eval(use_plansys=True)` fa `replace(cfg, plansys_enabled=True)`; report modalità `plansys` nel filename). **Esecuzione della micro (`_run_micro`), i 4 recinti aggiunti dai piloti**: (1) **Scope fisico per-micro** — J riceve `Scope(root, files_owned)` con Router/Worker propri, swap attorno a `_execute_subtask` (PS-D4 meccanico, non fiduciario; le letture restano libere: lo Scope limita solo le scritture); (2) **[PROOF TEST SOURCE]** — il sorgente verbatim dei test della micro (≤120 righe/file) iniettato nell'objective (contract anchoring all'ultimo anello); (3) **[PREVIOUS ATTEMPT FAILED]** — al retry la coda (500 char) dell'output dei proof falliti (l'assertion diff è informazione deterministica); (4) **IMPORTS** — la lista dei moduli locali importabili (esistenti su disco esclusa `tasks/` + posseduti dalle micro precedenti), calcolata nel loop di upsert. **Enum dinamici (batch20 strategia n.1)**: `PhaseCompiler._enum_schema(model, spots)` inietta enum nei punti giusti dello schema (top-level o `$defs`) e passa via `grammar_schema=` — M1 involved=file esistenti, M2 files/proves, M3 micro_id/cmd, M4 path=[file corrente], patch target=[id esistenti]; la grammatica vincola, le liste `[ALLOWED …]` nel volatile informano (F3). **Nomi canonici (PS-D11)**: dopo M3 il control plane sovrascrive id/test_file/test_name (`P1.S1.O1 → test_p1_s1.py::test_p1_s1_o1`, salvo file già esistenti su disco); M4 authora PER FILE (subset vbp, `[EXISTING TEST FILE]`, dedup by score, riconciliazione orfani→funzioni libere quando orfani ≤ libere, pruning AST dei test non legati nei soli file canonici). **Ordine = struttura**: sort topologico delle micro (inputs→owner) in `_norm`, dopo auto-split/dedup e prima della rinumerazione `P{k}.S{i}`.

**PS6 (A/B ufficiale, 2026-08-02 — report `bench/results/ab_ps6_plansys_official_20260802.md`):** baseline 6/13 vs plansys **2/13** su severino-sim @`11e3502` → **verdetto D11: plansys resta gated OFF**. Ma: fallimenti a −44% di token (636K vs 1.143K), utili +9pt, e le ablazioni (T040–42, tutti 0/3) dimostrano che ogni componente CONTIENE il costo dei fallimenti: senza oracle gate +51%, senza ledger +76%, senza entry gate +50% (quest'ultimo "resta con riserva": lo scenario fasi-ridondanti non si è materializzato). Forbice completed≠verified = 0 su 62 run ufficiali TRANNE 1 (T041, under-scoping del Senior). 5 fix identificati (ESITO PS6 nel piano): gate copertura-richiesta su S, synthesis gate scoped, eccezione canonica solo test_*.py, M4 a 4096 (+regola cap ≥ 1,5×p95 dal DB), bisection regressione baseline. Verdetto riapribile dopo i fix + thinking T-SM (`plan_thinking_ab.md`).

**PS4 (M3–M4 + Oracle Qualification):** `oracle_qualification_gate` (PS-D5) qualifica L'ORACOLO prima che J esista — check: esistenza statica via AST, asserzioni reali (niente `assert True`), aggancio al contratto (CORPO+import, mai il nome del test: un `test_subtract` vuoto si aggancerebbe da solo), scope, **red-baseline** (un `new_behavior` che passa ORA non prova niente; import error su modulo mancante = rosso legittimo), green-baseline sui characterization, copertura criteri, mutation probe assert-flip opzionale. `materialize_tests` = control plane (mai J), Scope dedicato ai path del bundle + syntax gate, **guardia anti-perdita**: sovrascrivere un test file esistente non può far sparire test (i nomi vecchi devono sopravvivere) e M4 riceve `[EXISTING TEST FILE]` col sorgente per fonderli. `compile_phase` = M1→M4 + loop qualificazione (max 2 round; violazioni instradate: contenuto→M4, disegno→M3; patch invalida = round fallito loggato, mai crash). `_SingleShot` gestisce il TRONCAMENTO come dato: un retry con istruzione di produrre meno, poi l'errore sale. Smoke live PS4.3: compile_phase completa in 134s con qualificazione verde al primo colpo; nei run precedenti il ciclo patch/rigenerazione è scattato live su M2 e M4.

**PS3 (M1–M2):** M1/M2 sono SINGLE-SHOT (base `_SingleShot`: una chiamata, un parse — le correzioni vivono nel compiler come patch, PS-D6). `validate_analysis` fa l'anti-invenzione MECCANICA (`involved` deve apparire testualmente nella proiezione); `validate_blueprint` impone ownership ESCLUSIVA dei file e perimetri dal ledger. `PhaseCompiler._repair_loop`: max 2 patch (`_request_patch` → schema `BlueprintPatch`, `_apply_patch` deterministico sulle liste patchabili micro/obligations/decisions/artifacts per id/path) + 1 rigenerazione citando le violazioni + `CompileFailed`. `decision_required` → `NeedsDecision` (analisi comunque persistita). Il ledger ora include il **listato repo come fact (max 40)**: a task fresco è l'unico ancoraggio possibile per gli `involved`. Card: `phase_analyst.md`, `work_decomposer.md`. Smoke live PS3.4 (severino-sim, brownfield csv_tools): M1 25s (involved ancorati, 2 decisioni), M2 20s (ownership esclusiva), blueprint renderizzato.

**PS2 (Senior):** `dag_problems` è l'UNICO validatore di grafi del repo (estratto da `roles/planner.py::validate_plan_logic`, che ora lo importa lazy — messaggi identici a F3); `macro_validation_gate` valida id (C\d+/P\d+), grafo e **copertura totale** (criterio scoperto = piano respinto); `SeniorPlanner.run` = 1 chiamata + 1 richiamata correttiva che cita le REGOLE, poi `MacroRejected`. Card `prompts/roles/senior_planner.md`. Smoke live PS2.3 su severino-sim: 3/3 piani validi (12–34s, copertura sempre totale).

**PS1 (Ledger):** `astscan.py` è l'UNICO estrattore di firme del repo (nato in `scripts/check_reference.py`, spostato qui perché il Ledger Builder usa le stesse firme; lo script ora importa da qui). `build_ledger` = deterministico da DB (tool_calls→file toccati, decisions via `StateStore.list_decisions` aggiunto per questo, ps_gates ko→failure, sottofasi completate→artifact) + AST + test file; `project_for_phase` riempie a budget con ordine normativo (criteri e intent SEMPRE, poi firme/test/decisioni/failure, troncamento dichiarato `[LEDGER TRUNCATED…]`).

### `redgiant/core/verify.py` — verifica deterministica (F1.6, D10)

Il trust boundary: tutti i check girano sempre; un check di `verification` sconosciuto è un FAIL (silenzio ≠ successo).

```python
class CheckResult   # name, ok, detail
class Verdict       # verdict pass|fail, checks
def verify_subtask(spec: SubtaskSpec, report: FinishReport, scope: Scope, router: ToolRouter, task_id: str) -> Verdict
```

### `redgiant/core/ablate.py` — leva di ablazione del percorso Worker

Regola di metodo (utente, 2026-08-03): **ogni componente aggiunto dev'essere ablabile**, sennò il suo contributo non è attribuibile. Env var di SOLO A/B, mai contratto di config, mai in produzione — stessa filosofia di `plansys.ablated()`.

| Componente | `RG_WORKER_ABLATE=` | Cosa toglie | Effetto misurato |
|---|---|---|---|
| ricerca | `search` | `search_code` dal catalogo | **0/5 su tutti i gradini**, replicato 3× — il componente portante |
| verifica | `verify` | la verifica deterministica non gira | 8 false dichiarazioni in 5 run (vs 1 in 550+) — compra onestà, non throughput |
| retry | `retry` | nessun secondo tentativo | (da misurare sulla ladder) |
| calcolatrice | `calc` | `calculator` dal catalogo | ~nullo: il tool era invocato nel 40% delle run |
| coerenza | `coherence` | la guardia F4 in scrittura | vedi `data.md` §7.6 |

```python
def worker_ablated(component: str) -> bool
def active_ablations() -> list[str]
```

### `redgiant/core/budget.py` — BudgetTracker (F1.7)

```python
class BudgetTracker
    def __init__(self, store: StateStore, budget: Budget, task_id: str) -> None
    def charge_llm(self, r: LlmResult) -> None
    def charge_tool(self) -> None
    def used(self) -> BudgetUsed
    def exceeded(self) -> str | None
```

### `redgiant/core/orchestrator.py` — Orchestrator v0 (F1.7) + TaskLog (F1.8)

Loop sequenziale su piano statico; pass→next, fail→retry entro budget→failed (la sofisticazione è F4, D11). Ripresa: sottofasi `running` orfane → pending. Stop budget = partial/failed spiegato. **Gate D11 (F3, post-A/B):** se `cfg.planner_enabled` è False (default), piano mancante → `_naive_plan` (1 fase / 1 sottofase do-everything, verification = primo cmd di test noto, zero LLM) e `_replan` ritorna False (fallimento esplicito, niente replanning).

```python
class TaskLog
    def __init__(self, tasks_dir: Path, task_id: str) -> None
    def line(self, actor: str, msg: str) -> None
class Orchestrator
    def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient, router: ToolRouter, assembler: PromptAssembler) -> None
    def run_task(self, task_id: str) -> TaskState
    def _naive_plan(self, task_id: str, log: TaskLog) -> None
def load_static_plan(store: StateStore, task_id: str, plan_file: Path) -> None
```

### `redgiant/eval/harness.py` — Evaluator v0 (F1.10)

Copia del repo in tmp (il sorgente non si sporca), run, poi giudice esterno (`success_cmd`). `completed` vs `verified`: la forbice è la metrica anti-bugia. `useful_tokens` v0 = token delle chiamate in sottofasi completed (linkage fine = debito).

```python
class EvalTask      # id, domain, prompt, repo_dir, plan_file, success_cmd, timeout_s, tags,
                    # writable_globs, test_commands, requires, expected_outcome,
                    # http_allowed_domains (F3b: override per-task della whitelist),
                    # service_script (F3b: servizio locale avviato/terminato dall'harness,
                    # vive nella dir del task NON nel repo — il modello non lo vede)
class EvalResult    # task_id, completed, verified, skipped, total_tokens, useful_tokens,
                    # wall_s, llm_calls, tool_calls, retries
def discover_tasks(tasks_dir: Path) -> list[EvalTask]
def run_eval(profile: str, only: list[str] | None, out_dir: Path, use_planner: bool = False, use_plansys: bool = False) -> Path
def write_report(results: list[EvalResult], profile: str, git_ref: str, out_dir: Path, use_planner: bool = False, use_plansys: bool = False) -> Path
# F3.5: use_planner=True ignora plan.json (genera il Planner); False = statico o
# piano "ingenuo" _naive_plan (baseline D11)
```

### `redgiant/web/jobs.py` + `redgiant/web/app.py` — GUI (F2)

JobQueue: UN worker thread (D7), ciclo di vita del server legato al job (container severino-sim su/giù), config per-task su disco (`data/tasks/<id>/task_config.json`: writable_globs, test_commands, plan, approve_writes), riaccodamento automatico dei task queued/running al riavvio. `cancel` cooperativo. `create_app`: rotte HTML/HTMX (tabella F2.2 del piano — inline in app.py: 10 rotte non giustificano un package), template Jinja2 in `web/templates/`, htmx 2.0.4 vendorizzato in `web/static/`. Avvio: `rg serve` o `scripts/start-gui.ps1` (doppio click). **PS7.1**: `_run_one` seleziona il driver — `cfg.plansys_enabled` E nessun piano statico (`state.plan is None and not tc.get("plan")`) → `PlanSysEngine`, altrimenti `Orchestrator` (default: `[plansys] enabled=false`). **PS7.2**: rotta `GET /tasks/{task_id}/plan/{name}` (read-only, nome vincolato `[A-Za-z0-9._-]+` — mai path traversal, riuso template log.html, `?tail=`); la pagina task riceve `plan_docs` (stem dei .md in `tasks/<id>/plan/`) e `gates` (righe `ps_gate_history` ✓/✗) — sezioni visibili solo se non vuote, zero impatto sui task naive.

```python
def write_task_config(tasks_dir: Path, task_id: str, *, writable_globs: list[str], test_commands: dict[str, list[str]], plan: dict | None = None) -> None
def read_task_config(tasks_dir: Path, task_id: str) -> dict
class JobQueue
    def __init__(self, cfg: Config, store: StateStore) -> None
    def submit(self, task_id: str) -> None
    def cancel(self, task_id: str) -> bool
    def current(self) -> str | None
    def queue_snapshot(self) -> list[str]
def create_app(cfg: Config) -> FastAPI
```

## 4. Database (SQLite, `data/redgiant.db` — DDL in `store.py::_DDL`)

Tutte le tabelle del piano §A5 esistono da F1 (le CREATE sono idempotenti): `tasks`, `plans`, `subtasks`, `llm_calls` (con `cached_tokens`, outcome `ok|timeout|error|invalid` e — TH0.2 — `thinking_tokens INTEGER DEFAULT 0` + `thinking_ms REAL DEFAULT 0`, migrazione additiva idempotente in `init_schema` via ALTER try/except), `tool_calls`, `decisions`, `budgets`, `eval_runs`, `approvals` (già scritta dal router), `checkpoints` (vuota fino a F4), `routing_log` (vuota fino a F6) + 4 indici. WAL, foreign_keys ON. `budget_used`: max(prompt−cached,0)+gen+thinking (il pensiero conta UNA volta, dalla chiamata 1).

## 5. Endpoint / rotte

Rotte GUI: tabella F2.2 del piano (inline in `web/app.py`) + **PS7.2**: `GET /tasks/{task_id}/plan/{name}?tail=` (documenti di piano plansys, read-only). Endpoint llama-server usati: `POST /completion` (json_schema, cache_prompt, seed), `POST /tokenize`, `GET /props`, `POST /slots/0?action=save|restore` (bench).

## 6. Configurazione

V. `config/default.toml` (commentato, con blocco decisioni F0.6) e piano §A6. Novità F1: `security.shell_whitelist` include `python` (serve ai giudici dei task). **Novità PS0:** sezione `[plansys]` (`enabled=false` PS-D9, `max_phases`, `max_micro_per_phase`, `projection_max_tokens`, `m_pass_max_tokens`, `test_author_max_tokens`, `mutation_probe`) → `Config.plansys_enabled: bool` + `Config.plansys: PlansysCfg`. **Novità F3b.1:** chiave `security.http_allowed_domains` (whitelist per `http_get`, default `[]` = niente rete; i task la estendono via task.toml, mai il default). **Novità TH0:** chiavi `[llm] think_open`/`think_close` (marcatori del canale di pensiero, estratti dal chat template incorporato nel GGUF: `<|channel>thought\n` / `<channel|>`; default "" nei profili senza thinking → `complete(think=N)` con marcatori vuoti alza LlmError). **Novità F3 (gate D11):** sezione `[planner]` con `enabled = false` di default → `Config.planner_enabled: bool` — a Planner spento l'Orchestrator usa `_naive_plan` e rifiuta il replanning; `rg eval --planner` riaccende via `dataclasses.replace(cfg, planner_enabled=True)` nell'harness. Pin di piattaforma: v. §6 della versione precedente, invariati (immagine ghcr digest b10200; binari win b10217; GGUF QAT UD-Q4_K_XL sha `e531...6889`).

## 7. Catalogo dei test

`tests/unit/` — 80 test, nessuno tocca il modello (delta PS4 in `test_plansys_gates.py`: validate_verification, oracle gate che qualifica l'oracolo buono e respinge tautologie/scollegati/new_behavior-che-passa, validate_bundle; delta PS5 in `test_plansys_compiler.py`: work_order con verification=proof:*, retry gate anti-fotocopia, bookkeeping fasi/eleggibilità/proof-commands) (delta PS2 in `test_plansys_gates.py`: gate macro su copertura/id/grafo, normalize dei sentinelli, richiamata correttiva del Senior con [RULES] e MacroRejected; delta PS3 in `test_plansys_compiler.py`: anti-invenzione M1, ownership esclusiva M2, _apply_patch replace/add/remove con ValueError su target ignoto, flusso patch→rigenerazione→CompileFailed, NeedsDecision con analisi persistita) (delta PS0 in `test_plansys_artifacts.py`: round-trip+forbid degli artefatti, tetti che mordono, versioning ps_artifacts monotono con KeyError esplicito, renderer deterministico e greppabile, config plansys spenta di default; delta PS1 in `test_plansys_ledger.py`: firme qualificate via AST anche su file rotti, ledger deterministico con decisioni/test/firme, proiezione a budget con obbligatori sempre presenti e troncamento dichiarato) (i conteggi per file sotto sono della fotografia F1; il delta F2 copre: rotte GUI, grant/override/estensioni budget, ripresa, syntax gate, CRLF, scoperta comandi, union strutturale, simmetria oracoli; il delta F3 copre: validazione logica piano/design incl. regola scoped, `normalize_plan` sentinelli+auto-dipendenza, `no_op_edit`, guard `identical_repeat` con esenzione run_tests, gate D11 `_naive_plan`+replan rifiutato):

| File | Dimostra |
|---|---|
| `test_state.py` (6) | roundtrip stato, KeyError su task ignoto, attempts su retry/repair, upsert idempotente, aggregati budget dal DB, versioning monotono del piano |
| `test_prompts.py` (6) | prefisso S1–S4 byte-identico tra build, ordine sezioni+turn markers, append-only che preserva il prefisso, schema in S2 (non in S7), KeyError su ruolo ignoto, sezione TOOLS sempre presente |
| `test_tools.py` (11) | Scope (traversal, globs di scrittura), read_file (troncamento dichiarato), edit_file (unico/ambiguo/mancante/replace_all/prefissi N-TAB), write_file (creazione+scope), write_patch (hunk pulito/respinto con expected/creazione file), run_tests (cmd_id ignoto, whitelist), dispatch (unknown/bad_args come dati, logging completo) |
| `test_verify_and_worker.py` (8) | blocked non passa mai, done+evidenze+output passa, output mancante/evidenze vuote/check sconosciuto = fail, incoerenza WorkerStep come dato |
| `test_thinking.py` (9, TH0) | think=None payload identico, two-call con stop/budget, troncamento pensiero NON errore, marcatori richiesti, TH-D2 parts intatte, clamp con spazio-risposta riservato + overflow esplicito, migrazione DB + budget che conta il pensiero una volta, phase_id come identità, leva RG_THINKING_* col fusibile 1536 |
| `test_web_tool.py` (4, F3b.1) | whitelist vuota = niente rete, schemi/domini (incl. suffisso-truffa), cache che rilegge LA copia a rete spenta, redirect fuori whitelist respinto |
| `test_f3bis_tasks.py` (5, F3b.2) | giudici T030-T032 SODDISFACIBILI con artefatti di riferimento (parametrizzato), servizio T031 vivo (payload+404), parsing harness delle chiavi F3b (whitelist per-task, service_script, domini) |

Integration (marker `llm`): la vera integration è l'Evaluator stesso (T001–T006 + T030–T032 multi-dominio + T040–T042 multi-sessione).

## 8. Regole non negoziabili

D1–D21 (piano §0) + rituale con Passo 2-bis (README) e regola main (merge a ogni major). Operativamente, da F1:

- **D3 operativa**: template di turno + schema nel prompt (S2) + JSON compatto + stop reason controllato + seed fisso.
- **Mai SQL fuori da store.py; mai prompt fuori da assemble.py; mai esecuzione tool fuori dal router.**
- **Il finish del Worker non chiude nulla**: solo `verify_subtask` chiude.
- **I fallimenti dei tool sono dati** per il modello, mai crash del task.

## 8-bis. Numeri di baseline

F0 (invariati): prefill 6.8/30.7/69.6/173.6s @ 1/4/8/16K · gen 35.8 tok/s · riuso 65 vs 7971 · grammatica 0.4–9.8%.
F1 (run ufficiale severino-sim, 2 core): **4/6 verified** (T001/T003/T004/T005: 100% useful, 0 retry, 5-8 chiamate, 45-65s); T002/T006 falliti onesti (debiti F4); forbice completed≠verified = 0; 184k token totali per la run. Report: `bench/results/eval_severino-sim_*.md`.
F3 (A/B ufficiale severino-sim, T001–T010): baseline statica **9/10 verified** (710.106 token, ~27,5 min, unico caduto T008) vs planner **2/10** (814.646 token, ~44 min; T001, T004) → **verdetto D11: Planner default OFF**. Prima run planner (0/10) INVALIDA: working tree sporco. Forbice = 0 in tutte le run. Report: `bench/results/eval_severino-sim_{static,planner}_2026080*.md`.

## 9. Trappole già disinnescate

Le 8 di F0 (v. storia git per il dettaglio: grammatica-non-informa, turn template, troncamento>grammatica, slot restore rotto su b10200, slot-save-path inesistente=morte silenziosa, pip-tools/pip 25.3, ghcr senza tag per-release, prompt di sfratto invertito) più le nuove di F1.11 — il collaudo end-to-end ne ha scovate 8, tutte della stessa famiglia: *l'interfaccia modello↔ambiente*:

- **PATH del venv non ereditata dai subprocess**: `pytest`/`python` si risolvono sull'interprete che esegue Red Giant (fix simmetrico: tool interno E giudice esterno dell'harness).
- **La coerenza cross-campo non è esprimibile in JSON Schema**: un validator Pydantic più severo dello schema trasforma incoerenze semantiche in falsi `LlmInvalidOutput`. La coerenza si verifica nel loop, l'incoerenza è un dato.
- **I diff unificati sono ostili agli E2B**: contesto sbagliato di UNA riga vuota (PEP8: 2 righe tra funzioni, il modello ne mette 1) = fix logicamente corretto respinto in loop. Risposta: `edit_file` come primario.
- **I modelli copiano SEMPRE i prefissi `N<TAB>` di read_file** (in diff e in old_string), regola nella card o no: l'ambiente normalizza.
- **Code `-` vuote spurie** in fondo ai hunk fanno fallire il match dell'intero hunk: potate perché cosmetiche.
- **Echo del nome tool negli args** (`"tool": "edit_file"`): tollerato dal router.
- **Senza seed, llama-server usa un seed casuale per richiesta**: run non confrontabili (T003/T005 passavano o fallivano a lotteria). Seed fisso 42 nel client.
- **Il modello dichiara azioni mai eseguite** ("answer written") — la verifica lo becca (expected_outputs), e la card ora dice esplicitamente "i pensieri non cambiano il mondo"; `write_file` dà il primitivo di creazione che mancava.

**Batch F2 (campagna di collaudo 2026-08-01/02 — 3 giri utente + batteria + 4 retest):**

- **⭐ Il derail da apice** (causa radice dei "loop caotici" 60+ chiamate): un `"` non escapato dentro un valore stringa chiude legalmente la stringa JSON; il modello deraglia e l'unica uscita grammaticale era `finish:null`. Fix STRUTTURALE: `WorkerStep` = union discriminata (il ramo incompleto non è generabile — probe live 8/8) + regola anti-apici nel preambolo.
- **Race submit/ripresa**: la ripresa post-approvazione arrivava mentre il worker rilasciava il task appena bloccato → scartata come duplicato → `queued` eterno. Fix: guard rimosso + sweep DB post-job.
- **CRLF dei checkout git Windows**: read_file mostra LF, il file è CRLF → `old_string` mai trovato (loop 12 step). Fix: edit_file lavora e scrive in LF.
- **Consenso a gettone → grant permanenti** per (famiglia-scrittura, path) nel task, con override/revoca dell'utente; il `no` è permanente uguale; `no→sì` riaccoda un task bloccato.
- **Contabilità budget rotta dalla cache**: il server riporta più cache del conteggio prompt client → righe negative che azzeravano il consumo e DISATTIVAVANO il budget. Fix: clamp per riga `MAX(prompt−cached,0)+gen` (il budget misura il lavoro).
- **Budget check su task finito**: chiedeva l'estensione dopo il PASS finale. Fix: prima si guarda se c'è lavoro, poi il budget.
- **Guard anti-loop aggirabile**: contava i fallimenti consecutivi, il modello li spezzava alternando letture ok. Fix: conteggio CUMULATIVO per (tool, errore) nel tentativo (consiglio a 3 e 5, stop a 8).
- **`not_found_in_file` non insegnava niente**: ora edit_file restituisce la regione più simile del file (`closest_match`) — il tool corregge l'old_string del giro dopo (mismatch tipico: righe vuote PEP8).
- **Simmetria degli oracoli** (dal retest D3: lavoro fatto, test verdi, worker "blocked" → bocciato): check oggettivi tutti verdi con test eseguiti = pass; i soggettivi (worker_done, evidence) diventano warning → `completed_with_warnings`.
- **Riavvio container a ogni ciclo di consenso** (~1 min di ricarica pesi a click): vivo con task attivi, spegnimento dopo `idle_shutdown_s`=30' (decisione utente, reaper thread).
- **Ripresa da zero post-approvazione**: ora IN-PLACE — il contesto volatile è salvato al blocco (`resume_<subtask>.ctx`) e si riparte dallo step esatto con la KV calda.
- **Troncamento che bruciava il tentativo**: gestito in-loop come dato; `worker.step_max_tokens` 512→768.
- **Doppio submit dal form, task queued muti, unreachable da processo morto**: anti doppio-submit, banner coda/avvio-server/ripresa con pulse e ultima attività dal log, `start-gui.ps1`, riaccodamento automatico al riavvio.

**Batch A/B ufficiale (2026-08-02 — run Planner 0/10, autopsia):**

- **⭐ Prompt e validatore devono muoversi INSIEME**: la revisione scoped-verification ha riscritto la regola 2 del Designer cancellando l'istruzione "i valori di `verification` sono ESATTAMENTE i cmd id noti". Il validatore (rimasto giusto) respingeva tutto; il modello non può indovinare una regola che nessuno gli dice: 6 task su 10 morti senza una tool call. Corollario: ogni regola del validatore deve avere la sua frase nel prompt del ruolo, e viceversa.
- **⭐ Le run ufficiali si lanciano SOLO da working tree pulito**: l'A/B è partito con modifiche non committate — la run 2 ha misurato uno stato intermedio mai collaudato e l'hash git nel report mentiva. Prima si committa, poi si misura.
- **`depends_on` spazzatura dal Planner** (`["none"]`, `["geometry.py"]`): i sentinelli inequivoci sono riparati da `normalize_plan`; la richiamata correttiva ora cita la regola (`depends_on` solo id di fasi del piano, root = `[]`), non solo i sintomi.
- **Loop di edit no-op**: `edit_file` con old==new "riusciva" senza cambiare nulla → 15 ripetizioni identiche fino a esaurire gli step, invisibili al guard (ogni chiamata era un successo). Fix doppio: `no_op_edit` è un errore, e la chiamata identica consecutiva conta nel guard cumulativo come `identical_repeat` anche se ok.

**Batch plansys PS4 (smoke live 2026-08-03 — 5 trappole pagate sul campo):**

- **`maxLength` grande = grammatica che uccide il server**: `Field(max_length=4000)` su una stringa diventa una ripetizione GBNF `{0,4000}` che llama-server rifiuta con **400 Bad Request**. I tetti stretti (≤300) reggono; i tetti larghi si tolgono (il limite vero è il budget di generazione).
- **M2 inventa criteri** (`proves: [C3, C4]` su un piano C1–C2): sentinello inequivoco → strip deterministico prima della validazione (come "none" in depends_on), non un giro di patch.
- **M4 sovrascrive i test esistenti**: scrivendo il "file completo" perdeva i test già presenti. Guardia deterministica in materializzazione (i nomi vecchi devono sopravvivere) + `[EXISTING TEST FILE]` nel contesto di M4.
- **Il troncamento nei passi M** va trattato come in F2: un retry con "produce a SMALLER object", poi errore esplicito — alzare il budget all'infinito non è una strategia (2048→3072 per M4 e 1024→1536 per M1-M3 sono i valori misurati).
- **La patch è una stringa libera dentro uno schema**: `payload_json` non è vincolato dalla grammatica → può essere deforme. La rivalidazione post-patch va SEMPRE try-ata: patch invalida = round fallito loggato, mai crash del compile.

**Rerun A/B ufficiale (2026-08-02, @611d894 — Planner 2/10 vs baseline 9/10: verdetto D11):**

- **Auto-dipendenza del Planner** (`P1 depends on P1`): altro sentinello dopo "none" — 2 task morti in 2 chiamate. Riparato in `normalize_plan` (dep == id → rimossa).
- **Il guard `identical_repeat` mordeva l'oracolo**: contava anche i `run_tests` identici e abortiva le sottofasi di sola analisi ("esegui pytest e registra i fallimenti") a 8 esecuzioni. Esentato, coerente con l'esclusione esistente di `tests_failed`.
- **Fasi ridondanti**: su task banali il Planner genera 3-4 fasi che ripetono lo stesso lavoro (P2 che ricerca ciò che P1 ha già trovato) — costo puro, nessun guadagno. È il volto strutturale dell'overhead di governance, non un bug puntuale.
- **Sottofasi-analisi artificiali**: la revisione scoped spinge il Designer a creare sottofasi "analizza e produci report.txt" con output che il Worker non produce naturalmente → 3 tentativi bloccati → replan. Il perimetro giusto non basta: gli expected_outputs devono essere artefatti del lavoro vero, non compiti in classe.
- **La verifica scoped sposta l'errore in avanti**: T009 rerun — P1.S1 "passa" sugli expected_outputs ma contiene `slugify` invece di `slug`; il falso positivo intermedio esplode solo sull'ultima sottofase. Trade-off accettato consapevolmente (F3.2-REVISIONE), ora con la sua prima evidenza di costo.

**Piloti PS5 + BATCH20 n.1–8 (2026-08-01/02, ~130 run end-to-end — la campagna che ha prodotto PS-D11 e le finding F15–F18 del README):**

- **⭐ La `tasks_dir` dentro la workdir inquina i prompt** (batch n.5): log/blueprint/ledger con ULID per-run entravano nei listati (`_existing_files`, fatti del ledger, `_repo_listing`) → prompt diversi a ogni run → seed 42 irrilevante. Esclusa ovunque. Corollario: su GPU il seed fisso NON è determinismo comunque (batching CUDA) — i batch GPU classificano famiglie, i numeri comparabili sono solo severino-sim.
- **⭐ M1 inventa i nomi dei file** (6/20 nel batch n.1): enum GBNF dei file ESISTENTI su `involved` → famiglia a zero da allora. Stessa medicina su M2 (files/proves), M3 (micro_id/cmd), M4 (path), patch (target).
- **⭐ M3 nomina test_X, M4 scrive test_Y** (11/20 nel batch n.3): i nomi canonici li impone il control plane (`P1.S1.O1 → test_p1_s1.py::test_p1_s1_o1`) — il modello crea il significato, il control plane l'identità.
- **⭐ Test new_behavior verdi a modulo assente** (5/20 nel batch n.7): import del bersaglio dentro la funzione o in try/except → la red baseline non può fallire. Obbligo di import TOP-LEVEL in `validate_bundle` → 0/20 al batch n.8.
- **⭐ Proof con import irrisolvibili = sessione J invincibile by design** (pilota n.3): il test importava un modulo che NESSUNA micro possiede. Check "ghost imports" in `validate_bundle` (stdlib+pytest+esistenti+micro precedenti).
- **Micro ordinate col deposito invertito** (pilota n.1): storage.py schedulata prima di models.py → J 4 step contro lo scope. Sort topologico inputs→owner in `_norm`.
- **J importa moduli futuri** (pilota n.2): `import storage` prima che storage.py esistesse. Riga IMPORTS nel work order coi moduli locali esistenti.
- **La prosa comanda più dello scope** (pilota n.4): goal "create both storage.py and report.py" su micro che possiede solo report.py → J insegue la prosa. `validate_blueprint`: goal/boundary citano solo file del perimetro.
- **J sovrascrive i test qualificati** (pilota n.18 pre-batch): PS-D4 era solo scritto. Scope fisico per-micro (`Scope(root, files_owned)`) — il perimetro applicato meccanicamente.
- **Covers duplicati → proves oltre il tetto → crash** (batch n.5 run 11): dedup in `normalize_macro` + guardia `len<8` nell'auto-assegnazione. Corollario generale: ogni lista che il control plane riempie automaticamente deve rispettare i tetti degli schemi.
- **La patch eredita il budget del chiamante** (batch n.7 run 15): `_request_patch` con budget m_pass troncava i payload di M4 (file interi). `max_tokens` passato dal `_repair_loop`.
- **Micro multi-file = contesto esploso** (7674 tok): cap meccanico 1 file nuovo/micro + AUTO-SPLIT dal control plane con rinumerazione (la patch non sa "dividere"; il codice sì).
- **Il retry cieco fotocopia**: senza l'output del test fallito J riproduce lo stesso errore. `[PREVIOUS ATTEMPT FAILED]` con la coda del proof — spesso comunque non basta (limite di capacità, F18): la fotocopia resta vietata.
- **PhaseAlreadySatisfied ingannato dai test vuoti**: richiede anche che i files_owned esistano, non solo proofs verdi.
- **⭐ Il synthesis gate su suite fornita multi-fase è morte certa a P1** (A/B ufficiale: 3 morti su 13 — T007, T010, T040): `synthesis_cmds=pytest` esegue TUTTA la suite alla chiusura della fase, ma i test delle fasi future sono rossi per definizione. Fix a piano (ESITO PS6): sintesi SCOPED (proof della fase + test delle fasi già chiuse), suite piena solo al coverage finale.
- **⭐ Il Senior sottodimensiona la richiesta e nessun gate se ne accorge** (T041 ufficiale, l'unica forbice completed≠verified): criteri = un terzo della richiesta, coverage interno verde, giudice esterno `No module named 'hist'`. Fix a piano: i file NOMINATI nella richiesta devono comparire negli artifacts di qualche fase (gate deterministico su S).
- **L'eccezione "test_file esistente" dei nomi canonici tiene anche file non-py** (T003 ufficiale: M3 punta a `test.php` esistente → non canonicalizzato → morte in repair). Fix a piano: eccezione solo per `test_*.py` esistenti.
- **⭐ Varianza run-to-run ANCHE su severino-sim** (ri-misura PS6-bis: baseline 6/13→8/13 a codice IDENTICO, 4 task flippati): lo stato della cache del server cambia i numeri (llama.cpp #2838: prompt valutato a freddo ≠ con cache, numericamente) — banda **±2/13**. Regola permanente: verdetti ufficiali SOLO su run multiple mediate; le diagnosi "è il codice, non il rumore" su run singola sono vietate (già costata una diagnosi troppo sicura sulla regressione 9/10→6/10, da rifare come bisection multi-run).
- **⭐ VERDETTO CAMPAGNA THINKING (TH3, 2026-08-03):** thinking a tempo pieno **OFF in produzione per ogni ruolo** — TH2 ufficiale (2 batterie/braccio): Giano pensante 1,5/13 medio vs controllo 1,5/13, Δ=0 a 1,4× token e 1,9× wall pulito. Lo scalpo T002 (batteria 1, mai passato nella storia) non riprodotto in batteria 2: reale ma nel rumore. Leva futura NON misurata: thinking selettivo al retry (TH-bis). Meccanica two-call pronta dietro `RG_THINKING_ROLES` per F7/chat.
- **⭐ Il muro migra verso chi non pensa** (TH1, 7 bracci × 20 run GPU): thinking su M → oracoli più esigenti (O2/O3) → muore J (0-2/20); thinking su J → morti J DIMEZZATE (5/20 vs 10-11) e 4/20 verdi a 1,6× costo; thinking su tutti → i due effetti si annullano a 4× costo (1/20). Regola: ogni potenziamento di un ruolo si misura sull'INTERA catena. Corollario fixato: M2 pensante copia la fase sbagliata nel phase_id → identità imposta dal control plane in `_norm` (5/20 nel round 1).
- **Residuo NON risolto (il muro, F18)**: ~metà delle morti residue è J che non riproduce i formati esatti chiesti dai proof (report/storage) pur vedendo sorgente dei test e assertion diff; gli f-string annidati restano una debolezza riconosciuta ma non attuata dal modello (hint + regola 12 della card). Leva proposta e in attesa di decisione: emendamento PS-D6 (un tentativo informato in più prima del blocco fotocopia).

## 10. Debito tecnico aperto

| Cosa | Perché rimandato | Quando |
|---|---|---|
| Slot-save inutilizzabile (restore non ripristina il riuso) | bug/limite di b10200 | F5.4 su build nuova |
| `useful_tokens` v0 approssimato (per sottofase, non per step) | serve linkage chiamata→tool | F5.2 con la strumentazione |
| Scarto binari win b10217 vs riferimento b10200 | b10200 senza asset Windows | prossimo bump di pin |
| T002 fallisce (il modello non capovolge "lib off-limits ⇒ bug nel chiamante") | è un limite di *ragionamento*, non d'ambiente: serve il retry con strategia del Supervisor | F4.2 (`retry_strategy`) |
| T006 fragile (pattern di ricerca sbagliati al retry) | idem: strategia di retry | F4 |
| `BudgetTracker.charge_*` no-op (i log li scrivono client/router) | API tenuta per il BudgetManager F4.5 | F4.5 |
| T007 verde ma laborioso (41 chiamate: giri di lettura ridondanti) | serve contesto selettivo e strategia | F4 + F5 |
| Registro delle tolleranze modello-specifiche (N-TAB, CRLF, code vuote, closest_match, soglie): euristiche overfittate su E2B QAT b10200 | vanno A/B-ate come sistema al cambio di modello/build | F6/F8 |
| Nessun task sintetico "sporco" (repo grande, rumore, test lenti) | il micro-mondo non prepara a F8 | pre-F8 |
| I marcatori di turno S1→S7 (`<start_of_turn>`) NON sono token speciali di questo GGUF (7 token testuali); il protocollo nativo è `<|turn>`/`<turn|>` (control 105/106, scoperto in TH0) | funziona così da F0 (60/60 misurato) — cambiare ora invaliderebbe la comparabilità di tutta la serie storica | A/B dedicato post-TH3, insieme al retest tolleranze |
| Streaming dei token in GUI per il percorso chat (decisione utente TH0: ~15s di pensiero per chiamata sono accettabili SE l'utente vede lo stream) | il runtime attuale è batch/non-streaming (D7: task asincroni); serve solo per l'uso conversazionale quotidiano | F7 (advice/chat), insieme al worker quotidiano con thinking |
| Evaluator senza varianza multi-seed (1 run = 1 traiettoria) | costa CPU; serve per distinguere "funziona" da "è passato" | F6 |
| `task_config.json` su file = seconda fonte di stato oltre al DB | uso single-writer, fallimento benigno e visibile | con l'evoluzione GUI di F4 |
| Protocollo umano = segreteria (solo ultima risposta, niente cronologia) | il dialogo vero è il protocollo F4 | F4.2/F4 GUI |
| Overhead di governance (utente, post-A/B): ~10× chiamate in modalità planner sui micro-task, 710K token per la batteria baseline — accettato come overhead sperimentale by design, ma va affrontato | serve la policy when-to-plan (pianificare solo quando paga) e la riduzione dei giri (sessioni multiple per sottofase, replan) | F6 (routing/Assessor) + dati F8 |

## 11. Il perché delle scelte non ovvie

Ereditate da F0 (QAT, digest-pin, 2 core, ctx 16K nel sim, niente framework, JSON, Final Reviewer assorbito) più:

- **Perché `edit_file` e non diff più tolleranti all'infinito**: si adatta l'ambiente alla natura del modello invece di combatterla — il formato a sostituzione esatta è verificabile (unicità), atomico, e l'evidenza empirica (round 5→6: T001/T004/T005 da 20+ chiamate fallite a 5-6 pulite) chiude la discussione.
- **Perché il seed è fisso**: una pipeline deterministica è debuggabile e i suoi eval sono confrontabili; la "creatività" non è un valore qui (specsheet §3).
- **Perché la connessione SQLite è per-operazione**: la GUI (F2) porterà thread; niente stato condiviso = niente lock nostri.
- **Perché lo step-log**: 20 chiamate/5 tool era invisibile prima; l'osservabilità §20 vale anche per i passi interni del Worker.

## 12. Cosa NON esiste ancora

Il sistema "Planner come autore + Gate" (`plan_planner_system.md` — seed, da estendere e implementare: plan-as-artifact/renderer, gate d'ingresso fase, retry/replan-deve-differire, ledger di task) · Debugger/Supervisor/LoopGuard/Checkpoint/BudgetManager (F4) · ContextBuilder/CacheProbe/SlotManager/Compressor (F5) · routing/Classifier/Assessor (F6) · tool web e verifica citazioni (F7, salvo `http_get` previsto in F3-bis) · deploy (F8). Il chatbot Laravel 13 vive in un altro scenario (F8). **Esiste ma è SPENTO di default:** Planner/PhaseDesigner/replanning (gate D11, `planner.enabled=false` — si riaccende con `rg eval --planner`). Esclusi per design: multi-modalità, multi-modello, parallelismo tra agenti, API JSON pubblica.

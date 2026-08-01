# Red Giant — Codebase Reference (atlante)

**Aggiornato al:** 2026-08-01 · **Versione repo:** `v2.0.0` · **Fase completata:** F1 (nucleo deterministico + Worker)
**Regola:** questo documento descrive **il codice che esiste**, non quello pianificato (per quello c'è [plan_red_giant.md](plan_red_giant.md)). Verifica meccanica: `python scripts/check_reference.py` — bloccante nel rituale di fine fase.

---

## 1. Indice "dove sta cosa"

| Cerchi… | Vai in… |
|---|---|
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
| Evaluator e task sintetici T001–T006 | `redgiant/eval/` |
| CLI di sviluppo (`rg`) | `redgiant/cli.py` |
| GUI web | **non esiste ancora** (F2) |

## 2. Albero dei file (reale, a fine F1)

```text
RedGiant/
├── pyproject.toml / requirements.lock / LICENSE (MIT+attribution) / README.md / logo.png
├── config/{default.toml, profiles/{dev-fast,severino-sim,severino}.toml}
├── docker/severino-sim/compose.yml     # 2 core (≈4 di Severino), 10g, digest-pinned b10200
├── scripts/{download-llama,download-model,start-llama}.ps1, check_reference.py
├── bench/{schemas_probe.py, run_bench.py, results/}
├── redgiant/
│   ├── __init__.py (__version__) · config.py · cli.py
│   ├── state/{models.py, store.py}
│   ├── llm/{client.py, schema.py}
│   ├── prompts/{assemble.py, preamble.md, roles/worker.md}
│   ├── tools/{base.py, fs.py, search.py, proc.py, router.py}
│   ├── roles/{base.py, worker.py}
│   ├── core/{orchestrator.py, verify.py, budget.py}
│   └── eval/{harness.py, tasks/T001..T006}
└── tests/unit/  (31 test)
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
    def complete(self, parts: PromptParts, *, role: str, schema: type[BaseModel] | None = None, max_tokens: int, temperature: float | None = None, task_id: str | None = None, subtask_id: str | None = None, cache_prompt: bool = True) -> LlmResult
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

`edit_file` è lo strumento di editing PRIMARIO (i diff unificati sono ostili agli E2B — evidenza F1.11); normalizza i prefissi `N<TAB>` che i modelli copiano da `read_file`. `write_file` crea file nuovi. `write_patch` resta per edit multi-punto, con matching tollerante (prefissi numerici, whitespace, code `-` vuote spurie).

**Syntax gate (post-F1, richiesta utente):** ogni writer verifica la sintassi del contenuto risultante PRIMA della scrittura atomica (`.py` ast.parse, `.php` php -l se disponibile, `.json`, `.toml`); sintassi rotta = scrittura rifiutata con `syntax_error` + dettaglio riga — un file rotto non esiste mai su disco.

```python
class ReadFileArgs
class ListFilesArgs
class WritePatchArgs
class EditFileArgs
class WriteFileArgs
def syntax_check(path: Path, content: str) -> str | None
def read_file(scope: Scope, path: str, start_line: int = 1, end_line: int | None = None) -> ToolResult
def list_files(scope: Scope, glob: str, max_results: int = 200) -> ToolResult
def edit_file(scope: Scope, path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult
def write_file(scope: Scope, path: str, content: str) -> ToolResult
def write_patch(scope: Scope, path: str, unified_diff: str) -> ToolResult
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

ReAct a passo singolo vincolato: un `WorkerStep` per step, contesto in append puro (KV cache riusata). L'incoerenza action↔payload NON è un validator (la grammatica non può esprimerla): è un dato gestito nel loop. Il `finish` non chiude la sottofase: la chiude la verifica.

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

### `redgiant/core/verify.py` — verifica deterministica (F1.6, D10)

Il trust boundary: tutti i check girano sempre; un check di `verification` sconosciuto è un FAIL (silenzio ≠ successo).

```python
class CheckResult   # name, ok, detail
class Verdict       # verdict pass|fail, checks
def verify_subtask(spec: SubtaskSpec, report: FinishReport, scope: Scope, router: ToolRouter, task_id: str) -> Verdict
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

Loop sequenziale su piano statico; pass→next, fail→retry entro budget→failed (la sofisticazione è F4, D11). Ripresa: sottofasi `running` orfane → pending. Stop budget = partial/failed spiegato.

```python
class TaskLog
    def __init__(self, tasks_dir: Path, task_id: str) -> None
    def line(self, actor: str, msg: str) -> None
class Orchestrator
    def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient, router: ToolRouter, assembler: PromptAssembler) -> None
    def run_task(self, task_id: str) -> TaskState
def load_static_plan(store: StateStore, task_id: str, plan_file: Path) -> None
```

### `redgiant/eval/harness.py` — Evaluator v0 (F1.10)

Copia del repo in tmp (il sorgente non si sporca), run, poi giudice esterno (`success_cmd`). `completed` vs `verified`: la forbice è la metrica anti-bugia. `useful_tokens` v0 = token delle chiamate in sottofasi completed (linkage fine = debito).

```python
class EvalTask      # id, domain, prompt, repo_dir, plan_file, success_cmd, timeout_s, tags,
                    # writable_globs, test_commands, requires, expected_outcome
class EvalResult    # task_id, completed, verified, skipped, total_tokens, useful_tokens,
                    # wall_s, llm_calls, tool_calls, retries
def discover_tasks(tasks_dir: Path) -> list[EvalTask]
def run_eval(profile: str, only: list[str] | None, out_dir: Path) -> Path
def write_report(results: list[EvalResult], profile: str, git_ref: str, out_dir: Path) -> Path
```

### `redgiant/web/jobs.py` + `redgiant/web/app.py` — GUI (F2)

JobQueue: UN worker thread (D7), ciclo di vita del server legato al job (container severino-sim su/giù), config per-task su disco (`data/tasks/<id>/task_config.json`: writable_globs, test_commands, plan, approve_writes), riaccodamento automatico dei task queued/running al riavvio. `cancel` cooperativo. `create_app`: rotte HTML/HTMX (tabella F2.2 del piano — inline in app.py: 10 rotte non giustificano un package), template Jinja2 in `web/templates/`, htmx 2.0.4 vendorizzato in `web/static/`. Avvio: `rg serve` o `scripts/start-gui.ps1` (doppio click).

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

Tutte le tabelle del piano §A5 esistono da F1 (le CREATE sono idempotenti): `tasks`, `plans`, `subtasks`, `llm_calls` (con `cached_tokens` e outcome `ok|timeout|error|invalid`), `tool_calls`, `decisions`, `budgets`, `eval_runs`, `approvals` (già scritta dal router), `checkpoints` (vuota fino a F4), `routing_log` (vuota fino a F6) + 4 indici. WAL, foreign_keys ON.

## 5. Endpoint / rotte

Nessuna rotta nostra (GUI = F2). Endpoint llama-server usati: `POST /completion` (json_schema, cache_prompt, seed), `POST /tokenize`, `GET /props`, `POST /slots/0?action=save|restore` (bench).

## 6. Configurazione

V. `config/default.toml` (commentato, con blocco decisioni F0.6) e piano §A6. Novità F1: `security.shell_whitelist` include `python` (serve ai giudici dei task). Pin di piattaforma: v. §6 della versione precedente, invariati (immagine ghcr digest b10200; binari win b10217; GGUF QAT UD-Q4_K_XL sha `e531...6889`).

## 7. Catalogo dei test

`tests/unit/` — 31 test, nessuno tocca il modello:

| File | Dimostra |
|---|---|
| `test_state.py` (6) | roundtrip stato, KeyError su task ignoto, attempts su retry/repair, upsert idempotente, aggregati budget dal DB, versioning monotono del piano |
| `test_prompts.py` (6) | prefisso S1–S4 byte-identico tra build, ordine sezioni+turn markers, append-only che preserva il prefisso, schema in S2 (non in S7), KeyError su ruolo ignoto, sezione TOOLS sempre presente |
| `test_tools.py` (11) | Scope (traversal, globs di scrittura), read_file (troncamento dichiarato), edit_file (unico/ambiguo/mancante/replace_all/prefissi N-TAB), write_file (creazione+scope), write_patch (hunk pulito/respinto con expected/creazione file), run_tests (cmd_id ignoto, whitelist), dispatch (unknown/bad_args come dati, logging completo) |
| `test_verify_and_worker.py` (8) | blocked non passa mai, done+evidenze+output passa, output mancante/evidenze vuote/check sconosciuto = fail, incoerenza WorkerStep come dato |

Integration (marker `llm`): la vera integration è l'Evaluator stesso (T001–T006).

## 8. Regole non negoziabili

D1–D21 (piano §0) + rituale con Passo 2-bis (README) e regola main (merge a ogni major). Operativamente, da F1:

- **D3 operativa**: template di turno + schema nel prompt (S2) + JSON compatto + stop reason controllato + seed fisso.
- **Mai SQL fuori da store.py; mai prompt fuori da assemble.py; mai esecuzione tool fuori dal router.**
- **Il finish del Worker non chiude nulla**: solo `verify_subtask` chiude.
- **I fallimenti dei tool sono dati** per il modello, mai crash del task.

## 8-bis. Numeri di baseline

F0 (invariati): prefill 6.8/30.7/69.6/173.6s @ 1/4/8/16K · gen 35.8 tok/s · riuso 65 vs 7971 · grammatica 0.4–9.8%.
F1 (run ufficiale severino-sim, 2 core): **4/6 verified** (T001/T003/T004/T005: 100% useful, 0 retry, 5-8 chiamate, 45-65s); T002/T006 falliti onesti (debiti F4); forbice completed≠verified = 0; 184k token totali per la run. Report: `bench/results/eval_severino-sim_*.md`.

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

## 10. Debito tecnico aperto

| Cosa | Perché rimandato | Quando |
|---|---|---|
| Slot-save inutilizzabile (restore non ripristina il riuso) | bug/limite di b10200 | F5.4 su build nuova |
| `useful_tokens` v0 approssimato (per sottofase, non per step) | serve linkage chiamata→tool | F5.2 con la strumentazione |
| Scarto binari win b10217 vs riferimento b10200 | b10200 senza asset Windows | prossimo bump di pin |
| T002 fallisce (il modello non capovolge "lib off-limits ⇒ bug nel chiamante") | è un limite di *ragionamento*, non d'ambiente: serve il retry con strategia del Supervisor | F4.2 (`retry_strategy`) |
| T006 fragile (pattern di ricerca sbagliati al retry) | idem: strategia di retry | F4 |
| `BudgetTracker.charge_*` no-op (i log li scrivono client/router) | API tenuta per il BudgetManager F4.5 | F4.5 |

## 11. Il perché delle scelte non ovvie

Ereditate da F0 (QAT, digest-pin, 2 core, ctx 16K nel sim, niente framework, JSON, Final Reviewer assorbito) più:

- **Perché `edit_file` e non diff più tolleranti all'infinito**: si adatta l'ambiente alla natura del modello invece di combatterla — il formato a sostituzione esatta è verificabile (unicità), atomico, e l'evidenza empirica (round 5→6: T001/T004/T005 da 20+ chiamate fallite a 5-6 pulite) chiude la discussione.
- **Perché il seed è fisso**: una pipeline deterministica è debuggabile e i suoi eval sono confrontabili; la "creatività" non è un valore qui (specsheet §3).
- **Perché la connessione SQLite è per-operazione**: la GUI (F2) porterà thread; niente stato condiviso = niente lock nostri.
- **Perché lo step-log**: 20 chiamate/5 tool era invisibile prima; l'osservabilità §20 vale anche per i passi interni del Worker.

## 12. Cosa NON esiste ancora

GUI web (F2) · Planner/PhaseDesigner e piano dinamico (F3) · Debugger/Supervisor/LoopGuard/Checkpoint/BudgetManager (F4) · ContextBuilder/CacheProbe/SlotManager/Compressor (F5) · routing/Classifier/Assessor (F6) · tool web e verifica citazioni (F7) · deploy (F8). Il chatbot Laravel 13 vive in un altro scenario (F8). Esclusi per design: multi-modalità, multi-modello, parallelismo tra agenti, API JSON pubblica.

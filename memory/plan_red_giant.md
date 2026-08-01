# Red Giant — Piano di sviluppo

**Versione piano:** 1.1 (riscrittura ossessiva)
**Data:** 2026-08-01
**Specsheet di riferimento:** [small-model-powerhouse-specsheet.md](small-model-powerhouse-specsheet.md) (v0.1)
**Atlante della codebase:** [codebase_reference.md](codebase_reference.md) — aggiornato a ogni fine fase, mai dopo.
**Stato:** ⬜ non iniziato — prossima azione: Fase 0, sottofase 0.1

> **Legenda:** 🧑 richiede l'utente · 🤖 fa l'agente · 🔎 verifica di fase · ⚠️ criticità · 📌 da registrare nel codebase_reference
>
> Le firme e i percorsi in questo piano sono **il contratto**: se durante l'implementazione una firma deve cambiare, si cambia *prima* qui (con la ragione), poi nel codice. Piano e codice non divergono mai in silenzio.

---

## 0. Decisioni vincolanti (esito del brainstorming 2026-08-01)

Integrano la specsheet e prevalgono in caso di conflitto.

| # | Decisione | Motivo |
|---|---|---|
| D1 | **Modello: Gemma 4 E2B, Q4, GGUF.** E4B *solo* come riferimento di confronto nell'Evaluator. | Validare sul modello più piccolo possibile; su E4B sarà semplicemente più performante. |
| D2 | **Runtime: llama.cpp (`llama-server`)**, API OpenAI-compatible + endpoint nativi (`/completion`, `/slots`, `/props`). | Constrained decoding (GBNF/JSON Schema) e controllo fine della KV cache; Ollama nasconde queste leve. |
| D3 | **Constrained decoding obbligatorio** su ogni output di ruolo: il sampler non può produrre output fuori schema. | Elimina alla radice la classe "output malformato" (§12/§18 spec). |
| D4 | **Formato di scambio: JSON** (non YAML). YAML solo nei documenti per umani. Gli esempi YAML della specsheet si leggono come JSON equivalente. | JSON è grammar-friendly ed è il formato nativo del guided decoding di llama.cpp. |
| D5 | **Hardware target: Severino** (Ryzen 3 5300U Zen 2 4c/8t @15W, CPU-only, iGPU inutilizzabile). All'MVP: 32 GB dual channel, **max 4 core** a Red Giant+llama-server (lo stack homelab resta acceso). | Inferenza sul PC di un non-prosumer, non su uno Strix Halo. Bottleneck = CPU (prefill), non RAM. |
| D6 | **Tre profili:** `dev-fast` (questo PC, RTX 4080 Super) · `severino-sim` (Docker CPU-only, cpuset 4 core, RAM limitata) · `severino` (box reale via Tailscale). **Metriche ufficiali solo CPU-only**; verifica di fase su `severino-sim` o Severino. | Il divario dev/prod (~50-100×) è il rischio n°1: il tuning su GPU nasconde l'economia dei token. |
| D7 | **Batch, strettamente sequenziale:** una inferenza alla volta, task = job asincroni. Modello residente per la durata del task, scaricato alla fine. | L'inferenza satura i core allocati; il `keep_alive` corto homelab vale per l'uso occasionale, non per task da decine di chiamate. |
| D8 | **Contesto piccolo by design: ~4-8K token/chiamata** (numeri definitivi dai bench F0), anche se il modello supporta di più. | Prefill lungo = minuti persi per chiamata su CPU; KV grossa = RAM sottratta allo stack. |
| D9 | **Prompt a prefisso comune** (preambolo statico condiviso + suffisso di ruolo), ordine di assemblaggio stabile S1→S7 (v. §A4). | Senza riuso del prefisso la pipeline multi-ruolo non è fattibile su CPU. Ispirazione: Dwarf Star di antirez — lavorare forte sul prefill. |
| D10 | **Verifica deterministica ovunque possibile**; Verifier-modello solo senza oracolo meccanico. Il Phase Designer **decompone preferendo sottofasi meccanicamente verificabili**. | Un verificatore piccolo quanto il worker approva errori plausibili. |
| D11 | **Ogni ruolo cognitivo si guadagna il posto coi numeri** (A/B nell'Evaluator). Metrica guida: **token utili / token totali**. | Anti-paradosso dell'overhead: mai più governance che lavoro. |
| D12 | **Python** per tutto il deterministico; **GUI: FastAPI + HTMX + SQLite**, processo unico, zero build frontend (htmx.min.js vendorizzato in `redgiant/web/static/`). | Se l'interfaccia è scomoda, l'utente non testa a fondo. |
| D13 | **Prompt interni in inglese**; interazione utente e documentazione in italiano. | I modelli piccoli rendono meglio in inglese. |
| D14 | **Pinning rigoroso** (lockfile, versioni esatte); **vendoring solo di ciò che modifichiamo**. | Trasparenza e modificabilità senza il peso del vendoring totale. |
| D15 | **Git doppia remote:** `origin` = `https://git.home.varitest.ovh/smp-webmaster/RedGiant.git` (Gitea, push-to-create) · `github` = `https://github.com/Frostmoore/RedGiant.git`. Branch = versioni da `v1.0.0`. | Istruzioni globali dell'utente + convenzione dei suoi progetti. |
| D16 | **Nessuna API LLM esterna, mai.** Se Gemma non basta → risposta onesta o escalation all'utente. | Policy homelab; è la tesi stessa del progetto. |
| D17 | **Domini in ordine:** coding → ricerca locale → ricerca web → consigli. Verifica di ricerca/consigli **per fonti e triangolazione**. | Il coding ha la verifica gratis: valida l'impianto prima. |
| D18 | **Benchmark:** prima mini-progetti sintetici; poi il **chatbot Laravel 13** (costruito in un altro scenario) come benchmark reale (F8). | I due progetti non si bloccano a vicenda. |
| D19 | **Deploy finale: Docker su Severino**, accanto a llama-server, resource limits §6.8 della specsheet homelab. | Confermato dall'utente. |
| D20 | **Il Worker è ReAct a passo singolo vincolato:** a ogni step il modello emette *un solo* oggetto `WorkerStep` (schema chiuso: o una tool call o la chiusura), la conversazione cresce in append. | Un E2B non regge piani d'azione lunghi in un colpo solo; l'append puro massimizza il riuso della KV cache (`cache_prompt`). |
| D21 | **Un ruolo = uno schema Pydantic** con enum chiusi e oggetti piccoli; mai un mega-oggetto. | Un E2B regge meglio N output piccoli che 1 grande; ogni schema è anche il contratto della grammatica. |

**Metriche cardine** (dall'Evaluator, sempre su profilo CPU-only): 1) token utili/token totali · 2) completion rate con evidenza · 3) tempo di parete per task/sottofase su `severino-sim` · 4) prefill riusato/riprocessato · 5) token per task, retry medi, loop fermati.

---

## A. Architettura di riferimento

Questa sezione è il progetto esecutivo. Le fasi la costruiscono pezzo per pezzo; il codebase_reference la fotografa dopo ogni fase.

### A1. Albero del repository (a regime — cosa nasce in quale fase)

```text
RedGiant/                              (root = e:\coding\XAMPP\htdocs\Red Giant)
├── pyproject.toml                     F0 — metadati, deps pinnate, entry point `rg`
├── requirements.lock                  F0 — lockfile esatto (pip-compile)
├── README.md                          F0
├── .gitignore                         F0 — esclude models/, data/, bench/results/raw/
├── memory/
│   ├── small-model-powerhouse-specsheet.md   (esiste)
│   ├── plan_red_giant.md                     (questo file)
│   └── codebase_reference.md                 F0 → aggiornato ogni fase
├── config/
│   ├── default.toml                   F0 — tutte le chiavi con default (v. §A6)
│   └── profiles/
│       ├── dev-fast.toml              F0 — override endpoint GPU
│       ├── severino-sim.toml          F0 — override endpoint Docker CPU
│       └── severino.toml              F0 — override endpoint Tailscale
├── docker/
│   ├── severino-sim/compose.yml       F0 — llama-server CPU, cpuset 4 core, mem limit
│   └── deploy/                        F8 — immagine Red Giant per Severino
├── scripts/
│   ├── start-llama.ps1                F0 — avvia llama-server per profilo (dev Windows)
│   ├── download-model.ps1             F0 — scarica il GGUF in models/ (gitignored)
│   └── check_reference.py             F0 — verifica meccanica firme ↔ codebase_reference
├── bench/
│   ├── run_bench.py                   F0 — baseline prefill/gen/cache
│   └── results/                       F0 — CSV+MD committati (raw/ gitignored)
├── models/                            F0 — GGUF (gitignored)
├── data/                              F1 — redgiant.db, workspace dei task (gitignored)
├── redgiant/
│   ├── __init__.py                    F0 — __version__
│   ├── config.py                      F0
│   ├── cli.py                         F1 — CLI dev (`rg run|status|eval|bench`)
│   ├── llm/
│   │   ├── client.py                  F1 — LlamaClient
│   │   └── schema.py                  F1 — Pydantic → json_schema per llama-server
│   ├── prompts/
│   │   ├── assemble.py                F1 — PromptAssembler, PromptParts
│   │   ├── preamble.md                F1 — S1: preambolo comune (EN, statico)
│   │   └── roles/                     F1+ — worker.md, F3: planner.md, phase_designer.md,
│   │                                        F4: debugger.md, supervisor.md, F6: classifier.md, assessor.md
│   ├── state/
│   │   ├── models.py                  F1 — tutti i modelli Pydantic dello stato
│   │   └── store.py                   F1 — StateStore (SQLite, DDL in §A5)
│   ├── tools/
│   │   ├── base.py                    F1 — ToolSpec, ToolResult, Scope
│   │   ├── router.py                  F1 — ToolRouter
│   │   ├── fs.py                      F1 — read_file, list_files, write_patch
│   │   ├── search.py                  F1 — search_code (ripgrep)
│   │   ├── proc.py                    F1 — run_tests, git_status, git_diff (whitelist)
│   │   └── web.py                     F7 — web_search, fetch_url
│   ├── roles/
│   │   ├── base.py                    F1 — Role, RoleContext, RoleName
│   │   ├── worker.py                  F1 — Worker (ReAct vincolato, D20)
│   │   ├── planner.py                 F3
│   │   ├── phase_designer.py          F3
│   │   ├── debugger.py                F4
│   │   ├── supervisor.py              F4
│   │   ├── classifier.py              F6
│   │   └── assessor.py                F6
│   ├── core/
│   │   ├── orchestrator.py            F1 — v0; F3 — v1 (piano dinamico)
│   │   ├── verify.py                  F1 — verifica deterministica; F4 — estesa
│   │   ├── budget.py                  F1 — conteggio; F4 — BudgetManager completo
│   │   ├── loopguard.py               F4 — LoopGuard
│   │   ├── checkpoint.py              F4 — CheckpointManager (git + slot KV in F5)
│   │   ├── context_builder.py         F5 — ContextBuilder (in F1-F4 assemblaggio semplice)
│   │   ├── cache_probe.py             F5 — metriche riuso KV
│   │   ├── slots.py                   F5 — SlotManager (--slot-save-path)
│   │   ├── compressor.py              F5 — StateCompressor
│   │   └── routing.py                 F6 — segnali deterministici + pipeline selection
│   ├── eval/
│   │   ├── harness.py                 F1 — discover/run/report
│   │   ├── tasks/                     F1+ — T001…/task.toml + repo/
│   │   └── report.py                  F1
│   └── web/
│       ├── app.py                     F2 — create_app()
│       ├── jobs.py                    F2 — JobQueue (1 inferenza alla volta)
│       ├── routes/                    F2 — tasks.py, approvals.py, metrics.py
│       ├── templates/                 F2 — Jinja2 + HTMX
│       └── static/htmx.min.js         F2 — vendorizzato
└── tests/
    ├── unit/                          F1+
    └── integration/                   F1+ — girano contro llama-server reale (marker pytest)
```

### A2. Dipendenze (pinnate in F0.1, versioni esatte nel lockfile)

`pydantic` (v2), `httpx`, `fastapi`, `uvicorn`, `jinja2`, `pytest`, `pip-tools` (dev). Niente ORM (SQL a mano su `sqlite3` stdlib), niente client LLM di terze parti (il wrapper è nostro), niente framework di agenti. Ripgrep: binario di sistema, path in config.

### A3. Flusso di un task (a regime, F6+)

```text
POST /tasks → StateStore.create_task → JobQueue.submit
→ [routing F6: segnali deterministici → Classifier → pipeline direct|short|full]
→ [full] Planner → Plan v1 → Phase Designer(fase corrente) → sottofasi
→ per ogni sottofase: Orchestrator._execute_subtask
     Worker (loop WorkerStep: tool via ToolRouter, evidenze su StateStore)
     → verify.py (oracoli deterministici) → Debugger (se serve) → Supervisor (decisione)
     → CheckpointManager.checkpoint → sottofase successiva
→ Final review → TaskState.status = completed|partial|failed (mai senza evidenza)
```

### A4. Convenzione dei prompt (D9, D20 — fissata in F1.3, immutabile senza revisione del piano)

Ogni prompt è la concatenazione **nell'ordine S1→S7** con separatori stabili (`\n\n### <SECTION>\n\n`), parti statiche byte-identiche tra chiamate:

| Sez. | Nome | Contenuto | Stabilità |
|---|---|---|---|
| S1 | `PREAMBLE` | Identità sistema, regole universali (EN), formato evidenze | statica globale (mai cambia dentro una release) |
| S2 | `ROLE` | Card del ruolo (da `prompts/roles/<role>.md`) | statica per ruolo |
| S3 | `TOOLS` | Catalogo tool autorizzati al ruolo (generato, ordinato per nome) | statica per (ruolo, dominio) |
| S4 | `TASK` | Richiesta utente, goal, vincoli | statica per task |
| S5 | `STATE` | Piano sintetico, fase corrente, decisioni durature | cambia poco (per fase) |
| S6 | `CONTEXT` | Sottofase corrente, file, errori aperti | volatile |
| S7 | `OUTPUT` | Istruzione schema + nome schema | statica per ruolo |

Regola: **mai** inserire contenuto volatile (timestamp, contatori, path temporanei) in S1–S4. Il Worker (D20) appende i passi in coda a S6: il prefisso resta intatto e `cache_prompt` riusa la KV.

### A5. Schema del database (SQLite, `data/redgiant.db` — DDL in `state/store.py::init_schema`)

| Tabella | Colonne (tipo — note) | Nasce |
|---|---|---|
| `tasks` | `id TEXT PK` (ULID) · `created_at TEXT` ISO · `request TEXT` · `target_dir TEXT` · `domain TEXT` · `status TEXT` CHECK in (`queued,running,blocked,completed,partial,failed,cancelled`) · `profile TEXT` · `pipeline TEXT` (F6) · `error TEXT NULL` | F1 |
| `plans` | `task_id TEXT` · `version INTEGER` · `actor TEXT` · `reason TEXT` · `json TEXT` (Plan serializzato) · PK(`task_id`,`version`) | F3 (in F1 una riga fittizia `version=0` col piano statico) |
| `subtasks` | `task_id` · `subtask_id TEXT` · `phase_id TEXT` · `title TEXT` · `status TEXT` CHECK in (`pending,running,completed,completed_with_warnings,retry,repair,blocked,failed,skipped`) · `spec JSON` · `result JSON NULL` · `attempts INTEGER DEFAULT 0` · PK(`task_id`,`subtask_id`) | F1 |
| `llm_calls` | `id INTEGER PK AUTOINCREMENT` · `task_id` · `subtask_id NULL` · `role TEXT` · `schema_name TEXT` · `t_start TEXT` · `prompt_tokens INT` · `cached_tokens INT` · `gen_tokens INT` · `prefill_ms REAL` · `gen_ms REAL` · `outcome TEXT` (`ok,timeout,error`) | F1 |
| `tool_calls` | `id INTEGER PK` · `task_id` · `subtask_id` · `tool TEXT` · `args JSON` · `ok INTEGER` · `evidence JSON` · `duration_ms REAL` | F1 |
| `decisions` | `id INTEGER PK` · `task_id` · `actor TEXT` · `decision TEXT` · `reason TEXT` · `target TEXT NULL` · `created_at TEXT` | F1 |
| `approvals` | `id INTEGER PK` · `task_id` · `kind TEXT` (`irreversible_op,clarification`) · `payload JSON` · `status TEXT` (`pending,answered,expired`) · `answer TEXT NULL` | F2 |
| `checkpoints` | `id INTEGER PK` · `task_id` · `kind TEXT` (`post_plan,post_subtask,pre_risky,pre_replan`) · `git_ref TEXT NULL` · `slot_file TEXT NULL` (F5) · `created_at TEXT` | F4 |
| `budgets` | `task_id` · `key TEXT` (`tokens,tool_calls,retries,wall_s`) · `limit_val INTEGER` · `used INTEGER DEFAULT 0` · PK(`task_id`,`key`) | F1 |
| `eval_runs` | `id INTEGER PK` · `started_at` · `profile TEXT` · `git_ref TEXT` · `report_path TEXT` | F1 |
| `routing_log` | `id INTEGER PK` · `task_id` · `signals JSON` · `classifier JSON NULL` · `pipeline TEXT` · `outcome TEXT NULL` (riempito a fine task per la calibrazione) | F6 |

Indici: `subtasks(task_id,status)`, `llm_calls(task_id)`, `tool_calls(task_id,subtask_id)`, `approvals(status)`. Scritture sempre in transazione; ogni UPDATE porta `actor`.

### A6. Chiavi di configurazione (`config/default.toml`, override per profilo)

| Chiave | Default | Significato |
|---|---|---|
| `llm.base_url` | `http://127.0.0.1:8080` | endpoint llama-server del profilo |
| `llm.ctx_size` | `8192` | contesto massimo per chiamata (D8; rivisto con F0.6) |
| `llm.timeout_s` | `600` | timeout per chiamata (alto: CPU) |
| `llm.temperature` | `0.2` | default ruoli; override per ruolo in `[roles.<name>]` |
| `llm.max_tokens_default` | `1024` | tetto generazione se il ruolo non specifica |
| `paths.db` | `data/redgiant.db` | database |
| `paths.models_dir` | `models/` | GGUF |
| `paths.ripgrep` | `rg` | binario ripgrep |
| `budget.max_total_tokens` | `32000` | per task (F0.6 può rivedere) |
| `budget.max_tool_calls` | `100` | per task |
| `budget.max_retries_per_subtask` | `2` | §13 spec |
| `budget.max_wall_s` | `7200` | per task |
| `worker.max_steps` | `20` | passi ReAct per sottofase |
| `web.host` / `web.port` | `127.0.0.1` / `8090` | GUI |
| `security.writable_globs` | `[]` | scope di scrittura del task (riempito per task) |
| `security.shell_whitelist` | `["pytest","php","composer","git"]` | eseguibili ammessi da `proc.py` |
| `eval.tasks_dir` | `redgiant/eval/tasks` | task sintetici |

### A7. Catalogo tool (F1; schema input = modello Pydantic omonimo in `tools/*.py`)

| Tool | Firma handler | Rischio | Reversibile | Note |
|---|---|---|---|---|
| `read_file` | `read_file(path: str, start_line: int = 1, end_line: int \| None = None) -> ToolResult` | low | sì | tronca a 400 righe, segnala troncatura |
| `list_files` | `list_files(glob: str, max_results: int = 200) -> ToolResult` | low | sì | rispetta Scope |
| `search_code` | `search_code(pattern: str, glob: str \| None = None, max_results: int = 50) -> ToolResult` | low | sì | ripgrep `--json` |
| `write_patch` | `write_patch(path: str, unified_diff: str) -> ToolResult` | medium | via git | applica diff unificato; hunks respinti in evidenza |
| `run_tests` | `run_tests(cmd_id: str) -> ToolResult` | medium | sì | `cmd_id` da whitelist del task, MAI stringa libera; evidenza = exit code + tail stdout |
| `git_status` / `git_diff` | `(repo: str) -> ToolResult` | low | sì | evidenze per il Verifier |
| `web_search` (F7) | `web_search(query: str, max_results: int = 8) -> ToolResult` | low | sì | motore deciso in F7.2 |
| `fetch_url` (F7) | `fetch_url(url: str) -> ToolResult` | medium | sì | estrazione testo, cache su disco |

---

## Rituale di fine fase (obbligatorio, identico per ogni fase)

Al completamento dell'ultima sottofase 🔎 di una fase, **senza che l'utente lo chieda**:

1. **Aggiornare `memory/plan_red_giant.md`**: checkbox della fase e delle sottofasi, campo *Stato* in testa al file, eventuali firme cambiate (con la ragione nella riga della sottofase).
2. **Aggiornare `memory/codebase_reference.md`**: ogni classe/metodo/tabella/endpoint/chiave nuovi o cambiati; sezione "Cosa NON esiste ancora" ripulita; trappole disinnescate aggiunte con la causa tecnica.
3. **Verifica meccanica dell'atlante:** `python scripts/check_reference.py` — estrae `class`/`def` reali da `redgiant/` e le confronta con le firme documentate; exit ≠ 0 = il rituale **non può proseguire** finché l'atlante non è allineato.
4. **Messaggio ESTREMAMENTE DETTAGLIATO** all'utente: stato dell'implementazione, checkbox fase+sottofasi, commento sullo stato generale e su quello della fase.
5. **Commit + push su branch versionato**: nuovo branch col numero di versione della fase (tabella sotto), push su `origin` (Gitea) **e** `github`. Messaggio di commit: `<versione> — <fase>: <sintesi>`.

Incrementi: commit intermedi piccoli `+0.0.1`, medi `+0.1.0`; il completamento fase fissa la versione della tabella:

| Fase | Versione a fine fase | Entità |
|---|---|---|
| Piano (questo commit) | `v1.0.0` | — |
| F0 | `v1.1.0` | media |
| F1 | `v2.0.0` | grande |
| F2 | `v2.1.0` | media |
| F3 | `v3.0.0` | grande |
| F4 | `v4.0.0` | grande |
| F5 | `v5.0.0` | grande |
| F6 | `v5.1.0` | media |
| F7 | `v6.0.0` | grande |
| F8 | `v7.0.0` | grande |

---

## Mappa delle fasi

| Fase | Titolo | Dipende da | Gate d'ingresso |
|---|---|---|---|
| F0 | Fondazioni e misure di base | — | — |
| F1 | Nucleo deterministico + Worker | F0 | numeri F0.6 approvati |
| F2 | GUI web minima | F1 | walking skeleton verde |
| F3 | Pianificazione (Planner + Phase Designer) | F1 | Evaluator v0 operativo |
| F4 | Verifica continua e supervisione | F3 | piano dinamico verde |
| F5 | Contesto e KV cache ("fase Dwarf Star") | F4 | pipeline completa misurabile |
| F6 | Routing adattivo (Classifier + Assessor) | F4 | metriche per-pipeline disponibili |
| F7 | Domini non-coding | F6 | routing per dominio attivo |
| F8 | Benchmark reale + deploy su Severino | F5, F7 | chatbot Laravel disponibile |

---

## Fase 0 — Fondazioni e misure di base → `v1.1.0`

📎 **Specsheet:** §15, §16, §23 · **Decisioni:** D1, D2, D3, D5, D6, D8, D14, D15
🎯 **Scope:** repo + ambiente Python, llama-server nei tre profili, Gemma 4 E2B Q4 verificato (constrained decoding incluso), numeri di baseline che fissano i budget.
🧭 **Perché qui:** ogni decisione a valle dipende da misure reali. Se il supporto GGUF/grammatiche del modello è acerbo (⚠️ la specsheet homelab lo segnala in §16.3), va scoperto quando cambiare rotta costa zero.

- [ ] **0.1** 🤖 Struttura repo e progetto Python.
  - `pyproject.toml`: nome `redgiant`, Python `>=3.12`, deps §A2, entry point `rg = "redgiant.cli:main"`.
  - `requirements.lock` via `pip-compile` (versioni esatte, D14). `.gitignore`: `models/`, `data/`, `bench/results/raw/`, `__pycache__/`, `.venv/`.
  - `redgiant/__init__.py` con `__version__: str` allineata al branch.
  - `README.md`: cos'è Red Giant, i tre profili, comandi base.
- [ ] **0.2** 🤖 llama.cpp e modello.
  - Binari llama.cpp su questo PC: release CUDA (`dev-fast`) + build/release CPU pura; versione **pinnata** (tag scritto in `config/default.toml` come commento e nel codebase_reference).
  - `scripts/download-model.ps1`: scarica il GGUF Gemma 4 E2B Q4 in `models/` (URL e SHA256 nel file).
  - `scripts/start-llama.ps1 -Profile dev-fast|severino-sim|severino`: avvia llama-server con i flag del profilo (`--ctx-size`, `--parallel 1`, `--threads N` solo CPU, `--slot-save-path data/slots/` predisposto).
  - Smoke test: `GET /props` + una generazione.
- [ ] **0.3** 🤖 ⚠️ Verifica constrained decoding con Gemma 4 E2B su llama-server.
  - Tre schemi di prova realistici: enum di decisione (stile `SupervisorDecision`), oggetto annidato (stile `Plan` con 5 fasi), lista di oggetti (stile `PhaseDesign` con 4 sottofasi).
  - Per ciascuno: 20 generazioni, misurare validità (attesa: 100% col guided decoding), qualità semantica a campione, degradazione di velocità con/senza grammatica.
  - Fallback se rotto: quantizzazione diversa → versione llama.cpp diversa → (ultima spiaggia) modello ponte più maturo. 📌 Esito e versioni nel codebase_reference.
- [ ] **0.4** 🤖 Profilo `severino-sim`: `docker/severino-sim/compose.yml` — llama-server CPU-only, `cpuset: "0-3"`, `mem_limit` concordata, `--threads 4 --parallel 1`. 🧑 Conferma dei numeri di allocazione (core/RAM) prima del freeze.
- [ ] **0.5** 🤖 Benchmark di baseline riproducibile: `bench/run_bench.py`.
  - Firma: `def run(profile: str, ctx_sizes: list[int], repeats: int, out_dir: Path) -> Path` (CSV + tabella MD in `bench/results/`).
  - Misure: prefill tok/s e gen tok/s a contesto 1K/4K/8K/16K su `dev-fast` e `severino-sim`; riuso reale del prefisso tra chiamate con prefisso comune (`cache_prompt: true`, lettura `timings` e `/slots`); prova `--slot-save-path` (salva/ripristina KV da disco, misura il tempo risparmiato).
- [ ] **0.6** 🤖 📌 Decisioni derivate dai numeri, scritte nel codebase_reference con le misure che le giustificano: `llm.ctx_size` definitivo, budget per ruolo, dimensione massima del preambolo S1–S3, timeout, soglia di convenienza dello slot-save.
- [ ] **0.7** 🤖 `scripts/check_reference.py` (serve dal primo rituale):
  - `def extract_signatures(pkg_dir: Path) -> dict[str, list[str]]` — AST di `redgiant/`, per modulo: classi e `def` con firma completa.
  - `def extract_documented(md_path: Path) -> dict[str, list[str]]` — parse dei blocchi firma dell'atlante.
  - `def main() -> int` — diff leggibile, exit 1 su divergenza.
- [ ] **0.8** 🔎 **Verifica di fase:** i tre profili si avviano da script; `bench/` produce la tabella con un comando; constrained decoding dimostrato sui 3 schemi con numeri; `check_reference.py` gira (a vuoto è ok).

**Rituale di fine fase** — incluso il **primo `codebase_reference.md` completo** (che da questa fase fotografa: struttura repo, config, script, bench, numeri di baseline).

---

## Fase 1 — Nucleo deterministico + Worker (walking skeleton) → `v2.0.0`

📎 **Specsheet:** §6.5, §7, §8, §11, §17, §23 · **Decisioni:** D3, D7, D9, D10, D20, D21
🎯 **Scope:** la catena minima che risolve un bugfix sintetico end-to-end (piano statico → Worker → tool → verifica deterministica → stato), più l'Evaluator v0 che la misura.
🧭 **Perché qui:** walking skeleton prima dei ruoli cognitivi: l'impianto si valida dove la verifica è gratis. Ogni ruolo successivo dovrà battere questa baseline (D11).

- [ ] **1.1** 🤖 Stato: `redgiant/state/models.py` + `redgiant/state/store.py`.
  - Modelli Pydantic (tutti `frozen=False`, `extra="forbid"`):
    ```python
    TaskStatus  = Literal["queued","running","blocked","completed","partial","failed","cancelled"]
    SubtaskStatus = Literal["pending","running","completed","completed_with_warnings",
                            "retry","repair","blocked","failed","skipped"]
    class Budget(BaseModel):     max_total_tokens: int; max_tool_calls: int; max_retries_per_subtask: int; max_wall_s: int
    class BudgetUsed(BaseModel): tokens: int = 0; tool_calls: int = 0; wall_s: float = 0.0
    class SubtaskSpec(BaseModel):
        id: str; phase_id: str; title: str; objective: str
        inputs: list[str]; tools: list[str]; expected_outputs: list[str]
        completion_criteria: list[str]; verification: list[str]
    class PhaseSpec(BaseModel):  id: str; title: str; depends_on: list[str]; completion_criteria: list[str]
    class Plan(BaseModel):       version: int; goal: str; success_criteria: list[str]; phases: list[PhaseSpec]
    class TaskState(BaseModel):
        id: str; request: str; target_dir: str; domain: str; status: TaskStatus
        plan: Plan | None; current_phase: str | None; current_subtask: str | None
        budget: Budget; used: BudgetUsed
    ```
  - `StateStore` (SQLite §A5, scritture atomiche, ogni mutazione con `actor: str`):
    ```python
    class StateStore:
        def __init__(self, db_path: Path) -> None
        def init_schema(self) -> None
        def create_task(self, request: str, target_dir: str, profile: str, budget: Budget) -> str
        def load_task(self, task_id: str) -> TaskState
        def list_tasks(self, limit: int = 50) -> list[dict]
        def set_task_status(self, task_id: str, status: TaskStatus, *, actor: str, error: str | None = None) -> None
        def save_plan(self, task_id: str, plan: Plan, *, actor: str, reason: str) -> None
        def upsert_subtask(self, task_id: str, spec: SubtaskSpec, *, actor: str) -> None
        def set_subtask_status(self, task_id: str, subtask_id: str, status: SubtaskStatus,
                               *, actor: str, result: dict | None = None) -> None
        def add_decision(self, task_id: str, *, actor: str, decision: str, reason: str, target: str | None = None) -> None
        def log_llm_call(self, task_id: str, row: LlmCallRow) -> None
        def log_tool_call(self, task_id: str, row: ToolCallRow) -> None
        def budget_used(self, task_id: str) -> BudgetUsed
    ```
- [ ] **1.2** 🤖 Model client: `redgiant/llm/client.py` + `redgiant/llm/schema.py`.
  ```python
  class LlmError(Exception): ...
  class LlmTimeout(LlmError): ...
  @dataclass
  class LlmResult:
      text: str; parsed: BaseModel | None
      prompt_tokens: int; cached_tokens: int; gen_tokens: int
      prefill_ms: float; gen_ms: float; raw_timings: dict
  class LlamaClient:
      def __init__(self, cfg: LlmProfileCfg, store: StateStore | None = None) -> None
      def complete(self, parts: PromptParts, *, role: str,
                   schema: type[BaseModel] | None = None,
                   max_tokens: int, temperature: float | None = None,
                   task_id: str | None = None, subtask_id: str | None = None,
                   cache_prompt: bool = True) -> LlmResult
      def health(self) -> bool
      def props(self) -> dict
  # llm/schema.py
  def to_llama_schema(model: type[BaseModel]) -> dict   # json_schema per guided decoding
  ```
  Ogni `complete` con `schema` passa `json_schema` a llama-server (D3), valida con Pydantic in difesa-in-profondità, logga su `llm_calls` (token, `cached_tokens` dai timings, prefill/gen ms).
- [ ] **1.3** 🤖 ⚠️ Prompt: `redgiant/prompts/assemble.py`, `preamble.md`, `roles/worker.md` — convenzione §A4 **fissata qui**.
  ```python
  @dataclass(frozen=True)
  class PromptParts:
      preamble: str; role_card: str; tool_card: str
      task_header: str; durable_state: str; volatile_context: str; output_instruction: str
      def render(self) -> str          # ordine S1→S7, separatori stabili
      def static_prefix_len(self) -> int  # per le metriche di riuso (F5)
  class PromptAssembler:
      def __init__(self, prompts_dir: Path) -> None
      def build(self, role: str, *, task: TaskState, subtask: SubtaskSpec | None,
                tools: list[ToolSpec], volatile: str) -> PromptParts
  ```
- [ ] **1.4** 🤖 Tool layer: `tools/base.py`, `router.py`, `fs.py`, `search.py`, `proc.py` (catalogo §A7).
  ```python
  class ScopeError(Exception): ...
  class Scope:
      def __init__(self, root: Path, writable_globs: list[str]) -> None
      def check_read(self, p: str) -> Path      # risolve, nega fuori-root e symlink esterni
      def check_write(self, p: str) -> Path
  @dataclass(frozen=True)
  class ToolSpec:
      name: str; description: str; risk: Literal["low","medium","high"]
      reversible: bool; requires_approval: bool; timeout_s: float
      input_model: type[BaseModel]
      handler: Callable[..., "ToolResult"]
  @dataclass
  class ToolResult:
      ok: bool; data: dict; evidence: list[str]; error: str | None = None
  class ToolRouter:
      def __init__(self, catalog: dict[str, ToolSpec], scope: Scope, store: StateStore) -> None
      def allowed_for(self, role: str, domain: str) -> list[ToolSpec]
      def dispatch(self, task_id: str, subtask_id: str, name: str, args: dict) -> ToolResult
  ```
  Regole: output dei tool = dati, mai istruzioni (wrappati in S6 come blocchi citati); `run_tests` accetta solo `cmd_id` dalla whitelist del task; ogni dispatch logga su `tool_calls` con evidenze.
- [ ] **1.5** 🤖 Worker ReAct vincolato (D20): `roles/base.py` + `roles/worker.py`.
  ```python
  class RoleContext(BaseModel):
      task: TaskState; subtask: SubtaskSpec | None; volatile: str
  class Role(ABC):
      name: ClassVar[str]; output_model: ClassVar[type[BaseModel]]
      def __init__(self, llm: LlamaClient, assembler: PromptAssembler, router: ToolRouter) -> None
  # worker.py
  class ToolCallSpec(BaseModel): tool: str; args: dict
  class FinishReport(BaseModel):
      status: Literal["done","blocked"]; summary: str
      evidence: list[str]; verification_requested: list[str]
  class WorkerStep(BaseModel):
      thought: str                     # max_length=300: pensiero corto, non saggio
      action: Literal["tool","finish"]
      tool_call: ToolCallSpec | None = None
      finish: FinishReport | None = None
  class Worker(Role):
      output_model = WorkerStep
      def run(self, ctx: RoleContext, *, max_steps: int) -> FinishReport
  ```
  Il loop appende ogni (step, risultato tool) in coda a S6 → prefisso stabile → KV riusata. `finish.status="done"` **non** chiude la sottofase: la chiude solo la verifica (1.6).
- [ ] **1.6** 🤖 Verifica deterministica: `core/verify.py`.
  ```python
  class CheckResult(BaseModel): name: str; ok: bool; detail: str
  class Verdict(BaseModel):     verdict: Literal["pass","fail"]; checks: list[CheckResult]
  def verify_subtask(spec: SubtaskSpec, scope: Scope, router: ToolRouter,
                     task_id: str) -> Verdict
  ```
  In F1: esegue i comandi di verifica della sottofase (`run_tests`), controlla esistenza degli `expected_outputs`, esige evidenze non vuote nel `FinishReport`.
- [ ] **1.7** 🤖 Orchestrator v0: `core/orchestrator.py` + budget minimo `core/budget.py`.
  ```python
  class Orchestrator:
      def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient,
                   router: ToolRouter, assembler: PromptAssembler) -> None
      def run_task(self, task_id: str) -> TaskState      # bloccante; F2 lo mette in JobQueue
      def _next_subtask(self, state: TaskState) -> SubtaskSpec | None
      def _execute_subtask(self, state: TaskState, spec: SubtaskSpec) -> Verdict
      def _finalize(self, state: TaskState) -> TaskState
  # budget.py (F1: solo conteggio e stop duro)
  class BudgetTracker:
      def __init__(self, store: StateStore, budget: Budget, task_id: str) -> None
      def charge_llm(self, r: LlmResult) -> None
      def charge_tool(self) -> None
      def exceeded(self) -> str | None    # chiave sforata o None
  ```
  In F1 il piano è **statico**: caricato da un file `plan.json` accanto al task sintetico (riga `plans.version=0`). Il modello propone, l'Orchestrator decide (§7).
- [ ] **1.8** 🤖 Logging leggibile: oltre alle tabelle, un log testuale per task in `data/tasks/<id>/task.log` (ruolo, sintesi input, esito, token, durata — §20).
- [ ] **1.9** 🤖 CLI dev: `redgiant/cli.py` (argparse).
  - `rg run --target DIR --prompt "..." [--plan plan.json] [--profile P]` → crea ed esegue il task.
  - `rg status <task_id>` → albero fase/sottofase testuale (§20).
  - `rg eval [--profile P] [--only T001,T002]` · `rg bench ...` (wrapper di `bench/run_bench.py`).
- [ ] **1.10** 🤖 Evaluator v0: `eval/harness.py`, `eval/report.py` + **6 task sintetici** in `redgiant/eval/tasks/`.
  ```python
  class EvalTask(BaseModel):
      id: str; domain: str; prompt: str; repo_dir: Path
      plan_file: Path | None; success_cmd: str; timeout_s: int; tags: list[str]
  class EvalResult(BaseModel):
      task_id: str; completed: bool; verified: bool
      total_tokens: int; useful_tokens: int; wall_s: float
      llm_calls: int; tool_calls: int; retries: int
  def discover_tasks(tasks_dir: Path) -> list[EvalTask]
  def run_eval(profile: str, only: list[str] | None, out_dir: Path) -> Path   # report MD+CSV
  ```
  Task iniziali (ognuno = `task.toml` + `repo/` con test): `T001` bugfix Python 1-file · `T002` bugfix Python 2-file · `T003` bugfix PHP 1-file · `T004` feature piccola con test forniti · `T005` test rosso da far passare senza rompere gli altri · `T006` ricerca in codebase ("dov'è definita X?" con risposta verificabile). *Definizione di `useful_tokens` (v0): token delle chiamate dei passi che hanno prodotto tool call accettate o il finish accettato; il resto è overhead.* 📌 Baseline nel codebase_reference.
- [ ] **1.11** 🔎 **Verifica di fase:** ≥4/6 task sintetici completati end-to-end su `severino-sim` senza intervento, con evidenza test-pass; zero output fuori schema nell'intera run (contatore su `llm_calls`); `pytest tests/unit` verde; report Evaluator committato.

---

## Fase 2 — GUI web minima → `v2.1.0`

📎 **Specsheet:** §20 · **Decisioni:** D7, D12
🎯 **Scope:** l'interfaccia con cui l'utente testa: coda job asincroni, albero live, approvazioni/chiarimenti.
🧭 **Perché qui:** senza interfaccia comoda l'utente non testa a fondo (sua dichiarazione esplicita). Da qui in poi ogni test passa dalla GUI. Legge lo stato dal DB: disaccoppiata dall'evoluzione della pipeline.

- [ ] **2.1** 🤖 `web/app.py` + `web/jobs.py`.
  ```python
  def create_app(cfg: Config) -> FastAPI
  class JobQueue:                       # thread worker singolo: UNA inferenza alla volta (D7)
      def __init__(self, make_orchestrator: Callable[[], Orchestrator]) -> None
      def submit(self, task_id: str) -> None
      def cancel(self, task_id: str) -> bool
      def current(self) -> str | None
  ```
  Avvio/arresto llama-server legati al ciclo del job (modello residente per il task, D7) tramite `scripts/start-llama.ps1` o endpoint di controllo, a seconda del profilo.
- [ ] **2.2** 🤖 Rotte (`web/routes/`) — tutte HTML/HTMX, niente API pubblica:

  | Metodo e path | Input | Output | Errori |
  |---|---|---|---|
  | `GET /` | — | lista task (stato, dominio, budget residuo) | — |
  | `GET /tasks/new` | — | form: prompt, target_dir, profilo, limiti | — |
  | `POST /tasks` | form | redirect `/tasks/{id}` (crea + submit) | 400 input invalido; 409 coda piena |
  | `GET /tasks/{id}` | — | dettaglio: albero fasi/sottofasi, budget, log link | 404 |
  | `GET /tasks/{id}/tree` | — | frammento HTMX dell'albero (polling 2s) | 404 |
  | `GET /tasks/{id}/log` | `?tail=200` | log leggibile | 404 |
  | `POST /tasks/{id}/cancel` | — | redirect | 404, 409 non attivo |
  | `GET /approvals` | — | coda pending (approvazioni + chiarimenti) | — |
  | `POST /approvals/{id}` | form `answer` | redirect; il task riparte da `blocked` | 404, 409 già risposta |
  | `GET /metrics` | — | metriche cardine ultima eval + task recenti | — |
- [ ] **2.3** 🤖 Protocollo umano: tabella `approvals` (§A5); l'Orchestrator crea una richiesta (`kind="irreversible_op"` o `"clarification"`), mette il task in `blocked`, il worker thread passa oltre; alla risposta il task torna in coda. 🧑 decide se collegare ntfy del homelab (opzionale).
- [ ] **2.4** 🤖 Template Jinja2 + `static/htmx.min.js` vendorizzato; albero stile §20 con colori di stato; zero JS custom oltre HTMX.
- [ ] **2.5** 🔎 **Verifica di fase:** 🧑 l'utente lancia `T004` dalla GUI, chiude la pagina, torna, vede l'albero completo; un task con operazione da approvare si ferma e riparte dopo la risposta. Le scomodità segnalate si sistemano **in questa fase**, non dopo.

---

## Fase 3 — Pianificazione: Planner + Phase Designer → `v3.0.0`

📎 **Specsheet:** §6.3, §6.4, §10, §11 · **Decisioni:** D10, D11, D21
🎯 **Scope:** dal piano statico al piano generato e versionato; espansione della sola fase corrente; Orchestrator v1 guidato dal piano; replanning minimale; A/B contro F1.
🧭 **Perché qui:** primo ruolo cognitivo vero: deve dimostrare coi numeri di valere il suo costo sui task multi-step, dove la lista statica non basta.

- [ ] **3.1** 🤖 `roles/planner.py` + `prompts/roles/planner.md`.
  ```python
  class PlannerOutput(BaseModel):       # = Plan senza version (la mette lo StateStore)
      goal: str; success_criteria: list[str]; phases: list[PhaseSpec]
  class Planner(Role):
      output_model = PlannerOutput
      def run(self, ctx: RoleContext) -> PlannerOutput
  ```
  Vincoli: max fasi = 7, `max_tokens` dal budget F0.6; ogni chiamata di replanning salva `plans.version+1` con `reason`.
- [ ] **3.2** 🤖 ⚠️ `roles/phase_designer.py` + card. Espande **solo** la fase corrente.
  ```python
  class PhaseDesign(BaseModel): phase_id: str; subtasks: list[SubtaskSpec]   # max 6 per fase
  class PhaseDesigner(Role):
      output_model = PhaseDesign
      def run(self, ctx: RoleContext) -> PhaseDesign
  ```
  Criterio D10 nella card: preferire sottofasi con oracolo meccanico; ogni sottofase deve stare in una sessione Worker (`worker.max_steps`).
- [ ] **3.3** 🤖 Orchestrator v1: `run_task` diventa: Planner → per ogni fase eleggibile (dipendenze soddisfatte) → PhaseDesigner → loop sottofasi; stati §11 completi; `current_phase`/`current_subtask` sempre aggiornati per la GUI.
- [ ] **3.4** 🤖 Replanning minimale (§10): trigger deterministici — dipendenza inesistente, sottofase `failed` oltre i retry, budget sotto soglia → invalidazione fase + richiamo Planner con il contesto del fallimento. Mai per errori locali.
- [ ] **3.5** 🤖 📌 Evaluator: +4 task multi-step (`T007`–`T010`: refactoring 3-file, feature cross-module, fix con migrazione dati fittizia, task con piano-trappola che richiede replanning). **A/B: pipeline F1 (piano statico ingenuo) vs F3** sull'intero set. Il Planner resta solo se migliora completion o token-utili.
- [ ] **3.6** 🔎 **Verifica di fase:** `T007`–`T009` completano con piano generato; `T010` esegue almeno un replanning corretto; A/B documentato; nessun piano oltre il limite token.

---

## Fase 4 — Verifica continua e supervisione → `v4.0.0`

📎 **Specsheet:** §6.6, §6.7, §12, §13, §14 · **Decisioni:** D10, D11
🎯 **Scope:** Debugger/Verifier a due stadi, Supervisor con decisioni chiuse, retry budget, anti-loop, checkpoint/rollback via git, Budget Manager completo.
🧭 **Perché qui:** con la pianificazione attiva gli errori diventano distinguibili (codice vs test vs piano). Prima si costruisce ciò che li distingue e li ferma.

- [ ] **4.1** 🤖 `roles/debugger.py` + estensione `core/verify.py` (due stadi: prima oracoli, poi modello solo sul residuo — D10).
  ```python
  class FailureItem(BaseModel):  kind: Literal["code","test","plan","model"]; ref: str; reason: str
  class DebugReport(BaseModel):
      verdict: Literal["pass","fail"]
      checks: list[CheckResult]; failures: list[FailureItem]
      severity: Literal["low","medium","high"]
      recommended_action: Literal["accept","retry","repair","replan_phase","replan_global","escalate"]
      repair_scope: list[str]
  class DebuggerRole(Role):
      output_model = DebugReport
      def run(self, ctx: RoleContext, *, deterministic: Verdict) -> DebugReport
  ```
- [ ] **4.2** 🤖 `roles/supervisor.py`.
  ```python
  class SupervisorDecision(BaseModel):
      decision: Literal["accept","retry_subtask","repair","redesign_phase",
                        "replan_global","rollback","ask_user","stop_partial","stop_failed"]
      reason: str; target: str | None; retry_strategy: str | None
  class Supervisor(Role):
      output_model = SupervisorDecision
      def run(self, ctx: RoleContext, *, report: DebugReport, attempts: int,
              budget_left: BudgetUsed) -> SupervisorDecision
  ```
  L'Orchestrator applica la decisione **solo se legale** (es. `retry` oltre il limite → declassa a `redesign_phase`): il modello propone, l'Orchestrator decide.
- [ ] **4.3** 🤖 `core/loopguard.py` (§13).
  ```python
  class LoopGuard:
      def __init__(self, store: StateStore, window: int = 5) -> None
      def error_signature(self, report: DebugReport) -> str    # hash normalizzato dei failure
      def register(self, task_id: str, sig: str) -> None
      def progress_score(self, task_id: str) -> float          # artefatti nuovi / token spesi
      def is_looping(self, task_id: str) -> bool               # stessa firma ≥2, patch che si annullano, score→0
  ```
  Scala §13: 1° fallimento repair locale · 2° strategia nuova · 3° revisione fase · oltre → Supervisor/stop.
- [ ] **4.4** 🤖 `core/checkpoint.py` — git come motore sul **repo target** del task.
  ```python
  CheckpointKind = Literal["post_plan","post_subtask","pre_risky","pre_replan"]
  class CheckpointManager:
      def __init__(self, store: StateStore, target_repo: Path) -> None
      def ensure_work_branch(self, task_id: str) -> str        # crea rg/task-<id> se manca
      def checkpoint(self, task_id: str, kind: CheckpointKind, *, subtask_id: str | None = None) -> str  # ref
      def rollback(self, task_id: str, ref: str) -> None
  ```
  Se il target non è un repo git → `git init` locale di servizio (fa parte dell'onboarding del task).
- [ ] **4.5** 🤖 `core/budget.py` → `BudgetManager` completo: limiti per task **e per ruolo** (F0.6); superamento = stop esplicito `partial`/`failed` con spiegazione, mai degradazione silenziosa (§14).
- [ ] **4.6** 🤖 📌 Evaluator: +4 task — `T011` bug indotto subdolo (test che passano ma criterio violato) · `T012` **task impossibile** (deve terminare `failed` con spiegazione onesta) · `T013` informazioni mancanti (deve fare `ask_user` via GUI) · `T014` loop-trappola (patch oscillanti: l'anti-loop deve fermarlo).
- [ ] **4.7** 🔎 **Verifica di fase:** zero successi senza evidenza su tutto il set; `T012` fallisce esplicitamente; `T013` si blocca e riparte con la risposta; `T014` fermato dal LoopGuard entro il budget; rollback dimostrato su un caso reale.

---

## Fase 5 — Contesto e KV cache (la fase "Dwarf Star") → `v5.0.0`

📎 **Specsheet:** §9, §16 · **Decisioni:** D8, D9, D20
🎯 **Scope:** Context Builder per ruolo, misura del riuso, ottimizzazione dei prefissi, slot save/restore, compressione dello stato. Qui si decide se Red Giant è usabile o solo dimostrativo.
🧭 **Perché qui:** ora la pipeline è completa e misurabile: ogni ottimizzazione ha un prima/dopo onesto su `severino-sim`. Su CPU il prefill è il costo dominante.

- [ ] **5.1** 🤖 `core/context_builder.py` (§9): sostituisce l'assemblaggio semplice di S5/S6.
  ```python
  class ContextBudgets(BaseModel):  s5_max_tokens: int; s6_max_tokens: int; files_max_lines: int
  class ContextBundle(BaseModel):   durable_state: str; volatile: str; sources: list[str]
  class ContextBuilder:
      def __init__(self, store: StateStore, scope: Scope, budgets: ContextBudgets) -> None
      def bundle(self, role: str, state: TaskState, subtask: SubtaskSpec | None) -> ContextBundle
  ```
  Regole §9: il Worker non vede fasi future, né log di test già superati, né cronologia Planner; selezione = sottofase corrente + criteri + file citati + errori aperti + decisioni rilevanti.
- [ ] **5.2** 🤖 📌 `core/cache_probe.py`: per ogni chiamata calcola `reuse_ratio = cached_tokens / prompt_tokens` (dai timings); aggregati per ruolo/task; pannello in `/metrics`. È **la** metrica della fase.
- [ ] **5.3** 🤖 Ottimizzazione dei prefissi: audit byte-level della stabilità S1–S4 (test unit: due chiamate consecutive stesso ruolo ⇒ prefisso identico); valutazione gerarchia di prefissi per ruolo; eliminazione di ogni volatilità residua (D9).
- [ ] **5.4** 🤖 `core/slots.py`: integrazione `--slot-save-path`.
  ```python
  class SlotManager:
      def __init__(self, base_url: str, slots_dir: Path) -> None
      def save(self, task_id: str, label: str) -> Path
      def restore(self, path: Path) -> None
  ```
  Uso: ripresa di un task interrotto e fork di fase **senza ripagare il prefill**; agganciato ai `checkpoints.slot_file` (§A5). Soglia di convenienza dai numeri F0.5.
- [ ] **5.5** 🤖 `core/compressor.py`: per task lunghi, riassunto strutturato (JSON vincolato) dello storico sottofasi, **verificato** contro lo stato reale (i fatti citati devono esistere nelle tabelle) prima di sostituire il testo esteso in S5.
- [ ] **5.6** 🔎 **Verifica di fase:** su `severino-sim`, sull'intero set Evaluator: **riduzione ≥40% del tempo medio di prefill per sottofase** rispetto a fine F4 (target rivedibile coi numeri F0, con ragione scritta), a parità di completion rate; `reuse_ratio` medio Worker ≥ soglia fissata in F0.6; ripresa da slot dimostrata.

---

## Fase 6 — Routing adattivo: Classifier + Assessor → `v5.1.0`

📎 **Specsheet:** §6.1, §6.2, §5 · **Decisioni:** D11, D21
🎯 **Scope:** la pipeline si riduce da sola: segnali deterministici prima, modello come spareggio; budget dinamici; misura della calibrazione.
🧭 **Perché qui:** dopo, non prima: ora esistono le pipeline tra cui scegliere e le metriche per giudicare. I modelli piccoli stimano male la difficoltà: il deterministico fa da prima linea.

- [ ] **6.1** 🤖 `core/routing.py`.
  ```python
  class RoutingSignals(BaseModel):
      prompt_len: int; mentions_files: bool; target_file_count: int
      has_tests: bool; is_question: bool; domain_hint: str | None
  def deterministic_signals(request: str, target_dir: Path | None) -> RoutingSignals
  def choose_pipeline(sig: RoutingSignals, cls: "ClassifierOutput | None") -> Literal["direct","short","full"]
  ```
  Regole dure prima del modello (es. domanda secca senza target ⇒ `direct`); il Classifier decide solo i casi ambigui.
- [ ] **6.2** 🤖 `roles/classifier.py` + `roles/assessor.py` (una chiamata combinata, §23).
  ```python
  class ClassifierOutput(BaseModel):
      domain: Literal["coding","research_local","research_web","advice"]
      pipeline: Literal["direct","short","full"]
      risk: Literal["low","medium","high"]
  class AssessorOutput(BaseModel):
      difficulty: Literal["trivial","low","medium","high","critical"]
      token_budget: int; retry_budget: int
      verification_level: Literal["none","standard","strict"]
  ```
- [ ] **6.3** 🤖 Pipeline `direct` (una chiamata, niente piano) e `short` (piano-lampo: PhaseDesigner diretto senza Planner) nell'Orchestrator; il **rischio**, non solo la difficoltà, decide i controlli (§6.2).
- [ ] **6.4** 🤖 📌 Calibrazione: `routing_log` (§A5) riempito a ogni task (segnali, scelta, esito reale); report di accuratezza del Classifier/Assessor nell'Evaluator; +3 task semplici (`T015`–`T017`: domanda secca, lettura file singolo, patch banale).
- [ ] **6.5** 🔎 **Verifica di fase:** sui task semplici l'overhead di governance ≤ soglia F0.6 (vicino alla chiamata diretta); nessun task complesso del set instradato su `direct`; report calibrazione committato.

---

## Fase 7 — Domini non-coding: ricerca e consigli → `v6.0.0`

📎 **Specsheet:** §5, §22 · **Decisioni:** D16, D17
🎯 **Scope:** ricerca locale, ricerca web e consigli sulla stessa pipeline; verifica per fonti e triangolazione; Classifier esteso.
🧭 **Perché qui:** l'impianto è collaudato sul coding; ora si sostituisce l'oracolo meccanico con la verifica documentale. Banco di prova della generalità: Red Giant non è un coding assistant.

- [ ] **7.1** 🤖 Ricerca locale (`research_local`): riuso di `search_code`/`read_file` su scope documentale; output con **citazioni obbligatorie**.
  ```python
  class Citation(BaseModel): kind: Literal["file","url"]; ref: str; quote: str
  class ResearchFinding(BaseModel): claim: str; sources: list[Citation]   # min_length=1
  class ResearchReport(BaseModel):  answer: str; findings: list[ResearchFinding]; not_found: list[str]
  # core/verify.py, nuovo oracolo:
  def verify_citations(report: ResearchReport, scope: Scope, fetch_cache: Path) -> Verdict
  ```
  Verifica deterministica: la fonte esiste e contiene la quote (match tollerante a whitespace/case).
- [ ] **7.2** 🤖 Ricerca web (`research_web`): `tools/web.py` — `web_search` + `fetch_url` (cache su disco, estrazione testo). 🧑 **Decisione a inizio sottofase:** SearXNG self-hosted su Severino vs API di sola-search; vincolo D16 (il motore cerca, Gemma pensa). Triangolazione: affermazioni fattuali con ≥2 fonti indipendenti o dichiarate single-source.
- [ ] **7.3** 🤖 Consigli (`advice`): decisione esplicita e loggata web-first vs conoscenza del modello (criteri: freschezza richiesta, rischio dell'errore); se conoscenza → dichiarato nella risposta. Mai fonti finte: `verify_citations` gira comunque.
- [ ] **7.4** 🤖 Classifier esteso ai 4 domini (già nello schema F6); card dei ruoli aggiornate per dominio; Evaluator: +5 task (`T018`–`T022`: fatto verificabile locale, fatto web, domanda senza risposta trovabile → `not_found` onesto, consiglio a rubrica, trappola-citazione).
- [ ] **7.5** 🔎 **Verifica di fase:** 100% delle citazioni del benchmark verificate meccanicamente; `T020` termina con "non trovato" esplicito; la trappola-citazione (`T022`) viene respinta dal verificatore.

---

## Fase 8 — Benchmark reale + deploy su Severino → `v7.0.0`

📎 **Specsheet:** §19, §22 · **Decisioni:** D5, D6, D18, D19
🎯 **Scope:** chatbot Laravel 13 come benchmark reale, confronti della tesi, packaging Docker, deploy su Severino con hardening.
🧭 **Perché qui:** chiusura del cerchio: i numeri della tesi sul ferro vero e su un progetto vero.

- [ ] **8.1** 🧑🤖 Onboarding del chatbot Laravel 13 (quando esiste): suite `T100+` di task reali — bugfix, feature piccole, refactoring, domande sulla codebase, ricerca nella documentazione del progetto.
- [ ] **8.2** 🤖 📌 I confronti §22, sul set completo, su `severino-sim` **e** Severino reale: (1) E2B nudo · (2) E2B+pipeline · (3) E4B+pipeline (riferimento D1).
- [ ] **8.3** 🤖 Packaging: `docker/deploy/` — immagine Red Giant + compose per Severino accanto a llama-server; resource limits §6.8 homelab (4 core, RAM concordata); dominio `redgiant.home.varitest.ovh` via Caddy (🧑 conferma nome); niente porte esposte fuori dalla tailnet.
- [ ] **8.4** 🤖 Hardening (§19): Scope enforcement rivisto (path traversal, symlink), approvazione obbligatoria per ogni tool `requires_approval`, segreti mai nel contesto del modello, rete dei tool limitata alla whitelist, log completi e ruotati.
- [ ] **8.5** 🤖 Report finale: la tesi con i numeri — correttezza, verificabilità, affidabilità, task lunghi, risorse (§22) — committato in `bench/results/`.
- [ ] **8.6** 🔎 **Verifica di fase:** 🧑 l'utente usa Red Giant dalla GUI **su Severino** per un task reale sul chatbot Laravel, end-to-end, con metriche raccolte lì.

---

## Rischi aperti e mitigazioni

| Rischio | Prob. | Mitigazione |
|---|---|---|
| Overhead di governance > lavoro utile | alta | D11: A/B per ogni ruolo; token-utili come gate; pipeline ridotte (F6). |
| Supporto llama.cpp per Gemma 4 E2B acerbo (GGUF/grammatiche) | media | F0.3 prima di tutto; fallback: quant → versione llama.cpp → modello ponte. |
| E2B troppo debole per output di pianificazione | media | D21 (schemi piccoli, enum chiusi); il confronto E4B (F8.2) dirà se è limite di modello o di sistema. |
| Tuning su GPU nasconde i problemi CPU | alta | D6: metriche ufficiali solo CPU-only; verifiche di fase su severino-sim/Severino. |
| Prefill comunque troppo lento per l'uso interattivo | media | D7: prodotto batch by design; F5 dedicata; aspettative = job, non chat. |
| GUI che diventa un progetto a sé | bassa | HTMX senza build; ogni feature nasce da un bisogno di testing dell'utente. |
| Verifica documentale aggirabile (fonti citate ma non pertinenti) | media | Triangolazione + string-match delle quote + task-trappola `T022`. |
| Firme del piano che divergono dal codice | media | `scripts/check_reference.py` bloccante nel rituale; le firme si cambiano prima nel piano. |

## Cosa NON esiste ancora (per non cercarlo invano)

- **Nessun codice**: alla `v1.0.0` il repo contiene solo specsheet, questo piano e l'atlante iniziale.
- Il chatbot Laravel 13 (benchmark reale) sarà costruito **in un altro scenario** e arriva solo in F8.
- Multi-modalità, multi-modello simultaneo, parallelismo tra agenti: **esclusi per design** (D7), non "mancanti".
- Final Reviewer come ruolo separato (§6.8 spec): assorbito dal Supervisor + verifica finale dell'Orchestrator fino a prova (Evaluator) che serva separato.

# Red Giant — Codebase Reference (atlante)

**Aggiornato al:** 2026-08-01 · **Versione repo:** `v1.0.1` · **Fase completata:** nessuna (pre-F0)
**Regola:** questo documento descrive **il codice che esiste**, non quello pianificato (per quello c'è [plan_red_giant.md](plan_red_giant.md)). Se una cosa è nel codice e non è qui, il documento è rotto; se è qui e non è più nel codice, è peggio. Verifica meccanica: `python scripts/check_reference.py` (da F0.7) — bloccante nel rituale di fine fase.

---

## 1. Indice "dove sta cosa"

| Cerchi… | Vai in… |
|---|---|
| La visione e i requisiti del sistema | [small-model-powerhouse-specsheet.md](small-model-powerhouse-specsheet.md) |
| Le decisioni vincolanti (D1–D21) e il piano fase per fase | [plan_red_giant.md](plan_red_giant.md) |
| L'architettura di riferimento (albero, DB, config, tool, prompt S1→S7) | plan_red_giant.md §A1–A7 |
| Il rituale di fine fase e il versionamento dei branch | plan_red_giant.md, sezione "Rituale di fine fase" |
| Codice Python | **non esiste ancora** (nasce in F0) |

## 2. Albero dei file (reale, ad oggi)

```text
RedGiant/
└── memory/
    ├── small-model-powerhouse-specsheet.md   # specsheet v0.1 (visione, ruoli, componenti)
    ├── plan_red_giant.md                     # piano di sviluppo v1.2 (contratto di implementazione, autosufficiente)
    └── codebase_reference.md                 # questo file
```

## 3. Classi e metodi

### `redgiant/config.py` — caricamento configurazione (F0.1)

Dataclass frozen, una per sezione TOML (§A6 del piano). `Config.load` fa il merge default+profilo (superficiale, per sezione) e fallisce con `ValueError` sul nome esatto di ogni chiave/sezione sconosciuta; profilo inesistente → `FileNotFoundError`.

```python
class LlmProfileCfg      # base_url, ctx_size, timeout_s, temperature, max_tokens_default
class PathsCfg           # db, models_dir, tasks_dir, slots_dir, ripgrep
class BudgetCfg          # max_total_tokens, max_tool_calls, max_retries_per_subtask, max_wall_s
class WebCfg             # host, port
class SecurityCfg        # writable_globs, shell_whitelist (tuple immutabili)
class Config
    def load(cls, profile_name: str, config_dir: Path | None = None) -> "Config"
```

### `redgiant/cli.py` — CLI (stub F0.1)

```python
def main(argv: list[str] | None = None) -> int   # --version/--help; sottocomandi reali in F1.9
```

Le altre firme contrattuali (da rispettare o da cambiare *prima* nel piano) sono in plan_red_giant.md, fase per fase: StateStore e modelli (F1.1), LlamaClient (F1.2), PromptAssembler (F1.3), Scope/ToolSpec/ToolRouter (F1.4), Worker/WorkerStep (F1.5), verify (F1.6), Orchestrator/BudgetTracker (F1.7), Evaluator (F1.10), JobQueue (F2.1), Planner/PhaseDesigner (F3), Debugger/Supervisor/LoopGuard/CheckpointManager/BudgetManager (F4), ContextBuilder/CacheProbe/SlotManager/StateCompressor (F5), routing/Classifier/Assessor (F6), tool web e verifica citazioni (F7).

## 4. Database

**Nessun database esiste.** Lo schema previsto (SQLite, `data/redgiant.db`) è in plan_red_giant.md §A5; nasce in F1.1 (`StateStore.init_schema`), con le tabelle `approvals` (F2), `checkpoints` (F4), `routing_log` (F6) aggiunte nelle fasi indicate.

## 5. Endpoint / rotte

**Nessun endpoint esiste.** La tabella delle rotte GUI (FastAPI+HTMX) è in plan_red_giant.md F2.2.

## 6. Configurazione

**Nessun file di configurazione esiste.** Le chiavi previste (`config/default.toml` + `config/profiles/{dev-fast,severino-sim,severino}.toml`) sono in plan_red_giant.md §A6; nascono in F0.1/F0.4.

## 7. Catalogo dei test

**Nessun test esiste.** Convenzioni previste: `tests/unit/` (senza modello), `tests/integration/` (contro llama-server reale, marker pytest dedicato), Evaluator con task sintetici `T001+` (F1.10) — ogni task dimostra una capacità dichiarata nel piano.

## 8. Regole non negoziabili

Sono le decisioni D1–D21 in plan_red_giant.md §0. Le più facili da violare per sbaglio:

- **D3**: nessuna chiamata al modello senza schema vincolato (eccezione: generazione di testo libero finale, comunque loggata).
- **D6**: mai registrare metriche ufficiali su profilo GPU; le verifiche di fase girano su `severino-sim` o Severino.
- **D9/A4**: mai contenuto volatile nelle sezioni S1–S4 del prompt; l'ordine S1→S7 non si cambia.
- **D16**: nessuna API LLM esterna, in nessun componente, mai.
- **Rituale**: `check_reference.py` deve passare prima del commit di fine fase.

## 9. Trappole già disinnescate

Nessuna ancora (nessun codice). Ereditate dal contesto homelab, da tenere presenti:

- **Gemma 4 E2B è nuovissimo**: il supporto GGUF/grammatiche in llama.cpp può essere acerbo — per questo F0.3 è la prima verifica sostanziale del progetto (causa tecnica: i tokenizer/architetture nuove arrivano in llama.cpp a ondate, spesso con bug di quantizzazione iniziali).
- **La iGPU Vega del 5300U non aiuta** (ROCm non supportato su quelle integrate, Vulkan marginale): Severino è CPU pura, ogni stima va fatta CPU-only.

## 10. Debito tecnico aperto

Nessuno (nessun codice).

## 11. Il perché delle scelte non ovvie

- **Perché il piano fissa le firme prima del codice:** con un rituale che verifica meccanicamente atlante↔codice, la direzione del vincolo dev'essere unica (piano → codice), altrimenti l'atlante insegue invece di comandare.
- **Perché JSON e non YAML (D4)** nonostante la specsheet usi YAML negli esempi: il guided decoding di llama.cpp lavora su JSON Schema/GBNF; YAML resta il formato dei documenti umani.
- **Perché niente framework di agenti:** l'orchestrazione deterministica È il progetto; delegarla a una libreria significherebbe non poter rispondere di ogni byte (criterio dell'utente).
- **Perché il Final Reviewer non è (per ora) un ruolo:** costerebbe una chiamata in più per task su CPU; Supervisor + verifica finale coprono §6.8 finché l'Evaluator non dimostri che serve separato (D11 vale anche per i ruoli della specsheet).

## 12. Cosa NON esiste ancora

Tutto il codice. In dettaglio: nessun `pyproject.toml`, nessun pacchetto `redgiant/`, nessuno script, nessun Docker, nessun benchmark, nessun DB, nessuna GUI, nessun tool, nessun ruolo, nessun task sintetico. Il chatbot Laravel 13 vive in un altro scenario e arriva in F8. Primo codice: Fase 0, sottofase 0.1.

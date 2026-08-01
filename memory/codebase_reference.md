# Red Giant — Codebase Reference (atlante)

**Aggiornato al:** 2026-08-01 · **Versione repo:** `v1.1.0` · **Fase completata:** F0 (fondazioni e misure di base)
**Regola:** questo documento descrive **il codice che esiste**, non quello pianificato (per quello c'è [plan_red_giant.md](plan_red_giant.md)). Se una cosa è nel codice e non è qui, il documento è rotto; se è qui e non è più nel codice, è peggio. Verifica meccanica: `python scripts/check_reference.py` — bloccante nel rituale di fine fase.

---

## 1. Indice "dove sta cosa"

| Cerchi… | Vai in… |
|---|---|
| La visione e i requisiti del sistema | [small-model-powerhouse-specsheet.md](small-model-powerhouse-specsheet.md) |
| Le decisioni vincolanti (D1–D21) e il piano fase per fase | [plan_red_giant.md](plan_red_giant.md) |
| **I numeri di baseline e le decisioni derivate (F0.6)** | §8-bis qui sotto + commenti in `config/default.toml` + `bench/results/` |
| Caricamento configurazione e profili | `redgiant/config.py` + `config/*.toml` |
| Avvio/download del runtime e del modello | `scripts/*.ps1` |
| Il simulatore di Severino | `docker/severino-sim/compose.yml` |
| Sonda constrained decoding e bench di baseline | `bench/schemas_probe.py`, `bench/run_bench.py` |
| Verifica firme atlante↔codice | `scripts/check_reference.py` |
| Codice della pipeline (stato, ruoli, tool, orchestrator, GUI) | **non esiste ancora** (nasce in F1–F2) |

## 2. Albero dei file (reale, a fine F0)

```text
RedGiant/
├── pyproject.toml                  # redgiant 1.1.0, py>=3.12, deps pinnate ==, entry point `rg`
├── requirements.lock               # pip-compile --generate-hashes --allow-unsafe
├── README.md                       # inglese, stile GitHub (hero+logo, badge, mermaid); refresh a ogni fine fase
├── logo.png                        # logo ufficiale (usato nel hero del README)
├── .gitignore                      # models/, bin/, data/, bench/results/raw/, .venv/, __pycache__/
├── config/
│   ├── default.toml                # tutte le chiavi §A6 + blocco decisioni F0.6 in commento
│   └── profiles/
│       ├── dev-fast.toml           # GPU locale :8080 (MAI metriche ufficiali)
│       ├── severino-sim.toml       # container CPU :8081 (metriche ufficiali)
│       └── severino.toml           # endpoint tailnet provvisorio, timeout 1200s
├── docker/severino-sim/compose.yml # immagine ghcr pinnata PER DIGEST (b10200), cpuset 0-1,
│                                   # --threads 2, mem 10g, ctx 16384 (per misure; budget d'uso=8192)
├── scripts/
│   ├── download-llama.ps1          # binari Windows b10217 (cuda+cpu) in bin/ — idempotente
│   ├── download-model.ps1          # GGUF QAT UD-Q4_K_XL, URL+SHA256 nel file — idempotente
│   ├── start-llama.ps1             # -Profile dev-fast|severino-sim|severino
│   └── check_reference.py          # verifica meccanica firme (Passo 3 del rituale)
├── bench/
│   ├── schemas_probe.py            # sonda F0.3 (3 schemi × 20 gen, guided decoding)
│   ├── run_bench.py                # baseline F0.5 (prefill/gen/riuso/slot, --steps selezionabili)
│   └── results/
│       ├── f0_constrained_decoding.md   # verdetto D3: 60/60+60/60, overhead 0.4-9.8%
│       └── f0_baseline_severino-sim.md  # tabella prefill/gen, prova D9, verdetto slot
├── models/   (gitignored)          # gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf (2.44 GB, SHA256 verificato)
├── bin/      (gitignored)          # llama-b10217/{cuda,cpu}/llama-server.exe
├── data/     (gitignored)          # slots/, log server; il DB nasce in F1
└── redgiant/
    ├── __init__.py                 # __version__ = "1.1.0"
    ├── config.py                   # loader TOML (v. §3)
    └── cli.py                      # stub (--version/--help; sottocomandi in F1.9)
```

## 3. Classi e metodi

### `redgiant/config.py` — caricamento configurazione (F0.1)

Dataclass frozen, una per sezione TOML (§A6 del piano). `Config.load` fa il merge default+profilo (superficiale, per sezione) e fallisce con `ValueError` sul nome esatto di ogni chiave/sezione sconosciuta (schema ammesso in `_KNOWN_KEYS`); profilo inesistente → `FileNotFoundError`.

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

*(Fuori perimetro del check meccanico ma documentati per completezza: `scripts/check_reference.py` espone `extract_signatures(pkg_dir) -> dict`, `extract_documented(md_path) -> dict`, `compare(real, doc) -> list[str]`, `main() -> int`; `bench/run_bench.py` espone `run(profile, url, ctx_sizes, repeats, out_dir, steps=None) -> Path` e `main() -> int`; `bench/schemas_probe.py` espone i tre schemi Probe* e `run(url, n, out_path) -> int`.)*

Le firme contrattuali future sono in plan_red_giant.md, fase per fase.

## 4. Database

**Nessun database esiste.** Lo schema (SQLite, DDL integrale) è in plan_red_giant.md §A5; nasce in F1.1.

## 5. Endpoint / rotte

**Nessun endpoint nostro esiste.** (Le rotte GUI arrivano in F2.2.) Endpoint llama-server usati finora: `POST /completion` (con `json_schema`, `cache_prompt`, `seed`), `POST /tokenize`, `GET /props`, `POST /slots/0?action=save|restore`.

## 6. Configurazione

Chiavi e default: v. `config/default.toml` (commentato) e piano §A6. Valori derivati/confermati da F0.6: `llm.ctx_size=8192`, `llm.timeout_s=600` (severino: 1200), budget generazione per ruolo (worker 512 · planner 1536 · phase_designer 2048 · debugger 768 · supervisor 512), preambolo S1–S3 ≤1500 token, reuse_ratio Worker target ≥0.6.

**Pin di piattaforma (F0.2):**
- Immagine di riferimento: `ghcr.io/ggml-org/llama.cpp@sha256:8b7f05d7d14d...e98db` (build **b10200**) — usata da severino-sim e, in F8, da Severino.
- Binari Windows dev: release **b10217** (b10200 non pubblica asset Windows; scarto di 17 build irrilevante per le metriche, che nascono solo sui profili CPU).
- Modello: `unsloth/gemma-4-E2B-it-qat-GGUF` → `gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf`, SHA256 `e531...6889` (2.620.370.976 byte). QAT scelta su Q4 "liscia": qualità quasi-BF16 al peso di una Q4. Testo-only: niente mmproj.

## 7. Catalogo dei test

**Nessun test pytest esiste ancora** (nascono in F1). Le verifiche eseguibili di F0 sono i due strumenti di bench: `schemas_probe.py` (dimostra D3: forma 60/60, contenuto 60/60, con soglia contenuto-pieno ≥90% cablata nell'exit code) e `run_bench.py` (produce la baseline; `--steps` per rieseguire un solo passo).

## 8. Regole non negoziabili

Sono le D1–D21 in plan_red_giant.md §0, più il rituale (incluso il **Passo 2-bis**: refresh del README a ogni fine fase). Le più facili da violare per sbaglio, aggiornate coi fatti di F0:

- **D3 operativa**: ogni chiamata con schema DEVE (a) usare il template di turno Gemma, (b) includere lo schema JSON nel prompt, (c) chiedere JSON compatto, (d) controllare lo stop reason — `limit` è un errore, mai output buono.
- **D6**: mai metriche da profili non vincolati; il bench si auto-marca "non ufficiale" su dev-fast.
- **D9/A4**: mai contenuto volatile nei prefissi — un byte a metà prompt costa ~120× l'append (misurato).
- **Pin**: cambiare build llama.cpp o quantizzazione = rifare F0.5 e annotare qui.

## 8-bis. Numeri di baseline (F0.5, severino-sim: 2 core 9900X ≈ 4 core Severino, mem 10g)

| Misura | Valore |
|---|---|
| Prefill freddo 1K / 4K / 8K / 16K | 151 / 133 / 118 / 94 tok/s → **6.8s / 30.7s / 69.6s / 173.6s** |
| Generazione | **35.8 tok/s** (dev.std 0.2; memory-bound: 24 thread → 42) |
| Riuso prefisso (ctx 8K) | append: **65** token riprocessati · 1 byte cambiato a metà: **7971** |
| Guided decoding | overhead **0.4–9.8%** sul tok/s di generazione |
| Slot save/restore | save 56-211ms, restore 42-164ms, ~13.4 KB/token su disco — **riuso post-restore NON funzionante** (v. §9) |

## 9. Trappole già disinnescate

- **La grammatica vincola ma non informa** (F0.3, run 1): guided decoding senza schema nel prompt → JSON valido pieno di placeholder letterali (`"..."`, `"$id"`). Causa: il sampler vede la grammatica, il modello no. Fix: schema sempre nel prompt (futuro S7).
- **Template di turno obbligatorio anche su `/completion`** (F0.3): senza `<start_of_turn>…` Gemma degenera. Fix: turn markers in ogni prompt.
- **Troncamento > grammatica** (F0.3, run 2): output tagliato a `n_predict` = JSON rotto nonostante la grammatica; il pretty-print spreca 20-30% dei token. Fix: budget per schema con margine ~2×, JSON compatto richiesto, stop reason controllato.
- **Slot restore non ripristina lo stato di riuso** (F0.5, build b10200): `n_restored` corretto ma il prompt identico post-restore riprocessa il 100% dei token (il bookkeeping LCP non viene ripristinato). Il riuso normale via `cache_prompt` funziona (1/872 su prompt ripetuto). → slot-save inutilizzabile come skip del prefill su questa build; riverifica in F5.4.
- **llama-server muore silenziosamente se `--slot-save-path` punta a una directory inesistente** (F0.2): nessun errore utile a video quando lanciato detached. Fix: gli script creano le directory prima dell'avvio.
- **pip-tools 7.6.0 incompatibile con pip ≥25.3** (F0.1): `ImportError: stdlib_pkgs`. Fix: pip bloccato a 25.2 nel venv (e pinnato nel lockfile con `--allow-unsafe`).
- **ghcr di llama.cpp non pubblica tag per-release** (F0.2): solo tag mobili (`server`) e buildcache. Fix: pin per digest; la build nell'immagine (`b10200`) letta con `--version` e allineata a posteriori.
- **Il prompt di sfratto "testo invertito" tokenizza ~2× peggio** (F0.5, run 1): `[::-1]` ha sforato il contesto (17182 > 16384). Fix: sfratto = frase diversa ripetuta, con conteggio token misurato.
- Ereditate dal contesto homelab: Gemma 4 nuovissimo → cautela sulle build llama.cpp; iGPU Vega inutilizzabile → Severino è CPU pura.

## 10. Debito tecnico aperto

| Cosa | Perché rimandato | Quando |
|---|---|---|
| Soglia di convenienza slot-save non fissata | il restore non ripristina il riuso su b10200: senza beneficio misurabile non c'è soglia | F5.4, provando una build più recente |
| `useful_tokens` v0 definita ma non ancora implementata | serve l'Evaluator | F1.10 |
| Scarto build b10217 (Windows) vs b10200 (riferimento) | b10200 senza asset Windows; impatto nullo sulle metriche | riallineare al prossimo bump di pin |
| Entry point CLI `rg` omonimo di ripgrep | nel venv attivo `rg` risolve al nostro stub; `search_code` userà il path assoluto di ripgrep risolto fuori dal venv | decidere in F1.4 (rinominare o risolvere via config) |

## 11. Il perché delle scelte non ovvie

- **Perché la quantizzazione QAT UD-Q4_K_XL** e non una Q4 "liscia": è la Q4 addestrata (quantization-aware), qualità vicina a BF16 allo stesso peso — sul modello più piccolo possibile ogni punto di qualità è prezioso (D1).
- **Perché il pin per digest e non per tag**: il registry non offre tag immutabili per release; il digest è l'unico riferimento che non può cambiare sotto i piedi.
- **Perché severino-sim usa 2 core del 9900X** (decisione utente, 2026-08-01): un core Zen 4 @5.3GHz vale ~2× un core Zen 2 @15W; 2 core qui approssimano i 4 che Red Giant avrà su Severino. Un bench parziale a 4 core è stato scartato.
- **Perché il container tiene ctx 16384 ma la config dice 8192**: il server è il laboratorio (deve poter *misurare* fino a 16K); il budget d'uso per chiamata è una politica del client (D8).
- **Perché niente framework di agenti / ORM / SDK LLM**: l'orchestrazione deterministica È il progetto; ogni byte deve essere rispondibile (criterio dell'utente).
- **Perché JSON e non YAML (D4)**: il guided decoding lavora su JSON Schema/GBNF; YAML è ostile alle grammatiche.
- **Perché il Final Reviewer non è (per ora) un ruolo**: costerebbe una chiamata in più per task su CPU; Supervisor + verifica finale coprono §6.8 finché un A/B non dimostri il contrario (D11).

## 12. Cosa NON esiste ancora

Tutta la pipeline: stato/StateStore, LlamaClient, PromptAssembler e prompt, tool layer, ruoli (Worker in primis), Orchestrator, Evaluator, GUI, DB, test pytest. Primo codice di pipeline: **F1.1**. Il chatbot Laravel 13 (benchmark reale) vive in un altro scenario e arriva in F8. Esclusi per design (non "mancanti"): multi-modalità, multi-modello simultaneo, parallelismo tra agenti, API JSON pubblica.

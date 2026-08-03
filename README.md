<div align="center">

<img src="logo.png" alt="Red Giant — Verify. Optimize. Execute." width="380">

**A verification-first agentic system that makes *tiny* local language models<br>reliably useful on non-prosumer hardware.**

[![Status](https://img.shields.io/badge/status-v4.2.0_·_thinking_measured_role_by_role_·_verdicts_enforced-brightgreen)](memory/plan_thinking_ab.md)
[![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Model](https://img.shields.io/badge/model-Gemma_4_E2B_·_Q4_QAT_·_GGUF-8A2BE2)](https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF)
[![Runtime](https://img.shields.io/badge/runtime-llama.cpp_(pinned)-555555)](docker/severino-sim/compose.yml)
[![Inference](https://img.shields.io/badge/inference-CPU--only_·_4_cores-D7263D)](#-target-hardware-severino)
[![No cloud](https://img.shields.io/badge/external_LLM_APIs-never-2E8B57)](#-key-technical-decisions)
[![License](https://img.shields.io/badge/license-MIT_·_attribution_required-blue)](LICENSE)

*The model stays small. The **system** becomes large.*

[Thesis](#-the-thesis) · [Niche](#-where-this-sits--the-niche-honestly) · [Findings](#-engineering-findings--measured-lessons-from-a-2b-local-agent) · [Scoreboard](#-the-scoreboard--every-official-ab-in-numbers) · [Cast](#-the-cast) · [Assembly line](#-how-the-assembly-line-actually-works) · [Roadmap](#%EF%B8%8F-roadmap--and-how-its-actually-going) · [Quickstart](#-getting-started-development-windows)

</div>

---

## 📑 Index

- **[🧠 The thesis](#-the-thesis)** — what this project bets on, in four principles
- **[🧭 Where this sits — the niche, honestly](#-where-this-sits--the-niche-honestly)** — the landscape, the supporting research (with sources), and the honest boundary
- **[⚙️ Key technical decisions](#-key-technical-decisions)** — model, runtime, grammar, sequentiality, no-cloud
- **[🔬 Engineering findings (F1–F20)](#-engineering-findings--measured-lessons-from-a-2b-local-agent)** — the measured lessons:
  - [🔧 Tool design](#-tool-design-how-a-small-model-edits-files-reliably) (F1–F2) · [🔒 Constrained decoding](#-constrained-decoding-the-grammar-gives-you-shape-not-meaning) (F3–F4) · [🧨 Small-model failure modes](#-failure-modes-of-small-models-in-agent-loops) (F5–F7)
  - [🪙 Token economy](#-token-economy-on-cpu-only-inference) (F8–F9) · [📏 **The scoreboard — every official A/B**](#-the-scoreboard--every-official-ab-in-numbers)
  - [♻️ KV-cache & prefill](#%EF%B8%8F-kv-cache-reuse-and-prefill-engineering) (F10–F11) · [🎛️ Orchestration](#%EF%B8%8F-orchestration-running-an-unreliable-proposer-safely) (F12) · [✅ Verification design](#-verification-design-trusting-an-agent-you-cannot-trust) (F13) · [🤝 Consent UX](#-consent-ux-humans-in-the-loop-without-losing-the-cache) (F14)
  - [🧭 Planner rebuild](#-planner-rebuild-smj-reference-coherence-is-the-control-planes-job) (F15–F18) · [🧠 **Thinking mode, role by role**](#-thinking-mode-measured-role-by-role) (F19–F20)
- **[🌟 The cast](#-the-cast)** — Sirio, Mira, Mizar, Vega, Altair, Giano: who does what
- **[🏭 How the assembly line actually works](#-how-the-assembly-line-actually-works)** — no agent talks to another; the three separations; the flow in one line
- **[🔁 Pipeline at a glance](#-pipeline-at-a-glance)** — the diagram and the four domains
- **[🖥️ Target hardware ("Severino")](#%EF%B8%8F-target-hardware-severino)** — the 15W mini-PC this is all for
- **[🗺️ Roadmap — and how it's actually going](#%EF%B8%8F-roadmap--and-how-its-actually-going)** — F0→F8, phase by phase, verdicts included
- **[📚 Repository map](#-repository-map)** · **[🚀 Getting started](#-getting-started-development-windows)**

Red Giant wraps a **~2B-effective-parameter model** — Gemma 4 E2B, Q4 QAT, GGUF, CPU-only — in a deterministic pipeline of **decomposition, continuous verification, minimal context, and KV-cache-aware prompt engineering**.

> Most agentic projects chase the biggest model they can reach. Red Giant goes the opposite way: the smallest usable model, on the kind of machine a non-prosumer actually owns — a 15W mini-PC with 4 CPU cores and no usable GPU. Anyone can build agents on a workstation-class GPU box; the interesting problem is closing the gap between local inference on consumer hardware and the inevitable scarcity of that scenario.

**Status:** early development, `v4.2.0` — **the thinking-mode campaign is closed: full-time thinking stays off by default — verdict deliberately left open** (Δverified = 0 on the official CPU A/B at 1.4× cost, *measured on synthetic coding without routing*; both the plan compiler and thinking are one config flag away, and a mandatory retest with the router active on everyday/math domains is written into the plan — F19–F20 map exactly where reasoning pays so far). And **F3-bis just landed: the first multi-domain battery — local document analysis, a whitelisted API call, a document-to-CSV transform — went 3/3 verified on the first official run**, the opening evidence that this engine is not a coding assistant. Next: F4 (continuous verification & supervision). The plan compiler (the cast below: Sirio → Mira/Mizar/Vega/Altair → Giano, behind a deterministic control plane) is **built, integrated into the product and gated off by its own A/B verdict** (`v4.0.0`, merged to `main`): 2/13 vs the naive baseline's 6–8/13 on micro-tasks, 0/3 both arms on the wide tasks it was built for — but its failures cost **44% fewer tokens**, its one honesty gap in 35 official runs was diagnosed and closed the same day, and every ablated gate proved its keep (+50–76% failure cost without). ~50 permanent deterministic rules were distilled from **over 400 instrumented end-to-end runs**. The current campaign measures Gemma 4's **native thinking mode role by role** (F19–F20): the executor's failures *halve* when he thinks — including the first-ever solve of the project's oldest reasoning-trap task — the planner's thinking buys record execution depth, and verification-side thinking raises the bar for everyone; the official CPU A/B is in progress, with a pre-registered decision rule. The earlier in-loop planner (2/10 vs 9/10) remains deprecated behind its own gate. Behind all of it, the Phase-2 single-process web GUI (async job queue, live execution tree, consent-based approvals with standing per-file grants, budget-extension prompts, guided relaunch, plan-document tabs and gate tables for compiler tasks) was live-tested through 3 rounds of user testing plus an automated battery: **15 defects found and fixed**, zero false claims in either direction. This README is refreshed at the end of every development phase.

## 🧠 The thesis

Small language models don't fail because they lack intelligence for a single step; they fail from *breadth*: tasks too wide, contexts too long, ambiguous instructions, unverified claims of success, errors compounding across steps. Red Giant doesn't try to make the model smarter — it systematically removes the conditions under which small models fail:

| # | Principle | In practice |
|---|---|---|
| 1 | **Global planning, local execution** | A synthetic, versioned plan; only the current phase is expanded; only one subtask runs at a time |
| 2 | **Continuous verification** | Deterministic oracles first (tests, compilers, linters, exit codes, citation matching); a model-based verifier only where no mechanical oracle exists. Subtasks are *designed* to be mechanically verifiable |
| 3 | **Minimal context** | Each role receives the least sufficient context (~4–8K tokens per call), never the full history |
| 4 | **Deterministic orchestration** | *The model proposes; the orchestrator decides.* Every state mutation is typed, attributed, persisted (SQLite). No success without recorded evidence |

## 🧭 Where this sits — the niche, honestly

The local-AI landscape splits into a few well-served categories, and Red Giant deliberately is none of them:

- **Agent orchestration frameworks** give you graphs, crews and tool-calling loops — but they implicitly assume a *capable* model (a cloud API or a large local one) that can recover from its own mistakes. Point them at a 2B model on a CPU and they spiral: the retry loops, verbose prompts and long contexts they rely on are exactly what small models and slow prefill cannot afford.
- **Local inference runners** solve *running* models on your hardware — quantization, serving, chat UIs. Essential plumbing (this project builds on one of them), but they stop where the hard problem starts: a served model is not a reliable agent.
- **Structured-output libraries** solve format validity via constrained decoding. Also essential, also a component: format-valid output can still be semantically empty, truncated, or confidently wrong — this project's field notes document exactly how.
- **Research on small-model agents** increasingly says the promising recipe is small models + strict specifications + external validators — and by now it says it with numbers. Grammar-constrained decoding helps *smallest models most* ([NVIDIA measured +42.5 points on a 0.6B](https://developer.nvidia.com/blog/improving-bash-generation-in-small-language-models-with-grammar-constrained-decoding/), single digits on 3–4B); tool-based external verification lets [a 1B outperform an 8B on MATH](https://arxiv.org/abs/2504.04718); much of small-model "unreliability" is interface failure, not reasoning failure, and is [fixable mechanically](https://arxiv.org/abs/2605.02363); small models' *self*-critique makes things worse while external grounding helps ([measured](https://arxiv.org/abs/2601.00513) — the reason this project's judges never trust the defendant); harness quality alone moves agent benchmarks by [20–40 points at fixed model size](https://arxiv.org/abs/2606.08529); and a ~1B model in a strict schema-validated harness [beats GPT-3.5-Turbo at function calling](https://arxiv.org/abs/2409.03215). NVIDIA's [SLM-agents position paper](https://arxiv.org/abs/2506.02153) argues the same direction. Still: mostly papers and benchmarks — few end-to-end engineered systems exist, and fewer still target genuinely constrained hardware.

**Red Giant sits at an intersection few projects serve**: a complete, engineered agentic *system* — not a library — purpose-built for ~2B-parameter models on watt-constrained, CPU-only consumer hardware (a 15W mini-PC, 4 cores), where token economy, KV-cache reuse, deterministic verification and human consent are the architecture, not afterthoughts. Every design decision is documented with the measurement that justifies it, and every failure mode found in the field is recorded with its technical cause.

**What it is not, equally honestly:** not a drop-in framework you `pip install` around your own model (it is opinionated end-to-end); not validated beyond small synthetic repositories yet (the real-codebase exam is a planned phase); currently calibrated on one specific model and runtime build; and not an attempt to compete with big-model agents on capability — the bet is on raising the *floor* of what trivial hardware can do reliably, not the ceiling of what intelligence can do. The literature draws the same boundary this project's own A/Bs found: per-step reliability compounds (p^H) over long dependent chains, [even frontier models collapse on multi-hour tasks](https://metr.org/time-horizons/), reasoning that isn't there [cannot be prompted into a 2B](https://arxiv.org/abs/2402.12038), and [4-bit quantization taxes small models disproportionately](https://arxiv.org/abs/2511.13023) (why this project uses QAT). The floor rises substantially; the ceiling does not move.

If you are trying to make a small local model do real, verified work on hardware you already own — this is the problem space this repository lives in, traps and all.

## ⚙️ Key technical decisions

| Decision | Rationale |
|---|---|
| 🐜 **Model: Gemma 4 E2B** (QAT, UD-Q4_K_XL GGUF) — the smallest, on purpose | Every measured improvement is attributable to the architecture, not model scale. E4B exists only as an evaluation reference |
| 📌 **Runtime: llama.cpp `llama-server`, version-pinned** (container digest = the reference) | Direct access to grammar-constrained decoding, KV-cache control (`cache_prompt`, slots, `--slot-save-path`), separate prefill/generation timings |
| 🔒 **Grammar-constrained decoding on every structured output** (JSON Schema → GBNF) | The sampler *cannot* produce malformed output: that failure class is eliminated by construction. Measured overhead: 0.4–10% |
| 🧩 **JSON-only runtime; one small Pydantic schema per role; closed enums** | A 2B model fills 8 constrained fields well and 40 free-text fields badly. Schemas double as the grammar contract |
| ♻️ **Stable prompt prefixes (S1→S7 layout), append-only agent loop** | llama.cpp reuses KV cache only for byte-identical prefixes. Prefill is the dominant cost on CPU — prefill engineering is a first-class goal of the project |
| 🚦 **Strictly sequential, batch-style execution; one inference at a time** | On 4 shared cores, concurrent inference is self-sabotage. Tasks are async jobs (launch, close the page, come back), not a chat |
| ⚖️ **Every cognitive role must earn its place** (A/B in a built-in evaluator) | Guards against governance overhead exceeding useful work. Guiding metric: **useful tokens / total tokens**. A role that doesn't pay for itself is removed |
| 📉 **Official metrics are CPU-only, on resource-capped profiles** | A dev GPU hides every token-economy problem. The reference profile is a Docker container capped to target-equivalent resources |
| 🚫 **No external LLM APIs, ever** | A system that escapes to a big model under pressure proves nothing. Honest explicit failure is a valid result |
| 🪶 **Stack: Python · FastAPI + HTMX + Jinja2 · SQLite · zero frontend build** | One process, one port, deployable as one container next to llama-server |

## 🔬 Engineering findings — measured lessons from a 2B local agent

This section records the engineering findings produced while building Red Giant. Most are **not claimed as novel principles in isolation**: several confirm established practice, but quantify its impact in an unusually constrained regime — a ~2B model, grammar-constrained JSON tool calls, CPU-only inference. Others document stack-specific failure modes or design patterns that emerged during implementation. Each finding states what was observed, the measured evidence, the countermeasure that now ships as working code, and how far the evidence reaches; findings may be revised, narrowed or retired as testing expands to other models, runtimes and real codebases. The **20 findings** below rest on **27 recorded observations** plus **over 400 instrumented end-to-end runs** of the planner-system rebuild and the thinking-mode campaign, culminating in the official PS6 A/B (F8, F15–F18) and the role-by-role thinking grid (F19–F20) — the full set, each mapped to its file and technical cause, lives in the [codebase atlas §9](memory/codebase_reference.md), with raw reports in [`bench/results/`](bench/results/).

*Labels:* **measured confirmation** — known principle, quantified in this regime · **implementation finding** — behaviour that emerged building the system · **stack-specific** — tied to Gemma 4 E2B / the pinned llama.cpp build (the lesson may transfer; the numbers won't) · **engineering safeguard** — ordinary robustness, listed because its absence measurably hurt · **open hypothesis** — preliminary, awaiting larger-scale tests.

### 🔧 Tool design: how a small model edits files reliably

- **F1 — The edit interface must adapt to the model, not vice versa.** *(measured confirmation)* In the tested setup, unified diffs rejected logically correct fixes over a single blank-line context mismatch and looped; switching the worker to `old_string → new_string` replacement with a uniqueness requirement turned the same fix tasks from 20+ failing calls into 5–6 clean ones. The posture generalized: the model copies every representation artifact it sees — line-number prefixes pasted into edits and whole-file writes (prompt rules alone did not eliminate it), CRLF checkouts displayed as LF making every match impossible — so every write path normalizes both directions rather than legislating against the behaviour.
- **F2 — Tool failures must be state-aware and actionable.** *(engineering safeguard)* Ordinary robustness, listed because its absence measurably hurt: an edit that changes nothing (old = new) is an error, not a success — 15 identical no-op edits once ran to step-budget death as "successes"; a failed match returns the *closest matching region* of the file, turning multi-call not-found loops into one-round recoveries; a write that would break the file's syntax is rejected before touching disk, with the error line returned as data.

### 🔒 Constrained decoding: the grammar gives you shape, not meaning

- **F3 — The grammar constrains, but does not inform — and only within the token budget.** *(implementation finding)* With guided decoding active but the schema absent from the prompt, outputs were structurally valid JSON filled with literal placeholders (`"..."`, `"$id"`): 0/60 semantically usable, 60/60 once the schema was shown in the prompt, at 0.4–9.8% grammar overhead. Corollaries: output truncated at the token limit is broken JSON *despite* the grammar, so stop reason `limit` is an explicit error and per-role budgets are sized with headroom; and the instruction-tuned model needed its chat template even for raw structured completions *(stack-specific evidence)*.
- **F4 — Make incoherent output unrepresentable instead of validating it away.** *(implementation finding)* A raw `"` inside a JSON string *legally* closes it; when the schema offered an escape branch (a nullable required object), a derailed model took it, and one bad character became a 60-call loop. Discriminated unions removed the branch from the grammar itself — after a derail the model is forced back into a coherent step. Measured: 8/8 derail probes recovered structurally.

### 🧨 Failure modes of small models in agent loops

- **F5 — Small models invent identifiers under pressure; anchor them to the contract.** *(implementation finding)* Asked to plan around unseen code, the model named things by association (`slugify` where the tests import `slug`) and the invention propagated plan → code → failure. Countermeasure: **contract anchoring** — planning roles receive verbatim excerpts of the tests they must satisfy, and objectives are phrased by outcome, never by imagined API.
- **F6 — The prompt and the validator are one artifact.** *(implementation finding)* Deleting one sentence from a role prompt (*"verification entries must be exactly the known command ids"*) while the validator kept enforcing it killed 6 tasks out of 10 before a single tool call. In the tested regime the model executes exactly what it is told and cannot infer the missing half of a contract — every validator rule needs its sentence in the prompt, and official measurements run only from committed, tested code.
- **F7 — Determinism is per-backend, and without a fixed seed it does not exist at all.** *(stack-specific)* Unseeded, the server draws a random seed per request — pass/fail became a lottery across runs; with a fixed seed, CUDA and CPU builds still produced *different* trajectories. Reproducibility required pinning seed + backend + build together — a GPU dev pass is a hint, never a result.

### 🪙 Token economy on CPU-only inference

- **F8 — Planning governance must earn its keep; measured twice, it has not — but the *cost of failing* tells a different story.** *(measured, verdict standing)* The in-loop planner lost its A/B outright (**2/10 vs 9/10** for the naive baseline, 815K vs 710K tokens) and was gated off. Its redesigned successor — a plan *compiler* behind deterministic gates (S/M/J) — was then measured on a harder battery including three genuinely multi-session tasks: **2/13 vs 6/13**, with both arms at **0/3 on the wide tasks** — so it stays gated. What the rebuilt system *does* buy, measured: failures cost **44% fewer tokens** (636K vs 1,143K, equal wall time), useful-token share +9pt, and component ablations show each gate pays for itself in failure containment (removing oracle qualification, the task ledger, or the entry gate raises failure cost by **+51% / +76% / +50%** respectively). Three of the wide-task deaths traced to fixable control-plane defects, not model limits; the verdict reopens after those fixes plus a controlled thinking-mode experiment on the planning roles.
- **F9 — Token accounting must be explicit, compact and clamped.** *(engineering safeguard)* Compact JSON (no pretty-printing, in either direction) saved 20–30% of output tokens with no measured quality loss. And budget math must clamp against runtime cache reporting: the server can report more cached tokens than the prompt count, naive `prompt − cached` goes negative, and a summed budget silently *disables itself* — work is charged as `max(prompt − cached, 0) + generated` per call.

### 📏 The scoreboard — every official A/B, in numbers

All runs on the CPU reference profile (`severino-sim`), committed code only, external judges. This is the evidence the thesis stands on — including the parts it does *not* yet support.

**Where the floor HAS been raised, measured** (same model, same hardware — only the workflow changed):

| Lever | Without | With | Finding |
|---|---|---|---|
| Edit interface adapted to the model (diff → exact-string) | 20+ failing calls per fix | **5–6 clean calls** | F1 |
| Schema shown in prompt (grammar alone) | **0/60** semantically usable | **60/60** | F3 |
| Structural derail recovery (discriminated unions) | 60-call chaos loop | **8/8 probes recovered** | F4 |
| Stable prompt prefixes (append-only loops) | 7,971 tokens reprocessed on one changed byte | **65 tokens** | F10 |
| Identity decisions moved to control plane | invented files 6/20 · name mismatches 11/20 · oracle-fooling tests 5/20 | **0 · 0 · 0** | F15 |
| False success claims (verification-first, both directions) | — | **1 gap in 35 official A/B runs**, cause diagnosed and gated | F13/F18 |

**Where it has NOT been raised (yet) — the planning A/Bs, honestly:**

| Official run (severino-sim) | Verified | Tokens | Useful % | Wall |
|---|---|---|---|---|
| F3 A/B — baseline static | **9/10** | 710K | — | — |
| F3 A/B — in-loop planner | 2/10 | 815K (~10× LLM calls) | — | — |
| PS6 A/B — baseline naive (13 tasks) | **6/13** | 1,143K | 20.8% | 2,610s |
| PS6 A/B — S/M/J plan compiler (13 tasks) | 2/13 | **636K (−44%)** | **30.2%** | 2,632s |
| PS6 — both arms on the 3 multi-session tasks | **0/3 vs 0/3** | 387K vs 192K | — | — |
| PS6-bis re-measure after 4 control-plane fixes | baseline **8/13** · compiler 2/13 | 1,178K · 857K | — | — |

*(The 6/13↔8/13 baseline swing on identical code revealed the CPU noise band of ±2/13 — see F17; verdicts now come from multiple runs. After the fixes the compiler's failures run far deeper — tasks that died at 0 tool calls now execute 20–38 calls with 80–93% useful tokens — and its one honesty gap closed to 0, but conversion is still blocked by the two model-capability walls.)*

**Component ablations** (plan compiler, 3 wide tasks — all arms 0/3, so the comparison is the *cost of failing*):

| Configuration | Tokens | vs full system |
|---|---|---|
| Full S/M/J compiler | 192K | — |
| − oracle qualification gate | 290K | **+51%** |
| − task ledger | 338K | **+76%** |
| − phase entry gate | 288K | **+50%** |

Reading: at the *step* level the workflow demonstrably turns an unreliable 2B into a reliable executor (first table). At the *plan* level the governance does not yet convert wide tasks — it makes failure **honest** (completed≠verified gap ≈ 0) and **cheap** (−44% tokens; every gate pays for itself in containment), which is the precondition for the next lever (explicit reasoning for the planning roles) to be measurable at all. The verdict stays: planner gated off until it wins its A/B.

### ♻️ KV-cache reuse and prefill engineering

- **F10 — Prefix instability dominated agent-loop cost in the tested CPU setup.** *(measured confirmation — the strongest numbers in this repository)* Cold prefill on target-equivalent cores: 6.8s @ 1K → 30.7s @ 4K → 69.6s @ 8K → **173.6s @ 16K** of context; generation is memory-bound at 35.8 tok/s. Against that physics, call count alone predicted latency poorly: an 88-call append-only session incurred only **~82s of total prefill**, while changing one byte inside the shared prefix raised reprocessing from **65 to 7,971 tokens** (~120×). This supports treating prompt layout — stable prefixes, append-only agent loops — as part of the runtime architecture, not as prompt style.
- **F11 — Persistence claims must be measured, not trusted.** *(stack-specific)* KV-slot `save`/`restore` on the pinned llama.cpp build round-trips cleanly and returns ok — and then the very same prompt reprocesses 100% of its tokens, while ordinary `cache_prompt` reuse works perfectly. The feature is shelved; only the reuse counters tell the truth.

### 🎛️ Orchestration: running an unreliable proposer safely

- **F12 — The model proposes; deterministic code decides — and every model-driven loop needs an exit the model cannot veto.** *(engineering safeguard)* Plan and design *logic* (unique ids, acyclic dependencies, known commands, scoped verification) is validated in plain code, with exactly one corrective re-call — which must *cite the violated rule*, not just list symptoms, or the small model cannot fix it — then explicit failure. Every cap in this codebase (design rounds, replans, per-error counts, step budgets) exists because its absence produced a real infinite loop: a designer redesigning the same phase forever, 49 rewrites of one file, 15 identical no-ops. Caps are the price of running an unreliable proposer safely.

### ✅ Verification design: trusting an agent you cannot trust

- **F13 — Verification must be symmetric, scoped, and closed-world.** *(implementation finding)* Model claims are hypotheses in both directions: "answer written to file" with no write call in the session fails, and "I am blocked" with green tests succeeds — objective checks override self-reports both ways, with mismatches downgraded to warnings. Closed-world: a verification step naming an unknown command FAILS the subtask instead of being skipped, or a typo becomes a false pass. And scope must coincide with verification: a subtask judged by tests it was forbidden to fix rewrote the one file it could touch **49 times**; the full suite now belongs only to the subtask that owns the final state — accepting, and recording as a cost, that intermediate errors then surface later.

### 🤝 Consent UX: humans in the loop without losing the cache

- **F14 — Consent must have memory, failure must be a dialogue, and pauses must not cost prefill.** *(implementation finding)* Per-call write approval produced real user revolt ("1000 approvals… like filing taxes"): one approval now grants a standing, revocable permission for that (action-family, file) pair, with `no` remembered exactly as long as `yes`. Budget exhaustion *asks* for an extension instead of killing the task, and failed tasks surface their reasons and offer a guided relaunch. And because on CPU every human pause once meant a cold restart of the work, the volatile context is saved at the block and resumed *in-place* with a warm KV cache — removing most of the avoidable prefill cost of having a human in the loop.

### 🧭 Planner rebuild (S/M/J): reference coherence is the control plane's job

- **F15 — The model creates the meaning; the control plane creates the identity.** *(implementation finding — the central lesson of the planner rebuild)* A 2B model calls the same thing by three names, orders dependent steps upside down, and imports modules that do not exist yet. Every time an *identity* decision was moved from the model into deterministic code — canonical obligation/test naming (`P1.S1.O1 → test_p1_s1.py::test_p1_s1_o1`), topological ordering of micro-phases, ownership dedup and auto-split, resolvable-import checks, contract prose confined to the micro's own file perimeter — the corresponding failure family went to **zero**, not merely down: invented file names 6/20 → 0 after existing-file grammar enums; planner↔test-author name mismatches 11/20 → 0 after canonical naming; oracle-fooling tests 5/20 → 0 the batch after the top-level-import rule. ~50 permanent deterministic rules were distilled this way from over 250 instrumented end-to-end runs.
- **F16 — A test's power to fail is checkable before trusting the test.** *(implementation finding)* Model-written tests cheated in every way a validator did not forbid: tautological asserts, `__dict__`/`__annotations__` introspection instead of behaviour, string-literal mentions of the target instead of calls, imports of the module under test wrapped in `try/except` so the file stays green while the module is missing. The oracle qualification gate now *executes* each test's claim to discriminate (red baseline on missing behaviour, green on existing) and AST checks reject the cheat patterns statically — so a weak oracle dies in the repair loop, where a patch costs hundreds of tokens, not at the end of the task, where it costs everything.
- **F17 — A fixed seed is not determinism on GPU; and determinism is a prompt property first.** *(stack-specific)* Runtime task artifacts (logs, plan documents with per-run ULID names) leaking into repo listings silently varied every prompt, making the fixed seed irrelevant — prompt-level determinism had to be engineered before seed-level determinism meant anything. After prompts were made bit-identical, CUDA continuous batching *still* produced divergent trajectories run-to-run. Consequence: GPU batches are used to classify failure families, never to compare fine success rates (2↔7 greens out of 20 on identical code is mostly noise). And the CPU profile is *quieter*, not silent: identical code re-measured across server sessions moved the baseline 6/13↔8/13 (llama.cpp evaluates a prompt differently cold vs from cache — upstream issue #2838), a ±2/13 band. Official verdicts are therefore drawn from **multiple averaged runs**, never a single one.
- **F18 — With references made coherent, the residual walls are capability walls — now visible, attributable, and split by role.** *(measured in the official A/B)* On the GPU iteration batches the dominant residual was the junior failing exact output formats even when shown the test source and the failing assertion diff. The official CPU A/B then exposed the upstream twin: the **planner under-scoping requests** (a plan covering one third of the ask, internally coherent, honestly "completed" — and externally wrong: the one completed≠verified gap in the 35 official A/B runs) and the mid-roles writing wrong characterizations that the oracle gate correctly kills at compile time. Every death now has a stage, a cause and a cost; the cheap next lever is explicit reasoning for the *deciding* roles (planner and phase compiler), which is exactly what the queued thinking-mode experiment measures — a stronger model dropped into the same scaffold inherits the entire discipline for free.

### 🧠 Thinking mode: measured, role by role

Gemma 4 E2B has a native reasoning channel (`<|channel>thought … <channel|>` — markers extracted from the chat template *embedded in the pinned GGUF*, since neither `/props` nor `/tokenize` exposes them on this build). Red Giant drives it with a **two-call protocol**: one ungrammared call opens the channel and captures the thought, then the usual grammar-constrained call runs with the thought in context — and the thought is **disposable by construction**: it never enters the ledger, later steps, or the stable KV prefixes (which matches the model's own embedded template, whose `strip_thinking` macro deletes past reasoning from history).

- **F19 — Let the model finish the thought: budgets are fuses, not targets.** *(measured)* Capped at 256 tokens, every single thought hit the cap mid-sentence — which read as "the model never closes the channel". Given room, it **closes the channel by itself, every time, at 322–543 tokens** (simple plan / wide plan / debugging). The thinking budget is now a circuit-breaker (1536, never trips in normal operation, caps the pathological case at ~43s on target hardware) and the answer's token budget is always reserved — a thought that starves its own answer would be the dumbest possible failure.
- **F20 — Where reasoning pays is a *placement* problem: the wall migrates to whoever is not thinking, and not all thinking is equal.** *(measured on a 7-arm × 20-run grid, GPU compliance profile — official CPU A/B in progress)*

| 20-run batch (same task, same code, same seed policy) | Verified | Giano's deaths | Avg green phases | Tokens/run | Wall/run |
|---|---|---|---|---|---|
| No thinking (reference) | 3/20 | 10/20 | 0.9 | 5.4K | 33s |
| Planning side thinks (Sirio + Mira→Altair) | 0→2/20¹ | 10–11/20 | 0.9–1.4 | 13–17K | 70–95s |
| **Executor thinks (Giano only)** | **4/20** | **5/20 (halved)** | 1.3 | **8.5K (1.6×)** | 50s |
| Everyone thinks | 1/20 | 7–8/20 | 1.1 | 16.9K | 88s |
| Sirio + Giano think | 2/20 | 9/20² | **1.9 (record)** | 14.1K | 87s |
| **Sirio + Mizar + Giano think** (verification sober) | **4/20** | 6/20² | **1.9 (record)** | 16.5K | 95s |
| Mizar + Giano think | 2/20 | 4/20 (14 die at compile) | 0.8 | 10.8K | 62s |

¹ Round 1 exposed a new thinking-induced failure family: Mizar, having *reasoned about the whole plan*, copied the wrong phase id into its output (5/20 runs) — fixed permanently by making phase identity control-plane-owned, one more F15 rule.
² Executor-death counts are not directly comparable across depths: in the Sirio arms far more runs *survive compilation and reach Giano* — deeper into later phases — so his exposure roughly doubles even as his per-attempt failure rate stays improved. The clean comparison is the executor-only row (same exposure as reference, deaths halved).

What the grid says, taxonomy-backed: (a) a thinking Giano **halves his own failure rate** against standard proofs — the single cheapest win (1.6× cost); (b) thinking on the *verification* side (Vega/Altair) designs **richer, more demanding proofs** (three obligations per micro instead of one) — honesty up, conversion down, and it poisons even the everyone-thinks arm; (c) with verification kept sober, a thinking **Sirio buys execution depth** — both Sirio-arms hit a record **1.9 average green phases**, double the reference — making Sirio+Mizar+Giano the depth champion at equal best conversion; (d) **no arm breaks the ~4/20 conversion ceiling**: the last mile is still the wall.

**The official CPU verdict (pre-registered decision rule, applied without mercy — and deliberately left open):** two batteries per arm on the reference profile — executor-thinking **1.5/13 mean vs control 1.5/13 mean**, Δverified = 0 (rule required ≥+2), at ~1.4× tokens and ~1.9× clean wall. Full-time thinking **stays off by default** — with an explicit caveat written into the plan: this was measured on *synthetic coding without routing*; reasoning may well pay on everyday, research or math workloads, and a mandatory retest with size-based routing active (post-F6/F7) plus public-benchmark runs at project end will reopen the question with data. One battery did produce a historic scalp — the reasoning-trap task that had never passed in the project's entire history (the model must flip "that library is off-limits, so the bug must be in the caller") fell to a thinking Giano — but it did not reproduce in the second battery: real, and inside the noise band. The identified next lever (unmeasured): *selective* thinking — only on retry, after a proof has already failed once, where the grid shows the benefit concentrates and the cost collapses. The general lesson — likely worth stealing for any multi-role agent system: **upgrading one role's intelligence moves the bottleneck, it does not dissolve it; placement beats quantity; measure every role upgrade on the whole chain, never on the role in isolation — and a scalp that doesn't reproduce is noise, however good it feels.**

Every countermeasure above ships as working code in this repository; the [codebase atlas §9](memory/codebase_reference.md) maps each of the 27 underlying observations to its exact file, signature and technical cause (the F15–F18 observations join the atlas at PS5 closure).

**Measured baselines** on the capped reference profile (2 workstation cores ≈ 4 target cores, [full report](bench/results/f0_baseline_severino-sim.md)):

| Metric | Value |
|---|---|
| Cold prefill @ 1K / 4K / 8K / 16K ctx | 6.8s / 30.7s / 69.6s / **173.6s** — why small contexts are a design constraint, not a preference |
| Generation | 35.8 tok/s (memory-bound: 24 threads only reach 42) |
| Prefix reuse (8K ctx) | append-only: **65** tokens reprocessed · one byte changed mid-prompt: **7,971** (~120× worse) |
| Grammar overhead | 0.4–9.8% on generation speed |

## 🌟 The cast

The plan-compiler roles have names (their technical ids in the DB, prompts and env vars stay stable — comparability is sacred):

| Name | Role | Technical id | Does |
|---|---|---|---|
| **Sirio** | Senior Planner (S) | `senior_planner` | writes the macro-plan once — criteria, phases, coverage — then exits |
| **Mira** | Phase Analyst (M1) | `phase_analyst` | analyzes one phase: involved files, decisions, risks |
| **Mizar** | Work Decomposer (M2) | `work_decomposer` | splits the phase into micro-tasks with exclusive file ownership |
| **Vega** | Verification Designer (M3) | `verification_designer` | designs the proof obligations for each micro-task |
| **Altair** | Test Author (M4) | `test_author` | writes the qualified tests, one file per call |
| **Giano** | Worker (J) | `worker` | the two-faced executor: thinks, acts, gets verified — never writes its own tests |

Sirio proposes meaning; the deterministic control plane owns every identity (names, order, existence); Giano executes inside a physical scope; external judges have the last word.

### 🏭 How the assembly line actually works

The single most important structural fact: **no agent ever talks to another agent.** Each one receives a *minimal context assembled by code*, produces *one typed artifact* (a small Pydantic schema, enforced by the decoding grammar), and that artifact is **validated, normalized and persisted** before the next agent sees any of it. Communication is always `agent → artifact → gate → cleaned artifact → next agent`. A broken artifact gets targeted patches (max 2, then one full regeneration citing the violated rules), then explicit failure — never silence.

1. **Sirio speaks exactly once.** Request + repo listing in; `MacroPlan` out — success criteria (C1…) and phases (P1…) declaring which criteria they cover and what they depend on. The gate rejects uncovered criteria, cyclic dependencies, and plans that ignore files named in the request. Then Sirio leaves the stage permanently: the plan is a document, not a process.
2. **Per phase, a deterministic compiler drives Mira → Mizar → Vega → Altair.** Mira analyzes under an anti-invention gate (she can only *copy* identifiers from the ledger projection, never coin them). Mizar decomposes into micro-tasks with **exclusive file ownership** — and the control plane then imposes the phase id, sorts micros topologically, splits oversized ones, dedups ownership. Vega designs proof obligations; the control plane assigns every test its **canonical name** (`P1.S1.O1 → test_p1_s1.py::test_p1_s1_o1`). Altair writes test files one per call, and his tests survive three layers of distrust: static AST checks (real asserts, real anchoring to the target, resolvable imports), then the **oracle qualification gate executes them** — a new-behaviour test must fail *now*, a characterization test must pass *now*; a test that cannot fail dies in the repair loop, not at the end of the task. Only qualified tests reach the disk — written by the control plane, never by an agent.
3. **Giano executes in a cage.** His work order carries the goal, the boundary, the importable modules, the **verbatim source of the tests that will judge him**, and the exact commands to run them. He works ReAct-style inside a **physical scope**: only his owned files are writable — the tests and everyone else's files are protected at the filesystem level, not by prompt-level pleading (he once overwrote the qualified tests; that day the scope became physical). On failure he retries with the failing test's output tail in front of him; failing twice *identically* is forbidden (photocopy gate) and dies explicitly.

Three separations hold the whole thing up:

- **Prosecution ≠ defendant**: who writes the tests (Altair) never writes the code (Giano), and the final judge — the task's external script — trusts neither.
- **Meaning ≠ identity** (the central rule, F15): *what to do* is proposed by models; *what things are called, in what order they run, what exists* is decided by deterministic code. Every identity moved from model to code sent a whole failure family to zero.
- **Nobody remembers anything**: between calls, agents have no memory. The only memory is the **task ledger**, rebuilt deterministically from the DB and the AST of the *real* code (never from model recollection) and projected per phase within a token budget — criteria and intent always, the rest as space allows, truncation declared.

The whole flow in one line:

```
Sirio → [gate] → per phase: Mira → [gate] → Mizar → [normalize+gate] → Vega → [canonical names+gate]
  → Altair → [static checks + oracle EXECUTES the tests] → per micro: Giano in scope → [proof gate]
  → phase synthesis → final coverage → external judge
```

Why this shape: 2B physics. Every station gets 4–8K tokens of *minimum sufficient* context, every output is small and constrained, every transition is verifiable — and when something dies, it dies **at a nameable station, for a nameable cause**, which is what made the whole measurement campaign above possible in the first place.

## 🔁 Pipeline at a glance

```mermaid
flowchart LR
    A[Request] --> B{Driver selection<br/><i>today: naive plan by default;<br/>plan compiler behind the config gate;<br/>size-based routing arrives in F6</i>}
    B -->|default| W[Giano<br/><i>single-step constrained ReAct,<br/>physical write scope,<br/>optional thinking channel</i>]
    B -->|gated| S1[Sirio<br/><i>macro-plan, once</i>]
    S1 --> M[Mira → Mizar → Vega → Altair<br/><i>per phase — deterministic<br/>compiler between every pair</i>]
    M --> OQ[Oracle qualification<br/><i>tests must prove<br/>they can fail</i>]
    OQ --> W
    W --> V[Proof gates<br/><i>deterministic, per micro</i>]
    V --> SY[Phase synthesis<br/>→ plan coverage]
    SY --> F[External judge<br/><i>trusts no one</i>]
```

*(The Debugger and Supervisor roles of the original design do not exist yet — they arrive in F4; the in-loop Planner and Phase Designer of F3 exist but are deprecated behind the D11 gate.)*

**Domains:** coding (verified by tests) · local research & web research (verified by mechanical citation checking and multi-source triangulation) · advice (explicit, logged choice between web-first and declared model-knowledge — the everyday path: one pass, cited sources, no hard gates). *Not a coding assistant* — the same pipeline serves all four.

## 🖥️ Target hardware ("Severino")

| | |
|---|---|
| **Machine** | BOSGAME E5 mini-PC home server |
| **CPU** | AMD Ryzen 3 5300U (Zen 2, 4C/8T, 15W) — **4 cores allocated** to Red Giant + llama-server |
| **GPU** | none usable (iGPU Vega: no ROCm, Vulkan marginal) → **CPU-only inference** |
| **RAM** | 32 GB dual-channel (at MVP time), ~10 GB budget |
| **Constraint** | the rest of a full homelab stack keeps running on the same box |

Development happens on a fast workstation, but **official numbers only come from CPU-capped profiles** (`severino-sim`: Docker, 2 workstation cores ≈ 4 target cores, 10 GB) and from the real box.

## 🗺️ Roadmap — and how it's actually going

This is the project's state of the union: for every phase, how it went, what
we learned, what's still owed. It is a *summary* — every phase, trap and test
mentioned here lives in full detail in its own document:

- 📐 [`plan_red_giant.md`](memory/plan_red_giant.md) — every phase with sub-phases, rationale, acceptance criteria and per-phase outcome blocks ("ESITO F*n*");
- 🗺️ [`codebase_reference.md`](memory/codebase_reference.md) — §9 lists **every trap** with its technical cause, §10 the open debt with its destination phase, §7 the test catalog;
- 📊 [`bench/results/`](bench/results/) — the committed measurement reports behind every number quoted below.

### ✅ F0 — Foundations (`v1.1.0`)

*Goal: pin the runtime, verify the model, measure the hardware — before writing any pipeline code.*

- **How it went:** everything shipped, but probing the model produced three surprises that shaped the whole project. In short: forcing the output format (the "grammar") guarantees *shape*, not *content* — the model must also *see* the schema, must have enough token budget, and must use its chat template, or it produces well-formed nonsense.
- **Key number:** on target-equivalent cores, reading a 16K-token context takes **3 minutes**. Small contexts are physics, not taste.
- **Owed:** KV slot persistence is broken on the pinned llama.cpp build — re-check in F5.

### ✅ F1 — Deterministic core + worker (`v2.0.0`)

*Goal: a walking skeleton that solves real (tiny) coding tasks, and becomes the control group every future "smart" role must beat.*

- **How it went:** 4 of 6 synthetic tasks solved and externally verified on the capped profile; zero false success claims.
- **What we learned** (the lesson that defines the project): in almost every failure the model had *reasoned correctly* — the environment was lying to it. Unified diffs punished correct fixes over a blank line; file reads showed line numbers the model then faithfully copied into its edits. **Adapt the environment, don't fight the model** — e.g. switching from diffs to exact-string replacement turned 20-call failures into 5-call successes.
- **Owed:** one task fails on pure reasoning (the model can't flip "that file is off-limits, so the bug must be in the caller") — it waits for the Supervisor (F4).

### ✅ F2 — Web GUI (`v2.1.0`)

*Goal: an interface comfortable enough that the user actually tests the system — before the pipeline gets complex.*

- **How it went:** the hardest shakedown so far. Three rounds of live user testing plus an automated battery found **15 defects**. The most instructive: a single unescaped quote inside a JSON string derails a small model into a 60-call chaos loop — fixed *structurally*, by making the incoherent output branch impossible to generate (discriminated unions).
- **What matured here:** the consent model. Approving a write grants that file for the whole task (revocable); running out of budget *asks you* instead of killing the task; approval requests show a readable diff of what would be written; after your approval the task resumes exactly where it stopped, with the cache still warm.
- **A principle worth stealing:** verification is symmetric — if the tests are green, the work is done even when the model *believes* it failed. Claims never beat oracles, in either direction.
- **Owed:** everything is proven on 2-4 file toy repos; several tolerances are calibrated on this exact model and build.

### ✅ F3 — Planning (`v3.0.0`) — shipped, measured, and demoted by its own A/B

*Goal: a Planner that maps the work into phases, expanded lazily, with replanning when reality disagrees.*

- **How it went:** everything was built and works mechanically — plan generation, deterministic logic validation with rule-citing corrective re-calls, lazy expansion, bounded replanning. Along the way: a planner that hasn't *seen* the tests invents function names the tests then reject (fixed with contract anchoring), and a subtask judged by tests it's forbidden to fix thrashes forever — 49 rewrites of one 5-line file (fixed with scoped verification). A first A/B run had to be invalidated: it ran from an uncommitted working tree where one deleted prompt sentence killed 6 tasks out of 10 — two permanent method rules came out of that (prompt and validator are one artifact; official runs only from committed code).
- **The honest verdict:** the official A/B was brutal — **2/10 verified vs the baseline's 9/10**, at higher token cost (815K vs 710K). On micro-tasks planning is not just overhead but a regression: redundant phases duplicated finished work, artificial "analysis" subtasks demanded artifacts nobody needed, and failed subtasks were retried verbatim. Per the project's own rule (every role earns its place or leaves), the planner is now **off by default behind a config gate** — tasks get the deterministic naive plan that won the A/B, at zero planning tokens.
- **What the failure taught:** the thrashing was the *gates'* fault, not the proposer's — nothing checked whether a phase was already satisfied, whether a retry differed from the failed attempt, whether a new plan differed from the failed one. That diagnosis reshaped the design.
- **Owed:** the planning system is being rebuilt as a standalone effort with its own plan — the planner as a plan-document *author* that writes once and exits, deterministic zero-token gates (phase-entry, retry-must-differ, replan-must-differ), a task ledger as external memory. *When* to plan stays F6's routing question; the final word belongs to the real codebase (F8).

### ✅ Interlude — the planner-system rebuild (`v3.1.0` → `v4.0.0`, closed)

*Goal: rebuild planning as a plan **compiler** behind deterministic gates, and let an official A/B decide its fate.*

- **How it went:** PS0–PS7 all shipped in one campaign — typed artifacts, task ledger, the full cast (Sirio → Mira/Mizar/Vega/Altair → Giano), oracle qualification, physical scopes, GUI integration. ~50 permanent deterministic rules distilled from the instrumented runs; whole failure families (invented files, name mismatches, cheating tests, ordering bugs) went to zero, not down.
- **The honest verdict (D11 confirmed):** 2/13 vs the baseline's 6–8/13 on micro-tasks, 0/3 both arms on wide tasks → **integrated but gated off**. What it bought, measured: failures at −44% tokens, useful-token share +9pt, one honesty gap in 35 official runs (found, diagnosed, closed), and ablations proving every gate pays for itself (+50–76% failure cost without).
- **Method discoveries that outlive the verdict:** GPU batches classify failure *families*, never fine rates; even the CPU profile has a ±2/13 noise band (cache-state numerics — verdicts now come from multiple averaged runs); and the baseline itself moved 9/10→6–8/13 across commits, a humbling lesson in diagnosis confidence.

### 🧠 Thinking campaign (current, `v4.1.x` — [`plan_thinking_ab.md`](memory/plan_thinking_ab.md))

- **TH0 done:** two-call protocol, markers extracted from the GGUF itself, budgets-as-fuses, disposable thoughts (the model's own template agrees).
- **TH1 done:** the 7-arm × 20-run grid of F20 — executor-thinking halves executor deaths; Sirio-thinking buys record depth; verification-thinking raises the bar; ~4/20 conversion ceiling.
- **TH2 done:** official CPU A/B, two batteries per arm — executor-thinking 1.5/13 mean vs control 1.5/13 mean, Δ=0 at 1.4× tokens.
- **TH3 verdict (left open by design):** full-time thinking **stays off by default** (pre-registered rule, no mercy) — but the verdict covers only synthetic coding without routing. Mandatory retests are written into the plan: with the router active on everyday/math domains (post-F6/F7), plus the identified *selective*-thinking follow-up (only on retry, TH-bis), plus public benchmarks at project end. The mechanics stay production-ready behind the config lever — the everyday chat worker of F7 can turn them on with streaming.

### ✅ F3-bis — Multi-domain micro-slice (`v4.3.0`)

*Goal: prove the engine on everyday non-coding work before designing the Supervisor — so F4 knows non-coding failure modes too.*

- **How it went: 3/3 verified on the first official run** (severino-sim, external judges): local document analysis with deliberate noise (68s), a **live whitelisted API call** through the new `http_get` tool — empty-by-default domain whitelist, redirect guard, per-task cache so verification re-reads *the copy the model saw* (45s) — and an exact document-to-CSV transform (279s, 1 retry: exact formats remain the 2B's hardest job, consistent with F18). Zero honesty gaps, 100% useful tokens on all three.
- **Method note:** every fixture calibration is *automated in the test suite* — judge satisfiability with reference artifacts, the local service probed live, harness parsing asserted. Calibration by hand is banned.
- **What it means:** the everyday regime (narrow tasks, short chains, cheap mechanical oracles) is exactly where both this project's data and the literature place small-model value — and the engine just delivered its first numbers there.

### ⏭️ Next

- **F4 — Continuous verification**: debugger, supervisor, anti-loop, git checkpoints. Two customers already waiting: the reasoning-trap task and a human protocol that evolves from answering machine to dialogue.
- **F5 — Context & KV-cache engineering**: the cache already proved itself (88 calls cost only 82s of prefill on CPU); F5 makes it measured and engineered, and re-checks slot persistence.
- **F6 — Adaptive routing**: small tasks go straight to the worker, big ones through the planner — where the "when is planning worth it" question gets its answer, and model-specific tolerances get A/B-ed as a system.
- **F7 — Non-coding domains in full**: web search, verified citations, multi-source triangulation, advice with declared provenance.
- **F8 — The real exam**: a Laravel 13 chatbot codebase on the target box — final numbers for the planner, the tolerances, and the whole thesis.

## 📚 Repository map

| Document | Purpose |
|---|---|
| [`memory/small-model-powerhouse-specsheet.md`](memory/small-model-powerhouse-specsheet.md) | Vision & requirements (the operating spec) |
| [`memory/plan_red_giant.md`](memory/plan_red_giant.md) | The implementation **contract**: 21 binding decisions, full architecture (DB DDL, config, tool catalog, prompt layout), 9 phases with real signatures, per-subphase rationale and acceptance criteria. Self-sufficient by design |
| [`memory/plan_planner_system.md`](memory/plan_planner_system.md) | The plan-compiler interlude, closed: PS-D1–D11 decisions, the cast's contracts, every in-course revision with its motivating failure, the D11 verdict |
| [`memory/plan_thinking_ab.md`](memory/plan_thinking_ab.md) | The thinking campaign (current): two-call protocol, TH-D1/TH-D2, the 7-arm grid, pre-registered decision rule |
| [`memory/codebase_reference.md`](memory/codebase_reference.md) | The codebase atlas — every real class/signature/table/endpoint, mechanically verified against the code by `scripts/check_reference.py` (build-blocking) |
| [`bench/results/`](bench/results/) | Committed measurement reports (constrained-decoding probe, CPU baselines) |

## 🚀 Getting started (development, Windows)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

scripts\download-llama.ps1     # pinned llama.cpp binaries (CUDA + CPU)
scripts\download-model.ps1     # Gemma 4 E2B QAT Q4 GGUF, SHA256-verified
scripts\start-llama.ps1 -Profile dev-fast                 # CPU-bound dev server (24 threads
                                                          # — the GPU is deliberately unused)
docker compose -f docker\severino-sim\compose.yml up -d   # the honest 2-core profile

python bench\schemas_probe.py --url http://127.0.0.1:8080   # constrained-decoding probe
python bench\run_bench.py --profile severino-sim            # CPU baseline
python scripts\check_reference.py                           # atlas ↔ code verification
```

---

<div align="center">
<sub>

Licensed under the [MIT License](LICENSE) — free to use, modify and redistribute, **provided the Red Giant attribution notice is preserved**.

**Topics:** small language models · SLM agents · local LLM · Gemma 4 E2B · llama.cpp · GGUF · grammar-constrained decoding · JSON Schema · GBNF · KV cache reuse · prefill optimization · CPU-only inference · agentic pipeline · deterministic orchestration · verification-first · home server · self-hosted AI

</sub>
</div>

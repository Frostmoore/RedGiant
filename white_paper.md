# Raising the Reliability Floor of a 2-Billion-Parameter Language Model on Consumer CPU Hardware

### A verification-first agentic architecture, and the measurements that judge it

**Red Giant Project** · Working paper, revision of 2026-08-03
Model under test: Gemma 4 E2B (≈2B effective parameters), Q4 QAT GGUF, CPU-only inference
Reference hardware: 4 CPU cores, 15 W, no usable GPU

---

## Abstract

Contemporary agentic systems are implicitly designed for models capable of recovering from
their own mistakes. When such systems are pointed at a ~2B-parameter model running on
consumer CPU hardware, the mechanisms they rely on — long contexts, verbose retry loops,
self-critique — are precisely the ones the regime cannot afford. This paper reports the
design and, more importantly, the *measurement* of an alternative: a deterministic,
verification-first orchestration layer built on the assumption that the model is an
unreliable proposer and never an authority.

We report results from **over 600 instrumented end-to-end runs** across seven measurement
campaigns. Our central methodological contribution is a **four-block measurement matrix**
(naked model / full workflow, each with and without explicit reasoning, with mandatory
component ablations in both workflow blocks) applied to a **difficulty ladder** — a
deterministically generated task family that scales breadth while holding per-step cognition
constant. This design makes the customary claim "our framework improves results" decomposable
into attributable components.

The findings are mixed, and we report them as such. At the **step level** the scaffolding
demonstrably converts an unusable model into a reliable executor: semantically usable
structured output rises from 0/60 to 60/60; a mis-specified edit interface costing 20+ failed
calls per fix drops to 5–6 clean ones; whole classes of reference incoherence go to zero, not
merely down. At the **task level** the results split sharply by task class. On tasks the naked
model can already solve, the workflow adds autonomy, safety and honesty — but no capability,
at ~100× the token cost. On tasks beyond the naked model's ceiling (measured at ≈5.8K tokens
of material and 5 facts, without aggregation), the workflow converts, and ablations attribute
the conversion to **selective retrieval** specifically. On genuinely multi-session software
engineering tasks, neither our plan compiler nor explicit reasoning produced any conversion at
all, and both were rejected by their own pre-registered decision rules.

We also isolate a component whose value is not throughput but *epistemic*: removing
deterministic verification does not merely reduce success — it makes the system **lie**, at a
rate of 8 false completion claims in 5 runs, against 1 in more than 550 runs with verification
active.

---

## 1. Introduction

### 1.1 Problem statement

Small language models do not fail primarily from lack of intelligence at a single step. They
fail from **breadth**: tasks too wide for one context, instructions with unstated halves,
claims of success nobody checked, and errors that compound across steps. The engineering
question this project addresses is therefore not *how do we make a small model smarter*, but:

> Given a fixed, small, quantized model on fixed, weak hardware, how much of the gap to
> "reliably useful" can be closed by the **system around the model**, and which parts of that
> system actually pay for themselves?

The second clause matters as much as the first. The literature on agent scaffolding is rich in
claims of the form *"system X improves results by N points"*, where X is an undifferentiated
bundle of a dozen mechanisms. Such claims are not actionable: they say a set of things does
something, without saying which thing does what.

### 1.2 Constraints as method

The project fixes the model deliberately at the smallest usable size and the hardware at a
15 W four-core mini-PC with no usable GPU. This is not asceticism; it is experimental hygiene.
Any improvement measured under these constraints is attributable to the architecture, because
model scale is held constant and cannot silently absorb design errors. Concretely:

- **No external LLM APIs, ever.** A system that escapes to a larger model under pressure
  proves nothing about the smaller one. Explicit failure is a valid result.
- **Official metrics on CPU-capped profiles only.** A development GPU hides every
  token-economy problem the target hardware will impose.
- **Every cognitive role must earn its place** through an A/B against a simpler alternative,
  or it is removed. Two roles have already been removed under this rule (§5.3, §5.5).

### 1.3 Contributions

1. **A measurement matrix** that decomposes agentic performance into model capability,
   scaffolding contribution, reasoning contribution, and per-component attribution (§4.2).
2. **A difficulty ladder**: a deterministic task generator that isolates *breadth* from
   cognition, allowing the naked model's ceiling to be located precisely, and the scaffolding
   to be evaluated only where that ceiling has been exceeded (§4.4).
3. **Twenty engineering findings** with their measurements, including four negative results
   reported at full strength (§6).
4. **An empirical demonstration that deterministic verification purchases honesty**, separable
   from and independent of throughput (§5.7).

---

## 2. Background and positioning

### 2.1 What the literature supports

Recent work converges on the recipe *small model + strict specification + external
validators*, and increasingly quantifies it. Grammar-constrained decoding helps the smallest
models disproportionately: NVIDIA report a 0.6B model rising from 16.7% to 59.2% on Bash
generation, while 3–4B models gain single digits [1]. Tool-based external verification allows
a 1B model under test-time scaling to outperform an 8B baseline on MATH [2]. A substantial
share of what is perceived as small-model unreliability is *interface* failure rather than
reasoning failure, and is mechanically fixable [3]. Critically for our design, small models'
**self**-critique degrades performance while external grounding improves it [4] — which is why
in our architecture no model ever judges its own output. Harness quality alone moves agent
benchmarks by 20–40 points at fixed model size [5], and a ~1B model inside a strict
schema-validated harness beats GPT-3.5-Turbo at function calling [6].

### 2.2 What the literature also says, and we confirm

The same body of work draws a boundary we independently rediscovered. Per-step reliability
compounds multiplicatively over dependent chains (p^H); even frontier models degrade from near
100% on sub-4-minute tasks to under 10% on multi-hour tasks [7]. Reasoning capability that is
absent cannot be prompted into existence in a 2B model [8]. Four-bit quantization taxes small
models disproportionately, unlike 70B-class models [9] — which is why this project uses
quantization-aware training weights.

The honest summary of the field, which our own results reproduce: **the floor rises
substantially; the ceiling does not move.**

### 2.3 Where this work differs

The cited work is largely papers and benchmarks. Complete, engineered systems targeting
genuinely constrained hardware are rare, and rarer still are systems that publish their own
negative A/B results. This project is an existence proof with the receipts attached: every
design decision carries the measurement that justifies it, and every mechanism that failed to
justify itself is documented as such, with the numbers that condemned it.

---

## 3. System design

### 3.1 Architectural principle

> **The model proposes; deterministic code decides.**

Concretely: every state mutation is typed, attributed and persisted; no subtask is complete
without recorded evidence; and every model-driven loop has an exit the model cannot veto.
Each of the caps in the system (design rounds, replans, per-error counts, step budgets) exists
because its absence produced a *measured* infinite loop — a designer redesigning the same phase
forever, 49 rewrites of one five-line file, 15 identical no-op edits accepted as successes.

### 3.2 The execution paths

Two paths coexist behind a configuration gate:

**Direct path (default).** A deterministic single-subtask plan hands the task to the executor,
which operates as a single-step constrained ReAct loop: one action per call, append-only
context, physically scoped writes, deterministic verification at the end.

**Plan-compiler path (gated off by A/B verdict, §5.5).** Six specialized roles, each producing
exactly one typed artifact, with deterministic validation between every pair:

| Role | Produces | Key constraint |
|---|---|---|
| Senior Planner | macro-plan (criteria + phases) | speaks once, then exits; the plan is a document, not a process |
| Phase Analyst | phase analysis | may only *copy* identifiers from the ledger projection, never coin them |
| Work Decomposer | micro-tasks | **exclusive file ownership**; one new file per micro-task |
| Verification Designer | proof obligations | test names are assigned canonically by the control plane, not by the model |
| Test Author | qualified tests | written per-file; must survive three layers of distrust (§3.4) |
| Worker (executor) | code | physically scoped; never writes its own tests |

**No role ever communicates with another role.** Communication is always
`role → typed artifact → deterministic gate → normalized artifact → next role`. A malformed
artifact receives at most two targeted patches, then one full regeneration citing the violated
rules, then explicit failure — never silence.

### 3.3 Meaning versus identity

The single most productive design rule to emerge from this project:

> **The model creates the meaning; the control plane creates the identity.**

*What to do* is proposed by models. *What things are called, in what order they run, and what
exists* is decided by deterministic code. Each time an identity decision was moved from model
to code, the corresponding failure family went to **zero**, not merely down (§5.4). Identity
decisions now owned by code include: canonical test naming, topological ordering of dependent
sub-tasks, ownership deduplication, phase identifiers, and the set of importable modules at
any point in time.

### 3.4 Three-layer distrust of model-written tests

Where the system must generate its own oracles, those oracles are themselves suspect. Tests
authored by the model pass through: (i) static AST checks rejecting tautological assertions,
introspection-based checks, and string-literal mentions of the target instead of calls;
(ii) resolvable-import checks; and (iii) an **oracle qualification gate that executes each
test's claim** — a test for new behaviour must *fail now*, a characterization test must *pass
now*. A test that cannot fail is discarded in the repair loop, where a patch costs hundreds of
tokens, rather than at the end of the task, where it costs everything.

### 3.5 Physical, not rhetorical, boundaries

Scope is enforced at the filesystem layer, not by prompt-level instruction. The executor
receives a scope whose writable set is exactly its owned files; the qualified tests are
unwritable by construction. This design was adopted after the executor was observed
overwriting the very tests that were about to judge it — an event that no amount of prompt
wording had prevented.

---

## 4. Experimental methodology

### 4.1 Profiles, judges, and what counts

| Profile | Configuration | Role |
|---|---|---|
| `severino-sim` | Docker, 2 workstation cores ≈ 4 target cores, 10 GB, CPU-only | **the only official profile**; all verdicts derive from it |
| `dev-fast` | CUDA server on a workstation GPU | iteration only: classifies *failure families*, never success rates |

`verified` means an **independent judge script** — not writable by the system under test —
returned exit 0. `completed` means the system claimed to be finished. The gap
`completed ≠ verified`, which we call the **honesty gap**, is the anti-deception metric and
must be zero.

### 4.2 The measurement matrix

Every battery is measured on four blocks, with ablations mandatory in both workflow blocks:

| | without reasoning | with reasoning |
|---|---|---|
| **Naked** (materials inline, one completion, no tools/loop/retry) | **B1** | **B3** |
| **Workflow** (agent loop, tools, verification) | **B2** + ablations | **B4** + the *same* ablations |

The derived quantities are: **B2 − B1** (value of scaffolding), **B3 − B1** (value of reasoning
with no scaffolding), **(B4 − B2) vs (B3 − B1)** (whether reasoning pays more inside or outside
the workflow), and **full − ablated** (price of each individual component).

The symmetry requirement in B4 is not decorative: it is the only configuration that can answer
*does reasoning substitute for a missing component?* — for instance, whether a reasoning
executor compensates for the absence of verification.

**Corollary of design.** If B1 passes, the task measures nothing about the system and must be
widened until the naked model fails. This corollary invalidated our first non-coding battery
(§5.6) and motivated the ladder.

### 4.3 Noise bands, and why single runs are inadmissible

| Environment | Observed band at identical code | Mechanism |
|---|---|---|
| GPU | up to 2↔7 successes out of 20 | non-deterministic CUDA batching [10] |
| CPU | ±2 out of 13 | server cache state alters prompt evaluation [11] |

Consequently, verdicts are drawn from **multiple averaged runs**. This rule was adopted after
a baseline arm moved from 6/13 to 8/13 on *identical code*, and after an earlier diagnosis had
confidently attributed a similar movement to a code change.

Two further method rules were adopted after being violated at cost: **official runs execute
only from committed code** (an early A/B was invalidated by an uncommitted working tree in
which one deleted prompt sentence killed 6 of 10 tasks), and **the prompt and the validator are
a single artifact** — every validator rule requires its corresponding sentence in the prompt,
because the model cannot infer the missing half of a contract.

### 4.4 The difficulty ladder

To locate the naked model's ceiling and evaluate the system only beyond it, we generate a
family of tasks along a single axis — **breadth** — holding per-fact cognition constant. Every
rung asks the same trivial question ("service X's `listen_port` is N"); only the haystack
grows, with distractors of identical surface form.

| Rung | Documents | Material | Facts | Additional demand |
|---|---|---|---|---|
| L1–L4 | 5 → 90 | 0.3K → 5.8K tokens | 2 → 5 | — |
| L5 | 90 (= L4) | 5.7K tokens | 5 | **aggregation** (a sum) |
| L6 | 200 | 12.7K tokens | 6 | — |
| L7 | 400 | 25.3K tokens | 8 | aggregation |

The corpus is generated from a fixed seed and is byte-reproducible. In the naked arm,
materials exceeding the context window are truncated and the truncation is declared: this is
the physical limit of a one-shot system, not an imposed handicap.

**A methodological failure worth reporting.** The first ladder generation marked target facts
with markdown emphasis (`Service **mensa**:`) while distractors were plain. This produced an
artifact that penalized *only* the workflow arm — a natural search for `Service mensa` failed
on the target because of the intervening characters, while the naked arm, reading everything
inline, was unaffected. The corpus was regenerated with uniform formatting and a permanent
test now asserts the absence of such markers. We report this because a benchmark that
disadvantages the treatment arm through a typographic accident is a failure mode likely to
recur elsewhere in the field.

---

## 5. Results

### 5.1 Hardware and runtime baselines

| Measurement | Value |
|---|---|
| Cold prefill @ 1K / 4K / 8K / 16K context | 6.8 s / 30.7 s / 69.6 s / **173.6 s** |
| Generation throughput | 35.8 tok/s (memory-bound; 24 threads reach only 42) |
| Prefix reuse, append-only, 8K context | **65** tokens reprocessed |
| Prefix reuse, one byte changed mid-prompt | **7,971** tokens (~120×) |
| Grammar-constrained decoding overhead | 0.4–9.8% |

The last two rows establish that prompt layout is a runtime-architecture concern rather than a
matter of style: an 88-call append-only session incurred only ~82 s of total prefill, whereas
a single mid-prefix byte change costs two orders of magnitude more reprocessing.

### 5.2 Step-level reliability: where the floor demonstrably rises

| Intervention | Without | With |
|---|---|---|
| Schema shown in prompt (grammar active in both) | **0/60** semantically usable | **60/60** |
| Edit interface adapted to the model | 20+ failed calls per fix | **5–6 clean calls** |
| Incoherent output made unrepresentable (discriminated unions) | 60-call derailment loop | **8/8 probes recovered** |
| Identity decisions moved to control plane | invented files 6/20 · name mismatches 11/20 · oracle-fooling tests 5/20 | **0 · 0 · 0** |

The first row deserves emphasis: constrained decoding guarantees *shape*, not *content*. With
guided decoding fully active but the schema absent from the prompt, the model emitted
structurally perfect JSON populated entirely with literal placeholders.

### 5.3 Planning, first attempt: rejected

An in-loop planner with lazy phase expansion and bounded replanning was built, validated, and
subjected to an official A/B.

| Arm | Verified | Tokens |
|---|---|---|
| Deterministic baseline plan | **9/10** | 710K |
| In-loop planner | 2/10 | 815K (≈10× LLM calls) |

Post-mortem attributed the loss not to the proposer but to **absent gates**: nothing checked
whether a phase was already satisfied, whether a retry differed from the failed attempt, or
whether a new plan differed from the failed one. The planner was gated off by default.

### 5.4 Planning, second attempt: the plan compiler

The redesign (§3.2) was developed across eight instrumented 20-run batches, from which ~50
permanent deterministic rules were distilled. Entire failure families were eliminated rather
than reduced: invented file names 6/20 → 0 after grammar enums restricted to existing files;
planner↔test-author name mismatches 11/20 → 0 after canonical naming; oracle-fooling tests
5/20 → 0 after a top-level-import requirement.

### 5.5 The plan compiler's official A/B: rejected, with a caveat

| Arm (13 tasks) | Verified | Tokens | Useful tokens | Wall |
|---|---|---|---|---|
| Baseline | **6/13** (8/13 on re-measure) | 1,143K | 20.8% | 2,610 s |
| Plan compiler | 2/13 | **636K (−44%)** | **30.2%** | 2,632 s |
| Both arms, 3 multi-session tasks | **0/3 vs 0/3** | — | — | — |

Component ablations on the three wide tasks (all arms 0/3, so the comparison is the *cost of
failing*): removing oracle qualification **+51%** tokens, removing the task ledger **+76%**,
removing the phase entry gate **+50%**.

**Verdict: gated off.** What the system demonstrably buys is not conversion but *containment*:
failures cost 44% less, useful-token share rises 9 points, and every gate pays for itself in
the cost of failing. Three of the wide-task failures traced to control-plane defects that were
subsequently fixed; the verdict is recorded as **open pending re-measurement** with adaptive
routing active.

### 5.6 Non-coding domains, and the control arm that invalidated them

A three-task multi-domain battery (local document analysis, whitelisted API call, exact
document-to-CSV transform) passed **3/3 verified on the first official run**, with zero honesty
gaps.

The naked control arm then passed **9/9**.

The correct interpretation is therefore: on these tasks the **cognition is entirely the
model's**; the workflow contributes end-to-end autonomy, honesty and safety, but **no
capability**, at a heavy packaging cost (140K tokens in the agent loop versus under 1K naked).
This result motivated the ladder and the corollary of §4.2.

### 5.7 Explicit reasoning: measured role by role, then rejected

The model's native reasoning channel was driven by a two-call protocol: an ungrammared call
opens the channel and captures the thought; the usual grammar-constrained call then runs with
the thought in context. The thought is **disposable by construction** — it never enters the
ledger, later steps, or the stable KV prefixes, matching the model's own embedded chat
template, which strips prior reasoning from history.

**Budgets are fuses, not targets.** Capped at 256 tokens, every thought hit the cap mid-
sentence, suggesting the model never closes the channel. Given room, it closes the channel
unprompted **every time**, at 322–543 tokens.

A seven-arm × 20-run grid produced the campaign's most generalizable finding:

| Arm (who reasons) | Verified | Executor failures | Mean depth | Tokens/run |
|---|---|---|---|---|
| nobody (reference) | 3/20 | 10/20 | 0.9 | 5.4K |
| planning side | 0–2/20 | 10–11/20 | 0.9–1.4 | 13–17K |
| **executor only** | **4/20** | **5/20 (halved)** | 1.3 | **8.5K** |
| everybody | 1/20 | 7–8/20 | 1.1 | 16.9K |
| planner + decomposer + executor | **4/20** | 6/20 | **1.9 (record)** | 16.5K |

> **The wall migrates to whoever is not reasoning.** A reasoning executor halves its own
> failure rate. Reasoning on the *verification* side designs richer, more demanding proofs —
> honesty up, conversion down — and poisons even the everybody-reasons arm. With verification
> held sober, a reasoning planner buys record execution depth. No arm broke the ~4/20
> conversion ceiling.

The official CPU A/B (two batteries per arm) yielded **Δverified = 0** at 1.4× tokens against a
pre-registered rule requiring ≥ +2. Full-time reasoning does not ship. One battery did resolve
a reasoning-trap task that had never passed in the project's history; it **did not reproduce**
in the second battery. We record it as noise, and as a reminder that a result which does not
reproduce is not a result.

### 5.8 The ladder: locating the ceiling, then attributing the conversion

**Naked ceiling.** With and without reasoning, across three configurations including one
controlled for context consumption, the naked model succeeds 3/3 on rungs up to ≈5.8K tokens
of material with 5 facts, and **0/3 on every rung above it** — whether the additional demand is
aggregation (L5) or volume (L6, L7).

**Failure diagnosis at the artifact level.** Rather than record "the model failed", we examined
what it produced. On L5 the model retrieved **5 of 5 facts correctly** and then mis-summed
them, producing 1892 against a true 1792 — and characteristically: units and tens always
correct, hundreds wrong, consistent with **dropped carry propagation** (one output, 1592, is
exactly the sum with the carry omitted). On L7 the majority of runs never wrote an answer file
at all.

**Attribution by ablation** (GPU, 5 runs per arm; treated as family classification, not as
rates):

| Arm | L5 (aggregation) | L6 (200 docs) | L7 (400 docs) | Honesty gap |
|---|---|---|---|---|
| full | 2/5 | **5/5** | 1/5 | 0 |
| − calculator | 1/5 | **5/5** | 0/5 | 0 |
| − search | **0/5** | **0/5** | **0/5** | 0 |
| − verification | 0/5 | 4/5 | 0/5 | **8** |

Three conclusions, of differing strength:

1. **Selective retrieval is load-bearing, and this replicated across two corpus versions.**
   Removing search takes every rung to zero while *increasing* token cost by 35% — the system
   reads blindly and arrives nowhere. This is the clearest attribution in the campaign.
2. **Verification purchases honesty, not throughput.** The ablated arm produced **8 false
   completion claims in 5 runs**. With verification active, the honesty gap has been non-zero
   exactly once in more than 550 instrumented runs, and that once was diagnosed and closed the
   same day.
3. **The calculator's attribution is currently weak** (2/5 vs 1/5, within the noise band) — and
   the artifact-level diagnosis explains why: across 43 analysed runs, **only 7 invoked the
   calculator at all**. Ablating a tool the model does not call cannot change outcomes. The
   same analysis found 13 of 43 runs squandering half their step budget calling non-existent
   tools with placeholder names. Both defects are of the workflow, not the model: the tool was
   available but its use was not mandated, and the unknown-tool error was not actionable. Both
   have been corrected and are under re-measurement at the time of writing.

---

## 6. Discussion

### 6.1 Two kinds of contribution, and why conflating them is the field's error

Our results separate cleanly into two categories that are routinely reported as one.

**Capability contributions** change what the system can do at all: selective retrieval on
corpora exceeding the context window is the clean example (0/3 naked → 5/5 with search → 0/5
without it). **Epistemic contributions** change what the system's outputs *mean*: verification
does not make the system succeed more often, it makes its claims true. A framework reporting
only aggregate success rate cannot distinguish these, and will attribute to capability what is
actually honesty — or, worse, will ship a system that succeeds slightly more often while
lying at an unmeasured rate.

### 6.2 Placement beats quantity

The reasoning grid (§5.7) suggests a general principle for multi-role agent systems:
**upgrading one role's intelligence moves the bottleneck rather than dissolving it.** Improving
the verification-designing roles produced more demanding proofs that the unchanged executor
then failed — honesty improved, conversion declined. Improving all roles simultaneously
re-raised the bar and re-failed it, at three times the cost. Any evaluation of a per-role
upgrade must therefore be conducted on the whole chain; measurement on the upgraded role in
isolation is systematically misleading.

### 6.3 Adapt the environment, do not fight the model

The highest-yield interventions in this project were not prompt refinements but *interface*
changes. Unified diffs rejected logically correct fixes over blank-line mismatches; the model
had reasoned correctly and the environment had lied to it. Line-number prefixes shown in file
reads were faithfully copied into edit payloads. Search was case-sensitive, so a natural query
returned nothing, and — lacking any actionable failure message — the model repeated the
identical failed query five times.

Each of these was fixed at the tool layer, not the prompt layer. The generalization:
**a tool failure must be state-aware and actionable**, or the model will loop on it. This is
ordinary software engineering, and it dominates prompt engineering in effect size.

### 6.4 What the model cannot be argued into

Three configurations of explicit reasoning — including one controlled to see the same material
as the non-reasoning arm — failed to make the model add five numbers correctly. A 40-line
AST-restricted calculator did. Where a deterministic mechanism exists, offloading beats
reasoning in this regime; this is consistent with the tool-verification literature [2] and with
the finding that small models' self-directed reasoning does not reliably improve their own
correctness [4].

### 6.5 On negative results

This project has now rejected two planning architectures and one reasoning configuration by
its own pre-registered rules. We consider these the most valuable outputs to date, for two
reasons. First, they are the rarest artifact in the field: published, quantified,
architecture-level negative results on small-model agents. Second, they redirected effort
precisely — the failure of in-loop planning identified missing gates rather than a weak
proposer, and the failure of reasoning identified placement rather than quantity as the
governing variable.

---

## 7. Threats to validity

**Single model, single runtime.** All results are obtained with one quantized model on one
pinned inference build. Several calibrated tolerances (retry thresholds, step budgets, string
formatting heuristics) are plausibly overfitted to this configuration and require re-validation
on any change of model or runtime.

**Non-determinism.** Neither environment is fully reproducible (§4.3). Verdicts drawn from
small numbers of runs are stated with their bands; several ladder attributions currently rest
on 5 runs per arm and are explicitly labelled as family classification rather than rates.

**Synthetic tasks.** All batteries to date are synthetic and small — 2 to 15 file repositories
and generated document corpora. The behaviour of the system on a real codebase with genuine
history, ambiguity and scale is untested and is the project's designated final examination.

**Judge design.** Judges are independent scripts, but they were written by the same author as
the tasks. A judge that is too lenient inflates results; a judge that is unsatisfiable
invalidates them. We mitigate by asserting judge satisfiability against reference
implementations in the automated test suite, but the risk of subtly mis-specified tasks
remains.

**Benchmark artifacts.** The ladder's first generation contained a formatting artifact that
selectively disadvantaged the treatment arm (§4.4). It was detected only through
artifact-level failure analysis. We assume, on the base rate demonstrated by this single
discovery, that further such artifacts may exist.

**Absence of public benchmarks.** All numbers here are internally comparable but externally
unanchored. Public benchmark runs are planned specifically to place the system on scales
others can read.

---

## 8. Limitations and future work

The system does not yet convert multi-session software-engineering tasks: both arms score 0/3
on the three tasks designed to exceed a single executor session, with or without the plan
compiler, with or without reasoning. This is the project's principal open failure.

Planned work, in order: (i) adaptive routing by task size, using the measured fact that
micro-tasks must **not** be planned; (ii) re-measurement of both rejected verdicts with routing
active and on non-coding domains, since both were measured on synthetic coding only;
(iii) selective reasoning, invoked only after a proof has already failed, where the grid
indicates the benefit concentrates and the cost collapses; (iv) public benchmark runs; and
(v) the real-codebase examination.

---

## 9. Conclusions

Within the tested regime, the answer to the question posed in §1.1 is neither the optimistic
nor the dismissive one.

**At the step level, the scaffolding works, decisively.** Structured output goes from
unusable to universally usable; interface adaptations convert 20-call failures into 5-call
successes; whole families of reference incoherence are eliminated by moving identity decisions
into deterministic code.

**At the task level, the contribution is conditional and must be attributed.** Where the naked
model already suffices, the system adds autonomy, safety and honesty at substantial token
cost, and no capability. Where the naked model fails for reasons of breadth, selective
retrieval converts — and the ablation isolates it as the responsible component. Where the task
requires genuine multi-session decomposition, nothing we have built converts, yet.

**And one contribution is categorically different from the others.** Deterministic
verification does not raise the success rate; it makes the system's statements about itself
true. Measured: 8 false claims in 5 unverified runs, against 1 in over 550 verified ones.
For a system intended to work unattended on hardware its owner already possesses, that is
plausibly the property that matters most — and it is the one an aggregate success metric is
structurally incapable of seeing.

---

## References

[1] NVIDIA, *Improving Bash Generation in Small Language Models with Grammar-Constrained
Decoding*. developer.nvidia.com
[2] *Tool-integrated self-verification for test-time scaling in small language models*,
arXiv:2504.04718
[3] *Structured output reliability in small language models*, arXiv:2605.02363
[4] *When Small Models Are Right for Wrong Reasons*, arXiv:2601.00513
[5] *Agent scaffolding and benchmark variance at fixed model size*, arXiv:2606.08529
[6] Salesforce AI Research, *xLAM: Large Action Models*, arXiv:2409.03215
[7] METR, *Measuring AI Ability to Complete Long Tasks*. metr.org/time-horizons
[8] *Self-AMPLIFY: rationale enhancement limits in small models*, arXiv:2402.12038
[9] *SLMQuant: quantization sensitivity of small language models*, arXiv:2511.13023
[10] llama.cpp issue #7052, non-deterministic output with multiple slots; and Thinking
Machines Lab, *Defeating Nondeterminism in LLM Inference* (batch-invariance)
[11] llama.cpp issue #2838, cold versus cached prompt evaluation
[12] NVIDIA, *Small Language Models are the Future of Agentic AI*, arXiv:2506.02153
(position paper)

---

## Appendix A — Reproducibility

All measurements derive from committed code and committed reports. The complete numeric
record, campaign by campaign, is maintained in [`data.md`](data.md); per-run reports are in
[`bench/results/`](bench/results/); the codebase atlas, mechanically verified against the
source, is in [`memory/codebase_reference.md`](memory/codebase_reference.md).

Measurement tooling is part of the repository, not of the analysis: the ladder generator
(`bench/ladder/generate.py`, fixed seed, byte-reproducible), the naked control arm
(`bench/ladder/run_naked.py`, `bench/naked_probe.py`), and the workflow arms with ablation
levers (`bench/ladder/run_agentic.py`). Ablations are environment-variable levers used
exclusively in A/B contexts and never in production paths.

Model: `gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf`, SHA-256 verified. Runtime: llama.cpp, pinned
build. Sampling: fixed seed 42, context 8192. The 114-test suite runs against every commit and
asserts, among other things, judge satisfiability, ladder monotonicity, and the absence of the
formatting artifact described in §4.4.

# Raising the Reliability Floor of a 2-Billion-Parameter Language Model on Consumer CPU Hardware

### A verification-first agentic architecture, and the measurements that judge it

**Red Giant Project** · Working paper, revision of 2026-08-04
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

We report results from **over 700 instrumented end-to-end runs** across seven measurement
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

A recurring result cuts across all campaigns and we state it as the paper's principal
practical claim: **in this regime, instruction is not a control surface.** Three independent
lines of evidence — an escalating textual mandate to use an available tool (16% → 40%
compliance, no change in outcome), a role-card prohibition violated in 40% of attempts, and a
failure message read and then repeated verbatim — indicate that any property the system
actually requires must be enforced structurally rather than requested. Applying that principle
to *content*, a write-time coherence gate that makes an internally inconsistent artifact
unrepresentable raises the aggregation rung from **9/20 to 18/20 (Fisher exact p = 0.0057)**
while running **37% faster**, and does so on runs in which the model typically never performs
the arithmetic at all. We also report the counterexample that bounds the principle: an
analogous gate targeting an equally frequent pathology produced **no effect whatsoever**
(p = 0.66 and p = 1.00), because an existing component was already absorbing it.

Finally, we state our position with respect to prior art without flattery to ourselves. We
audited seven mechanisms this project believed it had discovered against the published
literature, searching for each one individually and specifically. **All seven are already
documented** [13–37], several of them measured more precisely than we measured them, and one
under the very name we had independently coined. What this paper contributes is therefore not
the mechanisms but the **regime**: a single ~2B model performing every role, on 15 W of
consumer CPU, with no frontier model anywhere in the pipeline — a configuration the nearest
comparable work [13] does not target and explicitly does not report inference cost for. Within
that regime we contribute the numbers (0/20 → 20/20 on a 400-document corpus), a
**single-commit attribution table** across mutually ablatable levers, a catalogue of **negative
results governed by pre-registered decision rules**, and evidence of **substitution between
levers** — a role card and explicit reasoning each recovering what the other's absence costs.
The last of these bears directly on the gap the literature names for itself: that scaffolding
studies use "one-at-a-time ablation at best, never full factorial designs that reveal
higher-order interactions" [16].

---

## 0. Summary of findings

*This section exists so that a reader can obtain the entire result set in one page and then
descend into whichever campaign they wish to audit. Every row cites the section holding its
full data. **Placement criterion:** a row appears in §0.1 or §0.2 only if it has an A/B with
comparable arms and adequate power; anything observed but not isolated appears in §0.3. A
plausible-but-unmeasured improvement is not an improvement.*

### 0.1 Established: interventions that measurably raise the floor

| # | Intervention | Without | With | Mechanism | §|
|---|---|---|---|---|---|
| 1 | Grammar + schema in the prompt | 0/60 usable outputs | **60/60** | the malformed branch is not *generable*, rather than corrected afterwards | 5.1 |
| 2 | Stable prefix (append-only loop) | 7,971 tokens reprocessed | **65** (**122×**) | KV reuse survives only if the prefix never changes | 5.1 |
| 3 | Exact-string edit interface | 20+ failed calls per fix | **5–6 clean** | unified diffs are hostile to a 2B; uniqueness-guaranteed replacement is not | 5.2 |
| 4 | Discriminated unions over steps | 60-call loops after a derail | **8/8 recoveries** | after an unescaped quote there is no longer an incoherent syntactic exit | 5.2 |
| 5 | Identity owned by the control plane | 6/20 invented files · 11/20 name mismatches · 5/20 wrong phase ids | **0 · 0 · 0** | the model creates meaning; the control plane creates identity | 5.4 |
| 6 | **Selective retrieval** | **0/5 on every rung**, replicated **3×** across two corpora, at **+35%** token cost | 18/20 | the only component whose removal loses the won rung: it buys **capability** | 5.8 |
| 7 | **Deterministic verification** | **8 false completion claims in 5 runs** | 1 in **550+** verified runs | buys **honesty**, not throughput: the trust boundary | 5.8 |
| 8 | Retry (2 attempts) | 0/3, dies **fast and cheap** (−59% tokens) | — | absorbs transient failures, including the phantom finish (§5.9.4) | 5.8 |
| 9 | **Write-time arithmetic coherence gate** | **9/20 (45%)** · 797 s | **18/20 (90%)** · 500 s | **Fisher exact two-sided p = 0.0057**, and **37% faster**: refusing early costs less than failing late | 5.9 |
| 10 | Step budget proportional to task size | L7 died without ever writing the file | L7 **11/20** | 20 steps cannot collect 8 facts from 400 documents: not incapacity, budget | 5.9.5 |
| 11 | **Full reasoning budget with untruncated material** | **0/20** | **20/20** | **p = 1.45 × 10⁻¹¹** — but only where material and reasoning fit together within 8,192 tokens; on the full rung the material would be truncated and the gain disappears. A verdict about **hardware** | 6.4 |
| 12 | **Actionable errors** (refusals that state disk state; argument errors that name the missing field) | spirals up to **6 consecutive steps**, **7 fatal sequences** | **max 1 step**, **0 fatal**, recovery **100%** | they do not reduce mistakes (18% of calls still malformed): they remove the **spirals** mistakes used to cause. They act on the *cost* of failing, not its frequency | 6.4-ter |
| 13 | **Runtime cache flags** (full sliding-window cache + suffix shifting) | **2,748** tokens reprocessed to remove a block mid-prompt | **1** | the model family uses sliding-window attention; with a partial cache the runtime cannot reuse anything past a divergence. Costs memory, so adopted on the development profile only | 6.4-quinquies |
| 14 | **Wave compaction of the tool-result chain** | hardest rung **12/40 (30%)**, attempts dying at **7.7 steps**, **731** reprocessed tokens per call | **22/40 (55%)**, **13.2 steps**, **550** per call | **p = 0.0411**, sample size fixed *before* looking. Older results collapse onto the deterministic evidence line each tool already emits — no model-written summary. The +53% wall is the cost of **not dying**, and cache reuse *improves* (89.3% against 85.8%) | 6.4-sexies |
| 15 | **The role card, discovered by ablating it** | stripped card: **1/20**, and the model **reads** instead of searching (440 `read_file` against 169 `search_code`) | full card: **15/20** (294 searches against 146 reads) | **p = 1.0 × 10⁻⁵**. Its function is not to state rules but to **steer tool choice**, and only where selective retrieval is indispensable — on the narrow rung the difference is nil | 5.9 |
| 16 | **Explicit reasoning on wide-retrieval tasks** (not on coding: see §0.2 row 3) | **12/20** on the widest rung, 15.7 steps per attempt, 59 compaction waves | **20/20** (CI 84–100%), 12.4 steps, **13 waves** | **p = 0.0033**. Reasoning does not add context, it **reduces the need for** it: 168 searches against 5 reads. Yields the project's first measured routing rule | 6.4-quater |

**The common thread across the first fourteen: none of them teaches the model anything.** Eight
make an error *impossible to emit*; the rest grant more room, more attempts, or a better choice
of tool for the same work. Rows 15 and 16 are the exception that defines the boundary: both act
on a single behavioural variable — whether the model searches or reads — and they act on it
interchangeably (§6.4-quater).

### 0.2 Rejected: interventions that do not raise the floor

*"Rejected" means **falsified within the measured regime**. Three of the four carry a written
reopening condition, because the regime will change (routing, non-coding domains, larger
tasks). None was closed by opinion.*

| # | Intervention | Numbers | Why it fails | Reopens when |
|---|---|---|---|---|
| 1 | In-loop planner | **2/10 vs 9/10** static baseline · 815K vs 710K tokens · ~10× LLM calls | on small tasks, planning costs more than it returns: the plan becomes one more thing that can be wrong | routing active |
| 2 | Plan compiler | **2/13 vs 6/13**, and **2/13 vs 8/13** on re-measurement · −44% tokens, +9.4 points of useful tokens, no additional greens | the gates move deaths *deeper* (from 0 tool calls to 20–38 at 80–93% useful tokens) without converting them | multi-session tasks |
| 3 | Explicit reasoning **inside the workflow, on coding and narrow rungs** | Δ = 0 over four coding batteries · and on rungs L5–L6 **43/60 vs 47/60**, **p = 0.528**, at **+55% wall** | where the scaffolding already covers the bottleneck, reasoning has nothing to add: above a coherence gate that has made incoherent arithmetic unrepresentable, the work it would do is already done. **Substitutes on a shared bottleneck** | ⚠️ **the reopening condition fired and the answer was positive**: on the widest rung, once capacity was fixed, reasoning gives **20/20 against 12/20, p = 0.0033** (§0.1 row 16). The rejection now holds **only** for coding and narrow rungs |
| ~~4~~ | ~~Explicit reasoning on arithmetic~~ | ⛔ **RETRACTED 2026-08-04** — see §0.1 row 11 and §6.4: all three prior measurements were confounded | — | — |
| 4 | **The deterministic calculator** | `full` **16/20** vs ablated **17/20**, **Fisher p = 1.000** — and not for want of use: 27 successful calls in the full arm | the **coherence gate made it redundant**: the total is right because the control plane refuses incoherence and returns the number, without depending on the model choosing to compute | domains where the gate does not apply (it only understands totals in text files) |
| 5 | In-loop finish gate | L5 **18/20 vs 16/20**, **p = 0.66** · L7 **11/20 vs 11/20**, **p = 1.00** · **+15% wall** | ⚠️ **not shown useless — underpowered** (corrected 2026-08-04): ten points require ~200 runs/arm. The original explanation ("retry already pays") was falsified: all seven failing runs of a later campaign failed by phantom finish in all three attempts | an A/B sized for the effect · and large coding tasks |

**What unites the first three:** everything switched off is "intelligent" — planning, compiling
plans, reasoning, self-supervision. Almost everything switched on in §0.1 is mechanical —
searching, verifying, retrying, refusing the incoherent. The one intelligent mechanism that
survived (§0.1 row 16) survived for a mechanical reason: it changes which *tool* the model
reaches for, not how well it thinks.
**The fourth teaches something else:** a *frequent* pathology is not automatically a *costly*
one. Before building a defence, measure who is already paying for the problem.

### 0.3 Uncertain: decisions taken but not settled

| # | Item | Evidence | Missing | Risk if wrong |
|---|---|---|---|---|
| 1 | Refusals that declare world state | mechanism **observed**: recoveries from **2 of 4** to **4 of 4**; cause certain (`edit_file` on a never-created file, twice in one run) | never isolated in its own A/B — row 9 of §0.1 was measured with both fixes together | low: costless, but part of the guard's credit may belong here |
| 2 | The calculator's place in the catalogue | **switched on without proof** — the only such case: invoked ~40% of the time, often never in winning runs; ablation showed no difference **but at n=5** | an n=20 A/B, and only *after* the argument-error fix: 40% of its calls fail at the interface, so judging it now would condemn the implementation | medium: it consumes prompt tokens every step for a service the coherence gate may already provide |
| 3 | All ladder numbers | GPU profile, not the capped reference CPU profile | the official CPU campaign | medium: direction solid, magnitude not (95% CI on 18/20 is **70–97%**) |
| 4 | L7 = 11/20 | measured at n=20 | attribution: it is the sum of five fixes, none isolated | low on the number, high on its interpretation |
| ~~5~~ | ~~The reasoning verdict on arithmetic~~ | ✅ **RESOLVED 2026-08-04, and it was wrong** (§6.4): 20/20 against 0/20 at full budget and full material. The risk we had labelled "high" materialized exactly as pre-registered | confirmation on the reference CPU profile | — |
| ~~6~~ | ~~Reasoning × workflow (block B4)~~ | ✅ **CLOSED 2026-08-04** (§6.4-quater): both blocks re-measured on the **same commit**, 20 runs per rung. The ladder's 2×2 matrix is complete | the ablated arms of B4 | — |
| 6 | Reasoning × workflow (block B4) | the pre-fix block was **discarded** as non-comparable | re-measurement | medium: half the 2×2 matrix on the ladder is empty |
| 7 | Syntax gate, no-op-edit guard, near-name tool hints | validated by pilots (13 of 43 runs squandered steps on invented tool names; 15 consecutive no-op edits observed) | never passed through the ladder with ablated arms | low: documented pathologies, zero cost |
| 9 | **Which part of the role card steers tool selection** | ablating the card collapses the widest rung (**15/20 → 1/20**) by turning search into blind reading — but *which* rules do it is unknown | bisection: restore rule groups one at a time | medium: 414 tokens per call are provably not free, and provably not all necessary either |
| 8 | **Is the finish gate actually useless?** | ⚠️ its A/B was **underpowered** (§5.9.4): 18/20 against 16/20, and ten points need ~200 runs/arm. Mechanistic evidence now *favours* it — it targets 100% of residual failures on the rung the system wins | an A/B sized for the effect | **medium**: a component worth perhaps ten points on the won rung is currently switched off |

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

We state these after a deliberate priority audit (§2.3), and they are narrower than the ones
we would have claimed before it. None of the *mechanisms* below is new; what we claim is their
behaviour in a regime the literature does not cover, measured in a way it largely does not use.

1. **Results in an uncovered regime.** A single ~2B quantized model performs every role —
   worker, judge, compactor — on four CPU cores at 15 W, with no frontier model anywhere in the
   pipeline, not even as a generator, teacher or fallback. The closest published decomposition
   of agent reliability [13] uses a frontier model to drive smaller specialists and does not
   report inference on constrained hardware; the closest small-model agent system [18] reports
   capability but not hardware. We report both, and the conversion they permit: **0/20 → 20/20**
   on a rung requiring eight facts to be located across 400 documents (§5.8, §6.4).
2. **A single-commit attribution table.** Every component is built with its own ablation lever
   from the outset, so its contribution is measurable in isolation on *the same binary* as every
   other (§0.1, §4.2). Published decompositions are typically assembled across systems,
   benchmarks or model families; ours are fourteen levers on one commit.
3. **A difficulty ladder with an admissibility rule.** A deterministic generator that scales
   *breadth* at constant per-step cognition, plus the rule that governs its use: **if the naked
   model passes a rung, that rung measures nothing about the harness** (§4.4). The principle
   that baselines must precede architecture is established [15]; operationalizing it as a
   generator with a pass/exclude criterion is our formulation.
4. **Negative results with pre-registered decision rules.** Five rejections — an in-loop
   planner, a plan compiler, in-workflow reasoning, a deterministic calculator, a finish gate —
   each condemned by a rule written before the data existed, and one of them (§5.9.4) *corrected
   in public* when we discovered the test that produced it was underpowered (§6.5).
5. **Evidence of substitution between levers**, not merely of their individual effect: on the
   widest rung, a full role card without reasoning (12/20) and a stripped card with reasoning
   (19/20) both recover what their counterpart's absence costs (1/20). This is the class of
   higher-order interaction that the scaffolding literature identifies as systematically
   unmeasured [16], and the reason our next campaign is full-factorial rather than
   one-lever-at-a-time (§6.4-quater, §8).
6. **An empirical demonstration that deterministic verification purchases honesty**, separable
   from and independent of throughput (§5.7) — a property known qualitatively [25–27] which we
   quantify in this regime: 8 false completion claims in 5 unverified runs, 1 in 550+ verified.

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
schema-validated harness beats GPT-3.5-Turbo at function calling [6]. The same effect is
visible at leaderboard scale, where harness choice reorders systems built on identical models
[17], and the position that small models are the appropriate substrate for agentic work is now
argued explicitly [12] and surveyed [43].

### 2.2 What the literature also says, and we confirm

The same body of work draws a boundary we independently rediscovered. Per-step reliability
compounds multiplicatively over dependent chains (p^H); even frontier models degrade from near
100% on sub-4-minute tasks to under 10% on multi-hour tasks [7]. Reasoning capability that is
absent cannot be prompted into existence in a 2B model [8]. Four-bit quantization taxes small
models disproportionately, unlike 70B-class models [9] — which is why this project uses
quantization-aware training weights.

The honest summary of the field, which our own results reproduce: **the floor rises
substantially; the ceiling does not move.**

A third line of work is directly relevant to two of our rejections. Specification-driven and
multi-agent decomposition — role-differentiated pipelines [44], test-driven governance of
generated code [45], and the spec-first toolchains now shipping in industry [46] — is the family
our plan compiler belongs to; we report it failing in this regime (§5.4, §5.5), which is a
statement about 2B models on 15 W, not about the approach. Likewise, small dedicated critics
[41] and self-healing orchestration loops [42] are the family our rejected supervisor and our
in-loop finish gate belong to; the finish gate's rejection is now known to have been
underpowered rather than negative (§5.9.4), so we regard that question as open rather than
answered.

### 2.3 A priority audit of our own findings

The remainder of this paper reports mechanisms we designed, measured and in several cases
believed to be ours. Before publishing them we conducted a **priority audit**: for each
mechanism separately — not for the topic, but for the specific phenomenon, searched under the
words the phenomenon would attract rather than the words we had given it — we looked for prior
art. We report the outcome without softening it.

**Seven mechanisms audited, seven already documented.** The table below is the honest map of
what belongs to the field and what, if anything, remains ours.

| # | What we built and measured | Prior art | Verdict |
|---|---|---|---|
| 1 | Decomposing agent performance into scaffolding versus verification versus model capability, with per-component ablation | [13] performs exactly this decomposition across multiple benchmarks with contributions in percentage points: on SpreadsheetBench, **structure +9.5pp of 11.0 total, verification +1.5pp**. Also [14] (failure-localization taxonomy), [17] (leaderboard-scale harness effects) | **Known, and quantified more precisely than by us.** Their conclusion — scaffolding dominates, verification adds little to *success rate* — is ours, reached independently. Our addition: verification's value is not success rate but honesty (§5.7) |
| 2 | The naked-baseline rule: *if the naked model passes a rung, the rung measures nothing about the harness* | [15] argues that architectural claims must be preceded by properly tuned baselines, and shows scaffolds that vanish once the baseline is honest | **Known as a principle.** Our formulation as a *generator with an admissibility criterion* (§4.4) is the operational form, not the idea |
| 3 | Ablating groups of rules from the role card and measuring the outcome (15/20 → 1/20) | [20] removes individual rule categories from a system prompt and quantifies each one's impact ("output-contract rules have the highest impact") | **Known, and at finer granularity.** Our contribution is the *magnitude in this regime*: a prompt ablation that costs fourteen points on a task the full card wins |
| 4 | "Searching instead of reading" as the single variable predicting success on wide corpora | [21] finds retrieval-by-grep competitive with or superior to embedding retrieval for agents; [22] and [23] extend it; [24] argues for direct corpus interaction over semantic similarity | **Known.** These works study the *harness*; we observed the same variable being determined by the *prompt* at a granularity they do not examine (§6.4-quater) |
| 5 | The honesty gap: `completed ≠ verified`, an agent claiming success it did not achieve | [25] names the phenomenon **false success** and characterizes it as confident closing followed by silent failure; [26] detects near-miss latent policy failures; [27] studies agents deceiving their supervisor upward | **Known, under a name we independently reinvented.** We measure it as a *primary metric with an ablation attached* (8 in 5 versus 1 in 550+), which is less common than measuring it descriptively |
| 6 | Explicit reasoning compensating for a weakened role card | [28] states the **compensation hypothesis** — reasoning structure substitutes for capability gaps; [16] studies cross-component interference in scaffolding directly; [29] and [30] establish that reasoning's value is conditional on model strength (CoT takes Qwen3-30B from 18% to 64% and **costs GPT-5 fifteen points**) | **Known.** Our 2×2 (card × reasoning: 12/20, 1/20, 20/20, 19/20) is a small instance of an effect the field has already named |
| 7 | Wave compaction of the tool-result chain, collapsing old results onto deterministic evidence lines | An entire subfield: [31] learns compaction policies; [32] validates compaction against the trajectory; [33] has agents compact themselves; [34] compacts in parallel; [35] makes compacted content addressable for recall; [36] argues structured eviction beats compaction; [37] treats code as the harness for offloading. Production practice is documented by Anthropic, LangChain, Databricks, AgentScope and others [38] | **Known, thoroughly.** Our one non-obvious choice — collapsing onto the *tool's own evidence line* rather than a model-written summary — is a conservative variant of [32]'s concern, not a new idea |

Two further items were checked and found equally well covered: **KV-prefix fragility** under
any mutation of the prompt prefix, and the runtime cache flags that mitigate it for
sliding-window models [39, 40]; and **small models failing to exploit error feedback** —
[18] describes them retrying "the identical payload after an API error", which is the
pathology our actionable-error work targets (§6.4-bis, §6.4-ter), while [19] reports the
corresponding fix, that concrete errors ("re-read the file") outperform abstract ones
("system problem").

### 2.4 What this audit cost, and what it left standing

The audit changes nothing about the measurements. It changes what may honestly be claimed on
top of them:

**Not ours:** the mechanisms, the decomposition, the naming, the direction of every effect.

**Ours, and we believe defensible:**

- **The regime.** One ~2B model, four cores, 15 W, fully local, every role played by the same
  weights, no frontier model as generator, teacher, judge or fallback. [13] uses a frontier
  generator with 0.5–3B specialists and reports cloud serving economics; [18] reports small-model
  agent capability without constrained-hardware inference; [19] targets terminal coding agents at
  a scale well above ours. We are aware of no published decomposition in this configuration.
- **The numbers in that regime**, including the ones that flatter nobody: 0/20 naked to 20/20
  scaffolded on a 400-document rung, and equally the four campaigns where the addition of
  intelligence produced Δ = 0.
- **Attribution on a single commit.** Fourteen levers, each ablatable independently, measured
  against the same binary — as opposed to a decomposition assembled across systems or papers.
- **A catalogue of negative results with pre-registered rules**, including a public correction
  of one of our own verdicts (§5.9.4, §6.5). The field publishes few of these; [16] and [15]
  both argue that this is precisely what is missing.

### 2.5 The gap the literature names for itself

One sentence from [16] identifies the methodological hole into which this project's next
campaign is aimed:

> previous work uses one-at-a-time ablation at best, **never full factorial designs that
> reveal higher-order interactions**.

Our own results already contain such an interaction and were nearly misread because of it: a
stripped role card is catastrophic alone (1/20) and nearly harmless under reasoning (19/20),
so a one-lever-at-a-time protocol would have assigned each lever a value that does not exist
independently of the other. The full-factorial campaign described in §8 — every arm, coding and
non-coding, with every ablation and every switch in both positions, on one commit and on the
reference CPU profile — is therefore not thoroughness for its own sake. It is the design the
literature says is missing, run in the regime the literature does not cover.

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
3. **The calculator's attribution is weak** (2/5 vs 1/5, within the noise band) — and the
   artifact-level diagnosis explains why: across 43 analysed runs, **only 7 invoked the
   calculator at all**. Ablating a tool the model does not call cannot change outcomes. The
   same analysis found 13 of 43 runs squandering half their step budget calling non-existent
   tools with placeholder names. Both defects are of the workflow, not the model. §5.9 follows
   this thread to its conclusion.

---

### 5.9 Instruction is not a control surface

This section reports the campaign that followed from the weakest attribution above, and which
produced both the strongest single result in the project and its most instructive null result.

#### 5.9.1 Three levels of textual persuasion, measured

L5 asks for five facts plus their sum, over the same corpus as L4 — which the naked model
solves 3/3. The delta between the two rungs is exactly one addition. The model retrieves 5 of
5 facts and mis-sums them, with units and tens correct and hundreds wrong: dropped carry
propagation. A deterministic calculator was available throughout. We escalated textual
persuasion in three measured steps:

| Persuasion level | Tool actually invoked | L5 verified |
|---|---|---|
| tool present, no rule | 7/43 runs (16%) | 2/5 |
| + numbered rule in the role card, carrying the measured rationale | ~40% | 2/5 |
| + full tool name + description marked **MANDATORY** | 40% | 2/5 |

**Sixty per cent of runs continued to compute mentally, and the score never moved.** Ablating
the tool changed nothing either — one cannot ablate what is never called.

#### 5.9.2 Removing the operation from the model's hands

If instruction does not produce compliance, the operation must be made *unrepresentable*. A
total is not meaning: it is **identity derived** from values the model itself wrote, and
identity belongs to the control plane (§3.3). We therefore extended the project's
"make-it-impossible" principle — previously applied only to *syntax* — to **content**: before
any text artifact reaches disk, a declared total is checked against the values declared
alongside it; if incoherent, the write is **refused** and the correct figure is returned in the
error.

The gate is deliberately conservative — text files only, never code or configuration; the total
must be the final numeric assignment; at least two addends; exactly one total — because a false
positive blocks legitimate work, which is far worse than a missed catch. Critically, **it is not
an oracle over the task**: it sums what the model wrote, not what is true, so wrong facts still
yield a wrong total. Internal coherence, not correctness. **The prompt was not modified**, so
the delta is attributable to the mechanism alone.

| Arm (20 runs each) | L5 verified | Wall |
|---|---|---|
| coherence gate active | **18/20 (90%)** | 500 s |
| gate ablated | **9/20 (45%)** | 797 s |

**45 points, Fisher exact two-sided p = 0.0057**, and the gated arm is **37% faster** — refusing
before the write costs one rewrite, whereas an incoherent artifact costs a failed verification
plus a restart of retrieval. This is a rung the naked model does not pass in *any*
configuration (0/3 with and without reasoning): the 90% is entirely the scaffolding's.

The sharpest detail: in the passing runs the model frequently **never invokes the calculator at
all**. The total is correct because the control plane refuses the incoherence and hands back the
figure; transcription is all that remains to the model.

#### 5.9.3 A methodological failure, reported

The first blocks of this A/B were run at n=5 and produced, **on functionally identical code**,
9/20-equivalent results of **1/5 and then 5/5**; the treated arm gave 2/5, 3/5, 5/5 across
successive builds. An attribution was written on that basis and had to be retracted. The cause
is that this model's behaviour swings in *whole blocks* — the calculator went unused across five
consecutive runs and was then used continuously across the next five — so the effective variance
is far wider than the hardware noise band of §4.3. The resulting standing rule: **no conclusion
from this ladder below 20 runs per arm, reported with an exact test rather than an impression.**

#### 5.9.4 The null result: an in-loop finish gate

Reading complete step-level logs rather than scores exposed a second pathology: in **31 of 78
attempts (40%)** the executor declared the subtask *done* having called no write tool at all.
In one attempt it located all five facts, computed the sum correctly through the calculator
step by step, and then finished — with no file on disk. The system already reports this: the
judge's `answer file missing` is propagated into the next attempt's failure block. The model
reads it and repeats. This is the **third independent confirmation** that instruction does not
produce compliance; the role card has forbidden exactly this behaviour since the first phase.

We therefore built the structurally analogous defence: before the executor loop may return
*done*, the promised artifact is checked, and — where the attempt mutated nothing and the
oracle is red — the finish is refused and becomes one more step, with the context still warm.

| Rung (20 runs per arm) | gate active | gate off | Fisher exact |
|---|---|---|---|
| L5 | 18/20 · 725 s | 16/20 · 633 s | **p = 0.66** |
| L7 | 11/20 · 629 s | 11/20 · 623 s | **p = 1.00** |

**No detectable difference at n = 20, at a 15% wall-clock cost.** The gate ships switched off.

> **Correction (2026-08-04).** An earlier version of this subsection explained the null by
> asserting that *the retry loop was already paying for the phantom finish*, and drew from it a
> lesson about frequent-but-costless pathologies. **Subsequent log analysis falsified both.**
> In a later campaign on the same rung, every one of the seven failing runs failed by phantom
> finish — **in all three of its attempts**. Retry does not pay for it; it offers three chances
> and the model squanders all three identically.
>
> The correct reading of p = 0.66 is arithmetic rather than mechanistic: 18/20 against 16/20 is
> a **ten-point** effect, and separating ten points from noise requires on the order of **200
> runs per arm**, not twenty. **The A/B was underpowered, not conclusive.** We had adopted a
> standing rule of twenty runs per arm one day earlier without asking *twenty runs to detect
> what effect size* — and then read our own insufficient sample as a verdict.
>
> The gate remains disabled, but for a different reason: not redundancy, but **unproven
> effect**. The mechanistic evidence now favours it — it targets 100% of the residual failures
> on the rung the system otherwise wins.

The lesson we do retain, restated correctly: **a null result on a small effect is not a verdict,
it is an insufficient sample.** Power must be chosen against the effect size one expects to
matter, and "how many runs" is not answerable without "to detect what".

#### 5.9.5 Where the hardest rung actually dies

The same A/B answered a question open since the ladder was built. L7 — 400 documents, 25K
tokens, three times the context window, eight facts plus a sum — was assumed to fail on step
budget or on discipline. It fails on **neither**. Across 92 attempts the executor uses **8.5
steps on average and at most 18** of 60 available; not one exhausts its step budget. Attempts
die because the append-only chain of step results overflows the context window: a single search
result over 400 documents can occupy ~1,500 tokens, and five or six saturate 8,192.

L7 is therefore a **capacity** problem, not a cognition or compliance problem — which locates it
precisely in the context-and-cache work programme, now motivated by a measurement rather than an
intuition. The candidate levers (narrower results, compaction of older results, offloading found
facts to a scratch artifact) are in tension with the append-only KV reuse of §5.1 — 65 tokens
against 7,971 — and that trade-off must be measured, not assumed.

A secondary but notable figure: with the current code L7 passes **11/20**, against red in every
previously measured arm and 0/3 naked. The credit belongs to the accumulated fixes, not to the
finish gate, which was identical in both arms.

*(Method note, reported because it changed the conclusion: an initial automated classification
read these deaths as "step budget exhausted" — the pattern matched the phrase "exceeds budget"
in a context-overflow message. The correct diagnosis came from reading the failure reasons in
full rather than counting them.)*

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

This distinction is what reconciles our results with [13], which decomposes the same three
factors across several benchmarks and finds verification worth **+1.5pp against structure's
+9.5pp**. Read as a statement about success rate, that number is correct and ours agrees with
it. Read as a statement about *value*, it is an artifact of the metric: the component
contributing 1.5 points of throughput is the one contributing the difference between a system
that reports its own state truthfully and one that does not. The literature on false success
[25–27] measures the same pathology descriptively; our contribution is to place it under an
ablation lever, so that the honesty cost of removing verification is a number rather than an
observation.

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

Both halves of this are documented elsewhere and we cite them rather than claim them: small
models retrying "the identical payload after an API error" is reported in [18], and the
corresponding remedy — concrete, state-naming errors outperforming abstract ones — in [19].
What our measurement adds is the *shape* of the benefit (§6.4-ter): actionable errors do not
reduce the frequency of malformed calls at all, they eliminate the spirals those calls used to
cause.

### 6.4 A claim we published and then falsified ourselves

An earlier version of this section asserted that *explicit reasoning cannot be argued into
producing correct arithmetic, whereas a deterministic tool can*. Three configurations of
reasoning had failed the aggregation rung, one of them apparently controlled for context
consumption. We retract that claim, and the retraction is more informative than the claim was.

**All three configurations were confounded, in opposite directions.** Two granted the reasoning
channel its full budget but, on a rung already near the context limit, thereby *truncated the
material* (6,000 tokens of material against 7,536 for the non-reasoning arm). The third
equalized the material by shrinking the reasoning budget to 256 tokens — a budget our own
mechanics measurements had already shown never permits a natural close, cutting every trace
mid-sentence. A null result under that control cannot distinguish "reasoning does not help"
from "256 tokens are not enough to reason". **A control that mutilates the variable instead of
isolating it is not a control**; it produces an unreadable null that reads as confirmation.

The correct experiment holds *both* at full size, which requires either a larger context window
— beyond the platform's measured ceiling — or a smaller corpus. We took the second route: a
controlled variant of the aggregation rung, same task, corpus small enough that the material
fits in both arms with margin. Verified with the model's own tokenizer before reading any
outcome: 3,587 tokens of material against budgets of 7,536 and 6,000; **no truncation in either
arm**, the two arms seeing byte-identical material.

| Arm (20 runs each) | Verified |
|---|---|
| naked | **0/20** |
| naked + full reasoning budget | **20/20** |

**Fisher exact two-sided p = 1.45 × 10⁻¹¹.** The non-reasoning arm mis-sums stably; the
reasoning arm is correct twenty times out of twenty.

**What this does and does not overturn.** It does *not* overturn the official coding verdict
(Δ = 0 verified across four batteries at 1.9× wall): that is a different domain and a different
measurement, and reasoning remains disabled there. It does overturn the extension of that
verdict to arithmetic. The defensible statement is narrower and more useful: **reasoning does
buy arithmetic, and does not fit into 8,192 tokens alongside the material.** That is a verdict
about *hardware*, not about the model — and it converts the context-and-cache programme from a
performance concern into a capability one, with a second objective it did not previously have:
make room for reasoning, not only for material.

**Two independent solutions now exist for the same rung, and they occupy different regimes.**
The write-time coherence gate delivers 18/20 on the *full* rung at the shipping context size;
full reasoning delivers 20/20 only where material and reasoning fit together, which the full
rung does not permit. The gate is therefore the deployable answer today and reasoning is the
one that requires more context. They are not alternatives but two points on the same
cost-versus-capacity curve — and it is that curve the next phase must optimize.

We note that the retracted claim was consistent with the literature we cited for it [2][4],
which is precisely why it survived three measurements. Agreement with prior work is not
evidence; it is a reason to check the control harder.

### 6.4-bis Errors must state the world, not only the fault

A defect found while measuring the coherence gate generalizes beyond it. When a write was
refused, half the runs failed to recover — not because they could not fix the number, but
because **nothing told them the file did not exist**. One called an edit tool on a
never-created file, twice; another proceeded to verify an artifact it had never written. The
model treated a refusal as a success and reasoned about a world that did not exist.

Making every refusal declare the resulting disk state took recoveries from 2 of 4 to 4 of 4.
We propose the general form: **an error that reports what was wrong but not how the world was
left leaves the model reasoning about a state that does not exist.** This holds for every gate
that refuses an action, and we had shipped the same trap in the syntax gate since the first
phase without noticing it.

### 6.4-ter Two error families, acting on different axes

An earlier version of this subsection claimed to have found a *bound* on the make-it-impossible
principle: that a defence pays only where nothing already absorbs the failure, the phantom
finish supposedly being absorbed by retry. **That claim was falsified by later log analysis and
is withdrawn** (§5.9.4): retry does not absorb it, and the null that motivated the claim was an
underpowered sample rather than an absent effect.

What survives, and is better supported, is a distinction between two families of intervention
that we had been conflating:

**Deterministic gates change how often the system succeeds.** The write-time coherence gate
takes the aggregation rung from 45% to 90%. It asks the model for nothing.

**Actionable errors change how much a mistake costs.** Making a refused write declare the disk
state took recoveries from 2 of 4 to 4 of 4. Making a malformed-arguments error name the missing
field and show the exact call shape left the malformed-call *rate* barely improved — 32% to 18%,
the model still sends empty arguments roughly one time in five — but eliminated the spirals
those mistakes used to cause: the longest run of consecutive failures fell from **six to one**,
and **seven fatal sequences became zero**, with the following call succeeding in every case.

This distinction matters practically, because it dictates *what to measure*. We pre-registered
the wrong metric for the argument-error work — predicting the error *rate* would fall to zero —
and would have recorded a real improvement as a failure had we not read the sequences. An
intervention that acts on the cost of failing is invisible to a frequency metric.

The operative question before building a defence therefore remains worth asking — *what
currently happens when this occurs?* — but its answer must come from logs, not from the
assumption that some other component is coping.

### 6.4-quater Reasoning and scaffolding: substitutes on a shared bottleneck, complements otherwise

The four-block matrix exists to answer one question no single arm can pose: *does reasoning
substitute for a missing component?* With both workflow blocks measured on the same commit,
twenty runs per rung, it has an answer that took three campaigns to reach and required us to
narrow our own claim twice.

| Comparison | Effect of reasoning |
|---|---|
| **B3 − B1** — naked model, controlled rung | **0/20 → 20/20**, p = 1.45 × 10⁻¹¹ |
| **B4 − B2** — inside the workflow, rungs L5–L6 | 43/60 vs 47/60, **p = 0.528**, at **+55% wall** |
| **B4 − B2** — inside the workflow, **widest rung L7**, once capacity was fixed | **12/20 vs 20/20**, **p = 0.0033** |

The middle row is what we published first, and read alone it says *reasoning inside the workflow
does not pay*: per rung the signs alternate (−3, +3, +4) with p-values identical to three
decimals, noise about zero. The explanation we gave for it was that scaffolding and reasoning
resolve the same bottleneck and whichever arrives first takes all — unaided, reasoning performs
the arithmetic the naked model cannot; above a coherence gate that has already made incoherent
arithmetic unrepresentable, it has nothing left to contribute.

**That explanation was too general, and the third row falsified it.** We registered the
prediction before measuring: *"if the substitution thesis holds, reasoning's advantage must
disappear now that wave compaction covers capacity."* The opposite happened — the advantage
**grew**, from +4 to +8, with the reasoning arm at **20/20 and its confidence interval
84–100%**. The claim therefore narrows to its defensible form:

> Scaffolding and reasoning are **substitutes where they cover the same bottleneck** (arithmetic
> on L5: the coherence gate closes it, and reasoning adds nothing) and **complements where they
> do not** (retrieval strategy on L7: nothing in the scaffolding chooses *how* to look).

**The mechanism, and why it unified three separate findings.** Reasoning does not add context —
it *reduces the need for* context. On the widest rung the reasoning arm issues **168 searches
against 5 reads**, where the non-reasoning arm issues 109 against 23. It finds material sooner,
spends fewer steps, closes in half the attempts, and never approaches the window ceiling:
**13 compaction waves against 59.** That same variable turned out to govern two earlier results:

| Intervention | Effect on behaviour | Outcome on the widest rung |
|---|---|---|
| Ablating `search_code` (§5.8) | forced to read | **0/5 on every rung** |
| Stripping the role card (§5.9) | 440 reads against 169 searches | **1/20** |
| Adding reasoning (here) | 168 searches against 5 reads | **20/20** |

> **On wide corpora the single variable predicting success is whether the model searches or
> reads.** A tool, a piece of prose, and a reasoning channel all push that one lever, and their
> outcomes order exactly as the force with which they push it.

This is the same variable the retrieval literature has been converging on independently —
grep-style direct corpus interaction outperforming embedding retrieval for agents [21, 22, 24].
Our addition is the observation that the *prompt*, not only the harness, determines which
strategy the model adopts.

**The 2×2 that closes the argument.** If the three interventions push one lever, two of them
should be interchangeable. Measured, twenty runs per cell, on the widest rung:

| L7 | full role card | stripped role card |
|---|---|---|
| **without reasoning** | 12/20 | **1/20** |
| **with reasoning** | **20/20** | **19/20** |

The card is worth twelve points against one when reasoning is off, and one point against twenty
when it is on. **The levers are largely interchangeable**, which has a direct design consequence:
with reasoning active the card's 414 prompt tokens per call can be released for the price of
1/20. One may pay in reasoning instead of in prompt tokens — a choice, not a constraint.

This is an instance of the **compensation hypothesis** [28] — reasoning structure substituting
for capability gaps — and of the cross-component interference [16] that scaffolding studies are
criticized for not measuring. It is also why per-lever value is not a well-defined quantity here:
each of these two levers is worth almost everything or almost nothing depending on the other's
position, which is exactly the higher-order interaction a one-at-a-time protocol cannot see, and
the reason our next campaign is full-factorial (§8).

**A second registered prediction, also wrong, with an architectural payoff.** We predicted that
on the widest rung reasoning would make matters *worse* by consuming 1,536 tokens of an already
saturated window. The prediction rested on a wrong model of where the reasoning budget is spent:
the two-call protocol discards the reasoning trace and never appends it to the durable chain, so
its cost is **per call, not cumulative** — the context that overflows is composed of tool
results, identical with or without it. An architectural decision taken for chain purity turns
out to protect against a failure mode identified months later.

**The operational consequence** is the project's first routing rule derived from a measurement
rather than an intuition, and it matches the conditional-reasoning literature [30]: reasoning
**on** for wide-retrieval tasks, **off** for coding — where four batteries measured Δ = 0 at
+55% wall time. Reasoning pays where a *retrieval strategy* is needed, not where reasoning in
the abstract is needed.

### 6.4-quinquies A constraint that structured a phase, and belonged to our configuration

The context-and-cache phase was designed around a measurement from the project's first
benchmark: altering one byte mid-prompt costs 7,971 tokens of reprocessing against 65 for a pure
append (§5.1). That figure makes compaction look prohibitive and shaped the plan accordingly.

Re-measured before any code was written, it does not survive, for two independent reasons.

**The original probe answered a different question.** It changed a byte *in place* — the correct
test for prefix stability, which is what it was built for. Compaction instead **removes a block**
and shifts everything after it. Adding that scenario required repairing two design faults we
found only by measuring: cutting at an arbitrary character offset breaks tokenization at the
seam, so no reuse is possible under any configuration; and a homogeneous filler prompt makes a
middle removal byte-identical to a truncation, measuring the wrong thing entirely.

**The runtime has a mechanism for this case, and we were not using it.**

| Configuration | byte changed mid-prompt | **block removed** |
|---|---|---|
| our default | 4003 | **2748** |
| suffix-shifting alone | 4003 | **2748** |
| full sliding-window cache alone | **2001** | **1390** |
| **both** | **2001** | **1** |

Removing a block falls from 2,748 reprocessed tokens to one. The full sliding-window cache is
the prerequisite: this model family uses sliding-window attention, and with a partial cache the
runtime cannot reuse anything past a divergence — which is why enabling it halves the
byte-change case exactly as theory predicts. Suffix shifting then translates the remaining KV
rather than recomputing it.

Two consequences. First, an eviction-based context policy is no longer excluded on cache
grounds, and the phase must be redesigned with that option restored. Second — the transferable
part — **the standard warning that compaction invalidates the cache is correct in general and
runtime-dependent in practice**: this runtime can shift, if asked. The full cache costs memory,
so the flag is adopted on the development profile and remains unmeasured on the memory-
constrained reference profile.

**The methodological lesson:** *a constraint that structures an entire phase must be
re-measured before designing around it*, especially when the number supporting it is old and was
gathered to answer a different question. Ours was correct for prefix stability and simply did
not transfer to removal.

### 6.4-sexies Capacity, measured: where the window goes and what buying it back is worth

Persisting the per-section composition of every prompt — a computation that already existed but
was discarded except inside overflow errors — turns the capacity problem from a diagnosis into a
target. On 140 calls of the hardest rung: the tool-result chain is **the only section that
grows**, reaching **65% of the prompt** at the ceiling, while a **fixed 31% of the window** is
spent before any work begins. The largest fixed item is the executor's role card, at 837 tokens
per call — a figure nobody had computed, and an uncomfortable one, since the campaign was spent
*adding* rules to that document and measuring that they did not work.

The instrumentation also exposed a defect of a kind we expect to recur: a card rule mandating a
tool that had been removed from the catalogue two commits earlier — an unexecutable instruction
issued on every step, and the explanation for a set of calls to a non-existent tool we had
recorded as a curiosity. A permanent test now forbids any role card from naming a tool outside
the default catalogue.

**The intervention.** Past a threshold, older tool results collapse onto the deterministic
evidence line each tool already emits. No model-written summary is involved: a hallucinated
summary inside the chain of record would be worse than the verbose text it replaces. Compaction
happens **in waves** rather than continuously, because rewriting the prefix costs one token with
the runtime flags of §6.4-quinquies and a full reprocess without them — a wave pays that once,
continuous eviction pays it on every request.

Context compaction is a crowded field and we adopt rather than propose: policies can be learned
[31], validated against the trajectory [32], performed by the agent on itself [33], parallelized
[34], made addressable for later recall [35], replaced by structured eviction [36], or offloaded
into code [37], with production practice documented by several vendors [38]. Our only choice
worth stating is the conservative one — collapsing onto the tool's own evidence line rather than
onto generated prose — which is a stricter form of the concern [32] addresses by validation.
Two things we do report that this literature generally does not: the interaction with KV prefix
reuse (compaction *improved* reuse, 89.3% against 85.8%, contrary to the trade-off we had
assumed), and the failure mode of compacting **once per attempt** — a re-arm counter was
required, without which 49% of compacted attempts still died of context exhaustion.

| Arm (40 runs, hardest rung) | Verified | 95% CI | Steps per attempt |
|---|---|---|---|
| compaction active | **22/40 (55%)** | 40–69% | **13.2** |
| ablated | **12/40 (30%)** | 18–45% | 7.7 |

**Fisher exact two-sided p = 0.0411.** The rung had been red in every previously measured arm
and 0/3 naked. The 53% additional wall-clock is not compaction overhead but **the cost of not
dying**: ablated attempts stop at 7.7 steps, matching the context-exhaustion death diagnosed in
§5.9.5, and are fast for the same reason the no-retry arm was fast.

**On the method, which is the transferable part.** A 20-run pilot (11/20 against 6/20,
p = 0.20) was used *only to size the experiment*; the power calculation specified 40 per arm;
a **fresh** confirmatory sample was then collected, with no optional stopping. Pilot and
confirmatory agree to the percentage point. This is the retraction of §5.9.4 applied rather than
repeated — and it is the first result in this project obtained under a pre-specified sample
size.

**And it does not cost what it was expected to cost.** Compaction rewrites the prefix, so the
natural objection is that it must destroy cache reuse. Measured, the opposite holds: **89.3%
reuse with compaction against 85.8% without**, and **25% fewer reprocessed tokens per call**
(550 against 731) at a lower mean prefill. A wave costs about one token under the runtime flags
of §6.4-quinquies and leaves a *shorter* prompt, so every subsequent step processes less. The
per-step reuse curve starts low — cold prefix — and climbs to 90–95% from the third step in both
arms: the append-only design works as intended and survives compaction.

**What remains unestablished** is the same clause as everywhere else: this holds on the
development profile, which carries the runtime flags. On the memory-constrained reference
profile, where a rewrite would cost a full reprocess, the account must be redone. The
intervention is **accepted on the development profile and pending on the reference one**.

### 6.4-septies Instrumentation as an intervention: two defects and one self-inflicted cost

Two of this phase's findings came not from building a mechanism but from measuring one.

**A ratio that exceeded one.** Reuse instrumentation initially reported 102%. A ratio above unity
means the numerator is not the quantity one believes, so we interrogated the runtime rather than
adjusting the formula. The field we had been recording as "cached" (`tokens_cached` in the
server's completion response) is *how many tokens sit in the cache afterwards* — prompt+1,
identical on cold and warm calls — whereas the quantity actually wanted is the reported
prompt-processing count (`timings.prompt_n`: 721 cold, 1 on an identical prompt, 4 on an append). The consequence was not cosmetic: the task token
budget subtracted `prompt − cached`, which was therefore **always zero**, so the budget had been
counting generation and never prefill since the system's first phase. The original benchmark had
used the correct field, so no published measurement was affected; the defect lived purely in
runtime accounting. **The transferable point: it surfaced only because a derived quantity left
its admissible range.** Prefer metrics that *have* an admissible range — a ratio betrays itself,
a sum does not.

**A cost we had imposed on ourselves.** The per-section breakdown showed that a fixed 31% of the
window is consumed before any work begins, the largest single item being the executor's role
card. Reducing that card to the rules that either carry measured evidence or are not already
enforced by structure frees **414 tokens on every call, 5.1% of the window**. The removals fall
into three classes, each with a stated reason: rules the type system already makes unviolable;
rules measured ineffective, or inert under the current configuration because they describe
entities that no longer exist; and rules duplicated by an actionable error that arrives at the
moment of failure — the class we measured to work.

The second finding deserves emphasis because it inverts the usual direction of blame. Over the
campaign we repeatedly *added* prose to that card and repeatedly measured that the additions
changed nothing. The instrumentation revealed we had also been paying for them, on every step of
every run, in the scarcest resource the system has.

**And then the A/B rejected the reduction, which is the most instructive result of the phase.**
On the small corpus the two cards are indistinguishable (20/20 against 18/20). On the widest
rung the reduced card collapses: **15/20 against 1/20, Fisher exact p = 1.0 × 10⁻⁵.** The tool
logs identify the mechanism, and it is not the loss of any particular rule but a change of
behaviour: with the reduced card the executor issues **440 file reads against 169 searches**,
where the full card produces **294 searches against 146 reads**. It reads instead of searching —
which across four hundred documents is exactly the behaviour of the search-ablated arm that
scores zero on every rung, and it reaches the point of writing an answer twice in twenty runs
against forty-six.

Two conclusions follow, and the second is uncomfortable.

**The role card is not merely a list of rules: it steers tool selection**, and it does so
precisely where selective retrieval is indispensable. The component our ablations had identified
as load-bearing turns out to require the card in order to be *used*. This is a coupling between
prompt and capability that we had not measured and would not have predicted.

**And our reasoning for the reduction was plausible and wrong.** Each removal carried an
argument — the rule is already enforced by the type system; the rule was measured ineffective;
the rule is duplicated by an actionable error delivered at the moment of failure. All three are
sound arguments and **none is a measurement**. That a constraint is unviolable by construction
says nothing about what its *presence in the prompt* does to the model's choices. We record this
as the phase's clearest instance of a general hazard: an argument about why something should not
matter is not evidence that it does not.

### 6.5 On negative results

This project has now rejected two planning architectures, one reasoning configuration, and one
of its own structural defences by pre-registered rules. We consider these the most valuable
outputs to date, for two reasons. First, they are the rarest artifact in the field: published,
quantified, architecture-level negative results on small-model agents. Second, they redirected
effort precisely — the failure of in-loop planning identified missing gates rather than a weak
proposer, the failure of reasoning identified placement rather than quantity as the governing
variable, and the failure of the finish gate identified the precondition of §6.4-ter, which we
expect to save more construction effort than the gate would ever have saved runs.

---

## 7. Threats to validity

**Single model, single runtime.** All results are obtained with one quantized model on one
pinned inference build. Several calibrated tolerances (retry thresholds, step budgets, string
formatting heuristics) are plausibly overfitted to this configuration and require re-validation
on any change of model or runtime.

**Non-determinism, and two demonstrated failures to respect it.** Neither environment is fully
reproducible (§4.3). Worse, the effective variance exceeds the hardware noise band: the model's
behaviour swings in *whole blocks*, and we observed the same configuration produce 1/5 and then
5/5 on functionally identical code (§5.9.3). One attribution was published internally on that
basis and retracted. We then adopted a standing rule of twenty runs per arm — and immediately
committed the complementary error, reading an underpowered null (18/20 against 16/20) as a
verdict of no effect (§5.9.4). **A fixed run count is not a power calculation**; twenty runs
resolve a forty-point difference and are blind to a ten-point one. Verdicts here are drawn at
twenty runs per arm with an exact test, which is adequate for the large effects reported and
explicitly inadequate for the small ones — those are now labelled as unresolved rather than
negative.

**Synthetic tasks.** All batteries to date are synthetic and small — 2 to 15 file repositories
and generated document corpora. The behaviour of the system on a real codebase with genuine
history, ambiguity and scale is untested and is the project's designated final examination.

**Judge design.** Judges are independent scripts, but they were written by the same author as
the tasks. A judge that is too lenient inflates results; a judge that is unsatisfiable
invalidates them. We mitigate by asserting judge satisfiability against reference
implementations in the automated test suite, but the risk of subtly mis-specified tasks
remains.

**Confounded controls.** §6.4 documents a claim we published internally and then falsified: a
control that equalized one variable by *mutilating* another produced a null result that read as
confirmation for three measurements. We now require of any control that it be shown not to
disable the mechanism under test, and we verify material-parity with the model's tokenizer
before reading outcomes rather than after.

**Measurement defects, six found in one campaign.** Beyond the benchmark artifacts below, three
further defects were found in our own instrumentation and accounting: a control that mutilated
the variable it was meant to hold constant (§6.4); a fixed run count read as a power calculation
(§5.9.4); and a runtime field recorded as "cache reuse" that was nothing of the kind, leaving the
token budget blind to prefill for the system's entire history (§6.4-septies). **None was visible
in any success rate.** We report the count because it is the honest base rate for a project of
this kind, and because each was found by a different technique — reading artifacts, computing
required sample size, and checking that a derived quantity stayed inside its admissible range.

**Benchmark artifacts — three found, all by reading artifacts rather than scores.** The ladder's
first generation contained a formatting artifact that selectively disadvantaged the treatment
arm (§4.4). Separately, its judge printed the expected value alongside the observed one, so any
run that consulted the checker was handed the answer: for a period, that rung measured the
reading of an error message rather than retrieval and aggregation. Third, in the naked arm the
model intermittently emits chat-template markers as literal text, which the judge captures
inside the value — failing even a *correct* answer, and doing so specifically in the arm
against which our thesis is measured. None of the three was visible in any score. On the base
rate demonstrated by these discoveries, we assume that further such artifacts exist.

**Absence of public benchmarks.** All numbers here are internally comparable but externally
unanchored. Public benchmark runs are planned specifically to place the system on scales
others can read.

---

## 8. Limitations and future work

The system does not yet convert multi-session software-engineering tasks: both arms score 0/3
on the three tasks designed to exceed a single executor session, with or without the plan
compiler, with or without reasoning. This is the project's principal open failure.

**The context budget is now a capability constraint, not a performance one.** Two independent
results converge on it. The hardest rung dies from context exhaustion rather than step budget or
discipline (§5.9.5), and full-budget reasoning solves the aggregation rung outright but cannot
coexist with untruncated material inside 8,192 tokens (§6.4). Context and cache work therefore
acquires a second objective it did not previously have — making room for *reasoning* — and its
central trade-off is measurable rather than assumable: any compaction of older step results buys
window at the cost of the append-only prefix reuse worth 65 tokens against 7,971 (§5.1).

**The principal planned campaign is full-factorial, and the reason is in our own data.** The
2×2 of §6.4-quater shows a lever worth twelve points in one configuration and one point in
another, which means "the value of component X" is not a well-defined quantity in this system.
One-lever-at-a-time ablation — which is what every campaign in this paper used, and what the
literature identifies as its own standing limitation [16] — assigns each component a number that
exists only conditionally on the position of the others. The planned campaign therefore runs
every arm, coding and non-coding, with every ablation lever and every enable-switch in both
positions, on a single commit and on the reference CPU profile. It is expensive (an estimated
~22 hours of CPU wall time) and it is the only design that can produce an attribution table
whose rows are simultaneously true.

Planned work, in order: (i) the official campaign on the reference CPU profile, since every
number in §5 and §6 was obtained on the development GPU and is directionally but not
quantitatively transferable; (ii) the full-factorial campaign described above; (iii) bisection of
the role card, to identify *which* rule group steers tool choice — 414 tokens per call are
provably not free and provably not all necessary; (iv) a properly powered re-judgement of the
calculator and of the finish gate, the latter because its rejection is now known to have been
underpowered rather than negative; (v) the remaining context-and-cache components under the two
objectives above; (vi) adaptive routing by task size and task kind, using two measured rules —
micro-tasks must **not** be planned, and reasoning belongs on wide-retrieval tasks but not on
coding; (vii) re-measurement of all remaining rejected verdicts with routing active and on
non-coding domains, since all were measured on synthetic coding only; (viii) public benchmark
runs, to place the system on scales others can read; and (ix) the real-codebase examination.

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

**The mechanism of conversion is not persuasion.** Across three independent lines of evidence,
telling this model to do something did not make it do it — including when the instruction was
mandatory, carried its own measured rationale, and was repeated in the failure message of the
preceding attempt. What converts is removing the possibility of the error: a write-time
coherence gate takes the aggregation rung from 9/20 to 18/20 (p = 0.0057) while running 37%
faster, on runs where the model typically never performs the arithmetic at all. The model
creates meaning; the control plane creates identity — and a total, being derived, is identity.
The same principle, applied without checking what already absorbed the failure, produced
nothing at all (p = 0.66); we regard that bound as the more transferable half of the result.

**And one contribution is categorically different from the others.** Deterministic
verification does not raise the success rate; it makes the system's statements about itself
true. Measured: 8 false claims in 5 unverified runs, against 1 in over 550 verified ones.
For a system intended to work unattended on hardware its owner already possesses, that is
plausibly the property that matters most — and it is the one an aggregate success metric is
structurally incapable of seeing. It is also the reason we regard the published finding that
verification is worth "+1.5 percentage points" [13] as correct and incomplete: those 1.5 points
are the difference between a system that reports its own state truthfully and one that does not.

**On what is new here, we are deliberately narrow.** A per-mechanism audit against the
literature (§2.3) found prior art for every mechanism in this paper — decomposition of
scaffolding versus verification [13, 14], baselines before architecture [15], prompt-rule
ablation [20], search-over-read retrieval [21–24], false success [25–27], reasoning as
compensation [16, 28–30], and context compaction in a dozen variants [31–38]. We claim none of
them. What we claim is the regime — one ~2B model, four cores, 15 W, everything local, no
frontier model anywhere in the pipeline — together with what the regime yields: numbers under
that constraint, an attribution table built on a single commit from levers designed to be
ablatable, negative results governed by rules written before the data, and a demonstration that
two of these levers substitute for one another so completely that measuring either in isolation
misstates its value. That last point is not a curiosity. It is the reason the next campaign is
full-factorial, and it is the one place where our data speaks to a gap the field has named for
itself.

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

**Decomposition of agent performance: harness, verification, model**

[13] *Where Does Agent Reliability Come From? Decomposing Scaffolding, Verification and Model
Capability*, arXiv:2607.17044 — the closest work to ours; contributions in percentage points
(SpreadsheetBench: structure +9.5pp of 11.0 total, verification +1.5pp), 0.5–3B specialists
driven by a frontier generator, no constrained-hardware inference reported
[14] *Model or Harness? A Taxonomy for Localizing Agent Failures*, arXiv:2607.28802
[15] *Baselines Before Architecture*, arXiv:2607.13085 — architectural claims require properly
tuned baselines; several published scaffolds vanish once the baseline is honest
[16] *More Is Not Always Better: Cross-Component Interference in LLM Agent Scaffolding*,
arXiv:2605.05716 — source of the methodological gap this project aims at: *"previous work uses
one-at-a-time ablation at best, never full factorial designs"*
[17] *Holistic Agent Leaderboard*, arXiv:2510.11977 — harness effects at leaderboard scale
[18] *EffGen: Small Language Models as Capable Autonomous Agents*, arXiv:2602.00887 — documents
small models retrying an identical payload after an API error
[19] *Building AI Coding Agents for the Terminal*, arXiv:2603.05344 — concrete errors
("re-read the file") outperform abstract ones ("system problem")
[20] *RubricRefine*, arXiv:2605.09730 — removal of individual system-prompt rule categories with
per-category impact quantified

**Retrieval strategy: searching versus reading**

[21] *Is Grep All You Need?*, arXiv:2605.15184
[22] *GrepSeek*, arXiv:2605.29307
[23] *Towards Retrieving Interaction Spaces for Agentic Search*, arXiv:2606.06880
[24] *Beyond Semantic Similarity: Direct Corpus Interaction*, arXiv:2605.05242

**False success and the honesty gap**

[25] *From Confident Closing to Silent Failure: Characterizing False Success in LLM Agents*,
arXiv:2606.09863 — names the phenomenon we had independently called `completed ≠ verified`
[26] *Near-Miss: Latent Policy Failure Detection*, arXiv:2603.29665
[27] *Are Your Agents Upward Deceivers?*, arXiv:2512.04864

**Reasoning: conditional value and compensation**

[28] *Select-then-Solve*, arXiv:2604.06753 — the compensation hypothesis: reasoning structure
substitutes for capability gaps
[29] Wei et al., *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*,
arXiv:2201.11903
[30] *Think When Needed*, arXiv:2605.14448 — conditional reasoning; chain-of-thought takes
Qwen3-30B from 18% to 64% and costs GPT-5 fifteen points

**Context compaction and offloading**

[31] *CompactionRL*, arXiv:2607.05378
[32] *Slipstream: Trajectory-Grounded Compaction Validation*, arXiv:2605.08580
[33] *Self-Compacting Language Model Agents*, arXiv:2606.23525
[34] *Parallel Context Compaction*, arXiv:2605.23296
[35] *Addressable Recall Compaction*, arXiv:2607.25066
[36] *Beyond Compaction: Structured Context Eviction*, arXiv:2606.11213
[37] *Code as Agent Harness*, arXiv:2605.18747
[38] Engineering practice on the same problem: Anthropic, *Context engineering* (tool-use
cookbook); LangChain, *Context management for Deep Agents*; Databricks, *Memex: a programmable
scratchpad for LLM agents*; AgentScope context documentation; Arize, *Context management in
agent harnesses*; *Context Offloading* (Agentic Coding Patterns)

**KV cache behaviour and runtime**

[39] *Practical Online KV Cache Compaction*, arXiv:2608.00902; *IntentKV*, arXiv:2606.09916;
*When KV Cache Reuse Fails in Multi-Agent Systems*, arXiv:2601.08343; *KVCOMM*, arXiv:2510.12872
[40] llama.cpp discussion #20574, sliding-window attention and full-cache reuse (`--swa-full`),
with cache-reuse shifting — the mechanism of §6.4-quinquies

**Critics, orchestration, specification**

[41] *Steer, Don't Solve: Training Small Critic Models*, arXiv:2606.21811
[42] *Self-Healing Agentic Orchestrators*, arXiv:2606.01416
[43] *A survey of small language models for agentic systems*, arXiv:2510.03847
[44] *MetaGPT: Meta Programming for Multi-Agent Collaborative Frameworks*, arXiv:2308.00352
(ICLR)
[45] *Test-driven governance in multi-agent code generation*, arXiv:2604.26615; and
*Test-driven agentic development with mutation probes*, arXiv:2603.08806
[46] Spec-driven development toolkits: GitHub *Spec Kit*; AWS *Kiro*

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

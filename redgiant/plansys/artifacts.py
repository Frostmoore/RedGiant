"""Artefatti del plansys (PS0.1, contratto §PS-A2 del piano).

PS-D2: prima gli artefatti, poi i prompt. Ogni oggetto scambiato tra ruoli e'
uno di questi modelli, persistito e versionato in ps_artifacts; i limiti
(max_length/max_items) sono il contratto di grammatica (D21 del piano padre).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from redgiant.core.verify import CheckResult


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── S: il MacroPlan ──────────────────────────────────────────────────────────

class Criterion(_Strict):
    """Prodotto da S; immutabile. Un criterio globale osservabile (C1..C8)."""
    id: str
    text: str = Field(max_length=200)


class MacroPhase(_Strict):
    """Prodotto da S; immutabile. Una macrofase: intento, mai operazioni."""
    id: str
    title: str = Field(max_length=80)
    intent: str = Field(max_length=300)
    depends_on: list[str] = Field(max_length=5)
    covers: list[str] = Field(min_length=1, max_length=8)


class MacroPlan(_Strict):
    """Prodotto da S una volta per task; solo S via replan versionato (fuori v1)."""
    goal: str = Field(max_length=300)
    criteria: list[Criterion] = Field(min_length=1, max_length=8)
    phases: list[MacroPhase] = Field(min_length=1, max_length=6)


# ── M1: analisi di fase ──────────────────────────────────────────────────────

class DesignDecision(_Strict):
    """Prodotta da M1; modificabile solo via BlueprintPatch. PS-D8: esplicita."""
    id: str
    decision: str = Field(max_length=200)
    alternatives: list[str] = Field(max_length=3)
    constraint: str = Field(max_length=200)


class ChoicePoint(_Strict):
    """Prodotto da M1 quando la scelta non e' determinata: il control plane
    la instrada sul canale clarification (PS-D8), mai inventata in silenzio."""
    question: str = Field(max_length=200)
    options: list[str] = Field(min_length=2, max_length=3)
    recommended: str = Field(max_length=80)
    reason: str = Field(max_length=200)


class PhaseAnalysis(_Strict):
    """Prodotta da M1; modificabile da M via patch."""
    phase_id: str
    objective: str = Field(max_length=300)
    involved: list[str] = Field(max_length=10)
    artifacts: list[str] = Field(max_length=10)
    decisions: list[DesignDecision] = Field(max_length=4)
    risks: list[str] = Field(max_length=4)
    decision_required: ChoicePoint | None = None


# ── M2: decomposizione ───────────────────────────────────────────────────────

class WorkContract(_Strict):
    """PS-D4: il contratto di lavoro. Immutabile per J."""
    goal: str = Field(max_length=300)
    boundary: str = Field(max_length=300)
    files_owned: list[str] = Field(min_length=1, max_length=4)
    signatures: list[str] = Field(max_length=6)
    inputs: list[str] = Field(max_length=6)
    outputs: list[str] = Field(max_length=4)


class MicroPhase(_Strict):
    """Prodotta da M2; modificabile da M via patch fino alla qualificazione."""
    id: str
    title: str = Field(max_length=80)
    work: WorkContract
    proves: list[str] = Field(max_length=4)


class PhaseBlueprint(_Strict):
    phase_id: str
    micro: list[MicroPhase] = Field(min_length=1, max_length=6)


# ── M3: design della verifica ────────────────────────────────────────────────

class ProofObligation(_Strict):
    """PS-D4: il contratto di prova. Immutabile per J dopo la qualificazione."""
    id: str
    micro_id: str
    kind: Literal["new_behavior", "characterization"]
    behavior: str = Field(max_length=300)
    test_file: str
    test_name: str
    cmd_id: str


class VerificationBlueprint(_Strict):
    phase_id: str
    obligations: list[ProofObligation] = Field(min_length=1, max_length=12)
    synthesis_cmds: list[str] = Field(min_length=1, max_length=3)


# ── M4: stesura test ─────────────────────────────────────────────────────────

class TestArtifact(_Strict):
    """Prodotto da M4; materializzato dal CONTROL PLANE (Scope+syntax gate),
    mai da J. Immutabile dopo la qualificazione dell'oracolo."""
    path: str
    content: str


class TestBundle(_Strict):
    phase_id: str
    artifacts: list[TestArtifact] = Field(min_length=1, max_length=8)


# ── Correzioni (PS-D6: patch, mai rigenerazione) ─────────────────────────────

class PatchOp(_Strict):
    op: Literal["replace", "add", "remove"]
    target: str
    # NIENTE max_length: maxLength=4000 diventa una ripetizione GBNF {0,4000}
    # che llama-server rifiuta con 400 (smoke PS4.3). Il tetto vero e' il
    # budget di generazione della chiamata.
    payload_json: str


class BlueprintPatch(_Strict):
    phase_id: str
    ops: list[PatchOp] = Field(min_length=1, max_length=6)


# ── Gate (prodotti dal control plane, mai dal modello) ───────────────────────

class GateReport(_Strict):
    gate: Literal["macro_validation", "phase_entry", "oracle_qualification",
                  "micro", "phase_synthesis", "plan_coverage", "retry"]
    target: str
    ok: bool
    checks: list[CheckResult]

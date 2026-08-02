"""Renderer deterministico DB -> Markdown greppabile (PS0.3).

Il DB e' la fonte di verita'; questi file sono VISTE per umani e per il
modello piccolo (che le naviga coi tool come un grep). Struttura FISSA:
gli id sono le intestazioni, mai contenuto libero del modello nei titoli.
Niente timestamp: due render dello stesso artefatto sono byte-identici.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from redgiant.plansys.artifacts import (MacroPlan, PhaseAnalysis, PhaseBlueprint,
                                        VerificationBlueprint)


def render_macro_plan(plan: MacroPlan) -> str:
    out: list[str] = [f"# Macro Plan — {plan.goal}", "", "## Criteria", ""]
    for c in plan.criteria:
        out.append(f"- [ ] {c.id}: {c.text}")
    for p in plan.phases:
        out += ["", f"## {p.id} — {p.title}", "",
                f"**Intent:** {p.intent}",
                f"**Depends on:** {', '.join(p.depends_on) if p.depends_on else '—'}",
                f"**Covers:** {', '.join(p.covers)}"]
    return "\n".join(out) + "\n"


def render_blueprint(bp: PhaseBlueprint, vbp: VerificationBlueprint | None,
                     analysis: PhaseAnalysis | None) -> str:
    out: list[str] = [f"# {bp.phase_id} — Blueprint", ""]
    if analysis is not None:
        out += ["## Context", "", f"**Objective:** {analysis.objective}"]
        if analysis.involved:
            out.append(f"**Involved:** {', '.join(analysis.involved)}")
        if analysis.artifacts:
            out.append(f"**Artifacts:** {', '.join(analysis.artifacts)}")
        if analysis.decisions:
            out += ["", "**Decisions:**"]
            for d in analysis.decisions:
                alts = f"; alternatives: {', '.join(d.alternatives)}" if d.alternatives else ""
                out.append(f"- {d.id}: {d.decision} (constraint: {d.constraint}{alts})")
        if analysis.risks:
            out += ["", "**Risks:**"] + [f"- {r}" for r in analysis.risks]
        out.append("")
    for m in bp.micro:
        out += [f"## {m.id} — {m.title}", "",
                f"**Work:** {m.work.goal}",
                f"**Boundary:** {m.work.boundary}",
                f"**Files owned:** {', '.join(m.work.files_owned)}"]
        if m.work.signatures:
            out.append(f"**Signatures:** {'; '.join(m.work.signatures)}")
        if m.work.inputs:
            out.append(f"**Inputs:** {', '.join(m.work.inputs)}")
        if m.work.outputs:
            out.append(f"**Outputs:** {', '.join(m.work.outputs)}")
        if m.proves:
            out.append(f"**Proves:** {', '.join(m.proves)}")
        if vbp is not None:
            obs = [o for o in vbp.obligations if o.micro_id == m.id]
            if obs:
                out += ["", "**Proof:**"]
                for o in obs:
                    out.append(f"- {o.id} [{o.kind}] {o.behavior} -> "
                               f"{o.test_file}::{o.test_name} (cmd: {o.cmd_id})")
        out.append("")
    if vbp is not None:
        out += ["## Verification", "",
                f"**Synthesis:** {', '.join(vbp.synthesis_cmds)}", ""]
    return "\n".join(out)


def write_plan_doc(tasks_dir: Path, task_id: str, name: str, content: str) -> Path:
    """Scrittura atomica (tmp+replace), LF, in data/tasks/<id>/plan/<name>.md."""
    plan_dir = tasks_dir / task_id / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    dest = plan_dir / f"{name}.md"
    fd, tmp = tempfile.mkstemp(dir=plan_dir, suffix=".rgrender")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.replace(tmp, dest)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return dest

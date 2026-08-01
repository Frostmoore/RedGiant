"""F1.3 — la convenzione S1→S7: stabilità dei prefissi (D9), ordine, append-only."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from redgiant.prompts.assemble import PromptAssembler, PromptParts
from redgiant.state.models import Budget, BudgetUsed, TaskState

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "redgiant" / "prompts"


class _FakeArgs(BaseModel):
    path: str
    limit: int = 10


class _FakeTool:
    name = "read_file"
    description = "Read a file slice."
    input_model = _FakeArgs


def _task() -> TaskState:
    return TaskState(id="T", request="fix the bug", target_dir="/x", domain="coding",
                     status="running", plan=None, current_phase=None, current_subtask=None,
                     budget=Budget(max_total_tokens=1, max_tool_calls=1,
                                   max_retries_per_subtask=1, max_wall_s=1),
                     used=BudgetUsed())


@pytest.fixture()
def asm() -> PromptAssembler:
    return PromptAssembler(PROMPTS_DIR)


def test_static_prefix_is_byte_identical_across_builds(asm):
    a = asm.build("worker", task=_task(), subtask=None, tools=[_FakeTool()], volatile="v1")
    b = asm.build("worker", task=_task(), subtask=None, tools=[_FakeTool()], volatile="ALTRO")
    ra, rb = a.render(), b.render()
    n = a.static_prefix_len()
    assert ra[:n] == rb[:n]
    assert n > 100  # il prefisso stabile esiste davvero


def test_section_order_and_turn_markers(asm):
    r = asm.build("worker", task=_task(), subtask=None, tools=[], volatile="c").render()
    assert r.startswith("<start_of_turn>user\n")
    assert r.endswith("\n<end_of_turn>\n<start_of_turn>model\n")
    pos = [r.index(f"### {s}") for s in
           ("PREAMBLE", "ROLE", "TOOLS", "TASK", "STATE", "CONTEXT", "OUTPUT")]
    assert pos == sorted(pos)


def test_append_only_preserves_prefix(asm):
    p1 = asm.build("worker", task=_task(), subtask=None, tools=[], volatile="step1")
    p2 = p1.with_appended_context("\n[STEP 1 RESULT] ok")
    r1, r2 = p1.render(), p2.render()
    # il prefisso comune arriva fino alla FINE del vecchio volatile: e' la
    # proprieta' che la KV cache sfrutta (D20); il tail S7 si ripaga (per questo e' corto)
    cut = r1.index("step1") + len("step1")
    assert r2[:cut] == r1[:cut]
    assert "[STEP 1 RESULT] ok" in r2


def test_output_schema_lands_in_role_card_not_in_tail(asm):
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    p = asm.build("worker", task=_task(), subtask=None, tools=[], volatile="c",
                  output_schema=schema, schema_name="X")
    assert '"properties"' in p.role_card       # S2: cachata
    assert '"properties"' not in p.output_instruction  # S7 resta corta
    assert "schema X" in p.output_instruction


def test_unknown_role_raises(asm):
    with pytest.raises(KeyError):
        asm.build("nope", task=_task(), subtask=None, tools=[], volatile="")


def test_empty_tools_section_still_present(asm):
    p = asm.build("worker", task=_task(), subtask=None, tools=[], volatile="")
    assert "No tools available" in p.tool_card
    assert "### TOOLS" in p.render()  # la sezione c'è sempre: la forma non è condizionale

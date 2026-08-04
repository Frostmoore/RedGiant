"""PromptAssembler: la convenzione S1→S7 (piano §A4, D9, D13, D20).

Regole cablate qui e in nessun altro posto:
- ordine fisso S1→S7, separatori byte-stabili;
- parti statiche (S1–S4) MAI con contenuto volatile;
- template di turno Gemma sempre presente (lezione F0.3);
- lo schema di output completo vive nella card di ruolo (S2, statica → cachata);
  S7 resta corto perché sta DOPO il contesto volatile e si ripaga a ogni step.

Nessun ruolo concatena prompt per conto suo: si passa da build().
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence

from redgiant.state.models import SubtaskSpec, TaskState

if TYPE_CHECKING:  # solo per i tipi: il modulo tools importa questo a runtime? no, viceversa
    from redgiant.tools.base import ToolSpec

_SECTION_NAMES = ("PREAMBLE", "ROLE", "TOOLS", "TASK", "STATE", "CONTEXT", "OUTPUT")
_TURN_OPEN = "<start_of_turn>user\n"
_TURN_CLOSE = "\n<end_of_turn>\n<start_of_turn>model\n"


@dataclass(frozen=True)
class PromptParts:
    preamble: str
    role_card: str
    tool_card: str
    task_header: str
    durable_state: str
    volatile_context: str
    output_instruction: str

    def _sections(self) -> tuple[tuple[str, str], ...]:
        return tuple(zip(_SECTION_NAMES, (
            self.preamble, self.role_card, self.tool_card, self.task_header,
            self.durable_state, self.volatile_context, self.output_instruction)))

    def render(self) -> str:
        body = "\n\n".join(f"### {name}\n\n{content}" for name, content in self._sections())
        return _TURN_OPEN + body + _TURN_CLOSE

    def section_tokens(self, counter: Callable[[str], int]) -> dict[str, int]:
        return {name: counter(content) for name, content in self._sections()}

    def static_prefix_len(self) -> int:
        """Byte del prefisso stabile (turn marker + S1–S4): base della metrica di riuso."""
        stable = "\n\n".join(f"### {name}\n\n{content}"
                             for name, content in self._sections()[:4])
        return len(_TURN_OPEN + stable)

    def with_appended_context(self, block: str) -> "PromptParts":
        """Append-only su S6 (D20): tutto il resto resta byte-identico."""
        return self.with_volatile(self.volatile_context + block)

    def with_volatile(self, volatile: str) -> "PromptParts":
        """Sostituisce S6 per intero — le altre sezioni restano byte-identiche.

        Serve alla compattazione di F5.0-bis: riscrivere la catena volatile
        ROMPE l'append-only di D20, ed e' l'unico punto del sistema autorizzato
        a farlo. Il costo del cambio a meta' prompt e' misurato (F5.0-ante,
        `data.md` §7.11): **1 token** riprocessato con `--swa-full
        --cache-reuse`, **2.748** senza. Per questo la compattazione va fatta
        A ONDATE e non a ogni passo: dove i flag non ci sono, ogni ondata si
        ripaga il prefisso una volta sola invece che sempre.
        """
        return PromptParts(
            preamble=self.preamble, role_card=self.role_card, tool_card=self.tool_card,
            task_header=self.task_header, durable_state=self.durable_state,
            volatile_context=volatile,
            output_instruction=self.output_instruction)


class PromptAssembler:
    def __init__(self, prompts_dir: Path) -> None:
        self._preamble = (prompts_dir / "preamble.md").read_text(encoding="utf-8").strip()
        self._cards: dict[str, str] = {}
        roles_dir = prompts_dir / "roles"
        for card in sorted(roles_dir.glob("*.md")):
            self._cards[card.stem] = card.read_text(encoding="utf-8").strip()
        if not self._cards:
            raise FileNotFoundError(f"no role cards in {roles_dir}")

    def build(self, role: str, *, task: TaskState, subtask: SubtaskSpec | None,
              tools: Sequence["ToolSpec"], volatile: str,
              output_schema: dict | None = None, schema_name: str | None = None) -> PromptParts:
        if role not in self._cards:
            raise KeyError(f"no role card for '{role}'")
        role_card = self._cards[role]
        if output_schema is not None:
            # Lezione F0.3: la grammatica vincola ma non informa — lo schema DEVE
            # essere visibile. Sta in S2 (statica per ruolo) così la KV la cachea.
            role_card += ("\n\nOutput JSON Schema (follow it exactly, fill every field "
                          "with real, meaningful content - never placeholders):\n"
                          + json.dumps(output_schema, sort_keys=True))
        return PromptParts(
            preamble=self._preamble,
            role_card=role_card,
            tool_card=self._tool_card(tools),
            task_header=self._task_header(task),
            durable_state=self._durable_state(task),
            volatile_context=volatile,
            output_instruction=(
                f"Emit exactly one compact single-line JSON object matching schema "
                f"{schema_name or 'described in ROLE'}. No other text."),
        )

    @staticmethod
    def _tool_card(tools: Sequence["ToolSpec"]) -> str:
        if not tools:
            return "No tools available for this role."
        lines = []
        for t in sorted(tools, key=lambda t: t.name):  # ordine stabile (D9)
            schema = t.input_model.model_json_schema()
            props = ", ".join(schema.get("properties", {}).keys())
            lines.append(f"- {t.name}({props}): {t.description}")
        return "\n".join(lines)

    @staticmethod
    def _task_header(task: TaskState) -> str:
        # SOLO campi stabili per l'intera vita del task (D9): niente stato, niente esiti.
        return (f'User request: "{task.request}"\n'
                f"Domain: {task.domain}\nTarget directory: {task.target_dir}")

    @staticmethod
    def _durable_state(task: TaskState) -> str:
        if task.plan is None:
            return "No plan (single-subtask execution)."
        lines = [f"Plan v{task.plan.version} - goal: {task.plan.goal}"]
        for ph in task.plan.phases:
            marker = "current" if ph.id == task.current_phase else "listed"
            lines.append(f"- {ph.id} [{marker}]: {ph.title}")
        return "\n".join(lines)

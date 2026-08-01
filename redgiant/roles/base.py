"""Base dei ruoli cognitivi (piano F1.5).

Un ruolo = una configurazione (card + schema + tool autorizzati), non un
processo (specsheet §25.2). Ogni intelligenza che si è tentati di aggiungere a
un ruolo appartiene a un altro ruolo o a nessuno.
"""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redgiant.llm.client import LlamaClient
from redgiant.prompts.assemble import PromptAssembler
from redgiant.state.models import SubtaskSpec, TaskState
from redgiant.tools.router import ToolRouter


class RoleContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: TaskState
    subtask: SubtaskSpec | None
    volatile: str


class Role(ABC):
    name: ClassVar[str]
    output_model: ClassVar[type[BaseModel]]

    def __init__(self, llm: LlamaClient, assembler: PromptAssembler,
                 router: ToolRouter) -> None:
        self.llm = llm
        self.assembler = assembler
        self.router = router

"""BudgetTracker (piano F1.7): conteggio e stop duro. Il Manager completo arriva in F4.5.

I contatori non vivono in RAM: si leggono dal DB (una sola fonte di verita').
Il wall clock parte dal created_at del task, cosi' sopravvive alle riprese.
"""

from __future__ import annotations

from datetime import datetime, timezone

from redgiant.llm.client import LlmResult
from redgiant.state.models import Budget, BudgetUsed
from redgiant.state.store import StateStore


class BudgetTracker:
    def __init__(self, store: StateStore, budget: Budget, task_id: str) -> None:
        self.store = store
        self.budget = budget
        self.task_id = task_id

    def charge_llm(self, r: LlmResult) -> None:
        # la riga llm_calls e' gia' scritta dal client: qui non si duplica nulla
        pass

    def charge_tool(self) -> None:
        # idem: tool_calls scritta dal router
        pass

    def used(self) -> BudgetUsed:
        u = self.store.budget_used(self.task_id)
        created = next((t["created_at"] for t in self.store.list_tasks(1000)
                        if t["id"] == self.task_id), None)
        wall = 0.0
        if created:
            wall = (datetime.now(timezone.utc)
                    - datetime.fromisoformat(created)).total_seconds()
        return BudgetUsed(tokens=u.tokens, tool_calls=u.tool_calls, wall_s=wall)

    def exceeded(self) -> str | None:
        u = self.used()
        if u.tokens > self.budget.max_total_tokens:
            return "tokens"
        if u.tool_calls > self.budget.max_tool_calls:
            return "tool_calls"
        if u.wall_s > self.budget.max_wall_s:
            return "wall_s"
        return None

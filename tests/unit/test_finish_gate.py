"""LAD.9 — gate sul finish dentro il loop (il "finish fantasma").

Misura che lo motiva (data.md §7.6.5): 31 tentativi su 78 (40%) dichiaravano
`done` senza aver chiamato nessuno strumento di scrittura, ripetendo l'errore
anche col `FAIL: answer.txt missing` del giudice riportato nel tentativo dopo.

I test coprono le due condizioni del gate, il fatto che NON morda dove la
regola 11 della card autorizza a chiudere (test rossi fuori dal perimetro), il
tetto ai rifiuti e l'ablazione.
"""

from pathlib import Path

import pytest

from redgiant.config import Config
from redgiant.roles.worker import _MAX_FINISH_REFUSALS, Worker
from redgiant.state.models import Budget, SubtaskSpec
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter, default_catalog

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _spec(**kw) -> SubtaskSpec:
    base = dict(id="P1.S1", phase_id="P1", title="t", objective="o", inputs=[],
                tools=[], expected_outputs=[], completion_criteria=[],
                verification=[])
    base.update(kw)
    return SubtaskSpec(**base)


class _Ctx:
    def __init__(self, subtask, task=None):
        self.subtask = subtask
        self.task = task
        self.volatile = ""


@pytest.fixture
def worker(tmp_path, monkeypatch):
    monkeypatch.delenv("RG_WORKER_ABLATE", raising=False)
    cfg = Config.load("dev-fast", CONFIG_DIR)
    scope = Scope(tmp_path, ["*.txt"])
    store = StateStore(tmp_path / "t.db")
    cmds = {"check": ["python", str(tmp_path / "judge.py")]}
    router = ToolRouter(default_catalog(cfg, scope, cmds), scope, store)
    w = Worker.__new__(Worker)          # niente llm/assembler: si testa il gate
    w.router = router
    tid = store.create_task("r", str(tmp_path), "dev-fast", Budget(
        max_total_tokens=100, max_tool_calls=10, max_retries_per_subtask=1,
        max_wall_s=60))
    return w, tid, tmp_path


def test_promised_output_missing_is_refused(worker):
    w, tid, root = worker
    spec = _spec(expected_outputs=["answer.txt"])
    msg = w._finish_gate(_Ctx(spec), tid, mutated=False)
    assert msg is not None and "do NOT exist on disk" in msg
    (root / "answer.txt").write_text("x", encoding="utf-8")
    assert w._finish_gate(_Ctx(spec), tid, mutated=False) is None


def test_phantom_finish_signature_is_refused(worker):
    """Nessuna mutazione + oracolo rosso = il caso logicamente impossibile."""
    w, tid, root = worker
    (root / "judge.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.exit(0 if Path('answer.txt').is_file() else "
        "(print('FAIL: answer.txt missing') or 1))\n", encoding="utf-8")
    spec = _spec(verification=["check"])
    msg = w._finish_gate(_Ctx(spec), tid, mutated=False)
    assert msg is not None
    assert "never wrote, edited or patched any file" in msg
    assert "FAIL: answer.txt missing" in msg      # l'uscita REALE dell'oracolo
    assert "Describing an action does not perform it" in msg


def test_gate_does_not_fire_when_the_worker_actually_wrote(worker):
    """Regola 11 della card: test rossi FUORI dal perimetro non devono
    intrappolare chi ha davvero lavorato. Se ha mutato, il gate tace e decide
    la verifica esterna (D10)."""
    w, tid, root = worker
    (root / "judge.py").write_text("import sys; sys.exit(1)\n", encoding="utf-8")
    spec = _spec(verification=["check"])
    assert w._finish_gate(_Ctx(spec), tid, mutated=True) is None


def test_green_oracle_passes_even_without_mutation(worker):
    w, tid, root = worker
    (root / "judge.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")
    assert w._finish_gate(_Ctx(_spec(verification=["check"])), tid,
                          mutated=False) is None


def test_unknown_check_is_not_run_by_the_gate(worker):
    """Un check non registrato non e' eseguibile: lo tratta verify.py (che lo
    fa fallire), non il gate — che non deve inventarsi oracoli."""
    w, tid, _ = worker
    assert w._finish_gate(_Ctx(_spec(verification=["nope"])), tid,
                          mutated=False) is None


def test_no_subtask_no_gate(worker):
    w, tid, _ = worker
    assert w._finish_gate(_Ctx(None), tid, mutated=False) is None


def test_gate_is_ablatable_and_capped():
    """Le due valvole di sicurezza: la leva di ablazione esiste (attribuzione)
    e il tetto ai rifiuti impedisce di sostituire un loop degenere con un
    altro."""
    import os

    from redgiant.core.ablate import worker_ablated
    os.environ["RG_WORKER_ABLATE"] = "finishgate"
    try:
        assert worker_ablated("finishgate")
    finally:
        os.environ.pop("RG_WORKER_ABLATE")
    assert not worker_ablated("finishgate")
    assert _MAX_FINISH_REFUSALS == 2


def test_ablation_arms_are_registered():
    """Regola di metodo: ogni componente nasce col suo braccio in B2 E in B4."""
    p = Path(__file__).resolve().parents[2] / "bench" / "ladder" / "run_agentic.py"
    src = p.read_text(encoding="utf-8")
    assert '"-finishgate": ("finishgate", "")' in src
    assert '"think-finishgate": ("finishgate", "worker")' in src
    b2 = next(l for l in src.splitlines() if l.startswith("B2 = ["))
    b4 = src.split("\nB4 = [")[1].split("]")[0]
    assert '"-finishgate"' in b2 and '"think-finishgate"' in b4

"""PhaseCompiler (PS3.3/PS4): la pipeline di compilazione M1->M4.

PS-D3: quattro invocazioni dello stesso modello con schemi piccoli, validate
deterministicamente tra un passo e l'altro. PS-D6: le correzioni sono PATCH
tipizzate dell'artefatto (max 2 per passo, poi 1 rigenerazione, poi
CompileFailed esplicito) — mai rigenerazioni a raffica.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from redgiant.config import Config
from redgiant.llm.client import LlamaClient
from redgiant.plansys.artifacts import (BlueprintPatch, ChoicePoint, MacroPhase,
                                        MacroPlan, PhaseAnalysis, PhaseBlueprint,
                                        TestBundle, VerificationBlueprint)
from redgiant.plansys.gates import (_TEST_FILE, oracle_qualification_gate,
                                    validate_analysis, validate_blueprint,
                                    validate_bundle, validate_verification)
from redgiant.plansys.ledger import build_ledger, project_for_phase, render_ledger
from redgiant.plansys.render import render_blueprint, write_plan_doc
from redgiant.plansys.roles import (PhaseAnalyst, TestAuthor,
                                    VerificationDesigner, WorkDecomposer)
from redgiant.prompts.assemble import PromptAssembler
from redgiant.roles.base import RoleContext
from redgiant.state.store import StateStore
from redgiant.tools.base import Scope
from redgiant.tools.router import ToolRouter

_MAX_PATCHES = 2  # per passo; poi 1 rigenerazione intera, poi CompileFailed


class CompileFailed(Exception):
    def __init__(self, step: str, problems: list[str]) -> None:
        self.step = step
        self.problems = problems
        super().__init__(f"{step}: " + "; ".join(problems))


class PhaseAlreadySatisfied(Exception):
    """Pilota PS5: se TUTTE le prove new_behavior di una fase sono GIA' verdi
    prima di J, la fase e' gia' soddisfatta (fase-ridondante scoperta
    post-compile) — si chiude a costo zero, come l'entry gate."""

    def __init__(self, phase_id: str) -> None:
        self.phase_id = phase_id
        super().__init__(phase_id)


class NeedsDecision(Exception):
    """PS-D8: M1 ha emesso decision_required — il chiamante instrada la
    clarification sul canale approvals esistente e sospende la compilazione."""

    def __init__(self, phase_id: str, choice: ChoicePoint) -> None:
        self.phase_id = phase_id
        self.choice = choice
        super().__init__(f"{phase_id}: {choice.question}")


# Le liste patchabili di ogni artefatto: (chiave lista, chiave identita')
_PATCHABLE: dict[str, tuple[str, str]] = {
    "PhaseAnalysis": ("decisions", "id"),
    "PhaseBlueprint": ("micro", "id"),
    "VerificationBlueprint": ("obligations", "id"),
    "TestBundle": ("artifacts", "path"),
}


class PhaseCompiler:
    def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient,
                 assembler: PromptAssembler, router: ToolRouter,
                 scope: Scope) -> None:
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.assembler = assembler
        self.router = router
        self.scope = scope

    # ── passi M1/M2 (PS3; M3/M4 in PS4) ─────────────────────────────────────

    def projection(self, task_id: str, plan: MacroPlan, phase: MacroPhase) -> str:
        from redgiant.plansys import ablated
        if ablated("ledger"):
            # ablation B2: listato grezzo al posto della proiezione del ledger
            files = [p.relative_to(self.scope.root).as_posix()
                     for p in sorted(self.scope.root.rglob("*"))
                     if p.is_file()][:40]
            crit = {c.id: c.text for c in plan.criteria}
            proj = "\n".join(
                [f"[PHASE] {phase.id} — {phase.title}: {phase.intent}"]
                + [f"[CRITERION] {cid}: {crit[cid]}" for cid in phase.covers
                   if cid in crit]
                + [f"[FILE] {f}" for f in files])
        else:
            ledger = build_ledger(self.store, self.scope, task_id)
            write_plan_doc(self.cfg.paths.tasks_dir, task_id, "ledger",
                           render_ledger(ledger))
            proj = project_for_phase(ledger, plan, phase.id,
                                     self.cfg.plansys.projection_max_tokens,
                                     self.llm.count_tokens)
        answer = self.store.latest_clarification_answer(task_id)
        if answer:
            proj += f"\n[USER ANSWER] {answer}"
        return proj

    def _existing_files(self) -> list[str]:
        # batch n.5: la tasks_dir (log, plan renderizzati, ULID) puo' vivere
        # DENTRO la workdir — va ESCLUSA o inquina i prompt E li rende diversi
        # a ogni run (varianza selvaggia a parita' di seed)
        try:
            tasks_rel = self.cfg.paths.tasks_dir.resolve().relative_to(
                self.scope.root.resolve()).as_posix()
        except ValueError:
            tasks_rel = None
        out: list[str] = []
        for p in sorted(self.scope.root.rglob("*")):
            if not p.is_file() or ".git" in p.parts or p.suffix in (
                    ".db", ".rgedit", ".rgwrite"):
                continue
            rel = p.relative_to(self.scope.root).as_posix()
            if tasks_rel and (rel == tasks_rel or rel.startswith(tasks_rel + "/")):
                continue
            out.append(rel)
            if len(out) >= 60:
                break
        return out

    def analyze(self, task_id: str, plan: MacroPlan, phase: MacroPhase,
                projection: str, log) -> PhaseAnalysis:
        state = self.store.load_task(task_id)
        existing = self._existing_files()
        volatile = (f"{projection}\n[MACRO PHASE] {phase.id} — {phase.title}: "
                    f"{phase.intent} (covers: {', '.join(phase.covers)})"
                    f"\n[ALLOWED involved] only these existing files: "
                    f"{', '.join(existing) or '(repo empty: leave involved [])'}")
        ctx = RoleContext(task=state, subtask=None, volatile=volatile)
        role = PhaseAnalyst(self.llm, self.assembler, self.router)
        grammar = self._enum_schema(PhaseAnalysis,
                                    [(None, "involved", existing, True)])

        def _norm_paths(a: PhaseAnalysis) -> PhaseAnalysis:
            a.artifacts = [self._relativize(f) for f in a.artifacts]
            a.involved = [self._relativize(f) for f in a.involved]
            return a

        out: PhaseAnalysis = role.run(
            ctx, max_tokens=self.cfg.plansys.m_pass_max_tokens,
            grammar_schema=grammar)  # type: ignore
        out = self._repair_loop(
            "M1", role, ctx, out, PhaseAnalysis,
            lambda a: validate_analysis(_norm_paths(a), volatile, phase.id), log,
            grammar_schema=grammar)
        if out.decision_required is not None:
            self.store.save_ps_artifact(
                task_id, kind="phase_analysis", ref=phase.id,
                payload_json=out.model_dump_json(), actor="phase_compiler")
            raise NeedsDecision(phase.id, out.decision_required)
        self.store.save_ps_artifact(task_id, kind="phase_analysis", ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M1: {len(out.decisions)} decisioni, "
                             f"{len(out.artifacts)} artefatti")
        return out

    def decompose(self, task_id: str, phase: MacroPhase, analysis: PhaseAnalysis,
                  projection: str, log) -> PhaseBlueprint:
        state = self.store.load_task(task_id)
        allowed_files = sorted(set(self._existing_files())
                               | set(analysis.artifacts)
                               | set(analysis.involved))
        allowed_files = [f for f in allowed_files
                         if not f.rsplit("/", 1)[-1].startswith("test_")]
        volatile = (f"{projection}\n[ANALYSIS] {analysis.model_dump_json()}"
                    f"\n[ALLOWED files_owned/inputs/outputs] "
                    f"{', '.join(allowed_files)}"
                    f"\n[ALLOWED proves] {', '.join(phase.covers)}")
        ctx = RoleContext(task=state, subtask=None, volatile=volatile)
        role = WorkDecomposer(self.llm, self.assembler, self.router)
        grammar = self._enum_schema(PhaseBlueprint, [
            ("WorkContract", "files_owned", allowed_files, True),
            ("WorkContract", "inputs", allowed_files, True),
            ("WorkContract", "outputs", allowed_files, True),
            ("MicroPhase", "proves", list(phase.covers), True)])

        def _norm(b: PhaseBlueprint) -> PhaseBlueprint:
            # Smoke PS4.3: M2 inventa criteri mai esistiti (C3/C4 su un piano
            # C1-C2). Un id che non e' nel piano e' rumore inequivoco:
            # riparazione deterministica, non un giro di patch.
            for m in b.micro:
                m.proves = [c for c in m.proves if c in phase.covers]
                m.work.files_owned = [self._relativize(f)
                                      for f in m.work.files_owned]
                m.work.inputs = [self._relativize(f) for f in m.work.inputs]
                m.work.outputs = [self._relativize(f) for f in m.work.outputs]
            # batch n.3 (PS-D11): AUTO-SPLIT — una micro che crea N file nuovi
            # viene divisa dal control plane in N micro (un file nuovo l'una):
            # la STRUTTURA e' identita', non significato. La patch non sa
            # "dividere"; il codice si'.
            existing_set = set(self._existing_files())
            split: list = []
            for m in b.micro:
                new_files = [f for f in m.work.files_owned
                             if f not in existing_set]
                if len(new_files) <= 1:
                    split.append(m)
                    continue
                olds = [f for f in m.work.files_owned if f in existing_set]
                for i, nf in enumerate(new_files):
                    clone = m.model_copy(deep=True)
                    clone.work.files_owned = ([*olds, nf] if i == 0 else [nf])
                    keep = set(clone.work.files_owned)
                    clone.work.outputs = ([o for o in clone.work.outputs
                                           if o in keep] or [nf])
                    clone.title = f"{m.title} ({nf})"[:80]
                    split.append(clone)
            # batch n.3: DEDUP di ownership — un file conteso resta alla PRIMA
            # micro; le successive lo perdono; micro svuotate -> eliminate
            seen_files: set[str] = set()
            deduped: list = []
            for m in split:
                # batch n.4: dedup anche DENTRO la lista (files_owned poteva
                # contenere lo stesso file due volte nella stessa micro)
                m.work.files_owned = list(dict.fromkeys(
                    f for f in m.work.files_owned if f not in seen_files))
                seen_files.update(m.work.files_owned)
                if m.work.files_owned:
                    deduped.append(m)
            b.micro = deduped[:6]
            # PS5.5 tentativo 1: M2 ordina le micro col deposito INVERTITO
            # (storage.py prima di models.py) e J sbatte sullo scope. L'ordine
            # e' struttura, quindi identita': sort topologico inputs->owner.
            owner = {f: i for i, m in enumerate(b.micro)
                     for f in m.work.files_owned}
            deps = {i: {owner[f] for f in m.work.inputs
                        if f in owner and owner[f] != i}
                    for i, m in enumerate(b.micro)}
            ordered: list[int] = []
            while len(ordered) < len(b.micro):
                free = [i for i in range(len(b.micro))
                        if i not in ordered and deps[i] <= set(ordered)]
                if not free:
                    break  # ciclo: si lascia l'ordine del modello
                ordered.extend(free)
            if len(ordered) == len(b.micro):
                b.micro = [b.micro[i] for i in ordered]
            # id ri-numerati dal control plane (identita' canonica)
            for i, m in enumerate(b.micro, 1):
                m.id = f"{phase.id}.S{i}"
            # fast #6: con UNA sola micro l'assegnazione dei criteri orfani e'
            # INEQUIVOCA (possono andare solo li'): riparazione deterministica.
            # Con piu' micro resta una scelta di design -> violazione a M2.
            if len(b.micro) == 1:
                only = b.micro[0]
                for c in dict.fromkeys(phase.covers):
                    if c not in only.proves and len(only.proves) < 8:
                        only.proves.append(c)
            return b

        existing = {p.relative_to(self.scope.root).as_posix()
                    for p in self.scope.root.rglob("*.py") if p.is_file()}
        out: PhaseBlueprint = role.run(
            ctx, max_tokens=self.cfg.plansys.m_pass_max_tokens,
            grammar_schema=grammar)  # type: ignore
        out = self._repair_loop(
            "M2", role, ctx, out, PhaseBlueprint,
            lambda b: validate_blueprint(_norm(b), analysis, phase.covers,
                                         existing), log,
            grammar_schema=grammar)
        self.store.save_ps_artifact(task_id, kind="phase_blueprint", ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M2: {len(out.micro)} microfasi")
        return out

    # ── passi M3/M4 + qualificazione (PS4) ───────────────────────────────────

    def _known_cmd_ids(self) -> set[str]:
        spec = self.router.catalog.get("run_tests") if self.router else None
        if spec is None or not hasattr(spec.handler, "args"):
            return set()
        return set(spec.handler.args[1])

    def design_verification(self, task_id: str, phase: MacroPhase,
                            bp: PhaseBlueprint, projection: str,
                            log) -> VerificationBlueprint:
        known = self._known_cmd_ids()
        state = self.store.load_task(task_id)
        micro_ids = [m.id for m in bp.micro]
        volatile = (f"{projection}\n[BLUEPRINT] {bp.model_dump_json()}"
                    f"\n[KNOWN TEST COMMANDS] {sorted(known)}"
                    f"\n[ALLOWED micro_id] {', '.join(micro_ids)}")
        ctx = RoleContext(task=state, subtask=None, volatile=volatile)
        role = VerificationDesigner(self.llm, self.assembler, self.router)
        grammar = self._enum_schema(VerificationBlueprint, [
            ("ProofObligation", "micro_id", micro_ids, False),
            ("ProofObligation", "cmd_id", sorted(known), False),
            (None, "synthesis_cmds", sorted(known), True)])

        def _norm_kinds(v: VerificationBlueprint) -> VerificationBlueprint:
            # Pilota PS5: 'characterization' su file che NON esistono ancora
            # non puo' essere verde ora — il control plane lo sa: riparazione
            # deterministica a new_behavior (inequivoca), mai un giro di patch.
            micros = {m.id: m for m in bp.micro}
            for o in v.obligations:
                m = micros.get(o.micro_id)
                if (m and o.kind == "characterization"
                        and not any((self.scope.root / f).exists()
                                    for f in m.work.files_owned)):
                    o.kind = "new_behavior"
            return v

        out: VerificationBlueprint = role.run(
            ctx, max_tokens=self.cfg.plansys.m_pass_max_tokens,
            grammar_schema=grammar)  # type: ignore
        # GPU dry-run PS6: canonicalizzare PRIMA di validare — un test_file
        # inventato da M3 ('test.php') muore in patch per un nome che il
        # control plane sovrascrive comunque (normalizzazione, poi giudizio)
        out = self._repair_loop(
            "M3", role, ctx, out, VerificationBlueprint,
            lambda v: (self._canonical_names(_norm_kinds(v), log)
                       or validate_verification(v, bp, known)), log,
            grammar_schema=grammar)
        self.store.save_ps_artifact(task_id, kind="verification_blueprint",
                                    ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M3: {len(out.obligations)} obblighi")
        return out

    def _canonical_names(self, vbp: VerificationBlueprint, log) -> None:
        """Batch20 n.2 → n.3 (Closed Reference Loop, PS-D11): 'il modello crea
        il significato, il control plane crea l'IDENTITA''. Dopo M3 i nomi
        id/test_file/test_name diventano canonici e derivati — UNA autorita'
        nominale, mai due. Eccezione: se M3 punta a un test file ESISTENTE
        (suite fornita), l'ancora resta il file reale."""
        counters: dict[str, int] = {}
        for o in vbp.obligations:
            # A/B PS6 (T003): l'eccezione vale SOLO per test_*.py esistenti —
            # M3 che punta a un 'test.php' reale non e' un'ancora, e' un derail
            existing = ((self.scope.root / o.test_file).is_file()
                        and _TEST_FILE.search(o.test_file) is not None)
            n = counters.get(o.micro_id, 0) + 1
            counters[o.micro_id] = n
            new_id = f"{o.micro_id}.O{n}"
            if o.id != new_id:
                o.id = new_id
            if not existing:
                snake = o.micro_id.lower().replace(".", "_")
                o.test_file = f"test_{snake}.py"
                o.test_name = f"test_{snake}_o{n}"
        log.line("compiler", "nomi canonici assegnati agli obblighi "
                             f"({len(vbp.obligations)})")

    def author_tests(self, task_id: str, phase: MacroPhase, bp: PhaseBlueprint,
                     vbp: VerificationBlueprint, projection: str,
                     log) -> TestBundle:
        state = self.store.load_task(task_id)
        role = TestAuthor(self.llm, self.assembler, self.router)
        artifacts = []
        # batch n.3: M4 lavora PER-FILE — un file di test per chiamata, con i
        # soli obblighi di quel file (ask piccolo = niente file mancanti,
        # niente troncamenti; i nomi sono gia' canonici, PS-D11)
        for tf in sorted({o.test_file for o in vbp.obligations}):
            subset = VerificationBlueprint(
                phase_id=vbp.phase_id,
                obligations=[o for o in vbp.obligations if o.test_file == tf],
                synthesis_cmds=vbp.synthesis_cmds)
            volatile = (f"{projection}\n[BLUEPRINT] {bp.model_dump_json()}"
                        f"\n[OBLIGATIONS] {subset.model_dump_json()}"
                        f"\n[REQUIRED TEST FILES] exactly ONE artifact with "
                        f"path '{tf}' containing the test functions named by "
                        f"the obligations above, nothing else"
                        f"\n{self._import_hint(bp, subset)}")
            existing = self.scope.root / tf
            if existing.is_file():
                volatile += (f"\n[EXISTING TEST FILE {tf}]\n"
                             + existing.read_text(encoding="utf-8",
                                                  errors="replace"))
            ctx = RoleContext(task=state, subtask=None, volatile=volatile)
            grammar = self._enum_schema(TestBundle, [
                ("TestArtifact", "path", [tf], False)])

            def _val(b: TestBundle) -> list[str]:
                self._dedup_bundle(subset, b, log)
                self._reconcile_test_names(subset, b, log)
                return validate_bundle(b, subset, bp,
                                       set(self._existing_files()))

            one: TestBundle = role.run(
                ctx, max_tokens=self.cfg.plansys.test_author_max_tokens,
                grammar_schema=grammar)  # type: ignore
            one = self._repair_loop(
                "M4", role, ctx, one, TestBundle, _val, log,
                max_tokens=self.cfg.plansys.test_author_max_tokens,
                grammar_schema=grammar)
            artifacts.extend(a for a in one.artifacts if a.path == tf)

        out = TestBundle(phase_id=vbp.phase_id, artifacts=artifacts)
        self._prune_unbound_tests(out, vbp, log)
        probs = validate_bundle(out, vbp, bp, set(self._existing_files()))
        if probs:
            raise CompileFailed("M4", probs)
        self.store.save_ps_artifact(task_id, kind="test_bundle", ref=phase.id,
                                    payload_json=out.model_dump_json(),
                                    actor="phase_compiler")
        # la riconciliazione puo' aver ri-puntato i test_name degli obblighi
        self.store.save_ps_artifact(task_id, kind="verification_blueprint",
                                    ref=phase.id,
                                    payload_json=vbp.model_dump_json(),
                                    actor="phase_compiler")
        log.line("compiler", f"{phase.id} M4: {len(out.artifacts)} file di test")
        return out

    def _prune_unbound_tests(self, bundle: TestBundle,
                             vbp: VerificationBlueprint, log) -> None:
        """Batch n.4: i test EXTRA di M4 non legati a obblighi non passano
        dalla qualificazione — se rotti, esplodono in sintesi. Si potano via
        AST prima della materializzazione (solo per i file CANONICI nuovi:
        nei file esistenti i test forniti restano intoccabili)."""
        import ast as _ast
        bound = {(o.test_file, o.test_name) for o in vbp.obligations}
        for a in bundle.artifacts:
            if (self.scope.root / a.path).is_file():
                continue  # file esistente: mai potare i test forniti
            try:
                tree = _ast.parse(a.content)
            except SyntaxError:
                continue
            pruned = []
            kept_body = []
            for node in tree.body:
                if (isinstance(node, _ast.FunctionDef)
                        and node.name.startswith("test")
                        and (a.path, node.name) not in bound):
                    pruned.append(node.name)
                    continue
                kept_body.append(node)
            if pruned:
                tree.body = kept_body
                a.content = _ast.unparse(_ast.fix_missing_locations(tree)) + "\n"
                log.line("compiler", f"potati test non qualificati in "
                                     f"{a.path}: {pruned}")

    @staticmethod
    def _dedup_bundle(vbp: VerificationBlueprint, bundle: TestBundle,
                      log) -> None:
        """Pilota PS5 #19: M4 emette lo stesso path due volte. Dedup
        deterministico: vince l'artefatto che contiene PIU' test richiesti
        dagli obblighi (a parita', il piu' lungo)."""
        from redgiant.plansys.gates import _parse_tests
        needed = {o.test_file: {ob.test_name for ob in vbp.obligations
                                if ob.test_file == o.test_file}
                  for o in vbp.obligations}
        best: dict[str, tuple[int, int, int]] = {}  # path -> (score, len, idx)
        for i, a in enumerate(bundle.artifacts):
            fns, _ = _parse_tests(a.content)
            score = len(set(fns) & needed.get(a.path, set()))
            key = (score, len(a.content), -i)
            if a.path not in best or key > best[a.path]:
                best[a.path] = key
        seen: set[str] = set()
        kept = []
        for i, a in enumerate(bundle.artifacts):
            fns, _ = _parse_tests(a.content)
            score = len(set(fns) & needed.get(a.path, set()))
            if a.path in seen:
                log.line("compiler", f"dedup bundle: scartato duplicato "
                                     f"di {a.path}")
                continue
            if (score, len(a.content), -i) == best[a.path]:
                kept.append(a)
                seen.add(a.path)
        if len(kept) != len(bundle.artifacts):
            bundle.artifacts = kept

    @staticmethod
    def _reconcile_test_names(vbp: VerificationBlueprint, bundle: TestBundle,
                              log) -> None:
        """Pilota PS5 #14: M3 battezza un test, M4 lo scrive con un altro nome.
        Il nome e' un puntatore, il contratto e' il comportamento: quando il
        legame e' INEQUIVOCO (N obblighi orfani <-> N funzioni non reclamate,
        in ordine) il control plane ri-punta i test_name, loggandolo."""
        from redgiant.plansys.gates import _parse_tests
        for a in bundle.artifacts:
            fns, _ = _parse_tests(a.content)
            here = [o for o in vbp.obligations if o.test_file == a.path]
            claimed = {o.test_name for o in here if o.test_name in fns}
            orphans = [o for o in here if o.test_name not in fns]
            free = [n for n in fns if n not in claimed]
            # batch n.3: binding in ORDINE quando orfani <= libere — M4 che
            # scrive test EXTRA e' un bene, non una violazione (l'uguaglianza
            # stretta strozzava 11 run su 20)
            if orphans and len(orphans) <= len(free):
                for o, name in zip(orphans, free):
                    log.line("compiler", f"riconciliato {o.id}: "
                                         f"'{o.test_name}' -> '{name}'")
                    o.test_name = name

    # ── enum dinamici nella grammatica (batch20, strategia generale n.1) ─────
    # "Il modello non NOMINA mai cio' che il sistema gia' conosce": i campi di
    # riferimento diventano enum GBNF costruiti dalla realta' — l'invenzione
    # e' irrappresentabile (generalizzazione della lezione discriminated-union).
    # Lo schema in S2 resta statico (KV); la specializzazione viaggia solo nel
    # payload del server + come lista [ALLOWED] nel contesto volatile (D6:
    # la grammatica vincola ma non informa).

    @staticmethod
    def _enum_schema(model: type[BaseModel],
                     spots: list[tuple[str | None, str, list[str], bool]]) -> dict | None:
        """spots: (nome in $defs | None per il top-level, proprieta',
        valori, is_list). Valori vuoti -> spot saltato; nessuno spot -> None."""
        import copy
        schema = copy.deepcopy(model.model_json_schema())
        touched = False
        for defs_name, prop, values, is_list in spots:
            if not values:
                continue
            try:
                host = (schema["$defs"][defs_name]["properties"] if defs_name
                        else schema["properties"])
                if is_list:
                    host[prop]["items"] = {"type": "string",
                                           "enum": sorted(values)}
                else:
                    host[prop] = {"type": "string", "enum": sorted(values),
                                  "title": host[prop].get("title", prop)}
                touched = True
            except KeyError:
                continue
        return schema if touched else None

    def _relativize(self, p: str) -> str:
        """Pilota PS5: M1/M2 a volte scrivono path ASSOLUTI. Se il path sta
        sotto la root del task la riparazione e' inequivoca (si relativizza);
        fuori root resta com'e' e lo boccia il validatore."""
        from pathlib import Path as _P
        try:
            pp = _P(p)
            if pp.is_absolute():
                return pp.resolve().relative_to(
                    self.scope.root.resolve()).as_posix()
        except (ValueError, OSError):
            pass
        return p

    @staticmethod
    def _import_hint(bp: PhaseBlueprint, vbp: VerificationBlueprint) -> str:
        """Pilota PS5: un test che non importa il modulo bersaglio non prova
        niente — l'ancora la fornisce il control plane, deterministicamente."""
        owned = {o.micro_id for o in vbp.obligations}
        stems = sorted({f.rsplit("/", 1)[-1].removesuffix(".py")
                        for m in bp.micro if m.id in owned
                        for f in m.work.files_owned if f.endswith(".py")})
        return ("[MUST IMPORT] each test must import and exercise the target "
                "module(s): " + ", ".join(stems))

    def materialize_tests(self, bundle: TestBundle, log) -> None:
        """Il CONTROL PLANE scrive i test (mai J): Scope dedicato ai soli path
        del bundle + syntax gate dei writer esistenti. Guardia (smoke PS4.3):
        sovrascrivere un test file esistente NON deve far sparire test — i
        nomi esistenti devono sopravvivere nel contenuto nuovo."""
        from redgiant.plansys.gates import _parse_tests
        from redgiant.tools import fs
        test_scope = Scope(self.scope.root, [a.path for a in bundle.artifacts])
        for a in bundle.artifacts:
            dest = self.scope.root / a.path
            if dest.is_file():
                old, _ = _parse_tests(dest.read_text(encoding="utf-8",
                                                     errors="replace"))
                new, _ = _parse_tests(a.content)
                dropped = sorted(set(old) - set(new))
                if dropped:
                    raise CompileFailed(
                        "materialize",
                        [f"{a.path}: existing tests would be DROPPED: {dropped} "
                         f"— the artifact must contain them plus the new ones"])
            res = fs.write_file(test_scope, a.path, a.content)
            if not res.ok:
                raise CompileFailed("materialize", [f"{a.path}: {res.error}"])
            log.line("compiler", f"test materializzato: {a.path}")

    def compile_phase(self, task_id: str, plan: MacroPlan, phase: MacroPhase,
                      log) -> tuple[PhaseBlueprint, VerificationBlueprint,
                                    TestBundle]:
        """La pipeline M1->M4 + Oracle Qualification (flusso §PS-A5)."""
        projection = self.projection(task_id, plan, phase)
        analysis = self.analyze(task_id, plan, phase, projection, log)
        bp = self.decompose(task_id, phase, analysis, projection, log)
        vbp = self.design_verification(task_id, phase, bp, projection, log)
        bundle = self.author_tests(task_id, phase, bp, vbp, projection, log)

        state = self.store.load_task(task_id)
        rounds = 0
        while True:
            try:
                self.materialize_tests(bundle, log)
            except CompileFailed as e:
                rounds += 1
                if rounds > 2:
                    raise
                log.line("gate", f"{phase.id} materializzazione KO: patch M4")
                ctx = RoleContext(task=state, subtask=None,
                                  volatile=f"[OBLIGATIONS] {vbp.model_dump_json()}")
                patch = self._request_patch(ctx, "test_author", e.problems,
                                            bundle.model_dump_json())
                bundle = TestBundle.model_validate_json(self._apply_patch(
                    TestBundle, bundle.model_dump_json(), patch))
                probs = validate_bundle(bundle, vbp, bp,
                                        set(self._existing_files()))
                if probs:
                    raise CompileFailed("M4-patch", probs)
                self.store.save_ps_artifact(
                    task_id, kind="test_bundle", ref=phase.id,
                    payload_json=bundle.model_dump_json(), actor="phase_compiler")
                continue
            from redgiant.plansys import ablated
            if ablated("oracle"):
                # ablation B1: il gate di qualificazione e' bypassato
                from redgiant.core.verify import CheckResult
                from redgiant.plansys.artifacts import GateReport
                report = GateReport(gate="oracle_qualification", target=phase.id,
                                    ok=True, checks=[CheckResult(
                                        name="ABLATED", ok=True,
                                        detail="oracle gate bypassed (A/B)")])
            else:
                report = oracle_qualification_gate(
                    vbp, bundle, bp, self.scope, self.router, task_id,
                    mutation_probe=self.cfg.plansys.mutation_probe)
            self.store.log_ps_gate(
                task_id, gate="oracle_qualification", target=phase.id,
                ok=report.ok,
                checks_json=json.dumps([c.model_dump() for c in report.checks]))
            if report.ok:
                break
            failed = [c for c in report.checks if not c.ok]
            if failed and all(":baseline_new_behavior" in c.name
                              and "exit=0" in c.detail for c in failed):
                # prove nuove GIA' verdi: fase ridondante SOLO se il lavoro
                # esiste davvero (fast #1: senza questo check, test vuoti
                # chiudevano fasi mai eseguite)
                work_exists = all(
                    (self.scope.root / f).exists()
                    for m in bp.micro for f in m.work.files_owned)
                if work_exists:
                    self.store.log_ps_gate(
                        task_id, gate="phase_entry", target=phase.id, ok=True,
                        checks_json=json.dumps([{
                            "name": "satisfied_post_compile", "ok": True,
                            "detail": "all new_behavior proofs green AND owned "
                                      "files exist"}]))
                    log.line("gate", f"{phase.id} gia' soddisfatta post-compile "
                                     f"(prove verdi, file esistenti): chiusa a "
                                     f"costo zero")
                    raise PhaseAlreadySatisfied(phase.id)
                # file inesistenti + test verdi = test VUOTI: violazione a M4
                for c in failed:
                    c.detail += (" — the owned files do NOT exist yet: a green "
                                 "new_behavior here means the test proves "
                                 "nothing; import and call the target module")
            log.line("gate", f"{phase.id} oracle_qualification KO: "
                             f"{[c.name for c in failed][:6]}")
            rounds += 1
            if rounds > 2:
                raise CompileFailed("oracle_qualification",
                                    [f"{c.name}: {c.detail}" for c in failed])
            # routing della correzione: contenuto test -> M4; disegno prove -> M3.
            # Pilota PS5: anche i baseline vanno a M4 — un new_behavior che passa
            # gia' e' quasi sempre un TEST debole, non un obbligo sbagliato
            m4_keys = (":exists", ":asserts", ":targets_contract", ":scope",
                       ":baseline_", "bundle_covers")
            m4_issues = [f"{c.name}: {c.detail}" for c in failed
                         if any(k in c.name for k in m4_keys)]
            m3_issues = [f"{c.name}: {c.detail}" for c in failed
                         if not any(k in c.name for k in m4_keys)]
            if any(":baseline_new_behavior" in i for i in m4_issues):
                m4_issues.append(
                    "a new_behavior test PASSING now proves nothing: rewrite it "
                    "so it exercises the MISSING behaviour (import and call the "
                    "not-yet-implemented function) and FAILS on the current code")
            # una patch INVALIDA (payload deforme, target ignoto, validatore
            # rosso) e' un round fallito, non un crash: si logga e si ritenta
            # (il tetto rounds fa da uscita deterministica, PS-D1)
            if m4_issues:
                try:
                    required = sorted({o.test_file for o in vbp.obligations})
                    ctx = RoleContext(
                        task=state, subtask=None,
                        volatile=(f"[OBLIGATIONS] {vbp.model_dump_json()}"
                                  f"\n[REQUIRED TEST FILES] only these: "
                                  f"{', '.join(required)}"
                                  f"\n{self._import_hint(bp, vbp)}"))
                    patch = self._request_patch(ctx, "test_author", m4_issues,
                                                bundle.model_dump_json())
                    cand = TestBundle.model_validate_json(self._apply_patch(
                        TestBundle, bundle.model_dump_json(), patch))
                    probs = validate_bundle(cand, vbp, bp,
                                            set(self._existing_files()))
                    if probs:
                        raise ValueError("; ".join(probs)[:300])
                    bundle = cand
                    self.store.save_ps_artifact(
                        task_id, kind="test_bundle", ref=phase.id,
                        payload_json=bundle.model_dump_json(),
                        actor="phase_compiler")
                except (ValidationError, ValueError, json.JSONDecodeError) as e:
                    log.line("gate", f"patch M4 invalida: {str(e)[:120]}")
            if m3_issues:
                try:
                    ctx = RoleContext(
                        task=state, subtask=None,
                        volatile=f"[BLUEPRINT] {bp.model_dump_json()}")
                    patch = self._request_patch(ctx, "verification_designer",
                                                m3_issues, vbp.model_dump_json())
                    cand = VerificationBlueprint.model_validate_json(
                        self._apply_patch(VerificationBlueprint,
                                          vbp.model_dump_json(), patch))
                    probs = validate_verification(cand, bp, self._known_cmd_ids())
                    if probs:
                        raise ValueError("; ".join(probs)[:300])
                    vbp = cand
                    self.store.save_ps_artifact(
                        task_id, kind="verification_blueprint", ref=phase.id,
                        payload_json=vbp.model_dump_json(),
                        actor="phase_compiler")
                except (ValidationError, ValueError, json.JSONDecodeError) as e:
                    log.line("gate", f"patch M3 invalida: {str(e)[:120]}")

        write_plan_doc(self.cfg.paths.tasks_dir, task_id,
                       f"{phase.id}.blueprint",
                       render_blueprint(bp, vbp, analysis))
        log.line("compiler", f"{phase.id} qualificata: blueprint completo")
        return bp, vbp, bundle

    # ── meccanica delle correzioni (PS-D6) ───────────────────────────────────

    def _repair_loop(self, step: str, role, ctx: RoleContext, artifact: BaseModel,
                     model: type[BaseModel], validate, log,
                     max_tokens: int | None = None,
                     grammar_schema: dict | None = None) -> BaseModel:
        if max_tokens is None:
            max_tokens = self.cfg.plansys.m_pass_max_tokens
        problems = validate(artifact)
        patches = 0
        while problems and patches < _MAX_PATCHES:
            patches += 1
            log.line("compiler", f"{step} respinto ({len(problems)}): patch {patches}")
            patch = self._request_patch(ctx, role.name, problems,
                                        artifact.model_dump_json(),
                                        max_tokens=max_tokens)
            try:
                artifact = model.model_validate_json(
                    self._apply_patch(model, artifact.model_dump_json(), patch))
            except (ValidationError, ValueError) as e:
                problems = [f"patch not applicable: {e}"[:200]]
                continue
            problems = validate(artifact)
        if problems:
            # ultima spiaggia: UNA rigenerazione intera con le violazioni citate
            log.line("compiler", f"{step}: patch esaurite, rigenerazione unica")
            retry_ctx = RoleContext(
                task=ctx.task, subtask=None,
                volatile=ctx.volatile + "\n[REJECTED] your previous output had "
                "these problems, produce a corrected COMPLETE object: "
                + "; ".join(problems))
            artifact = role.run(retry_ctx, max_tokens=max_tokens,
                                grammar_schema=grammar_schema)
            problems = validate(artifact)
            if problems:
                raise CompileFailed(step, problems)
        return artifact

    def _request_patch(self, ctx: RoleContext, role_name: str,
                       violations: list[str], current_json: str,
                       max_tokens: int | None = None) -> BlueprintPatch:
        # enum dinamico anche sul TARGET della patch: si puo' patchare solo
        # un elemento che ESISTE nell'artefatto corrente
        targets: list[str] = []
        try:
            data = json.loads(current_json)
            for list_key, id_key in _PATCHABLE.values():
                for item in data.get(list_key, []):
                    if isinstance(item, dict) and item.get(id_key):
                        targets.append(str(item[id_key]))
        except json.JSONDecodeError:
            pass
        patch_grammar = self._enum_schema(BlueprintPatch, [
            ("PatchOp", "target", targets, False)]) if targets else None
        parts = self.assembler.build(
            role_name, task=ctx.task, subtask=None, tools=[],
            volatile=(f"[ARTIFACT] {current_json}\n[VIOLATIONS] "
                      + "; ".join(violations)
                      + "\nEmit a BlueprintPatch that fixes ONLY the violated "
                        "parts. op=replace/add/remove; target = the id (or path)"
                        " of the element; payload_json = the complete corrected "
                        "element as a JSON string (empty for remove). For TEST "
                        "FILE artifacts, payload_json may simply be the raw "
                        "corrected file content (not JSON).\nExample: "
                        '{"phase_id": "P1", "ops": [{"op": "replace", '
                        '"target": "test_mod.py", "payload_json": '
                        '"import mod\\n\\ndef test_x():\\n    assert '
                        'mod.f() == 1\\n"}]}'),
            output_schema=BlueprintPatch.model_json_schema(),
            schema_name="BlueprintPatch")
        # batch n.6 run 15: la patch di M4 porta file di test INTERI nel
        # payload — col budget m_pass (1536) troncava; usa quello del chiamante
        return self.llm.complete(
            parts, role=role_name, schema=BlueprintPatch,
            max_tokens=max_tokens or self.cfg.plansys.m_pass_max_tokens,
            task_id=ctx.task.id,
            grammar_schema=patch_grammar).parsed  # type: ignore[return-value]

    @staticmethod
    def _apply_patch(model: type[BaseModel], artifact_json: str,
                     patch: BlueprintPatch) -> str:
        """Applicazione DETERMINISTICA: opera sulla lista patchabile del tipo
        (micro/obligations/decisions/artifacts), identita' per id/path."""
        list_key, id_key = _PATCHABLE[model.__name__]
        data = json.loads(artifact_json)
        items: list[dict] = data.get(list_key, [])
        for op in patch.ops:
            if op.op == "remove":
                items = [i for i in items if i.get(id_key) != op.target]
                continue
            try:
                payload = json.loads(op.payload_json)
                if not isinstance(payload, dict):
                    raise ValueError("payload is not an object")
            except (json.JSONDecodeError, ValueError):
                if model.__name__ == "TestBundle":
                    # accomodamento (lezione F1: adatta l'ambiente): per i test
                    # il payload puo' essere il CONTENUTO GREZZO del file —
                    # il JSON-annidato-nella-stringa e' ostile a un 2B
                    payload = {"path": op.target, "content": op.payload_json}
                else:
                    raise
            if op.op == "add":
                items.append(payload)
            else:  # replace
                idx = next((k for k, i in enumerate(items)
                            if i.get(id_key) == op.target), None)
                if idx is None:
                    raise ValueError(f"replace target '{op.target}' not found")
                items[idx] = payload
        data[list_key] = items
        return json.dumps(data)

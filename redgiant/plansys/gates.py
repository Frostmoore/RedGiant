"""Gate deterministici del plansys (PS2+). Zero token per costruzione (PS-D1).

Ogni gate produce un GateReport con TUTTI i check eseguiti (mai fermarsi al
primo ko: il quadro completo e' cio' che la patch correttiva deve vedere).
"""

from __future__ import annotations

import ast
import re

from redgiant.core.verify import CheckResult
from redgiant.plansys.artifacts import (GateReport, MacroPlan, PhaseAnalysis,
                                        PhaseBlueprint, TestBundle,
                                        VerificationBlueprint)
from redgiant.tools.base import Scope


def dag_problems(pairs: list[tuple[str, list[str]]]) -> list[str]:
    """Check condivisi su un grafo (id, depends_on) — estratto da
    roles/planner.py::validate_plan_logic (PS2.2): un solo validatore di
    dipendenze in tutto il repo, messaggi identici a F3."""
    problems: list[str] = []
    ids = [i for i, _ in pairs]
    if len(ids) != len(set(ids)):
        problems.append(f"duplicate phase ids: {ids}")
    known = set(ids)
    for pid, deps in pairs:
        for dep in deps:
            if dep not in known:
                problems.append(f"phase {pid} depends on unknown phase '{dep}'")
            if dep == pid:
                problems.append(f"phase {pid} depends on itself")
    graph = {pid: [d for d in deps if d in known] for pid, deps in pairs}
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)

    def dfs(node: str) -> bool:
        color[node] = GREY
        for nxt in graph[node]:
            if color[nxt] == GREY or (color[nxt] == WHITE and dfs(nxt)):
                return True
        color[node] = BLACK
        return False

    if any(dfs(n) for n in graph if color[n] == WHITE):
        problems.append("dependency cycle detected")
    if ids and not any(not deps for _, deps in pairs):
        problems.append("no root phase (every phase has dependencies)")
    return problems


def normalize_macro(plan: MacroPlan) -> MacroPlan:
    """Sentinelli inequivoci riparati (stessa politica di roles/planner.py:
    'none'/'null'/... e auto-dipendenza significano 'nessuna dipendenza')."""
    from redgiant.roles.planner import _DEP_SENTINELS
    for p in plan.phases:
        p.depends_on = [d for d in p.depends_on
                        if d.strip().lower() not in _DEP_SENTINELS and d != p.id]
    return plan


_CRIT_ID = re.compile(r"^C\d+$")
_PHASE_ID = re.compile(r"^P\d+$")


def macro_validation_gate(plan: MacroPlan) -> GateReport:
    """PS2.2 — la logica del MacroPlan, validata in codice. Include la matrice
    di copertura (PS-D9/13): un criterio scoperto e' un piano respinto."""
    checks: list[CheckResult] = []

    bad_crit = [c.id for c in plan.criteria if not _CRIT_ID.match(c.id)]
    dup_crit = len({c.id for c in plan.criteria}) != len(plan.criteria)
    checks.append(CheckResult(
        name="criterion_ids", ok=not bad_crit and not dup_crit,
        detail=f"bad: {bad_crit}, duplicates: {dup_crit}"))

    bad_phase = [p.id for p in plan.phases if not _PHASE_ID.match(p.id)]
    checks.append(CheckResult(name="phase_ids", ok=not bad_phase,
                              detail=f"bad: {bad_phase}"))

    dag = dag_problems([(p.id, p.depends_on) for p in plan.phases])
    checks.append(CheckResult(name="dependencies", ok=not dag,
                              detail="; ".join(dag) or "acyclic, root present"))

    crit_ids = {c.id for c in plan.criteria}
    ghost = sorted({cid for p in plan.phases for cid in p.covers
                    if cid not in crit_ids})
    checks.append(CheckResult(name="covers_exist", ok=not ghost,
                              detail=f"unknown criteria referenced: {ghost}"))

    covered = {cid for p in plan.phases for cid in p.covers}
    uncovered = sorted(crit_ids - covered)
    checks.append(CheckResult(
        name="coverage_total", ok=not uncovered,
        detail=f"criteria covered by no phase: {uncovered}" if uncovered
        else "every criterion covered"))

    return GateReport(gate="macro_validation", target="macro_plan",
                      ok=all(c.ok for c in checks), checks=checks)


def validate_analysis(analysis: PhaseAnalysis, projection: str,
                      phase_id: str) -> list[str]:
    """PS3.1 — M1 validata in codice. Anti-invenzione MECCANICA: gli 'involved'
    devono apparire testualmente nella proiezione del ledger (il modello puo'
    solo COPIARE identificatori, mai coniarli — contract anchoring)."""
    problems: list[str] = []
    if analysis.phase_id != phase_id:
        problems.append(f"phase_id must be '{phase_id}', got '{analysis.phase_id}'")
    for sym in analysis.involved:
        if sym and sym not in projection:
            problems.append(f"involved '{sym}' does not appear in CONTEXT: "
                            f"copy identifiers exactly, never invent them")
    dec_ids = [d.id for d in analysis.decisions]
    if len(dec_ids) != len(set(dec_ids)):
        problems.append(f"duplicate decision ids: {dec_ids}")
    for a in analysis.artifacts:
        if not a.strip():
            problems.append("empty path in artifacts")
    return problems


_MICRO_ID = re.compile(r"^(P\d+)\.S(\d+)$")
_TEST_FILE = re.compile(r"(^|/)test_[^/]+\.py$")


def validate_blueprint(bp: PhaseBlueprint, analysis: PhaseAnalysis,
                       covers: list[str],
                       existing: set[str] | None = None) -> list[str]:
    """PS3.2 — M2 validata in codice. Ownership ESCLUSIVA dei file (il difetto
    'fasi ridondanti' di F3 reso irrappresentabile) e perimetri dal ledger.
    Fast #2: `existing` = file reali del repo — lavorare su un file che ESISTE
    non e' invenzione (l'anti-invenzione vieta i fantasmi, non il brownfield)."""
    problems: list[str] = []
    if bp.phase_id != analysis.phase_id:
        problems.append(f"phase_id must be '{analysis.phase_id}', got '{bp.phase_id}'")
    ids = [m.id for m in bp.micro]
    if len(ids) != len(set(ids)):
        problems.append(f"duplicate micro ids: {ids}")
    for m in bp.micro:
        mm = _MICRO_ID.match(m.id)
        if not mm or mm.group(1) != bp.phase_id:
            problems.append(f"micro id '{m.id}' must match {bp.phase_id}.S<n>")
    owned: dict[str, str] = {}
    allowed = set(analysis.artifacts) | set(analysis.involved) | (existing or set())
    for m in bp.micro:
        for f in m.work.files_owned:
            if _TEST_FILE.search(f):
                problems.append(f"{m.id} owns test file '{f}': FORBIDDEN — "
                                f"tests are written by the compiler and are "
                                f"immutable for the junior (PS-D4); own the "
                                f"implementation files instead")
                continue
            if f in owned:
                problems.append(f"file '{f}' owned by both {owned[f]} and {m.id}: "
                                f"ownership is EXCLUSIVE")
            owned[f] = m.id
            if allowed and f not in allowed:
                problems.append(f"{m.id} owns '{f}' which is neither in the "
                                f"analysis artifacts nor in involved")
        for cid in m.proves:
            if cid not in covers:
                problems.append(f"{m.id} proves '{cid}' which this phase does "
                                f"not cover (covers: {covers})")
    # fast #7: una micro che CREA piu' di un file nuovo non sta in una
    # sessione Junior (PS-D10 reso meccanico: contesto esploso a 7674 tok,
    # loop di write) — granularita' minima: un file nuovo per micro
    if existing is not None:
        for m in bp.micro:
            new_files = [f for f in m.work.files_owned if f not in existing]
            if len(new_files) > 1:
                problems.append(f"{m.id} creates {len(new_files)} new files "
                                f"{new_files}: too big for one junior session "
                                f"— split into one micro phase per new file")
    # fast #3: la CATENA di copertura deve chiudersi — ogni criterio coperto
    # dalla fase deve essere PROVATO da almeno una micro, o restera' orfano
    # fino al coverage gate finale (fallimento tardivo = fallimento caro)
    proved = {cid for m in bp.micro for cid in m.proves}
    orphan = sorted(set(covers) - proved)
    if orphan:
        problems.append(f"criteria {orphan} are covered by this phase but "
                        f"proved by NO micro phase: add them to the 'proves' "
                        f"of the micro phase whose work demonstrates them")
    return problems


def validate_verification(vbp: VerificationBlueprint, bp: PhaseBlueprint,
                          known_cmd_ids: set[str]) -> list[str]:
    """PS4.1 — M3 validata in codice. La regola che ha ucciso F3 (cmd id
    esatti) qui e' meccanica, non solo scritta nella card."""
    problems: list[str] = []
    if vbp.phase_id != bp.phase_id:
        problems.append(f"phase_id must be '{bp.phase_id}', got '{vbp.phase_id}'")
    ob_ids = [o.id for o in vbp.obligations]
    if len(ob_ids) != len(set(ob_ids)):
        problems.append(f"duplicate obligation ids: {ob_ids}")
    micro_ids = {m.id for m in bp.micro}
    proved = {o.micro_id for o in vbp.obligations}
    for m in bp.micro:
        if m.id not in proved:
            problems.append(f"micro {m.id} has NO proof obligation")
    for o in vbp.obligations:
        if o.micro_id not in micro_ids:
            problems.append(f"{o.id}: unknown micro '{o.micro_id}'")
        if o.cmd_id not in known_cmd_ids:
            problems.append(f"{o.id}: cmd_id '{o.cmd_id}' is not a known test "
                            f"command (known: {sorted(known_cmd_ids)})")
        if not _TEST_FILE.search(o.test_file):
            problems.append(f"{o.id}: test_file '{o.test_file}' must be named "
                            f"test_*.py")
        if not o.test_name.startswith("test"):
            problems.append(f"{o.id}: test_name '{o.test_name}' must start "
                            f"with 'test'")
    for cmd in vbp.synthesis_cmds:
        if cmd not in known_cmd_ids:
            problems.append(f"synthesis cmd '{cmd}' is not a known test command")
    return problems


def _fn_identifiers(fn: "ast.FunctionDef", imports_src: str) -> set[str]:
    used: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    for tok in imports_src.replace(",", " ").split():
        used.add(tok.strip("."))
    return used


def validate_bundle(bundle: TestBundle, vbp: VerificationBlueprint,
                    bp: PhaseBlueprint | None = None) -> list[str]:
    """PS4.1 — M4 validata in codice PRIMA della materializzazione: file giusti,
    sintassi che parsa, niente file fuori nomenclatura. Batch n.3: con `bp`
    anche l'AGGANCIO al bersaglio si valida QUI (riparazione nel loop giusto,
    non al gate finale)."""
    problems: list[str] = []
    if bundle.phase_id != vbp.phase_id:
        problems.append(f"phase_id must be '{vbp.phase_id}', got '{bundle.phase_id}'")
    paths = [a.path for a in bundle.artifacts]
    if len(paths) != len(set(paths)):
        problems.append(f"duplicate artifact paths: {paths}")
    needed = {o.test_file for o in vbp.obligations}
    for miss in sorted(needed - set(paths)):
        problems.append(f"obligation test_file '{miss}' has no artifact in bundle")
    # ogni obbligo deve trovare la SUA funzione nel file del bundle (pilota PS5:
    # M3 nomina test_X, M4 scrive test_Y — va beccato QUI, non al gate)
    by_path = {a.path: a.content for a in bundle.artifacts}
    for o in vbp.obligations:
        content = by_path.get(o.test_file)
        if content is None:
            continue
        fns, imports_src = _parse_tests(content)
        if o.test_name not in fns:
            problems.append(f"obligation {o.id} requires test function "
                            f"'{o.test_name}' in {o.test_file} — missing "
                            f"(found: {sorted(fns)[:6]})")
            continue
        if bp is not None:
            try:
                syms = _micro_symbols(bp, o.micro_id)
            except StopIteration:
                continue
            used = _fn_identifiers(fns[o.test_name], imports_src)
            if syms and not (syms & used):
                problems.append(f"{o.test_name} in {o.test_file} references "
                                f"NONE of {sorted(syms)}: import and call the "
                                f"target module — a test that avoids the "
                                f"target proves nothing")
    for a in bundle.artifacts:
        if re.match(r"^[A-Za-z]:[\\/]|^[\\/]", a.path):
            problems.append(f"artifact '{a.path}': paths must be RELATIVE to "
                            f"the repo root, never absolute")
            continue
        if not _TEST_FILE.search(a.path):
            problems.append(f"artifact '{a.path}' must be named test_*.py — "
                            f"you write ONLY the test files named by the "
                            f"obligations, never implementation files")
        try:
            ast.parse(a.content)
        except SyntaxError as e:
            lines = a.content.splitlines()
            src = lines[e.lineno - 1] if e.lineno and e.lineno <= len(lines) else ""
            problems.append(f"artifact '{a.path}' does not parse: line "
                            f"{e.lineno}: {e.msg} | offending line: {src!r}")
    return problems


# ── Oracle Qualification Gate (PS4.2, PS-D5) ─────────────────────────────────

def _parse_tests(content: str) -> tuple[dict[str, ast.FunctionDef], str]:
    """Ritorna (funzioni test per nome, sorgente degli import del file)."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {}, ""
    fns = {n.name: n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef) and n.name.startswith("test")}
    imports = "\n".join(ast.unparse(n) for n in tree.body
                        if isinstance(n, (ast.Import, ast.ImportFrom)))
    return fns, imports


def _has_real_assert(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            # 'assert True' / 'assert 1' = tautologia
            if isinstance(node.test, ast.Constant):
                continue
            return True
        if isinstance(node, ast.withitem):
            src = ast.unparse(node.context_expr)
            if "raises" in src:
                return True
    return False


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _micro_symbols(bp: PhaseBlueprint, micro_id: str) -> set[str]:
    m = next(x for x in bp.micro if x.id == micro_id)
    syms: set[str] = set()
    for f in m.work.files_owned:
        stem = f.rsplit("/", 1)[-1].removesuffix(".py")
        if stem and _IDENT.match(stem):
            syms.add(stem)
    for sig in m.work.signatures:
        name = re.sub(r"^(def|class)\s+", "", sig.strip()).split("(")[0].split(":")[0].strip()
        # solo identificatori VERI: M2 a volte mette prose nelle signatures
        # ("Item dataclass definition in models.py") — non sono ancore
        if name and _IDENT.match(name):
            syms.add(name)
    return syms


def _run_probe(scope: Scope, argv: list[str]) -> tuple[int, str]:
    """Esegue pytest via il run_tests esistente (stessa risoluzione interprete)."""
    from redgiant.tools.proc import run_tests
    res = run_tests(scope, {"__probe": argv}, ("pytest", "python"), "__probe",
                    timeout_s=120.0)
    exit_code = res.data.get("exit_code", 1 if not res.ok else 0)
    tail = str(res.data.get("output_tail", ""))
    return int(exit_code), tail


def oracle_qualification_gate(vbp: VerificationBlueprint, bundle: TestBundle,
                              bp: PhaseBlueprint, scope: Scope, router,
                              task_id: str, *,
                              mutation_probe: bool = False) -> GateReport:
    """PS-D5: si qualifica L'ORACOLO prima che J esista. Ogni check corrisponde
    a un modo reale in cui M puo' produrre una prova inutile. Costa run di
    test (secondi), zero token."""
    checks: list[CheckResult] = []
    by_path = {a.path: a.content for a in bundle.artifacts}

    # bundle copre tutti i test_file degli obblighi
    missing = sorted({o.test_file for o in vbp.obligations} - set(by_path))
    checks.append(CheckResult(name="bundle_covers_obligations", ok=not missing,
                              detail=f"missing test files: {missing}" if missing
                              else f"{len(by_path)} files"))

    for o in vbp.obligations:
        content = by_path.get(o.test_file, "")
        fns, imports_src = _parse_tests(content)
        fn = fns.get(o.test_name)

        # (1) il test ESISTE staticamente (collezione statica via AST)
        checks.append(CheckResult(
            name=f"{o.id}:exists", ok=fn is not None,
            detail=f"{o.test_file}::{o.test_name}"
                   + ("" if fn is not None else " NOT FOUND in bundle")))
        if fn is None:
            continue

        # (4) asserzioni reali, niente tautologie
        checks.append(CheckResult(
            name=f"{o.id}:asserts", ok=_has_real_assert(fn),
            detail="has observable assert" if _has_real_assert(fn)
            else "no real assertion (empty body or tautology)"))

        # (4b) niente INTROSPEZIONE nei test: __annotations__ (#13), __dict__
        # (#17), get_type_hints... — pattern fragili che falliscono anche su
        # implementazioni corrette. Generalizzato: nessun accesso a dunder.
        fragile = sorted({n.attr for n in ast.walk(fn)
                          if isinstance(n, ast.Attribute)
                          and n.attr.startswith("__") and n.attr.endswith("__")})
        if "get_type_hints" in ast.unparse(fn):
            fragile.append("get_type_hints")
        checks.append(CheckResult(
            name=f"{o.id}:no_introspection", ok=not fragile,
            detail=f"fragile introspection: {fragile} — test behaviour "
                   f"(construct, call, compare results) instead" if fragile
            else "behavioural"))

        # (5) aggancio al bersaglio: IDENTIFICATORI usati dal test (AST: nomi,
        # attributi, import) — mai sottostringhe (fast #1: "models" dentro un
        # letterale ingannava il check) ne' il nome del test stesso
        syms = _micro_symbols(bp, o.micro_id)
        used = _fn_identifiers(fn, imports_src)
        hooked = bool(syms & used)
        checks.append(CheckResult(
            name=f"{o.id}:targets_contract", ok=hooked,
            detail=f"references one of {sorted(syms)}" if hooked
            else f"references NONE of the contract symbols {sorted(syms)}"))

        # (6) scope: il test non scrive nei file posseduti da ALTRE micro
        others = {f for m in bp.micro if m.id != o.micro_id
                  for f in m.work.files_owned}
        leaks = [f for f in others
                 if re.search(r"open\(\s*['\"]" + re.escape(f), content)]
        checks.append(CheckResult(
            name=f"{o.id}:scope", ok=not leaks,
            detail=f"writes into foreign files: {leaks}" if leaks else "clean"))

    # (2)(3) red/green baseline: eseguiti SOLO se i check statici sono passati
    static_ok = all(c.ok for c in checks)
    if static_ok:
        for o in vbp.obligations:
            code, tail = _run_probe(
                scope, ["pytest", "-q", f"{o.test_file}::{o.test_name}"])
            noran = "no tests ran" in tail.lower()
            if o.kind == "new_behavior":
                # un new_behavior che PASSA ora non prova niente; import error
                # su modulo non ancora esistente = rosso legittimo
                ok = code != 0
                detail = (f"red baseline: exit={code}"
                          + (" [no tests ran]" if noran else ""))
            else:
                ok = code == 0 and not noran
                detail = f"green baseline: exit={code}" + \
                         (" [no tests ran]" if noran else "")
            checks.append(CheckResult(name=f"{o.id}:baseline_{o.kind}",
                                      ok=ok, detail=detail))
            # (8) mutation probe leggero: un characterization deve POTER fallire
            if mutation_probe and o.kind == "characterization" and ok:
                mut_ok = _mutation_probe(scope, by_path[o.test_file], o.test_name)
                checks.append(CheckResult(
                    name=f"{o.id}:mutation_probe", ok=mut_ok,
                    detail="assert-flip turns it red" if mut_ok
                    else "flipped assert STILL passes: test proves nothing"))

    # (7) copertura: ogni criterio 'proves' della fase ha >=1 obbligo
    proved_micros = {o.micro_id for o in vbp.obligations}
    uncovered = sorted({cid for m in bp.micro for cid in m.proves
                        if m.id not in proved_micros})
    checks.append(CheckResult(
        name="criteria_coverage", ok=not uncovered,
        detail=f"criteria with no obligation: {uncovered}" if uncovered
        else "all proved"))

    return GateReport(gate="oracle_qualification", target=vbp.phase_id,
                      ok=all(c.ok for c in checks), checks=checks)


def micro_gate(verdict_ok: bool, target: str,
               checks: list[CheckResult]) -> GateReport:
    """PS5.2 — involucro del verdetto di verify_subtask nel formato gate."""
    return GateReport(gate="micro", target=target, ok=verdict_ok, checks=checks)


def failure_signature(failed_checks: list[str], summary: str) -> str:
    """Firma normalizzata di un fallimento micro (per il retry gate)."""
    norm = re.sub(r"\s+", " ", summary.lower())[:100]
    return "|".join(sorted(failed_checks)) + "::" + norm


def retry_gate(prev_sig: str | None, new_sig: str) -> GateReport:
    """PS5.2 — un retry DEVE differire: stessa firma di fallimento due volte di
    fila = fotocopia vietata (il ritentare identico e' il thrashing di F3).
    REVISIONE PS5 (dal piano): si confrontano le FIRME DI FALLIMENTO consecutive
    (piu' forte del confronto tra istruzioni emendate: misura l'esito, non
    l'intenzione)."""
    identical = prev_sig is not None and prev_sig == new_sig
    return GateReport(gate="retry", target=new_sig[:80], ok=not identical,
                      checks=[CheckResult(
                          name="failure_differs", ok=not identical,
                          detail="identical failure twice in a row: retry would "
                                 "be a photocopy" if identical
                          else "new failure information present")])


def _mutation_probe(scope: Scope, content: str, test_name: str) -> bool:
    """Assert-flip: nega il primo assert del test e verifica che diventi rosso.
    Non dimostra che il test sia buono; dimostra che PUO' fallire."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False
    flipped = False
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef) and node.name == test_name):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assert) and not isinstance(sub.test,
                                                                  ast.Constant):
                    sub.test = ast.UnaryOp(op=ast.Not(), operand=sub.test)
                    flipped = True
                    break
        if flipped:
            break
    if not flipped:
        return False
    probe_name = "_rg_mutation_probe.py"
    probe_path = scope.root / probe_name
    probe_path.write_text(ast.unparse(ast.fix_missing_locations(tree)),
                          encoding="utf-8")
    try:
        code, _ = _run_probe(scope, ["pytest", "-q",
                                     f"{probe_name}::{test_name}"])
        return code != 0
    finally:
        probe_path.unlink(missing_ok=True)

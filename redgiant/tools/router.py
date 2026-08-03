"""ToolRouter: l'unico punto di esecuzione dei tool (piano F1.4, §A7).

dispatch, in ordine: tool esistente? → args validi (input_model)? →
requires_approval? → esecuzione. Un'eccezione imprevista NON uccide il task:
diventa ToolResult(ok=False, error='internal:...') — il fallimento del tool
è un dato per il modello. Tutto loggato su tool_calls, sempre.
"""

from __future__ import annotations

import json
import time
from functools import partial

from pydantic import ValidationError

from redgiant.config import Config
from redgiant.state.models import ToolCallRow
from redgiant.state.store import StateStore
from redgiant.tools import fs, proc, search, web
from redgiant.tools.base import Scope, ToolResult, ToolSpec


def default_catalog(cfg: Config, scope: Scope,
                    test_commands: dict[str, list[str]],
                    persist_test_commands=None) -> dict[str, ToolSpec]:
    rg_bin = None  # risolto lazy: non tutti i task usano search_code

    def _register(cmd_id: str, argv: list[str]) -> ToolResult:
        """F2 (richiesta utente): il modello scopre e registra i comandi di test.
        Guardia: l'eseguibile DEVE stare nella shell_whitelist umana."""
        cmd_id = cmd_id.strip()
        if not cmd_id or not argv:
            return ToolResult(ok=False, data={}, error="bad_args")
        if argv[0] not in cfg.security.shell_whitelist:
            return ToolResult(ok=False,
                              data={"whitelist": list(cfg.security.shell_whitelist)},
                              error=f"executable_not_whitelisted:{argv[0]}")
        test_commands[cmd_id] = list(argv)  # stesso dict visto da run_tests e verify
        if persist_test_commands is not None:
            persist_test_commands(dict(test_commands))
        return ToolResult(ok=True, data={"registered": {cmd_id: argv}},
                          evidence=[f"registered test command '{cmd_id}' = {argv}"])

    def _search(pattern: str, glob: str | None = None, max_results: int = 50) -> ToolResult:
        nonlocal rg_bin
        if rg_bin is None:
            try:
                rg_bin = search.resolve_ripgrep(cfg.paths.ripgrep)
            except FileNotFoundError:
                rg_bin = ""  # fallback permanente per questo catalogo
        if rg_bin:
            return search.search_code(scope, rg_bin, pattern, glob, max_results)
        return search.search_python(scope, pattern, glob, max_results)

    specs = [
        ToolSpec("read_file", "Read a slice of a text file (max 400 lines per call).",
                 "low", True, False, 10.0, fs.ReadFileArgs, partial(fs.read_file, scope)),
        ToolSpec("list_files", "List files matching a glob, relative to the task root.",
                 "low", True, False, 10.0, fs.ListFilesArgs, partial(fs.list_files, scope)),
        ToolSpec("search_code", "Search file contents with a regex (ripgrep).",
                 "low", True, False, 30.0, search.SearchCodeArgs, _search),
        ToolSpec("edit_file", "Replace an exact string in a file (must match exactly once). "
                 "PRIMARY editing tool.",
                 "medium", True, False, 10.0, fs.EditFileArgs, partial(fs.edit_file, scope)),
        ToolSpec("write_file", "Create a NEW small text file (or fully overwrite one) with "
                 "the given content.",
                 "medium", True, False, 10.0, fs.WriteFileArgs, partial(fs.write_file, scope)),
        ToolSpec("write_patch", "Apply a unified diff to one file (for multi-spot edits).",
                 "medium", True, False, 10.0, fs.WritePatchArgs, partial(fs.write_patch, scope)),
        ToolSpec("run_tests", "Run a registered test command by its cmd_id.",
                 "medium", True, False, 300.0, proc.RunTestsArgs,
                 partial(proc.run_tests, scope, test_commands, cfg.security.shell_whitelist)),
        ToolSpec("register_test_command", "Register how tests are run in this repo "
                 "(cmd_id + argv, e.g. ['pytest','-q']) after discovering it from the "
                 "project files. The executable must be whitelisted.",
                 "medium", True, False, 5.0, proc.RegisterTestCommandArgs, _register),
        ToolSpec("http_get", "Fetch a small http(s) page from a whitelisted "
                 "domain (per-task cache: the same URL returns the same copy).",
                 "medium", True, False, 30.0, web.HttpGetArgs,
                 partial(web.http_get, scope,
                         cfg.security.http_allowed_domains)),
        ToolSpec("git_status", "Show changed paths in the task repo (porcelain).",
                 "low", True, False, 30.0, proc.GitStatusArgs, partial(proc.git_status, scope)),
        ToolSpec("git_diff", "Show the unified diff against a ref (default HEAD).",
                 "low", True, False, 30.0, proc.GitDiffArgs, partial(proc.git_diff, scope)),
    ]
    # ablazione di SOLO A/B (mai in produzione): senza search_code il modello
    # deve listare e leggere file per file — misura il valore della ricerca
    from redgiant.core.ablate import worker_ablated
    if worker_ablated("search"):
        specs = [s for s in specs if s.name != "search_code"]
    return {s.name: s for s in specs}


class ToolRouter:
    def __init__(self, catalog: dict[str, ToolSpec], scope: Scope, store: StateStore) -> None:
        self.catalog = catalog
        self.scope = scope
        self.store = store

    def allowed_for(self, role: str, domain: str) -> list[ToolSpec]:
        # F1: il Worker vede tutto il catalogo del task; il restringimento per
        # ruolo/dominio arriva con i ruoli di F3+ (il campo esiste per quello).
        if role == "worker":
            return sorted(self.catalog.values(), key=lambda s: s.name)
        return []

    def render_tool_card(self, specs: list[ToolSpec]) -> str:
        from redgiant.prompts.assemble import PromptAssembler
        return PromptAssembler._tool_card(specs)

    def dispatch(self, task_id: str, subtask_id: str, name: str, args: dict) -> ToolResult:
        t0 = time.monotonic()
        spec = self.catalog.get(name)
        if spec is None:
            result = ToolResult(ok=False, data={"known": sorted(self.catalog)},
                                error="unknown_tool")
            return self._done(task_id, subtask_id, name, args, result, t0)
        # tolleranza F1.11: i modelli piccoli echeggiano il nome del tool negli args
        if args.get("tool") == name:
            args = {k: v for k, v in args.items() if k != "tool"}
        try:
            parsed = spec.input_model.model_validate(args)
        except ValidationError as e:
            result = ToolResult(ok=False, data={"detail": e.errors()[:5]}, error="bad_args")
            return self._done(task_id, subtask_id, name, args, result, t0)

        if spec.requires_approval:
            # F2.3: se l'utente ha GIA' risposto a questa identica richiesta, consumala
            answer = self.store.consume_matching_approval(
                task_id, name, json.dumps(args, sort_keys=True))
            if answer == "no":
                result = ToolResult(ok=False, data={"hint": "the user denied this "
                                                            "operation; choose another way"},
                                    error="approval_denied")
                return self._done(task_id, subtask_id, name, args, result, t0)
            if answer != "yes":
                # F2 (chiusura): consenso INFORMATO — la richiesta porta una preview
                # leggibile di cio' che verrebbe scritto, non solo il JSON grezzo.
                preview = None
                if name == "edit_file":
                    preview = ("--- da sostituire\n" + str(args.get("old_string", ""))[:400]
                               + "\n+++ con\n" + str(args.get("new_string", ""))[:400])
                elif name == "write_file":
                    preview = "contenuto completo:\n" + str(args.get("content", ""))[:600]
                elif name == "write_patch":
                    preview = str(args.get("unified_diff", ""))[:600]
                self.store.add_approval(task_id, kind="irreversible_op",
                                        payload=json.dumps({"tool": name, "args": args,
                                                            "subtask_id": subtask_id,
                                                            "preview": preview}))
                self.store.set_task_status(task_id, "blocked", actor="tool_router",
                                           error=f"awaiting approval for {name}")
                result = ToolResult(ok=False, data={}, error="awaiting_approval")
                return self._done(task_id, subtask_id, name, args, result, t0)
            # answer == "yes": si prosegue con l'esecuzione normale qui sotto

        try:
            result = spec.handler(**parsed.model_dump())
        except Exception as e:  # il task vive: il fallimento e' un dato
            result = ToolResult(ok=False, data={}, error=f"internal:{type(e).__name__}: {e}")
        return self._done(task_id, subtask_id, name, args, result, t0)

    def _done(self, task_id: str, subtask_id: str, name: str, args: dict,
              result: ToolResult, t0: float) -> ToolResult:
        self.store.log_tool_call(task_id, ToolCallRow(
            subtask_id=subtask_id, tool=name, args=args, ok=result.ok,
            evidence=result.evidence, duration_ms=(time.monotonic() - t0) * 1000))
        return result

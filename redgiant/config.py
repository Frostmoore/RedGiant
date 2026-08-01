"""Caricamento configurazione (piano F0.1, chiavi in §A6).

Merge: config/default.toml + config/profiles/<nome>.toml, override superficiale
per sezione. Una chiave sconosciuta in un TOML è un errore fatale con il nome
della chiave: gli errori di config si pagano subito, non a runtime.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

# Directory config di default: <root repo>/config (relativa a questo file:
# redgiant/config.py -> parent.parent = root). Sovrascrivibile in Config.load.
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

# Schema delle sezioni/chiavi ammesse: la validazione "chiave sconosciuta"
# confronta contro questo. Aggiungere una chiave = aggiungerla anche qui.
_KNOWN_KEYS: dict[str, set[str]] = {
    "llm": {"base_url", "ctx_size", "timeout_s", "temperature", "max_tokens_default"},
    "paths": {"db", "models_dir", "tasks_dir", "slots_dir", "ripgrep"},
    "budget": {"max_total_tokens", "max_tool_calls", "max_retries_per_subtask", "max_wall_s"},
    "worker": {"max_steps"},
    "web": {"host", "port"},
    "security": {"writable_globs", "shell_whitelist"},
    "eval": {"tasks_dir"},
}


@dataclass(frozen=True)
class LlmProfileCfg:
    base_url: str
    ctx_size: int
    timeout_s: float
    temperature: float
    max_tokens_default: int


@dataclass(frozen=True)
class PathsCfg:
    db: Path
    models_dir: Path
    tasks_dir: Path
    slots_dir: Path
    ripgrep: str


@dataclass(frozen=True)
class BudgetCfg:
    max_total_tokens: int
    max_tool_calls: int
    max_retries_per_subtask: int
    max_wall_s: int


@dataclass(frozen=True)
class WebCfg:
    host: str
    port: int


@dataclass(frozen=True)
class SecurityCfg:
    writable_globs: tuple[str, ...]
    shell_whitelist: tuple[str, ...]


@dataclass(frozen=True)
class Config:
    profile_name: str
    llm: LlmProfileCfg
    paths: PathsCfg
    budget: BudgetCfg
    web: WebCfg
    security: SecurityCfg
    worker_max_steps: int
    eval_tasks_dir: Path

    @classmethod
    def load(cls, profile_name: str, config_dir: Path | None = None) -> "Config":
        cfg_dir = config_dir if config_dir is not None else _DEFAULT_CONFIG_DIR
        default_path = cfg_dir / "default.toml"
        profile_path = cfg_dir / "profiles" / f"{profile_name}.toml"
        if not default_path.is_file():
            raise FileNotFoundError(f"config file not found: {default_path}")
        if not profile_path.is_file():
            raise FileNotFoundError(
                f"unknown profile '{profile_name}': {profile_path} does not exist"
            )
        merged = _read_toml(default_path)
        for section, values in _read_toml(profile_path).items():
            merged.setdefault(section, {}).update(values)

        llm = merged["llm"]
        paths = merged["paths"]
        budget = merged["budget"]
        worker = merged["worker"]
        web = merged["web"]
        security = merged["security"]
        eval_ = merged["eval"]
        return cls(
            profile_name=profile_name,
            llm=LlmProfileCfg(
                base_url=str(llm["base_url"]),
                ctx_size=int(llm["ctx_size"]),
                timeout_s=float(llm["timeout_s"]),
                temperature=float(llm["temperature"]),
                max_tokens_default=int(llm["max_tokens_default"]),
            ),
            paths=PathsCfg(
                db=Path(paths["db"]),
                models_dir=Path(paths["models_dir"]),
                tasks_dir=Path(paths["tasks_dir"]),
                slots_dir=Path(paths["slots_dir"]),
                ripgrep=str(paths["ripgrep"]),
            ),
            budget=BudgetCfg(
                max_total_tokens=int(budget["max_total_tokens"]),
                max_tool_calls=int(budget["max_tool_calls"]),
                max_retries_per_subtask=int(budget["max_retries_per_subtask"]),
                max_wall_s=int(budget["max_wall_s"]),
            ),
            web=WebCfg(host=str(web["host"]), port=int(web["port"])),
            security=SecurityCfg(
                writable_globs=tuple(security["writable_globs"]),
                shell_whitelist=tuple(security["shell_whitelist"]),
            ),
            worker_max_steps=int(worker["max_steps"]),
            eval_tasks_dir=Path(eval_["tasks_dir"]),
        )


def _read_toml(path: Path) -> dict[str, dict]:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    for section, values in data.items():
        if section not in _KNOWN_KEYS:
            raise ValueError(f"{path.name}: unknown config section [{section}]")
        if not isinstance(values, dict):
            raise ValueError(f"{path.name}: top-level key '{section}' must be a section")
        for key in values:
            if key not in _KNOWN_KEYS[section]:
                raise ValueError(f"{path.name}: unknown config key '{section}.{key}'")
    return data

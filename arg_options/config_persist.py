"""Guardar y cargar YAML de cadena y screening desde la TUI (sin perder el resto del archivo)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from arg_options.settings import load_yaml


def resolve_settings_yaml_path() -> Path:
    return Path(os.environ.get("ARG_OPTIONS_CONFIG", "config/settings.yaml")).expanduser()


def resolve_screening_path_for_settings(paths_dict: dict[str, Any] | None) -> Path:
    if paths_dict and paths_dict.get("screening"):
        return Path(str(paths_dict["screening"])).expanduser()
    env = os.environ.get("ARG_OPTIONS_SCREENING")
    if env:
        return Path(env).expanduser()
    return Path("config/screening.yaml")


def save_chain_profile(path: Path, option_root: str, spot_ticker: str) -> None:
    """Actualiza underlying_spot y chain.option_roots (un solo root) en settings.yaml."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_yaml(path)
    root = option_root.strip().upper()
    spot = spot_ticker.strip().upper()
    if not root or not spot:
        raise ValueError("Raíz y spot no pueden estar vacíos.")
    data.setdefault("underlying_spot", {})
    data["underlying_spot"][root] = spot
    data.setdefault("chain", {})["option_roots"] = [root]
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def save_screening_file(path: Path, rules: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(dict(rules), f, default_flow_style=False, allow_unicode=True, sort_keys=False)

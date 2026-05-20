from __future__ import annotations

from pathlib import Path

import yaml


def resolve_project_root() -> Path:
    import os as _os

    root = _os.environ.get("ARGOPTIONS_ROOT")
    if root:
        return Path(root).resolve()

    current = Path(__file__).resolve().parent
    for parent in current.parents:
        if (parent / ".env_test").exists():
            return parent
    return current.parents[-2]


def resolve_settings_yaml_path() -> Path:
    return resolve_project_root() / "config" / "settings.yaml"


def resolve_screening_path_for_settings(paths_config: dict) -> Path:
    rel = paths_config.get("screening_file", "config/screening.yaml")
    return resolve_project_root() / rel


def save_chain_profile(settings_path: str | Path, root: str, spot: str) -> None:
    p = Path(settings_path)
    data = load_yaml(p)
    chain = data.setdefault("chain", {})
    roots = chain.setdefault("option_roots", [])
    if root not in roots:
        roots.append(root)
    chain["underlying_spot"] = float(spot)
    _write_yaml(p, data)


def save_screening_file(path: str | Path, rules: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _write_yaml(p, rules)


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml(path: str | Path, data: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

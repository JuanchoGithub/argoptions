from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from arg_options.config.config_persist import resolve_project_root, load_yaml, _write_yaml
from arg_options.db import save_strategy, get_strategies


class ExecutionMode(Enum):
    SEMI_AUTO = "semi-auto"
    AUTO = "auto"


class StrategyType(Enum):
    MARIPOSA = "mariposa"
    IRON_CONDOR = "iron_condor"
    CREDIT_SPREAD = "credit_spread"
    CALENDAR = "calendar"
    SYNTHETIC = "synthetic"


@dataclass
class StrategyConfig:
    name: str
    type: StrategyType
    root: str
    spot_ticker: str
    enabled: bool = True
    mode: ExecutionMode = ExecutionMode.SEMI_AUTO
    min_dte: int = 7
    max_dte: int = 45
    min_volume: int = 0
    max_spread_pct: float = 35.0
    min_abs_delta: float = 0.0
    max_abs_delta: float = 0.99
    max_risk_ars: float = 50000.0
    max_contracts: int = 10
    target_credit_pct: float = 0.0
    target_debt_pct: float = 0.0
    run_interval_minutes: int = 60
    active_trading_hours: tuple = (10, 17)
    require_confirmation: bool = True


def _get_yaml_path() -> Path:
    return resolve_project_root() / "config" / "strategies.yaml"


def _load_strategies_yaml_data() -> list[dict]:
    path = _get_yaml_path()
    data = load_yaml(path)
    return data.get("strategies", [])


def _save_strategies_yaml_data(strategies: list[dict]) -> None:
    path = _get_yaml_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_yaml(path, {"strategies": strategies})


def strategy_from_dict(data: dict) -> StrategyConfig:
    type_val = data.get("type", "mariposa")
    if isinstance(type_val, StrategyType):
        type_val = type_val.value
    mode_val = data.get("mode", "semi-auto")
    if isinstance(mode_val, ExecutionMode):
        mode_val = mode_val.value
    active_hours = data.get("active_trading_hours", (10, 17))
    if isinstance(active_hours, list):
        active_hours = tuple(active_hours)
    return StrategyConfig(
        name=data["name"],
        type=StrategyType(type_val),
        root=data["root"],
        spot_ticker=data["spot_ticker"],
        enabled=bool(data.get("enabled", True)),
        mode=ExecutionMode(mode_val),
        min_dte=int(data.get("min_dte", 7)),
        max_dte=int(data.get("max_dte", 45)),
        min_volume=int(data.get("min_volume", 0)),
        max_spread_pct=float(data.get("max_spread_pct", 35.0)),
        min_abs_delta=float(data.get("min_abs_delta", 0.0)),
        max_abs_delta=float(data.get("max_abs_delta", 0.99)),
        max_risk_ars=float(data.get("max_risk_ars", 50000.0)),
        max_contracts=int(data.get("max_contracts", 10)),
        target_credit_pct=float(data.get("target_credit_pct", 0.0)),
        target_debt_pct=float(data.get("target_debt_pct", 0.0)),
        run_interval_minutes=int(data.get("run_interval_minutes", 60)),
        active_trading_hours=active_hours,
        require_confirmation=bool(data.get("require_confirmation", True)),
    )


def _strategy_from_db_row(row: dict) -> StrategyConfig:
    config = row.get("config", {})
    if isinstance(config, dict):
        merged = dict(config)
        merged.setdefault("name", row.get("name", ""))
        merged.setdefault("type", row.get("type", "mariposa"))
        return strategy_from_dict(merged)
    base = {
        "name": row.get("name", ""),
        "type": row.get("type", "mariposa"),
        "root": "",
        "spot_ticker": "",
    }
    return strategy_from_dict(base)


def strategy_to_dict(config: StrategyConfig) -> dict:
    d = asdict(config)
    d["type"] = config.type.value
    d["mode"] = config.mode.value
    if isinstance(d.get("active_trading_hours"), tuple):
        d["active_trading_hours"] = list(d["active_trading_hours"])
    return d


def load_strategies() -> list[StrategyConfig]:
    try:
        yaml_data = _load_strategies_yaml_data()
        if yaml_data:
            return [strategy_from_dict(s) for s in yaml_data]
    except Exception as e:
        logging.warning("Failed to load strategies from YAML: %s", e)
    try:
        db_rows = get_strategies(enabled_only=False)
        return [_strategy_from_db_row(r) for r in db_rows]
    except Exception as e:
        logging.warning("Failed to load strategies from DB: %s", e)
    return []


def save_strategy_config(config: StrategyConfig) -> int:
    serialized = strategy_to_dict(config)
    db_id = save_strategy(config.name, config.type.value, serialized)
    try:
        existing = _load_strategies_yaml_data()
        updated = False
        for i, s in enumerate(existing):
            if s.get("name") == config.name:
                existing[i] = serialized
                updated = True
                break
        if not updated:
            existing.append(serialized)
        _save_strategies_yaml_data(existing)
    except Exception as e:
        logging.warning("Failed to save strategy to YAML: %s", e)
    return db_id


def get_enabled_strategies() -> list[StrategyConfig]:
    return [s for s in load_strategies() if s.enabled]

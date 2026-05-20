from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from arg_options.broker import create_broker
from arg_options.broker.interfaces import BrokerConfig
from arg_options.config.config_persist import (
    resolve_project_root,
    resolve_screening_path_for_settings,
)
from arg_options.core.chain import build_full_chain, get_latest_chain, persist_chain

logger = logging.getLogger(__name__)

DEFAULT_RULES: dict = {
    "dte_min": 30,
    "dte_max": 180,
    "volume_min": 100,
    "max_spread_pct": 0.15,
    "delta_min": 0.1,
    "delta_max": 0.9,
}


def load_screening_config(
    path: str | None = None,
    settings: Optional[BrokerConfig] = None,
) -> dict:
    if path is not None:
        p = Path(path)
    else:
        p = resolve_project_root() / "config" / "screening.yaml"

    if not p.exists():
        logger.warning("Screening config not found at %s, using defaults", p)
        return dict(DEFAULT_RULES)

    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    screening = data.get("screening", data)
    rules = dict(DEFAULT_RULES)
    rules.update({k: v for k, v in screening.items() if k in DEFAULT_RULES})
    return rules


def run_screen(
    settings: BrokerConfig,
    rules_override: dict | None = None,
) -> pd.DataFrame:
    config = settings
    rules = load_screening_config(settings=config)
    if rules_override:
        rules.update(rules_override)

    broker = create_broker(config)
    broker.connect()

    try:
        rows = build_full_chain(broker, config)
    finally:
        try:
            broker.disconnect()
        except Exception:
            pass

    if not rows:
        logger.info("Chain is empty, no screening possible")
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    dte_min = rules.get("dte_min", 0)
    dte_max = rules.get("dte_max", 9999)
    volume_min = rules.get("volume_min", 0)
    max_spread_pct = rules.get("max_spread_pct", 1.0)
    delta_min = rules.get("delta_min", -1.0)
    delta_max = rules.get("delta_max", 1.0)

    mask = (
        (df["dte"] >= dte_min)
        & (df["dte"] <= dte_max)
        & (df["volume"] >= volume_min)
        & (df["spread_pct"] <= max_spread_pct)
        & (df["delta"] >= delta_min)
        & (df["delta"] <= delta_max)
    )

    filtered = df[mask].copy()
    filtered = filtered.sort_values(["expiry", "strike", "right"])
    filtered = filtered.reset_index(drop=True)

    logger.info("Screen returned %d / %d rows", len(filtered), len(df))
    return filtered


def get_latest_snapshot_rows(settings: BrokerConfig) -> list[dict]:
    return get_latest_chain(settings)


def explain_why_screen_empty(
    latest_rows: list[dict],
    rules: dict,
) -> str:
    if not latest_rows:
        return "No option chain data available. Run a chain build first."

    df = pd.DataFrame(latest_rows)
    reasons: list[str] = []

    dte_min, dte_max = rules.get("dte_min", 0), rules.get("dte_max", 9999)
    vol_min = rules.get("volume_min", 0)
    spread_max = rules.get("max_spread_pct", 1.0)
    delta_min, delta_max = rules.get("delta_min", -1.0), rules.get("delta_max", 1.0)

    total = len(df)

    if dte_min > 0 or dte_max < 9999:
        after = len(df[(df["dte"] >= dte_min) & (df["dte"] <= dte_max)])
        if after == 0:
            reasons.append(
                f"No options with DTE between {dte_min} and {dte_max} "
                f"(min DTE={int(df['dte'].min())}, max DTE={int(df['dte'].max())})"
            )

    if vol_min > 0:
        after = len(df[df["volume"] >= vol_min])
        if after == 0:
            reasons.append(
                f"No options with volume >= {vol_min} "
                f"(max volume={int(df['volume'].max())})"
            )

    if spread_max < 1.0:
        after = len(df[df["spread_pct"] <= spread_max])
        if after == 0:
            reasons.append(
                f"No options with spread <= {spread_max:.0%} "
                f"(min spread={df['spread_pct'].min():.2%})"
            )

    after = len(
        df[(df["delta"] >= delta_min) & (df["delta"] <= delta_max)]
    )
    if after == 0:
        reasons.append(
            f"No options with delta between {delta_min} and {delta_max} "
            f"(min delta={df['delta'].min():.3f}, max delta={df['delta'].max():.3f})"
        )

    if not reasons:
        reasons.append(
            f"All filters pass but no rows returned (check underlying data: {total} rows in chain)"
        )

    return "Screening returned zero results. " + " ".join(reasons)

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd

from arg_options.broker.interfaces import Broker, BrokerConfig
from arg_options.config.config_persist import (
    load_yaml,
    resolve_project_root,
    resolve_settings_yaml_path,
)
from arg_options.core.greeks import all_greeks, iv
from arg_options.core.instruments import (
    get_spot_price,
    parse_ticker_parts,
    search_instruments,
)

logger = logging.getLogger(__name__)


def _get_option_roots(config: BrokerConfig) -> list[str]:
    yaml_path = resolve_settings_yaml_path()
    data = load_yaml(yaml_path)
    return data.get("chain", {}).get("option_roots", [])


def _load_underlying_map(data: dict | None = None) -> dict[str, str]:
    if data is None:
        yaml_path = resolve_settings_yaml_path()
        data = load_yaml(yaml_path)
    return data.get("underlying_spot", {})


def _root_to_underlying(root: str) -> str:
    data = load_yaml(resolve_settings_yaml_path())
    mapping = _load_underlying_map(data)
    legacy: dict[str, str] = {"GFG": "GGAL", "YPF": "YPFD", "PMP": "PAMP", "BMA": "BMA"}
    for k, v in legacy.items():
        mapping.setdefault(k, v)
    return mapping.get(root, root)


def build_full_chain(
    broker: Broker,
    config: BrokerConfig,
) -> list[dict]:
    roots = _get_option_roots(config)
    if not roots:
        logger.warning("No option_roots configured in settings.yaml chain")
        return []

    all_rows: list[dict] = []
    today = date.today()

    for root in roots:
        logger.info("Building chain for root: %s", root)
        instruments = search_instruments(broker, root)
        if not instruments:
            logger.warning("No instruments found for root: %s", root)
            continue

        underlying = _root_to_underlying(root)
        spot = get_spot_price(broker, underlying)
        if spot is None:
            logger.warning("Could not resolve spot price for %s", underlying)
            continue

        for instr in instruments:
            parsed = parse_ticker_parts(instr.ticker)
            if parsed is None:
                continue

            opt_root, raw_strike, right, expiry_yyyymmdd = parsed

            try:
                expiry = datetime.strptime(expiry_yyyymmdd, "%Y%m%d").date()
                dte = max((expiry - today).days, 0)
                T = max(dte / 365.0, 1e-6)
            except (ValueError, OverflowError):
                continue

            book = None
            current = None
            try:
                book = broker.market_data.get_book(
                    instr.ticker, "OPCIONES", "A-48HS",
                )
            except Exception:
                pass
            try:
                current = broker.market_data.get_current(
                    instr.ticker, "OPCIONES", "A-48HS",
                )
            except Exception:
                pass

            bid = book.bids[-1].price if (book and book.bids) else 0.0
            ask = book.offers[0].price if (book and book.offers) else 0.0
            last = current.price if (current and current.price) else 0.0
            volume = current.volume if current else 0.0

            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else last

            strike = raw_strike / 100.0

            greeks: dict[str, float] = {}
            if mid > 0 and T > 0:
                try:
                    implied_vol = iv(spot, strike, T, config.risk_free_rate, mid, right)
                    greeks = all_greeks(spot, strike, T, config.risk_free_rate, implied_vol, right)
                    greeks["iv"] = implied_vol
                except Exception:
                    greeks = {"iv": 0.0, "delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
            else:
                greeks = {"iv": 0.0, "delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}

            sp = (ask - bid) / mid if mid > 0 else 0.0

            all_rows.append({
                "ticker": instr.ticker,
                "root": opt_root,
                "strike": strike,
                "right": "CALL" if right == "C" else "PUT",
                "expiry": expiry_yyyymmdd,
                "dte": dte,
                "bid": bid,
                "ask": ask,
                "last": last,
                "mid": mid,
                "volume": volume,
                "open_interest": 0.0,
                "spread_pct": round(sp, 6),
                "spot": spot,
                "iv": round(greeks.get("iv", 0.0), 6),
                "delta": round(greeks.get("delta", 0.0), 6),
                "gamma": round(greeks.get("gamma", 0.0), 6),
                "theta": round(greeks.get("theta", 0.0), 6),
                "vega": round(greeks.get("vega", 0.0), 6),
                "rho": round(greeks.get("rho", 0.0), 6),
                "timestamp": datetime.now().isoformat(),
            })

    logger.info("Chain built: %d rows across %d root(s)", len(all_rows), len(roots))
    return all_rows


def persist_chain(
    rows: list[dict],
    config: BrokerConfig,
    export_parquet: bool = False,
) -> tuple[int, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not rows:
        logger.warning("No rows to persist")
        return 0, timestamp

    chains_dir = resolve_project_root() / "data" / "chains"
    chains_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows)
    path = chains_dir / f"chain_{timestamp}.parquet"
    df.to_parquet(str(path), index=False)
    logger.info("Persisted %d rows to %s", len(rows), path)
    return len(rows), timestamp


def get_latest_chain(config: BrokerConfig) -> list[dict]:
    chains_dir = resolve_project_root() / "data" / "chains"
    if not chains_dir.exists():
        return []

    files = sorted(chains_dir.glob("chain_*.parquet"), reverse=True)
    if not files:
        return []

    df = pd.read_parquet(str(files[0]))
    return df.to_dict(orient="records")

"""Armar cadena de opciones, cotizaciones y persistencia."""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from ppi_client.ppi import PPI

from arg_options import db as dbmod
from arg_options.greeks import enrich_row_with_greeks
from arg_options.instruments import normalize_instrument_row
from arg_options.ppi_client import with_retries
from arg_options.settings import AppSettings

logger = logging.getLogger(__name__)


def _mid_from_book(book: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    bids = book.get("bids") or []
    offers = book.get("offers") or []
    best_bid = float(bids[0]["price"]) if bids else None
    best_ask = float(offers[0]["price"]) if offers else None
    if best_bid is not None and best_ask is not None:
        return best_bid, best_ask, (best_bid + best_ask) / 2
    if best_bid is not None:
        return best_bid, best_ask, best_bid
    if best_ask is not None:
        return best_bid, best_ask, best_ask
    return best_bid, best_ask, None


def fetch_spot_price(ppi: PPI, ticker: str, settings: AppSettings) -> float | None:
    ppi_cfg = settings.ppi
    inst = ppi_cfg.get("instrument_type_equity", "ACCIONES")
    settle = ppi_cfg.get("default_settlement", "A-48HS")
    try:
        q = with_retries(lambda: ppi.marketdata.current(ticker, inst, settle))
        p = q.get("price")
        return float(p) if p is not None else None
    except Exception as e:
        logger.error("No se pudo obtener spot %s: %s", ticker, e)
        return None


def fetch_option_quotes(
    ppi: PPI,
    ticker: str,
    settings: AppSettings,
) -> dict[str, float | None]:
    ppi_cfg = settings.ppi
    opt_type = ppi_cfg.get("instrument_type_options", "OPCIONES")
    settle = ppi_cfg.get("default_settlement", "A-48HS")
    bid = ask = mid = last = vol = None
    try:
        book = with_retries(lambda: ppi.marketdata.book(ticker, opt_type, settle))
        bid, ask, mid = _mid_from_book(book)
        vol = None
    except Exception as e:
        logger.debug("book() falló para %s: %s", ticker, e)
    last_f: float | None = None
    try:
        cur = with_retries(lambda: ppi.marketdata.current(ticker, opt_type, settle))
        last = cur.get("price")
        last_f = float(last) if last is not None else None
        vol_raw = cur.get("volume")
        vol = float(vol_raw) if vol_raw is not None else None
        if mid is None and last_f is not None:
            mid = last_f
    except Exception as e:
        logger.debug("current() falló para %s: %s", ticker, e)
    return {"bid": bid, "ask": ask, "mid": mid, "last": last_f, "volume": vol}


def build_chain_for_root(
    ppi: PPI,
    option_root: str,
    settings: AppSettings,
    throttle_s: float = 0.15,
) -> list[dict[str, Any]]:
    ppi_cfg = settings.ppi
    market = ppi_cfg.get("market", "Byma")
    opt_type = ppi_cfg.get("instrument_type_options", "OPCIONES")
    settle = ppi_cfg.get("default_settlement", "A-48HS")

    raw = with_retries(lambda: ppi.marketdata.search_instrument(option_root, "", market, opt_type))
    rows: list[dict[str, Any]] = []
    if not raw:
        return rows
    spot_cache: dict[str, float | None] = {}
    for item in raw:
        norm = normalize_instrument_row(item, settings.underlying_spot)
        if norm is None:
            continue
        ticker = norm["ticker"]
        quotes = fetch_option_quotes(ppi, ticker, settings)
        norm["bid"] = quotes["bid"]
        norm["ask"] = quotes["ask"]
        norm["mid"] = quotes["mid"]
        norm["last"] = quotes.get("last")
        norm["volume"] = quotes["volume"]
        norm["settlement"] = settle

        spot_tk = norm.get("underlying_spot_ticker")
        if spot_tk:
            if spot_tk not in spot_cache:
                spot_cache[spot_tk] = fetch_spot_price(ppi, spot_tk, settings)
                time.sleep(throttle_s)
            spot = spot_cache[spot_tk]
        else:
            spot = None
        enrich_row_with_greeks(norm, spot, settings.risk_free_rate, as_of=date.today())
        rows.append(norm)
        time.sleep(throttle_s)
    return rows


def build_full_chain(ppi: PPI, settings: AppSettings) -> list[dict[str, Any]]:
    roots = settings.chain_config.get("option_roots") or []
    out: list[dict[str, Any]] = []
    for r in roots:
        out.extend(build_chain_for_root(ppi, str(r).strip().upper(), settings))
    return out


def persist_chain(
    rows: list[dict[str, Any]],
    settings: AppSettings,
    export_parquet: bool = False,
) -> tuple[int, str]:
    conn = dbmod.connect(settings.db_path())
    ts = dbmod.utc_now_iso()
    n = dbmod.insert_snapshots(conn, rows, ts=ts)
    conn.close()
    pq = settings.parquet_export_path()
    if export_parquet and pq and rows:
        pq.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(pq, index=False)
    return n, ts


def load_last_snapshots(settings: AppSettings, limit: int = 5000) -> pd.DataFrame:
    conn = dbmod.connect(settings.db_path())
    df = pd.read_sql_query(
        "SELECT * FROM chain_snapshots ORDER BY ts DESC, ticker ASC LIMIT ?",
        conn,
        params=(limit,),
    )
    conn.close()
    return df

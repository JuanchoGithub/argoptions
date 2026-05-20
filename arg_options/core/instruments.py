from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from arg_options.broker.interfaces import Broker
from arg_options.broker.models import Instrument

logger = logging.getLogger(__name__)

OPTION_TICKER_RE = re.compile(r"(\w{2,4})(\d{6})([CP])(\d+)")
_BYMA_TICKER_RE = re.compile(r"^([A-Z0-9]{2,})([CV])(\d+)([A-Z]{1,2})(\d{2})?$")

_MONTH_CODE_TO_MONTH: dict[str, int] = {
    "EN": 1, "FE": 2, "MA": 3, "AB": 4,
    "MY": 5, "JU": 6, "JL": 7, "AG": 8,
    "SE": 9, "OC": 10, "NO": 11, "DI": 12,
    "E": 1, "F": 2, "M": 3, "A": 4, "Y": 5,
    "J": 6, "L": 7, "G": 8, "S": 9, "O": 10,
    "N": 11, "D": 12,
}

_HARDCODED_ROOT_MAP: dict[str, str] = {
    "GGAL": "GFG",
    "YP": "YPF",
    "YPFD": "YPF",
    "PAMP": "PMP",
    "BMA": "BMA",
}


def resolve_option_root(root: str, spot: str = "") -> str:
    mapping = dict(_HARDCODED_ROOT_MAP)
    try:
        from arg_options.config.config_persist import load_yaml, resolve_settings_yaml_path
        data = load_yaml(resolve_settings_yaml_path())
        yaml_map = data.get("underlying_spot", {})
        for root_k, stock_v in yaml_map.items():
            mapping[stock_v] = root_k
    except Exception:
        pass
    return mapping.get(root, root)


def search_instruments(
    broker: Broker,
    ticker: str,
    instrument_type: str = "OPCIONES",
    market: str = "BYMA",
) -> list[Instrument]:
    return broker.market_data.search_instruments(
        ticker=ticker,
        instrument_type=instrument_type,
        market=market,
    )


def get_spot_price(broker: Broker, ticker: str) -> float | None:
    for settlement in ("A-48HS", "INMEDIATA"):
        try:
            data = broker.market_data.get_current(
                ticker=ticker,
                instrument_type="ACCIONES",
                settlement=settlement,
            )
            if data is not None and data.price:
                return float(data.price)
        except Exception:
            continue
    return None


def _third_thursday(year: int, month: int) -> date:
    first = date(year, month, 1)
    days_to_first_thu = (3 - first.weekday()) % 7
    first_thu = first + timedelta(days=days_to_first_thu)
    return first_thu + timedelta(weeks=2)


def _parse_byma_format(ticker: str) -> tuple[str, float, str, str] | None:
    m = _BYMA_TICKER_RE.match(ticker.upper())
    if not m:
        return None
    root, cv, strike_str, month_code, yy = m.groups()
    month = _MONTH_CODE_TO_MONTH.get(month_code)
    if month is None:
        return None
    year = date.today().year
    if yy:
        year = 2000 + int(yy) if int(yy) < 70 else 1900 + int(yy)
    try:
        strike = float(strike_str)
    except ValueError:
        return None
    right = "C" if cv == "C" else "P"
    exp = _third_thursday(year, month)
    expiry_yyyymmdd = exp.isoformat().replace("-", "")
    return root, strike, right, expiry_yyyymmdd


def parse_ticker_parts(ticker: str) -> tuple[str, float, str, str] | None:
    m = OPTION_TICKER_RE.match(ticker.upper())
    if m:
        root, expiry_digits, right, strike_str = m.groups()
        try:
            strike = float(strike_str)
        except ValueError:
            return None
        try:
            yy, mm, dd = int(expiry_digits[0:2]), int(expiry_digits[2:4]), int(expiry_digits[4:6])
            year = 2000 + yy if yy < 70 else 1900 + yy
            expiry_yyyymmdd = date(year, mm, dd).isoformat().replace("-", "")
        except (ValueError, IndexError):
            return None
        return root, strike, right, expiry_yyyymmdd
    return _parse_byma_format(ticker)

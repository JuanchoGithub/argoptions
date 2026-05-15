"""Parseo de tickers de opciones BYMA y modelo interno."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

# Códigos de mes usados en tickers BYMA.
# 1 letra (oficial BYMA) para strikes altos, 2 letras (PPI) para strikes bajos.
MONTH_SUFFIX_TO_MONTH: dict[str, int] = {
    "EN": 1,  "FE": 2,  "MA": 3,  "AB": 4,
    "MY": 5,  "JU": 6,  "JL": 7,  "AG": 8,
    "SE": 9,  "OC": 10, "NO": 11, "DI": 12,
    "E": 1, "F": 2, "M": 3, "A": 4, "Y": 5,
    "J": 6, "L": 7, "G": 8, "S": 9, "O": 10,
    "N": 11, "D": 12,
}

# Patrón: GFGC2800MY, GFGC10200J, GGALV1500OC24 (1 o 2 letras para el mes + año opcional)
_TICKER_RE = re.compile(
    r"^([A-Z0-9]+)(C|V)(\d+)([A-Z]{1,2})(\d{2})?$",
    re.IGNORECASE,
)


def third_thursday(year: int, month: int) -> date:
    first = date(year, month, 1)
    days_to_first_thu = (3 - first.weekday()) % 7
    first_thu = first + timedelta(days=days_to_first_thu)
    return first_thu + timedelta(weeks=2)


@dataclass(frozen=True)
class ParsedOption:
    option_root: str
    right: str  # "C" or "P"
    strike: float
    month_code: str
    year: int
    expiry: date
    """Vencimiento BYMA habitual: tercer jueves del mes (aproximación)."""


def parse_byma_option_ticker(ticker: str, reference_year: int | None = None) -> ParsedOption | None:
    """
    Interpreta tickers estilo GFGC2800MY según documentación pública de brokers.
    Si falla el parseo, devuelve None.
    """
    m = _TICKER_RE.match(ticker.strip().upper())
    if not m:
        return None
    root, cv, strike_s, month_code, yy = m.groups()
    month = MONTH_SUFFIX_TO_MONTH.get(month_code.upper())
    if month is None:
        return None
    year = int(yy) + 2000 if yy else (reference_year or date.today().year)
    if yy is None and reference_year is None:
        # Si estamos después del vencimiento del año corriente, BYMA suele rotar serie;
        # el caller puede pasar reference_year explícito.
        pass
    strike = float(strike_s)
    right = "P" if cv.upper() == "V" else "C"
    exp = third_thursday(year, month)
    return ParsedOption(
        option_root=root,
        right=right,
        strike=strike,
        month_code=month_code.upper(),
        year=year,
        expiry=exp,
    )


def spot_ticker_for_root(option_root: str, underlying_spot: dict[str, str]) -> str | None:
    return underlying_spot.get(option_root)


def normalize_instrument_row(
    row: dict[str, Any],
    underlying_spot: dict[str, str],
) -> dict[str, Any] | None:
    """
    Convierte un dict devuelto por search_instrument en un registro enriquecido
    o None si no es parseable como opción BYMA clásica.
    """
    ticker = (row.get("ticker") or "").strip().upper()
    if not ticker:
        return None
    parsed = parse_byma_option_ticker(ticker)
    if parsed is None:
        return None
    spot = spot_ticker_for_root(parsed.option_root, underlying_spot)
    return {
        "ticker": ticker,
        "description": row.get("description"),
        "currency": row.get("currency"),
        "type": row.get("type"),
        "market": row.get("market"),
        "option_root": parsed.option_root,
        "underlying_spot_ticker": spot,
        "right": parsed.right,
        "strike": parsed.strike,
        "expiry": parsed.expiry.isoformat(),
        "month_code": parsed.month_code,
    }

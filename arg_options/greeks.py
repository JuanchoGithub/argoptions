"""Black–Scholes europeo, IV implícita y griegos."""

from __future__ import annotations

import math
from datetime import date

from scipy.optimize import brentq
from scipy.stats import norm


def _d1_d2(
    spot: float,
    strike: float,
    rate: float,
    div_yield: float,
    vol: float,
    t: float,
) -> tuple[float, float]:
    if t <= 0 or vol <= 0:
        raise ValueError("t y vol deben ser positivos")
    sig_sqrt_t = vol * math.sqrt(t)
    d1 = (
        math.log(spot / strike) + (rate - div_yield + 0.5 * vol * vol) * t
    ) / sig_sqrt_t
    d2 = d1 - sig_sqrt_t
    return d1, d2


def bs_price(
    right: str,
    spot: float,
    strike: float,
    rate: float,
    div_yield: float,
    vol: float,
    t: float,
) -> float:
    """Prima por unidad nominal (no multiplicada por lote)."""
    d1, d2 = _d1_d2(spot, strike, rate, div_yield, vol, t)
    df_r = math.exp(-rate * t)
    df_q = math.exp(-div_yield * t)
    if right.upper() == "C":
        return spot * df_q * norm.cdf(d1) - strike * df_r * norm.cdf(d2)
    if right.upper() == "P":
        return strike * df_r * norm.cdf(-d2) - spot * df_q * norm.cdf(-d1)
    raise ValueError("right debe ser C o P")


def bs_greeks(
    right: str,
    spot: float,
    strike: float,
    rate: float,
    div_yield: float,
    vol: float,
    t: float,
) -> dict[str, float]:
    """Griegos por unidad nominal."""
    d1, d2 = _d1_d2(spot, strike, rate, div_yield, vol, t)
    df_r = math.exp(-rate * t)
    df_q = math.exp(-div_yield * t)
    pdf_d1 = norm.pdf(d1)
    sqrt_t = math.sqrt(t)
    theta_common = -(spot * df_q * pdf_d1 * vol) / (2 * sqrt_t)
    if right.upper() == "C":
        delta = df_q * norm.cdf(d1)
        gamma = df_q * pdf_d1 / (spot * vol * sqrt_t)
        vega = spot * df_q * pdf_d1 * sqrt_t
        theta = (
            theta_common
            - rate * strike * df_r * norm.cdf(d2)
            + div_yield * spot * df_q * norm.cdf(d1)
        )
    elif right.upper() == "P":
        delta = df_q * (norm.cdf(d1) - 1)
        gamma = df_q * pdf_d1 / (spot * vol * sqrt_t)
        vega = spot * df_q * pdf_d1 * sqrt_t
        theta = (
            theta_common
            + rate * strike * df_r * norm.cdf(-d2)
            - div_yield * spot * df_q * norm.cdf(-d1)
        )
    else:
        raise ValueError("right debe ser C o P")
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta}


def year_fraction_to_expiry(expiry: date, as_of: date | None = None) -> float:
    as_of = as_of or date.today()
    days = (expiry - as_of).days
    return max(days, 0) / 365.25


def implied_vol(
    right: str,
    spot: float,
    strike: float,
    rate: float,
    div_yield: float,
    market_price: float,
    t: float,
    lo: float = 1e-6,
    hi: float = 5.0,
) -> float | None:
    if market_price <= 0 or t <= 0 or spot <= 0 or strike <= 0:
        return None

    def f(sig: float) -> float:
        return bs_price(right, spot, strike, rate, div_yield, sig, t) - market_price

    intrinsic = max(0.0, spot - strike) if right.upper() == "C" else max(0.0, strike - spot)
    if market_price + 1e-9 < intrinsic * math.exp(-div_yield * t) * 0.999:
        return None

    try:
        return float(brentq(f, lo, hi, maxiter=80))
    except ValueError:
        return None


def enrich_row_with_greeks(
    row: dict,
    spot: float | None,
    rate: float,
    div_yield: float = 0.0,
    as_of: date | None = None,
) -> dict:
    if spot is None:
        row.update({"iv": None, "delta": None, "gamma": None, "vega": None, "theta": None})
        return row
    expiry = date.fromisoformat(row["expiry"]) if isinstance(row.get("expiry"), str) else row.get("expiry")
    if not isinstance(expiry, date):
        row.update({"iv": None, "delta": None, "gamma": None, "vega": None, "theta": None})
        return row
    t = year_fraction_to_expiry(expiry, as_of)
    mid = row.get("mid")
    if mid is None or (isinstance(mid, float) and math.isnan(mid)):
        row.update({"iv": None, "delta": None, "gamma": None, "vega": None, "theta": None})
        return row
    iv = implied_vol(str(row["right"]), float(spot), float(row["strike"]), rate, div_yield, float(mid), t)
    if iv is None:
        row.update({"iv": None, "delta": None, "gamma": None, "vega": None, "theta": None})
        return row
    g = bs_greeks(str(row["right"]), float(spot), float(row["strike"]), rate, div_yield, iv, t)
    row["iv"] = iv
    row["delta"] = g["delta"]
    row["gamma"] = g["gamma"]
    row["vega"] = g["vega"]
    row["theta"] = g["theta"]
    return row

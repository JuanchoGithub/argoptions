from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm


def black_scholes_price(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str
) -> float:
    if T <= 0 or sigma <= 0:
        intrinsic = (S - K) if option_type.upper() == "C" else (K - S)
        return max(0.0, intrinsic)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type.upper() == "C":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def delta(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str
) -> float:
    if T <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    if option_type.upper() == "C":
        return norm.cdf(d1)
    return norm.cdf(d1) - 1.0


def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm.pdf(d1) / (S * sigma * math.sqrt(T))


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return S * norm.pdf(d1) * math.sqrt(T) * 0.01


def theta(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str
) -> float:
    if T <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    term = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
    if option_type.upper() == "C":
        return (term - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365.0
    return (term + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365.0


def rho(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str
) -> float:
    if T <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type.upper() == "C":
        return K * T * math.exp(-r * T) * norm.cdf(d2) * 0.01
    return -K * T * math.exp(-r * T) * norm.cdf(-d2) * 0.01


def iv(
    S: float,
    K: float,
    T: float,
    r: float,
    market_price: float,
    option_type: str,
    initial_guess: float = 0.3,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> float:
    sigma = initial_guess
    for _ in range(max_iter):
        price = black_scholes_price(S, K, T, r, sigma, option_type)
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        v = vega(S, K, T, r, sigma)
        raw_vega = v / 0.01
        if abs(raw_vega) < 1e-12:
            break
        sigma = sigma - diff / raw_vega
        if sigma <= 0:
            sigma = 0.001
    return sigma


def all_greeks(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str
) -> dict[str, float]:
    return {
        "delta": delta(S, K, T, r, sigma, option_type),
        "gamma": gamma(S, K, T, r, sigma),
        "vega": vega(S, K, T, r, sigma),
        "theta": theta(S, K, T, r, sigma, option_type),
        "rho": rho(S, K, T, r, sigma, option_type),
    }

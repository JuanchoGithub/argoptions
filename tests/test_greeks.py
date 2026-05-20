from __future__ import annotations

import math

import pytest

from arg_options.core.greeks import (
    all_greeks,
    black_scholes_price,
    delta,
    gamma,
    iv,
    rho,
    theta,
    vega,
)


S_ATM = 100.0
K_ATM = 100.0
T_1YR = 1.0
R = 0.05
SIGMA = 0.2


def test_black_scholes_price_call():
    price = black_scholes_price(S_ATM, K_ATM, T_1YR, R, SIGMA, "C")
    assert price == pytest.approx(10.45, abs=0.02)


def test_black_scholes_price_put():
    price = black_scholes_price(S_ATM, K_ATM, T_1YR, R, SIGMA, "P")
    assert price == pytest.approx(5.57, abs=0.02)


def test_black_scholes_zero_time():
    price_call = black_scholes_price(100.0, 90.0, 0.0, R, SIGMA, "C")
    assert price_call == pytest.approx(10.0)
    price_put = black_scholes_price(90.0, 100.0, 0.0, R, SIGMA, "P")
    assert price_put == pytest.approx(10.0)


def test_black_scholes_zero_sigma():
    price_call = black_scholes_price(105.0, 100.0, 1.0, R, 0.0, "C")
    assert price_call == pytest.approx(5.0)
    price_put = black_scholes_price(95.0, 100.0, 1.0, R, 0.0, "P")
    assert price_put == pytest.approx(5.0)


def test_black_scholes_put_call_parity():
    call = black_scholes_price(S_ATM, K_ATM, T_1YR, R, SIGMA, "C")
    put = black_scholes_price(S_ATM, K_ATM, T_1YR, R, SIGMA, "P")
    parity = call - put
    expected = S_ATM - K_ATM * math.exp(-R * T_1YR)
    assert parity == pytest.approx(expected, abs=0.01)


def test_delta_call_atm():
    d = delta(S_ATM, K_ATM, T_1YR, R, SIGMA, "C")
    assert 0.55 <= d <= 0.65


def test_delta_put_atm():
    d = delta(S_ATM, K_ATM, T_1YR, R, SIGMA, "P")
    assert -0.45 <= d <= -0.35


def test_gamma_positive():
    g = gamma(S_ATM, K_ATM, T_1YR, R, SIGMA)
    assert g > 0


def test_vega_positive():
    v = vega(S_ATM, K_ATM, T_1YR, R, SIGMA)
    assert v > 0


def test_theta_call_negative():
    t = theta(S_ATM, K_ATM, T_1YR, R, SIGMA, "C")
    assert t < 0


def test_theta_put_negative():
    t = theta(S_ATM, K_ATM, T_1YR, R, SIGMA, "P")
    assert t < 0


def test_rho_call():
    r = rho(S_ATM, K_ATM, T_1YR, R, SIGMA, "C")
    assert r > 0


def test_rho_put():
    r = rho(S_ATM, K_ATM, T_1YR, R, SIGMA, "P")
    assert r < 0


def test_iv_recovers_sigma():
    target_sigma = 0.35
    price = black_scholes_price(S_ATM, K_ATM, T_1YR, R, target_sigma, "C")
    recovered = iv(S_ATM, K_ATM, T_1YR, R, price, "C")
    assert recovered == pytest.approx(target_sigma, abs=1e-4)


def test_iv_put():
    target_sigma = 0.25
    price = black_scholes_price(S_ATM, K_ATM, T_1YR, R, target_sigma, "P")
    recovered = iv(S_ATM, K_ATM, T_1YR, R, price, "P")
    assert recovered == pytest.approx(target_sigma, abs=1e-4)


def test_all_greeks_keys():
    result = all_greeks(S_ATM, K_ATM, T_1YR, R, SIGMA, "C")
    expected_keys = {"delta", "gamma", "vega", "theta", "rho"}
    assert set(result.keys()) == expected_keys


def test_all_greeks_values():
    result = all_greeks(S_ATM, K_ATM, T_1YR, R, SIGMA, "C")
    assert result["delta"] == pytest.approx(delta(S_ATM, K_ATM, T_1YR, R, SIGMA, "C"))
    assert result["gamma"] == pytest.approx(gamma(S_ATM, K_ATM, T_1YR, R, SIGMA))
    assert result["theta"] == pytest.approx(theta(S_ATM, K_ATM, T_1YR, R, SIGMA, "C"))
    assert result["vega"] == pytest.approx(vega(S_ATM, K_ATM, T_1YR, R, SIGMA))
    assert result["rho"] == pytest.approx(rho(S_ATM, K_ATM, T_1YR, R, SIGMA, "C"))


def test_deep_itm_call_delta():
    d = delta(200.0, 100.0, T_1YR, R, SIGMA, "C")
    assert d == pytest.approx(1.0, abs=0.02)


def test_deep_itm_put_delta():
    d = delta(50.0, 100.0, T_1YR, R, SIGMA, "P")
    assert d == pytest.approx(-1.0, abs=0.02)


def test_deep_otm_call_delta():
    d = delta(50.0, 200.0, T_1YR, R, SIGMA, "C")
    assert d == pytest.approx(0.0, abs=0.02)


def test_deep_otm_put_delta():
    d = delta(200.0, 100.0, T_1YR, R, SIGMA, "P")
    assert d == pytest.approx(0.0, abs=0.02)


def test_delta_zero_time():
    d = delta(100.0, 90.0, 0.0, R, SIGMA, "C")
    assert d == 0.0


def test_gamma_zero_time():
    g = gamma(100.0, 90.0, 0.0, R, SIGMA)
    assert g == 0.0


def test_vega_zero_time():
    v = vega(100.0, 90.0, 0.0, R, SIGMA)
    assert v == 0.0


def test_theta_zero_time():
    t = theta(100.0, 90.0, 0.0, R, SIGMA, "C")
    assert t == 0.0


def test_rho_zero_time():
    r = rho(100.0, 90.0, 0.0, R, SIGMA, "C")
    assert r == 0.0


def test_call_price_increases_with_spot():
    low = black_scholes_price(90.0, K_ATM, T_1YR, R, SIGMA, "C")
    high = black_scholes_price(110.0, K_ATM, T_1YR, R, SIGMA, "C")
    assert high > low


def test_put_price_decreases_with_spot():
    low = black_scholes_price(110.0, K_ATM, T_1YR, R, SIGMA, "P")
    high = black_scholes_price(90.0, K_ATM, T_1YR, R, SIGMA, "P")
    assert high > low


def test_iv_converges_from_low_guess():
    target = 0.30
    price = black_scholes_price(S_ATM, K_ATM, T_1YR, R, target, "C")
    recovered = iv(S_ATM, K_ATM, T_1YR, R, price, "C", initial_guess=0.1)
    assert recovered == pytest.approx(target, abs=1e-4)


def test_iv_converges_from_high_guess():
    target = 0.20
    price = black_scholes_price(S_ATM, K_ATM, T_1YR, R, target, "C")
    recovered = iv(S_ATM, K_ATM, T_1YR, R, price, "C", initial_guess=0.5)
    assert recovered == pytest.approx(target, abs=1e-4)

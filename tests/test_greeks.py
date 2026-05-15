from datetime import date

import math

from arg_options.greeks import bs_price, implied_vol, year_fraction_to_expiry


def test_bs_call_positive():
    p = bs_price("C", spot=100, strike=100, rate=0.05, div_yield=0.0, vol=0.2, t=1.0)
    assert p > 0


def test_implied_vol_roundtrip():
    spot, strike, r, q, sig, t = 100.0, 100.0, 0.05, 0.0, 0.25, 0.5
    mid = bs_price("C", spot, strike, r, q, sig, t)
    iv = implied_vol("C", spot, strike, r, q, mid, t)
    assert iv is not None
    assert abs(iv - sig) < 1e-4


def test_year_fraction_non_negative():
    yf = year_fraction_to_expiry(date.today(), date.today())
    assert yf >= 0
    assert not math.isnan(yf)

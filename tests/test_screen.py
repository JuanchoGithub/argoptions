import pandas as pd

from arg_options.screen import apply_screen


def test_screen_dte():
    df = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "expiry": ["2099-01-15", "2099-06-01"],
            "volume": [100, 100],
            "bid": [1.0, 1.0],
            "ask": [1.1, 1.2],
            "mid": [1.05, 1.15],
            "delta": [0.3, 0.4],
        }
    )
    rules = {"min_days_to_expiry": 0, "max_days_to_expiry": 30000, "max_bid_ask_spread_pct_mid": 50}
    out = apply_screen(df, rules)
    assert len(out) == 2


def test_screen_filters_delta():
    df = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "expiry": ["2099-01-15", "2099-01-15"],
            "volume": [10, 10],
            "bid": [1, 1],
            "ask": [1.05, 1.05],
            "mid": [1.02, 1.02],
            "delta": [0.05, 0.35],
        }
    )
    rules = {
        "min_days_to_expiry": 0,
        "max_days_to_expiry": 100000,
        "max_bid_ask_spread_pct_mid": 100,
        "min_abs_delta": 0.2,
    }
    out = apply_screen(df, rules)
    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "B"

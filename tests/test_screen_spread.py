import pandas as pd

from arg_options.screen import apply_screen


def test_spread_filter_keeps_row_when_bid_ask_missing():
    df = pd.DataFrame(
        {
            "ticker": ["X"],
            "expiry": ["2099-01-15"],
            "volume": [10],
            "bid": [None],
            "ask": [None],
            "mid": [1.5],
            "delta": [0.4],
        }
    )
    rules = {
        "min_days_to_expiry": 0,
        "max_days_to_expiry": 50000,
        "max_bid_ask_spread_pct_mid": 10,
        "min_abs_delta": 0.1,
        "max_abs_delta": 0.9,
    }
    out = apply_screen(df, rules)
    assert len(out) == 1

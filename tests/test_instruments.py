from __future__ import annotations

import pytest

from arg_options.core.instruments import OPTION_TICKER_RE, parse_ticker_parts, resolve_option_root


class TestParseTicker:
    def test_parse_ticker_full(self):
        result = parse_ticker_parts("GFG251018C10000")
        assert result is not None
        root, strike, right, expiry = result
        assert root == "GFG"
        assert strike == 10000.0
        assert right == "C"
        assert expiry == "20251018"

    def test_parse_ticker_call(self):
        result = parse_ticker_parts("YPFD250619C2000")
        assert result is not None
        root, strike, right, expiry = result
        assert root == "YPFD"
        assert strike == 2000.0
        assert right == "C"
        assert expiry == "20250619"

    def test_parse_ticker_put(self):
        result = parse_ticker_parts("PMP251219P1500")
        assert result is not None
        root, strike, right, expiry = result
        assert root == "PMP"
        assert strike == 1500.0
        assert right == "P"
        assert expiry == "20251219"

    def test_parse_ticker_invalid(self):
        assert parse_ticker_parts("INVALID") is None
        assert parse_ticker_parts("") is None

    def test_parse_ticker_lowercase(self):
        result = parse_ticker_parts("gfg251018c10000")
        assert result is not None
        root, strike, right, expiry = result
        assert root == "GFG"
        assert right == "C"

    def test_parse_ticker_short_root(self):
        result = parse_ticker_parts("BMA251018C5000")
        assert result is not None
        root, strike, right, expiry = result
        assert root == "BMA"
        assert strike == 5000.0

    def test_parse_ticker_long_root(self):
        result = parse_ticker_parts("ABCD251018C1000")
        assert result is not None
        root, strike, right, expiry = result
        assert root == "ABCD"
        assert strike == 1000.0

    def test_parse_ticker_three_letter_root(self):
        result = parse_ticker_parts("GGAL250117C15000")
        assert result is not None
        root, strike, right, expiry = result
        assert root == "GGAL"
        assert strike == 15000.0
        assert expiry == "20250117"

    def test_regex_pattern_matches(self):
        assert OPTION_TICKER_RE.match("GFG251018C10000")
        assert OPTION_TICKER_RE.match("YPFD250619P5000")
        assert OPTION_TICKER_RE.match("PMP251219C750")
        assert OPTION_TICKER_RE.match("BMA250321C20000")
        assert not OPTION_TICKER_RE.match("ABC")
        assert not OPTION_TICKER_RE.match("GFG251018")


class TestResolveOptionRoot:
    def test_ggal_to_gfg(self):
        assert resolve_option_root("GGAL") == "GFG"

    def test_ypfd_to_ypf(self):
        assert resolve_option_root("YPFD") == "YPF"

    def test_yp_to_ypf(self):
        assert resolve_option_root("YP") == "YPF"

    def test_pamp_to_pmp(self):
        assert resolve_option_root("PAMP") == "PMP"

    def test_bma_to_bma(self):
        assert resolve_option_root("BMA") == "BMA"

    def test_unknown_returns_uppercase(self):
        assert resolve_option_root("unknown") == "unknown"
        assert resolve_option_root("TECO") == "TECO"
        assert resolve_option_root("AAPL") == "AAPL"

    def test_case_sensitive(self):
        assert resolve_option_root("ggal") == "ggal"

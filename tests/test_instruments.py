from datetime import date

from arg_options.instruments import parse_byma_option_ticker, third_thursday


def test_third_thursday_may_2024():
    assert third_thursday(2024, 5) == date(2024, 5, 16)


def test_parse_gfg_call():
    p = parse_byma_option_ticker("GFGC2800MY", reference_year=2026)
    assert p is not None
    assert p.option_root == "GFG"
    assert p.right == "C"
    assert p.strike == 2800.0
    assert p.month_code == "MY"
    assert p.expiry.month == 5


def test_parse_with_year_suffix():
    p = parse_byma_option_ticker("GFGC2800OC24")
    assert p is not None
    assert p.month_code == "OC"
    assert p.year == 2024


def test_invalid_ticker():
    assert parse_byma_option_ticker("GGAL") is None

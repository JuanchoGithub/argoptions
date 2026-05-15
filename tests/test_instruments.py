from datetime import date

import pytest

from arg_options.instruments import (
    MONTH_SUFFIX_TO_MONTH,
    parse_byma_option_ticker,
    third_thursday,
)


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


def test_parse_put_with_v_to_p():
    """V del ticker BYMA debe normalizarse a P para el modelo interno."""
    p = parse_byma_option_ticker("GFGV4200AG", reference_year=2026)
    assert p is not None
    assert p.option_root == "GFG"
    assert p.right == "P"
    assert p.strike == 4200.0
    assert p.month_code == "AG"


def test_parse_one_letter_month():
    """Ticker con 1 letra para el mes (strike alto, poco espacio)."""
    p = parse_byma_option_ticker("GFGC10200J", reference_year=2026)
    assert p is not None
    assert p.option_root == "GFG"
    assert p.right == "C"
    assert p.strike == 10200.0
    assert p.month_code == "J"
    assert p.expiry.month == 6


def test_parse_one_letter_month_with_year():
    p = parse_byma_option_ticker("GFGC10200J25")
    assert p is not None
    assert p.strike == 10200.0
    assert p.month_code == "J"
    assert p.year == 2025


def test_parse_july_one_letter():
    p = parse_byma_option_ticker("GFGV5000L", reference_year=2026)
    assert p is not None
    assert p.option_root == "GFG"
    assert p.right == "P"
    assert p.strike == 5000.0
    assert p.month_code == "L"
    assert p.expiry.month == 7


@pytest.mark.parametrize(
    "code, expected_month",
    [
        # 1 letra (oficial BYMA)
        *[(c, m) for c, m in MONTH_SUFFIX_TO_MONTH.items() if len(c) == 1],
        # 2 letras (PPI)
        *[(c, m) for c, m in MONTH_SUFFIX_TO_MONTH.items() if len(c) == 2],
    ],
)
def test_all_month_codes(code, expected_month):
    ticker = f"GFGC100{code}"
    p = parse_byma_option_ticker(ticker, reference_year=2026)
    assert p is not None, f"Fallo con código {code}"
    assert p.expiry.month == expected_month, f"{code} → mes {expected_month}"


def test_invalid_ticker():
    assert parse_byma_option_ticker("GGAL") is None

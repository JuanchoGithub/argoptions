from pathlib import Path

import pytest

from arg_options import db as dbmod
from arg_options.orders import LimitOrderRequest, place_limit_order
from arg_options.settings import AppSettings


class _FakePPI:
    pass


def _settings(tmp_path: Path, **kwargs) -> AppSettings:
    base = dict(
        ppi_api_key="k",
        ppi_api_secret="s",
        ppi_account_number="12345",
        ppi_sandbox=True,
        allow_live_orders=kwargs.get("allow_live_orders", False),
        daily_order_notional_cap_ars=kwargs.get("cap", 1_000_000.0),
        max_contracts_per_order=kwargs.get("max_q", 5),
        yaml_config={"paths": {"database": str(tmp_path / "db.sqlite")}},
    )
    return AppSettings(**base)


def test_place_order_dry_run_skips_ppi(tmp_path: Path):
    s = _settings(tmp_path)
    req = LimitOrderRequest(ticker="GFGC2800MY", side="COMPRA", quantity=1, limit_price=10.0)
    out = place_limit_order(_FakePPI(), s, req, dry_run=True)
    assert out["status"] == "skipped_dry_run"


def test_place_order_quantity_cap(tmp_path: Path):
    s = _settings(tmp_path, max_q=2)
    req = LimitOrderRequest(ticker="GFGC2800MY", side="COMPRA", quantity=10, limit_price=1.0)
    with pytest.raises(ValueError):
        place_limit_order(_FakePPI(), s, req, dry_run=True)


def test_place_order_daily_cap(tmp_path: Path):
    s = _settings(tmp_path, cap=1000.0)
    conn = dbmod.connect(s.db_path())
    dbmod.add_daily_notional(conn, 999.0)
    conn.close()
    req = LimitOrderRequest(ticker="GFGC2800MY", side="COMPRA", quantity=1, limit_price=10.0)
    with pytest.raises(ValueError, match="Tope diario"):
        place_limit_order(_FakePPI(), s, req, dry_run=True)

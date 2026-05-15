"""Tests del Discovery Engine (butterfly, iron condor, calendar, sintéticos)."""

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from arg_options import db as dbmod
from arg_options.discovery import (
    DiscoveryEngine,
    Leg,
    Opportunity,
    analyze_butterfly,
    analyze_calendars,
    analyze_iron_condor,
    analyze_synthetics_single,
    load_discovery_rules,
    _infer_strike_gap,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_chain():
    """DataFrame simulando un snapshot de cadena para GGAL."""
    expiry1 = "2026-06-18"
    expiry2 = "2026-09-17"
    rows = []

    strikes_call = [4100, 4200, 4300, 4400, 4500, 4600, 4700, 4800, 4900, 5000]
    for s in strikes_call:
        rows.append({
            "ticker": f"GFGC{s:.0f}MY",
            "option_root": "GFG",
            "underlying_spot": "GGAL",
            "strike": float(s),
            "right": "C",
            "expiry": expiry1,
            "bid": max(10, 2000 - s * 0.4),
            "ask": max(12, 2005 - s * 0.4),
            "mid": max(11, 2002.5 - s * 0.4),
            "last": max(11, 2002.5 - s * 0.4),
            "volume": 50 if s in (4300, 4500, 4700) else 5,
            "iv": 0.35,
            "delta": max(0.05, min(0.95, (5000 - s) / 1000)),
            "gamma": 0.0001,
            "vega": 5,
            "theta": -0.5,
            "description": f"GFG Call {s:.0f}",
        })

    strikes_put = [4100, 4200, 4300, 4400, 4500, 4600, 4700, 4800, 4900, 5000]
    for s in strikes_put:
        call_d = max(0.05, min(0.95, (5000 - s) / 1000))
        rows.append({
            "ticker": f"GFGV{s:.0f}MY",
            "option_root": "GFG",
            "underlying_spot": "GGAL",
            "strike": float(s),
            "right": "P",
            "expiry": expiry1,
            "bid": max(5, s * 0.3 - 500),
            "ask": max(7, s * 0.3 - 498),
            "mid": max(6, s * 0.3 - 499),
            "last": max(6, s * 0.3 - 499),
            "volume": 30 if s in (4300, 4500, 4700) else 3,
            "iv": 0.38,
            "delta": call_d - 1,
            "gamma": 0.0001,
            "vega": 5,
            "theta": -0.4,
            "description": f"GFG Put {s:.0f}",
        })

    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# Leg / Opportunity model tests
# ---------------------------------------------------------------------------

def test_leg_to_dict():
    leg = Leg("GFGC4500MY", "COMPRA", 1, 4500.0, "C", mid=80.0, delta=0.5, bid=75.0, ask=85.0)
    d = leg.to_dict()
    assert d["ticker"] == "GFGC4500MY"
    assert d["mid"] == 80.0
    assert d["delta"] == 0.5


def test_opportunity_to_structure():
    leg = Leg("GFGC4500MY", "VENTA", 2, 4500.0, "C")
    opp = Opportunity(root="GFG", strategy="mariposa", side="neutral", legs=[leg])
    struct = opp.to_structure_dicts()
    assert len(struct) == 1
    assert struct[0]["qty"] == 2


# ---------------------------------------------------------------------------
# _infer_strike_gap
# ---------------------------------------------------------------------------

def test_infer_strike_gap():
    assert _infer_strike_gap([4100, 4200, 4300, 4400]) == 100
    assert _infer_strike_gap([4100, 4150, 4200]) == 50
    assert _infer_strike_gap([4100]) == 50


# ---------------------------------------------------------------------------
# Butterfly analyzer
# ---------------------------------------------------------------------------

def test_butterfly_found(sample_chain):
    expiry = "2026-06-18"
    rules = {"strategies": {"mariposa": {
        "target_delta": 0.50, "delta_range": [0.30, 0.70],
        "max_cost_pct_of_width": 50,
    }}}
    opp = analyze_butterfly("GFG", expiry, sample_chain, rules)
    assert opp is not None
    assert opp.strategy == "mariposa"
    assert len(opp.legs) == 3
    assert opp.metrics["net_debit"] >= 0
    assert opp.confidence > 0
    assert opp.metrics["gap"] > 0


def test_butterfly_needs_three_calls():
    df = pd.DataFrame([{
        "ticker": "GFGC4500MY", "option_root": "GFG",
        "strike": 4500, "right": "C", "expiry": "2026-06-18",
        "bid": 70, "ask": 80, "mid": 75, "delta": 0.5,
        "volume": 10,
    }])
    rules = {"strategies": {"mariposa": {
        "target_delta": 0.50, "delta_range": [0.30, 0.70],
        "max_cost_pct_of_width": 50,
    }}}
    opp = analyze_butterfly("GFG", "2026-06-18", df, rules)
    assert opp is None


# ---------------------------------------------------------------------------
# Iron Condor analyzer
# ---------------------------------------------------------------------------

def test_iron_condor_found(sample_chain):
    expiry = "2026-06-18"
    rules = {"strategies": {"renta_ic": {
        "short_delta_target": 0.20, "short_delta_range": [0.10, 0.35],
        "insurance_delta_target": 0.10, "insurance_delta_range": [0.05, 0.20],
        "min_credit_pct_of_width": 1,
    }}}
    opp = analyze_iron_condor("GFG", expiry, sample_chain, rules)
    assert opp is not None
    assert opp.strategy == "renta_ic"
    assert len(opp.legs) == 4
    assert opp.metrics["credit_received"] > 0
    assert opp.confidence > 0


def test_iron_condor_no_puts():
    df = pd.DataFrame([{
        "ticker": "GFGC4500MY", "option_root": "GFG",
        "strike": 4500, "right": "C", "expiry": "2026-06-18",
        "bid": 70, "ask": 80, "mid": 75, "delta": 0.20, "volume": 10,
    }])
    rules = {"strategies": {"renta_ic": {
        "short_delta_target": 0.20, "short_delta_range": [0.15, 0.30],
        "insurance_delta_target": 0.10, "insurance_delta_range": [0.05, 0.15],
        "min_credit_pct_of_width": 1,
    }}}
    opp = analyze_iron_condor("GFG", "2026-06-18", df, rules)
    assert opp is None


# ---------------------------------------------------------------------------
# Calendar analyzer
# ---------------------------------------------------------------------------

def test_calendar_found():
    rows = []
    for exp, dte, bid, ask, delta, theta in [
        ("2026-06-18", 34, 70, 80, 0.50, -0.8),
        ("2026-09-17", 125, 130, 140, 0.50, -0.3),
    ]:
        rows.append({
            "ticker": f"GFGC4500{'JU' if dte == 34 else 'SE'}",
            "option_root": "GFG",
            "underlying_spot": "GGAL",
            "strike": 4500.0,
            "right": "C",
            "expiry": exp,
            "bid": bid,
            "ask": ask,
            "mid": (bid + ask) / 2,
            "last": (bid + ask) / 2,
            "volume": 50,
            "iv": 0.35,
            "delta": delta,
            "gamma": 0.0001,
            "vega": 5,
            "theta": theta,
            "description": f"GFG Call 4500",
        })
    df = pd.DataFrame(rows)

    rules = {"strategies": {"temporal": {
        "min_dte_short": 7, "max_dte_short": 60,
        "min_dte_long": 60, "max_dte_long": 200,
    }}}
    opps = analyze_calendars("GFG", df, rules)
    assert len(opps) >= 1
    assert opps[0].strategy == "calendar"
    assert len(opps[0].legs) == 2


# ---------------------------------------------------------------------------
# Synthetic analyzer
# ---------------------------------------------------------------------------

def test_synthetic_found(sample_chain):
    expiry = "2026-06-18"
    rules = {"strategies": {"sintetico": {"enabled": True}}}
    opps = analyze_synthetics_single("GFG", expiry, sample_chain, rules)
    assert len(opps) >= 2
    strategies = set(o.strategy for o in opps)
    assert "sintetico" in strategies
    sides = set(o.side for o in opps)
    assert "compra" in sides or "venta" in sides


# ---------------------------------------------------------------------------
# NaN handling — valores faltantes de PPI
# ---------------------------------------------------------------------------

def test_safe_float_rejects_nan():
    import math
    import pandas as pd
    s = pd.Series({"bid": float("nan"), "ask": 100.0})
    from arg_options.discovery import _safe_float
    assert _safe_float(s, "bid") is None
    assert _safe_float(s, "ask") == 100.0


def test_butterfly_skips_nan_bidask():
    import math
    df = pd.DataFrame([
        {"ticker": "GFGC4300MY", "option_root": "GFG", "strike": 4300, "right": "C",
         "expiry": "2026-06-18", "bid": float("nan"), "ask": float("nan"),
         "mid": 150, "delta": 0.70, "volume": 0},
        {"ticker": "GFGC4500MY", "option_root": "GFG", "strike": 4500, "right": "C",
         "expiry": "2026-06-18", "bid": 75, "ask": 85,
         "mid": 80, "delta": 0.50, "volume": 50},
        {"ticker": "GFGC4700MY", "option_root": "GFG", "strike": 4700, "right": "C",
         "expiry": "2026-06-18", "bid": 25, "ask": 35,
         "mid": 30, "delta": 0.25, "volume": 10},
    ])
    rules = {"strategies": {"mariposa": {
        "target_delta": 0.50, "delta_range": [0.30, 0.70],
        "max_cost_pct_of_width": 50,
    }}}
    opp = analyze_butterfly("GFG", "2026-06-18", df, rules)
    assert opp is None, "K1 con bid/ask NaN debería descartar la mariposa"


def test_safe_metric_in_summary():
    from arg_options.cli import _safe_metric
    assert _safe_metric(float("nan")) == 0
    assert _safe_metric(None) == 0
    assert _safe_metric(50.0) == 50.0
    assert _safe_metric("not a number", default=10) == 10


# ---------------------------------------------------------------------------
# Discovery Engine integration
# ---------------------------------------------------------------------------

def test_engine_persist(sample_chain):
    rules = {
        "auto_chain_if_stale": False,
        "min_confidence": 0,
        "strategies": {
            "mariposa": {
                "enabled": True, "target_delta": 0.50,
                "delta_range": [0.30, 0.70],
                "max_cost_pct_of_width": 50,
            },
            "renta_ic": {
                "enabled": True, "short_delta_target": 0.20,
                "short_delta_range": [0.10, 0.35],
                "insurance_delta_target": 0.10,
                "insurance_delta_range": [0.05, 0.20],
                "min_credit_pct_of_width": 1,
            },
            "temporal": {"enabled": False},
            "sintetico": {"enabled": True},
        },
    }

    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        conn = dbmod.connect(db_path)

        dbmod.insert_snapshots(conn, sample_chain.to_dict("records"))

        metrics = {"test": 1}
        dbmod.insert_discovery_opportunity(
            conn, root="GFG", strategy="test", side="neutral",
            expiry="2026-06-18", structure=[], metrics=metrics,
            confidence=50, status="pending",
        )

        rows = dbmod.load_latest_discovery(conn, root="GFG")
        assert len(rows) >= 1
        loaded_metrics = json.loads(rows[0]["metrics_json"])
        assert loaded_metrics["test"] == 1

        dbmod.update_discovery_status(conn, rows[0]["id"], "executed")
        updated = dbmod.load_latest_discovery(conn, root="GFG", limit=1)[0]
        assert updated["status"] == "executed"

        conn.close()


def test_load_discovery_rules_defaults():
    rules = load_discovery_rules()
    assert "strategies" in rules
    assert "mariposa" in rules["strategies"]
    assert rules["strategies"]["mariposa"]["enabled"] is True
    assert "auto_chain_if_stale" in rules

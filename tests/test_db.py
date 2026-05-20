from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

import arg_options.db as db


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    monkeypatch.setattr(db, "get_db_path", lambda: db_path)
    db.init_db()
    yield
    db_path.unlink(missing_ok=True)


class TestInitDB:
    def test_tables_created(self):
        conn = sqlite3.connect(str(db.get_db_path()))
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        conn.close()
        assert "journal" in tables
        assert "orders" in tables
        assert "positions" in tables
        assert "strategies" in tables
        assert "pending_approvals" in tables


class TestLogEvent:
    def test_log_event_inserts_row(self):
        db.log_event("test_event", "test description", "some details")
        conn = sqlite3.connect(str(db.get_db_path()))
        rows = conn.execute("SELECT * FROM journal").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][2] == "test_event"
        assert rows[0][3] == "test description"
        assert rows[0][4] == "some details"

    def test_log_event_without_details(self):
        db.log_event("test_event", "no details")
        conn = sqlite3.connect(str(db.get_db_path()))
        row = conn.execute("SELECT * FROM journal").fetchone()
        conn.close()
        assert row[4] is None


class TestOrderRoundTrip:
    def test_save_and_get_orders(self):
        order_data = {
            "order_id": 1001,
            "account_number": "ACC001",
            "ticker": "GGAL",
            "operation": "COMPRA",
            "quantity": 100.0,
            "price": 150.0,
            "status": "pending",
            "instrument_type": "ACCIONES",
            "settlement": "A-48HS",
            "order_type": "LIMITE",
            "operation_type": "PRECIO-LIMITE",
            "external_id": "ext-001",
            "raw_response": json.dumps({"budget_id": 1, "order_id": 1001}),
        }
        row_id = db.save_order(order_data)
        assert row_id > 0

        orders = db.get_orders(limit=10)
        assert len(orders) >= 1
        saved = next(o for o in orders if o["order_id"] == 1001)
        assert saved["ticker"] == "GGAL"
        assert saved["operation"] == "COMPRA"
        assert saved["external_id"] == "ext-001"

    def test_save_order_updates_existing(self):
        order_data = {
            "order_id": 2002,
            "account_number": "ACC001",
            "ticker": "YPFD",
            "operation": "VENTA",
            "quantity": 50.0,
            "price": 2000.0,
            "status": "pending",
            "instrument_type": "ACCIONES",
            "settlement": "A-48HS",
            "order_type": "LIMITE",
            "operation_type": "PRECIO-LIMITE",
        }
        first_id = db.save_order(order_data)

        update_data = {
            "order_id": 2002,
            "account_number": "ACC001",
            "ticker": "YPFD",
            "operation": "VENTA",
            "quantity": 50.0,
            "price": 2100.0,
            "status": "filled",
            "instrument_type": "ACCIONES",
            "settlement": "A-48HS",
            "order_type": "LIMITE",
            "operation_type": "PRECIO-LIMITE",
        }
        second_id = db.save_order(update_data)
        assert second_id == first_id


class TestPositionRoundTrip:
    def test_save_and_get_positions(self):
        pos_data = {
            "ticker": "GGAL",
            "side": "long",
            "quantity": 100.0,
            "entry_price": 150.0,
            "current_price": 155.0,
            "pnl": 500.0,
            "strategy": "test_strat",
            "account_number": "ACC001",
        }
        row_id = db.save_position(pos_data)
        assert row_id > 0

        positions = db.get_positions(open_only=True)
        assert len(positions) >= 1
        saved = next(p for p in positions if p["ticker"] == "GGAL")
        assert saved["side"] == "long"
        assert saved["entry_price"] == 150.0
        assert saved["current_price"] == 155.0

    def test_get_positions_excludes_closed(self):
        open_pos = {
            "ticker": "OPEN",
            "side": "long",
            "quantity": 10.0,
            "entry_price": 100.0,
            "current_price": 110.0,
            "pnl": 100.0,
            "account_number": "ACC001",
        }
        closed_pos = {
            "ticker": "CLOSED",
            "side": "long",
            "quantity": 10.0,
            "entry_price": 100.0,
            "current_price": 110.0,
            "pnl": 100.0,
            "closed_at": "2025-01-15T12:00:00",
            "account_number": "ACC001",
        }
        db.save_position(open_pos)
        db.save_position(closed_pos)

        open_positions = db.get_positions(open_only=True)
        open_tickers = [p["ticker"] for p in open_positions]
        assert "OPEN" in open_tickers
        assert "CLOSED" not in open_tickers

        all_positions = db.get_positions(open_only=False)
        all_tickers = [p["ticker"] for p in all_positions]
        assert "OPEN" in all_tickers
        assert "CLOSED" in all_tickers


class TestStrategyCRUD:
    def test_create_strategy(self):
        sid = db.save_strategy(
            "test_strat", "bull_call_spread", {"strike": 100, "premium": 5.0}
        )
        assert sid > 0

        strategies = db.get_strategies(enabled_only=True)
        assert len(strategies) >= 1
        saved = next(s for s in strategies if s["name"] == "test_strat")
        assert saved["type"] == "bull_call_spread"
        assert saved["config"] == {"strike": 100, "premium": 5.0}
        assert saved["enabled"] == 1

    def test_update_strategy(self):
        sid = db.save_strategy("update_strat", "initial_type", {"key": "value"})
        sid2 = db.save_strategy("update_strat", "updated_type", {"key": "new_value"})
        assert sid == sid2

        strategies = db.get_strategies(enabled_only=False)
        saved = next(s for s in strategies if s["name"] == "update_strat")
        assert saved["type"] == "updated_type"
        assert saved["config"] == {"key": "new_value"}

    def test_get_strategies_enabled_only(self):
        db.save_strategy("enabled_strat", "type", {})
        db.save_strategy("disabled_strat", "type", {})
        conn = sqlite3.connect(str(db.get_db_path()))
        conn.execute(
            "UPDATE strategies SET enabled = 0 WHERE name = 'disabled_strat'"
        )
        conn.commit()
        conn.close()

        enabled = db.get_strategies(enabled_only=True)
        names = [s["name"] for s in enabled]
        assert "enabled_strat" in names
        assert "disabled_strat" not in names


class TestPendingApprovalFlow:
    def test_create_pending_approval(self):
        sid = db.save_strategy("approval_strat", "custom", {"param": 1})
        aid = db.save_pending_approval(sid, {"signal": "buy", "confidence": 0.85})
        assert aid > 0

        pending = db.get_pending_approvals()
        assert len(pending) >= 1
        saved = next(a for a in pending if a["id"] == aid)
        assert saved["status"] == "pending"
        assert saved["opportunity_data"]["signal"] == "buy"

    def test_approve_pending(self):
        sid = db.save_strategy("approve_strat", "type", {})
        aid = db.save_pending_approval(sid, {"action": "buy"})
        db.approve_or_reject(aid, "approved")

        pending = db.get_pending_approvals()
        assert all(a["id"] != aid for a in pending)

        conn = sqlite3.connect(str(db.get_db_path()))
        row = conn.execute(
            "SELECT status FROM pending_approvals WHERE id = ?", (aid,)
        ).fetchone()
        conn.close()
        assert row[0] == "approved"

    def test_reject_pending(self):
        sid = db.save_strategy("reject_strat", "type", {})
        aid = db.save_pending_approval(sid, {"action": "sell"})
        db.approve_or_reject(aid, "rejected")

        pending = db.get_pending_approvals()
        assert all(a["id"] != aid for a in pending)

        conn = sqlite3.connect(str(db.get_db_path()))
        row = conn.execute(
            "SELECT status FROM pending_approvals WHERE id = ?", (aid,)
        ).fetchone()
        conn.close()
        assert row[0] == "rejected"

    def test_approve_or_reject_invalid_decision(self):
        with pytest.raises(ValueError, match="decision must be 'approved' or 'rejected'"):
            db.approve_or_reject(1, "invalid")

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def resolve_project_root() -> Path:
    import os as _os

    root = _os.environ.get("ARGOPTIONS_ROOT")
    if root:
        return Path(root).resolve()

    current = Path(__file__).resolve().parent
    for parent in current.parents:
        if (parent / ".env_test").exists():
            return parent
    return current.parents[-2]


def get_db_path() -> Path:
    root = resolve_project_root()
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "journal.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(
            """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            order_id INTEGER,
            account_number TEXT,
            ticker TEXT,
            operation TEXT,
            quantity REAL,
            price REAL,
            status TEXT,
            instrument_type TEXT,
            settlement TEXT,
            order_type TEXT,
            operation_type TEXT,
            created_at TEXT,
            updated_at TEXT,
            external_id TEXT,
            raw_response TEXT
        );

        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY,
            ticker TEXT,
            side TEXT,
            quantity REAL,
            entry_price REAL,
            current_price REAL,
            pnl REAL,
            opened_at TEXT,
            closed_at TEXT,
            strategy TEXT,
            account_number TEXT
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            event_type TEXT,
            description TEXT,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            config TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS pending_approvals (
            id INTEGER PRIMARY KEY,
            strategy_id INTEGER,
            opportunity_data TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            decided_at TEXT
        );
        """
        )
        conn.commit()
    finally:
        conn.close()


def log_event(event_type: str, description: str, details: str | None = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO journal (timestamp, event_type, description, details) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), event_type, description, details),
        )
        conn.commit()
    finally:
        conn.close()


def save_order(order_data: dict) -> int:
    conn = get_connection()
    try:
        order_id = order_data.get("order_id")
        if order_id:
            existing = conn.execute(
                "SELECT id FROM orders WHERE order_id = ?", (order_id,)
            ).fetchone()
            if existing:
                order_data["updated_at"] = datetime.now().isoformat()
                fields = [
                    k
                    for k in (
                        "account_number",
                        "ticker",
                        "operation",
                        "quantity",
                        "price",
                        "status",
                        "instrument_type",
                        "settlement",
                        "order_type",
                        "operation_type",
                        "updated_at",
                        "external_id",
                        "raw_response",
                    )
                    if k in order_data
                ]
                set_clause = ", ".join(f"{k} = ?" for k in fields)
                values = [order_data[k] for k in fields] + [order_id]
                conn.execute(
                    f"UPDATE orders SET {set_clause} WHERE order_id = ?", values
                )
                conn.commit()
                return existing["id"]

        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO orders
               (order_id, account_number, ticker, operation, quantity, price,
                status, instrument_type, settlement, order_type, operation_type,
                created_at, updated_at, external_id, raw_response)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                order_data.get("order_id"),
                order_data.get("account_number"),
                order_data.get("ticker"),
                order_data.get("operation"),
                order_data.get("quantity"),
                order_data.get("price"),
                order_data.get("status"),
                order_data.get("instrument_type"),
                order_data.get("settlement"),
                order_data.get("order_type"),
                order_data.get("operation_type"),
                order_data.get("created_at", now),
                order_data.get("updated_at", now),
                order_data.get("external_id"),
                order_data.get("raw_response"),
            ),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def get_orders(limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_position(position_data: dict) -> int:
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO positions
               (ticker, side, quantity, entry_price, current_price, pnl,
                opened_at, closed_at, strategy, account_number)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                position_data.get("ticker"),
                position_data.get("side"),
                position_data.get("quantity"),
                position_data.get("entry_price"),
                position_data.get("current_price"),
                position_data.get("pnl"),
                position_data.get("opened_at", now),
                position_data.get("closed_at"),
                position_data.get("strategy"),
                position_data.get("account_number"),
            ),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def get_positions(open_only: bool = True) -> list[dict]:
    conn = get_connection()
    try:
        if open_only:
            rows = conn.execute(
                "SELECT * FROM positions WHERE closed_at IS NULL ORDER BY opened_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM positions ORDER BY opened_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_strategy(name: str, strategy_type: str, config: dict) -> int:
    conn = get_connection()
    try:
        import json

        now = datetime.now().isoformat()
        existing = conn.execute(
            "SELECT id FROM strategies WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE strategies SET type = ?, config = ?, updated_at = ? WHERE id = ?",
                (strategy_type, json.dumps(config), now, existing["id"]),
            )
            conn.commit()
            return existing["id"]

        conn.execute(
            """INSERT INTO strategies (name, type, config, enabled, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (name, strategy_type, json.dumps(config), now, now),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def get_strategies(enabled_only: bool = True) -> list[dict]:
    conn = get_connection()
    try:
        import json

        if enabled_only:
            rows = conn.execute(
                "SELECT * FROM strategies WHERE enabled = 1 ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM strategies ORDER BY created_at DESC"
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["config"] = json.loads(d["config"]) if d["config"] else {}
            except (json.JSONDecodeError, TypeError):
                d["config"] = {}
            result.append(d)
        return result
    finally:
        conn.close()


def save_pending_approval(strategy_id: int, opportunity_data: dict) -> int:
    conn = get_connection()
    try:
        import json

        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO pending_approvals
               (strategy_id, opportunity_data, status, created_at)
               VALUES (?, ?, 'pending', ?)""",
            (strategy_id, json.dumps(opportunity_data), now),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def get_pending_approvals() -> list[dict]:
    conn = get_connection()
    try:
        import json

        rows = conn.execute(
            "SELECT * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["opportunity_data"] = (
                    json.loads(d["opportunity_data"]) if d["opportunity_data"] else {}
                )
            except (json.JSONDecodeError, TypeError):
                d["opportunity_data"] = {}
            result.append(d)
        return result
    finally:
        conn.close()


def approve_or_reject(approval_id: int, decision: str) -> None:
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be 'approved' or 'rejected'")
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE pending_approvals SET status = ?, decided_at = ? WHERE id = ?",
            (decision, now, approval_id),
        )
        conn.commit()
    finally:
        conn.close()


init_db()

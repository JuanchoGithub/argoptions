"""Persistencia SQLite para snapshots y diario."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chain_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ticker TEXT NOT NULL,
            underlying_spot TEXT,
            option_root TEXT,
            strike REAL,
            right TEXT,
            expiry TEXT,
            bid REAL,
            ask REAL,
            mid REAL,
            last REAL,
            volume REAL,
            iv REAL,
            delta REAL,
            gamma REAL,
            vega REAL,
            theta REAL,
            description TEXT,
            market TEXT,
            settlement TEXT,
            UNIQUE(ts, ticker)
        );

        CREATE INDEX IF NOT EXISTS idx_snap_ts ON chain_snapshots(ts);
        CREATE INDEX IF NOT EXISTS idx_snap_under ON chain_snapshots(underlying_spot);

        CREATE TABLE IF NOT EXISTS orders_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at TEXT NOT NULL,
            account_number TEXT NOT NULL,
            order_id TEXT,
            payload TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at TEXT NOT NULL,
            account_number TEXT NOT NULL,
            payload TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alert_dedupe (
            fingerprint TEXT PRIMARY KEY,
            last_sent_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_order_usage (
            day TEXT PRIMARY KEY,
            notional_ars REAL NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()


def insert_snapshots(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]], ts: str | None = None) -> int:
    ts = ts or utc_now_iso()
    cur = conn.cursor()
    n = 0
    for r in rows:
        cur.execute(
            """
            INSERT OR REPLACE INTO chain_snapshots (
              ts, ticker, underlying_spot, option_root, strike, right, expiry,
              bid, ask, mid, last, volume, iv, delta, gamma, vega, theta,
              description, market, settlement
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ts,
                r.get("ticker"),
                r.get("underlying_spot_ticker"),
                r.get("option_root"),
                r.get("strike"),
                r.get("right"),
                r.get("expiry"),
                r.get("bid"),
                r.get("ask"),
                r.get("mid"),
                r.get("last"),
                r.get("volume"),
                r.get("iv"),
                r.get("delta"),
                r.get("gamma"),
                r.get("vega"),
                r.get("theta"),
                r.get("description"),
                r.get("market"),
                r.get("settlement"),
            ),
        )
        n += 1
    conn.commit()
    return n


def append_orders_batch(conn: sqlite3.Connection, account_number: str, orders: list[dict[str, Any]]) -> int:
    cur = conn.cursor()
    sync = utc_now_iso()
    for o in orders:
        oid = str(o.get("id", ""))
        cur.execute(
            "INSERT INTO orders_raw(synced_at, account_number, order_id, payload) VALUES (?,?,?,?)",
            (sync, account_number, oid, json.dumps(o, default=str)),
        )
    conn.commit()
    return len(orders)


def append_positions_snapshot(conn: sqlite3.Connection, account_number: str, payload: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO positions_raw(synced_at, account_number, payload) VALUES (?,?,?)",
        (utc_now_iso(), account_number, json.dumps(payload, default=str)),
    )
    conn.commit()


def get_daily_notional(conn: sqlite3.Connection, day: date | None = None) -> float:
    day = day or date.today()
    cur = conn.execute("SELECT notional_ars FROM daily_order_usage WHERE day = ?", (day.isoformat(),))
    row = cur.fetchone()
    return float(row[0]) if row else 0.0


def add_daily_notional(conn: sqlite3.Connection, add_ars: float, day: date | None = None) -> None:
    day = day or date.today()
    d = day.isoformat()
    conn.execute(
        """
        INSERT INTO daily_order_usage(day, notional_ars) VALUES (?,?)
        ON CONFLICT(day) DO UPDATE SET notional_ars = notional_ars + excluded.notional_ars
        """,
        (d, add_ars),
    )
    conn.commit()


def should_send_alert(conn: sqlite3.Connection, fingerprint: str, min_interval_s: int) -> bool:
    cur = conn.execute("SELECT last_sent_at FROM alert_dedupe WHERE fingerprint = ?", (fingerprint,))
    row = cur.fetchone()
    now = datetime.now(timezone.utc)
    if row is None:
        conn.execute(
            "INSERT INTO alert_dedupe(fingerprint, last_sent_at) VALUES (?,?)",
            (fingerprint, now.isoformat()),
        )
        conn.commit()
        return True
    last = datetime.fromisoformat(row["last_sent_at"])
    if (now - last).total_seconds() >= min_interval_s:
        conn.execute(
            "UPDATE alert_dedupe SET last_sent_at = ? WHERE fingerprint = ?",
            (now.isoformat(), fingerprint),
        )
        conn.commit()
        return True
    return False

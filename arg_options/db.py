"""Persistencia SQLite para snapshots y diario."""

from __future__ import annotations

import json
import math
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

        CREATE TABLE IF NOT EXISTS discovery_opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            root TEXT NOT NULL,
            strategy TEXT NOT NULL,
            side TEXT,
            expiry TEXT,
            structure_json TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            confidence_score REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending'
        );

        CREATE INDEX IF NOT EXISTS idx_disc_ts ON discovery_opportunities(ts);
        CREATE INDEX IF NOT EXISTS idx_disc_root ON discovery_opportunities(root);
        CREATE INDEX IF NOT EXISTS idx_disc_strategy ON discovery_opportunities(strategy);
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


class _SafeEncoder(json.JSONEncoder):
    def default(self, o: Any) -> str:
        return str(o)

    def encode(self, o: Any) -> str:
        return super().encode(_clean_nan(o))


def _clean_nan(o: Any) -> Any:
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    if isinstance(o, dict):
        return {k: _clean_nan(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean_nan(v) for v in o]
    return o


def insert_discovery_opportunity(
    conn: sqlite3.Connection,
    root: str,
    strategy: str,
    side: str | None,
    expiry: str | None,
    structure: list[dict[str, Any]],
    metrics: dict[str, float],
    confidence: float,
    ts: str | None = None,
    status: str = "pending",
) -> int:
    _ts = ts or utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO discovery_opportunities
            (ts, root, strategy, side, expiry, structure_json, metrics_json, confidence_score, status)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            _ts,
            root,
            strategy,
            side,
            expiry,
            json.dumps(structure, cls=_SafeEncoder),
            json.dumps(metrics, cls=_SafeEncoder),
            confidence,
            status,
        ),
    )
    conn.commit()
    return cur.lastrowid or 0


def load_latest_discovery(
    conn: sqlite3.Connection,
    root: str | None = None,
    strategy: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    wheres: list[str] = []
    params: list[Any] = []
    if root:
        wheres.append("root = ?")
        params.append(root)
    if strategy:
        wheres.append("strategy = ?")
        params.append(strategy)
    where_clause = " AND ".join(wheres) if wheres else "1"
    sql = f"""
        SELECT * FROM discovery_opportunities
        WHERE {where_clause}
        ORDER BY ts DESC, confidence_score DESC
        LIMIT ?
    """
    params.append(limit)
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def update_discovery_status(conn: sqlite3.Connection, opp_id: int, status: str) -> None:
    conn.execute("UPDATE discovery_opportunities SET status = ? WHERE id = ?", (status, opp_id))
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

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from arg_options.db import (
    save_pending_approval,
    get_pending_approvals,
    approve_or_reject,
    log_event,
    get_connection,
)


@dataclass
class PendingOpportunity:
    id: int
    strategy_name: str
    strategy_type: str
    ticker: str
    operation_details: dict = field(default_factory=dict)
    detected_at: Optional[str] = None
    expires_at: Optional[str] = None
    status: str = "pending"
    confidence: float = 0.0


def _build_opportunity_data(
    strategy_name: str,
    strategy_type: str,
    details: dict,
    confidence: float,
    expires_minutes: int,
) -> dict:
    now = datetime.now()
    expires = now + timedelta(minutes=expires_minutes)
    return {
        "strategy_name": strategy_name,
        "strategy_type": strategy_type,
        "ticker": details.get("ticker", ""),
        "operation_details": details,
        "detected_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "confidence": confidence,
    }


def _parse_db_row(row: dict) -> PendingOpportunity:
    opp_data = row.get("opportunity_data", {})
    if isinstance(opp_data, str):
        try:
            opp_data = json.loads(opp_data)
        except (json.JSONDecodeError, TypeError):
            opp_data = {}
    return PendingOpportunity(
        id=row["id"],
        strategy_name=opp_data.get("strategy_name", ""),
        strategy_type=opp_data.get("strategy_type", ""),
        ticker=opp_data.get("ticker", ""),
        operation_details=opp_data.get("operation_details", {}),
        detected_at=opp_data.get("detected_at"),
        expires_at=opp_data.get("expires_at"),
        status=row.get("status", "pending"),
        confidence=float(opp_data.get("confidence", 0.0)),
    )


def queue_opportunity(
    strategy_name: str,
    strategy_type: str,
    details: dict,
    confidence: float,
    expires_minutes: int = 30,
) -> int:
    opp_data = _build_opportunity_data(
        strategy_name, strategy_type, details, confidence, expires_minutes
    )
    strategy_id = details.get("strategy_id", 0)
    db_id = save_pending_approval(strategy_id, opp_data)
    log_event(
        "opportunity_queued",
        f"Opportunity queued for {strategy_name} ({strategy_type})",
        f"confidence={confidence}, expires_in={expires_minutes}m",
    )
    return db_id


def get_pending_list() -> list[PendingOpportunity]:
    rows = get_pending_approvals()
    return [_parse_db_row(r) for r in rows]


def approve_opportunity(approval_id: int) -> bool:
    try:
        approve_or_reject(approval_id, "approved")
        log_event("opportunity_approved", f"Opportunity {approval_id} approved")
        return True
    except Exception as e:
        logging.error("Failed to approve opportunity %d: %s", approval_id, e)
        return False


def reject_opportunity(approval_id: int) -> bool:
    try:
        approve_or_reject(approval_id, "rejected")
        log_event("opportunity_rejected", f"Opportunity {approval_id} rejected")
        return True
    except Exception as e:
        logging.error("Failed to reject opportunity %d: %s", approval_id, e)
        return False


def expire_stale_opportunities() -> int:
    now = datetime.now().isoformat()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, opportunity_data FROM pending_approvals WHERE status = 'pending'"
        ).fetchall()
        expired_count = 0
        for r in rows:
            opp_data = r["opportunity_data"]
            if isinstance(opp_data, str):
                try:
                    opp_data = json.loads(opp_data)
                except (json.JSONDecodeError, TypeError):
                    continue
            expires_at = opp_data.get("expires_at")
            if expires_at and expires_at <= now:
                conn.execute(
                    "UPDATE pending_approvals SET status = 'rejected', decided_at = ? WHERE id = ?",
                    (now, r["id"]),
                )
                expired_count += 1
        if expired_count:
            conn.commit()
            log_event(
                "opportunities_expired",
                f"Expired {expired_count} stale opportunities",
            )
        return expired_count
    finally:
        conn.close()


def wait_for_approval(
    approval_id: int, timeout_seconds: int = 300
) -> Optional[str]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT status FROM pending_approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
            if row and row["status"] in ("approved", "rejected"):
                return row["status"]
        finally:
            conn.close()
        time.sleep(1)
    return None

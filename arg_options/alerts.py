"""Alertas con deduplicación y envío Telegram / email."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from arg_options import chain as chainmod
from arg_options import db as dbmod
from arg_options.settings import AppSettings

logger = logging.getLogger(__name__)


def _latest_chain(settings: AppSettings) -> pd.DataFrame:
    df = chainmod.load_last_snapshots(settings, limit=8000)
    if df.empty:
        return df
    ts = df["ts"].max()
    return df[df["ts"] == ts]


def build_alert_messages(df: pd.DataFrame, rules: dict[str, Any]) -> list[str]:
    if df.empty:
        return []
    alert_cfg = rules.get("alerts") or {}
    near = int(alert_cfg.get("near_expiry_days", 7))
    if "expiry" not in df.columns:
        return []
    exp = pd.to_datetime(df["expiry"], errors="coerce")
    today = pd.Timestamp.now().normalize()
    dte = (exp - today).dt.days
    sub = df.loc[(dte.notna()) & (dte <= near) & (dte >= 0)].copy()
    if sub.empty:
        return []
    sub["_dte"] = dte.loc[sub.index]
    msgs: list[str] = []
    for _, row in sub.head(20).iterrows():
        msgs.append(
            f"Vencimiento cercano ({int(row['_dte'])} d): {row.get('ticker')} "
            f"strike={row.get('strike')} {row.get('right')} expiry={row.get('expiry')}"
        )
    return msgs


def send_telegram(settings: AppSettings, text: str) -> bool:
    token = settings.telegram_bot_token
    chat = settings.telegram_chat_id
    if not token or not chat:
        logger.info("Telegram no configurado; mensaje omitido.")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat, "text": text[:4000]}, timeout=30)
    r.raise_for_status()
    return True


def send_email(settings: AppSettings, subject: str, body: str) -> bool:
    if not all(
        [
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_user,
            settings.smtp_password,
            settings.alert_email_from,
            settings.alert_email_to,
        ]
    ):
        logger.info("SMTP no configurado; email omitido.")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.alert_email_from
    msg["To"] = settings.alert_email_to
    msg.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls(context=context)
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    return True


def run_alerts_once(
    settings: AppSettings,
    screening_path: Path | None = None,
    min_interval_s: int | None = None,
) -> list[str]:
    from arg_options.screen import load_screening_config

    rules = load_screening_config(screening_path, settings)
    alert_cfg = rules.get("alerts") or {}
    min_interval_s = min_interval_s or int(alert_cfg.get("min_interval_seconds", 3600))

    df = _latest_chain(settings)
    if df.empty:
        return ["sin datos de cadena para alertar"]
    exp = pd.to_datetime(df["expiry"], errors="coerce")
    today = pd.Timestamp.now().normalize()
    df = df.copy()
    df["_dte"] = (exp - today).dt.days
    messages = build_alert_messages(df.drop(columns=["_dte"], errors="ignore"), rules)
    if not messages:
        return ["(sin alertas de vencimiento en la ventana configurada)"]

    conn = dbmod.connect(settings.db_path())
    sent: list[str] = []
    for m in messages:
        fp = m[:200]
        if dbmod.should_send_alert(conn, fp, min_interval_s):
            body = "[arg_options]\n" + m
            try:
                send_telegram(settings, body)
                send_email(settings, "arg_options alert", body)
            except Exception as e:
                logger.exception("Fallo enviando alerta: %s", e)
            sent.append(m)
    conn.close()
    return sent

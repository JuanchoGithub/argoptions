"""Carga de variables de entorno y YAML."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def _parse_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class AppSettings:
    ppi_api_key: str
    ppi_api_secret: str
    ppi_account_number: str
    ppi_sandbox: bool
    allow_live_orders: bool
    daily_order_notional_cap_ars: float
    max_contracts_per_order: int
    yaml_config: dict[str, Any] = field(default_factory=dict)
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    alert_email_from: str | None = None
    alert_email_to: str | None = None

    @property
    def ppi(self) -> dict[str, Any]:
        return self.yaml_config.get("ppi", {})

    @property
    def underlying_spot(self) -> dict[str, str]:
        return dict(self.yaml_config.get("underlying_spot", {}))

    @property
    def risk_free_rate(self) -> float:
        return float(self.yaml_config.get("risk_free_rate", 0.40))

    @property
    def contract_multiplier(self) -> int:
        return int(self.yaml_config.get("contract_multiplier", 100))

    @property
    def paths(self) -> dict[str, Any]:
        return dict(self.yaml_config.get("paths", {}))

    @property
    def chain_config(self) -> dict[str, Any]:
        return dict(self.yaml_config.get("chain", {}))

    def db_path(self) -> Path:
        raw = self.paths.get("database", "data/arg_options.db")
        return Path(raw).expanduser()

    def parquet_export_path(self) -> Path | None:
        raw = self.paths.get("snapshot_export_parquet")
        if not raw:
            return None
        return Path(raw).expanduser()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_settings(
    env_path: Path | None = None,
    yaml_path: Path | None = None,
) -> AppSettings:
    if env_path is None:
        env_path = Path(os.environ.get("ARG_OPTIONS_ENV", ".env"))
    load_dotenv(env_path)

    if yaml_path is None:
        yaml_path = Path(os.environ.get("ARG_OPTIONS_CONFIG", "config/settings.yaml"))

    yml = load_yaml(yaml_path)

    return AppSettings(
        ppi_api_key=os.environ.get("PPI_API_KEY", "").strip(),
        ppi_api_secret=os.environ.get("PPI_API_SECRET", "").strip(),
        ppi_account_number=os.environ.get("PPI_ACCOUNT_NUMBER", "").strip(),
        ppi_sandbox=_parse_bool(os.environ.get("PPI_SANDBOX"), True),
        allow_live_orders=_parse_bool(os.environ.get("ALLOW_LIVE_ORDERS"), False),
        daily_order_notional_cap_ars=float(os.environ.get("DAILY_ORDER_NOTIONAL_CAP_ARS", "500000")),
        max_contracts_per_order=int(os.environ.get("MAX_CONTRACTS_PER_ORDER", "5")),
        yaml_config=yml,
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID") or None,
        smtp_host=os.environ.get("ALERT_SMTP_HOST") or None,
        smtp_port=int(os.environ["ALERT_SMTP_PORT"]) if os.environ.get("ALERT_SMTP_PORT") else None,
        smtp_user=os.environ.get("ALERT_SMTP_USER") or None,
        smtp_password=os.environ.get("ALERT_SMTP_PASSWORD") or None,
        alert_email_from=os.environ.get("ALERT_EMAIL_FROM") or None,
        alert_email_to=os.environ.get("ALERT_EMAIL_TO") or None,
    )

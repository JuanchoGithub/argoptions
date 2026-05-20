from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from arg_options.broker.interfaces import BrokerConfig


def resolve_project_root() -> Path:
    root = os.environ.get("ARGOPTIONS_ROOT")
    if root:
        return Path(root).resolve()

    current = Path(__file__).resolve().parent
    for parent in current.parents:
        if (parent / ".env_test").exists():
            return parent
    return current.parents[-2]


def get_mode(mode: str | None = None) -> str:
    if mode is not None:
        return mode
    env_mode = os.environ.get("ARGOPTIONS_MODE", "test")
    if env_mode in ("production", "prod"):
        return "production"
    return "test"


def load_settings(mode: str | None = None) -> BrokerConfig:
    resolved_mode = get_mode(mode)
    root = resolve_project_root()

    if resolved_mode == "production":
        env_path = root / ".env_prod"
    else:
        env_path = root / ".env_test"

    load_dotenv(env_path)

    def env_bool(key: str, default: str = "false") -> bool:
        return os.environ.get(key, default).strip().lower() == "true"

    return BrokerConfig(
        api_key=os.environ.get("PPI_API_KEY", ""),
        api_secret=os.environ.get("PPI_API_SECRET", ""),
        account_number=os.environ.get("PPI_ACCOUNT_NUMBER", ""),
        authorized_client=os.environ.get("PPI_AUTHORIZED_CLIENT", ""),
        client_key=os.environ.get("PPI_CLIENT_KEY", ""),
        sandbox=env_bool("PPI_SANDBOX", "true"),
        allow_live_orders=env_bool("ALLOW_LIVE_ORDERS", "false"),
        daily_notional_cap_ars=float(
            os.environ.get("DAILY_ORDER_NOTIONAL_CAP_ARS", "1000000")
        ),
        max_contracts_per_order=int(
            os.environ.get("MAX_CONTRACTS_PER_ORDER", "100")
        ),
        contract_multiplier=int(os.environ.get("CONTRACT_MULTIPLIER", "1")),
        risk_free_rate=float(os.environ.get("RISK_FREE_RATE", "0.05")),
    )

"""Sesión PPI: login, reintentos y helpers de solo lectura."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, TypeVar

from ppi_client.ppi import PPI

from arg_options.settings import AppSettings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def connect_ppi(settings: AppSettings) -> PPI:
    if not settings.ppi_api_key or not settings.ppi_api_secret:
        raise ValueError("Definí PPI_API_KEY y PPI_API_SECRET en el entorno.")
    ppi = PPI(sandbox=settings.ppi_sandbox)
    ppi.account.login_api(settings.ppi_api_key, settings.ppi_api_secret)
    return ppi


def with_retries(
    fn: Callable[[], T],
    attempts: int = 4,
    base_delay_s: float = 0.5,
) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            wait = base_delay_s * (2**i)
            logger.warning("PPI call failed (%s/%s): %s — retry in %.2fs", i + 1, attempts, e, wait)
            time.sleep(wait)
    assert last is not None
    raise last


def ping_readonly(ppi: PPI, account_number: str) -> dict[str, Any]:
    """Comprueba sesión y devuelve datos mínimos (sin órdenes)."""
    out: dict[str, Any] = {}
    out["instrument_types"] = with_retries(lambda: ppi.configuration.get_instrument_types())
    out["markets"] = with_retries(lambda: ppi.configuration.get_markets())
    if account_number:
        out["accounts"] = with_retries(lambda: ppi.account.get_accounts())
    return out

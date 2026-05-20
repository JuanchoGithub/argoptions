from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import requests

from arg_options.broker.exceptions import AuthError, ConnectionError
from arg_options.broker.interfaces import (
    AccountService,
    Broker,
    BrokerConfig,
    ConfigurationService,
    MarketDataService,
    OrderService,
    RealtimeService,
)
from arg_options.broker.ppi.ppi_account import PpiAccountService
from arg_options.broker.ppi.ppi_configuration import PpiConfigurationService
from arg_options.broker.ppi.ppi_market_data import PpiMarketDataService
from arg_options.broker.ppi.ppi_orders import PpiOrderService
from arg_options.broker.ppi.ppi_realtime import PpiRealtimeService
from ppi_client.api.constants import MIME_JSON
from ppi_client.ppi import PPI
from ppi_client.ppi_restclient import RestClient, PPIAPIResponse

logger = logging.getLogger(__name__)

_LOG_INITIALIZED = False


def _ensure_file_logging() -> None:
    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return
    _LOG_INITIALIZED = True
    try:
        from arg_options.config.config_persist import resolve_project_root
        log_path = resolve_project_root() / "data" / "arg_options.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(log_path), encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        root.addHandler(handler)
        logger.info("File logging initialized: %s", log_path)
    except Exception as exc:
        logger.warning("Could not set up file logging: %s", exc)

_patch_applied = False


def _log_response(uri: str, response: requests.Response) -> None:
    status = response.status_code
    text = response.text[:2000]
    logger.info("PPI %s -> HTTP %d: %s", uri, status, text)
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        logger.warning("PPI %s Retry-After: %ss", uri, retry_after)


def _patched_get(self, uri, params=None, headers=None, data=None, content_type=MIME_JSON):
    session = self.get_session()
    base_url = self._RestClient__API_BASE_URL
    verify = self._RestClient__SSL_VERIFY

    if data is not None and content_type == MIME_JSON:
        from json.encoder import JSONEncoder
        data = JSONEncoder().encode(data)
        headers.update({
            "x-tracking-id": self.TRACKING_ID,
            "User-Agent": self.USER_AGENT,
            "Accept": MIME_JSON,
            "Content-type": content_type,
        })
        api_result = session.get(base_url + uri, data=data, headers=headers, verify=verify)
    else:
        headers.update({
            "x-tracking-id": self.TRACKING_ID,
            "User-Agent": self.USER_AGENT,
            "Accept": MIME_JSON,
        })
        api_result = session.get(base_url + uri, params=params, headers=headers, verify=verify)

    _log_response(uri, api_result)

    if not api_result.text:
        return PPIAPIResponse(api_result.status_code, "")
    return PPIAPIResponse(api_result.status_code, api_result.json())


def _patched_post(self, uri, data=None, params=None, headers=None, content_type=MIME_JSON):
    from json.encoder import JSONEncoder

    session = self.get_session()
    base_url = self._RestClient__API_BASE_URL
    verify = self._RestClient__SSL_VERIFY

    if data is not None and content_type == MIME_JSON:
        data = JSONEncoder().encode(data)

    complete_headers = {
        "x-tracking-id": self.TRACKING_ID,
        "User-Agent": self.USER_AGENT,
        "Accept": MIME_JSON,
        "Content-type": content_type,
    }
    complete_headers.update(headers or {})
    api_result = session.post(base_url + uri, params=params, data=data, headers=complete_headers, verify=verify)

    _log_response(uri, api_result)

    if not api_result.text:
        return PPIAPIResponse(api_result.status_code, "")
    return PPIAPIResponse(api_result.status_code, api_result.json())


def _patch_restclient() -> None:
    global _patch_applied
    if _patch_applied:
        return
    _patch_applied = True
    _ensure_file_logging()
    RestClient.get = _patched_get
    RestClient.post = _patched_post


def _format_ppi_error(e: Exception) -> str:
    msg = str(e)
    if isinstance(e, (json.JSONDecodeError, requests.exceptions.JSONDecodeError)):
        logger.error("PPI non-JSON response — check logs above for raw response body")
        return "PPI API returned a non-JSON response (rate-limited or service unavailable)"
    m = re.search(r"API calls quota exceeded", msg, re.IGNORECASE)
    if m:
        return "PPI sandbox rate limit hit (10 calls/hour). Wait ~1 hour and try again."
    return msg


class PpiBroker(Broker):
    def __init__(self, config: BrokerConfig) -> None:
        self._config = config
        _patch_restclient()
        self._ppi = PPI(sandbox=config.sandbox)
        self._account_service = PpiAccountService(self._ppi)
        self._configuration_service = PpiConfigurationService(self._ppi)
        self._market_data_service = PpiMarketDataService(self._ppi)
        self._order_service = PpiOrderService(self._ppi)
        self._realtime_service = PpiRealtimeService(self._ppi)

    def connect(self) -> None:
        try:
            self._ppi.account.login_api(
                self._config.api_key, self._config.api_secret
            )
        except AuthError:
            raise
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PPI: {_format_ppi_error(e)}") from e

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return self._ppi is not None

    @property
    def name(self) -> str:
        return "PPI"

    @property
    def sandbox(self) -> bool:
        return self._config.sandbox

    @property
    def account(self) -> AccountService:
        return self._account_service

    @property
    def configuration(self) -> ConfigurationService:
        return self._configuration_service

    @property
    def market_data(self) -> MarketDataService:
        return self._market_data_service

    @property
    def orders(self) -> OrderService:
        return self._order_service

    @property
    def realtime(self) -> RealtimeService:
        return self._realtime_service

    @property
    def config(self) -> BrokerConfig:
        return self._config

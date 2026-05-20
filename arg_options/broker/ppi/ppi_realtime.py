from __future__ import annotations

from typing import Any, Callable

from arg_options.broker.interfaces import (
    ConnectionCallback,
    DisconnectionCallback,
    RealtimeAccountCallback,
    RealtimeMarketDataCallback,
    RealtimeService,
)
from ppi_client.models.instrument import Instrument as PpiInstrument


class PpiRealtimeService(RealtimeService):
    def __init__(self, ppi: Any) -> None:
        self._ppi = ppi

    def connect_to_market_data(
        self,
        on_connect: ConnectionCallback,
        on_disconnect: DisconnectionCallback,
        on_data: RealtimeMarketDataCallback,
    ) -> None:
        self._ppi.realtime.connect_to_market_data(
            on_connect, on_disconnect, on_data
        )

    def connect_to_account(
        self,
        on_connect: ConnectionCallback,
        on_disconnect: DisconnectionCallback,
        on_data: RealtimeAccountCallback,
    ) -> None:
        self._ppi.realtime.connect_to_account(
            on_connect, on_disconnect, on_data
        )

    def subscribe_to_element(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
    ) -> None:
        instrument = PpiInstrument(
            ticker=ticker,
            instrument_type=instrument_type,
            settlement=settlement,
        )
        self._ppi.realtime.subscribe_to_element(instrument)

    def subscribe_to_account_data(self, account_number: str) -> None:
        self._ppi.realtime.subscribe_to_account_data(account_number)

    def start_connections(self) -> None:
        self._ppi.realtime.start_connections()

    def stop_connections(self) -> None:
        pass

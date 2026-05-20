from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from arg_options.broker.exceptions import BrokerError
from arg_options.broker.interfaces import MarketDataService
from arg_options.broker.models import Book, BookEntry, Instrument, IntradayPoint, MarketDataPoint
from ppi_client.models.estimate_bonds import EstimateBonds


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class PpiMarketDataService(MarketDataService):
    def __init__(self, ppi: Any) -> None:
        self._ppi = ppi

    def search_instruments(
        self,
        ticker: str,
        name: Optional[str] = None,
        market: Optional[str] = None,
        instrument_type: Optional[str] = None,
    ) -> list[Instrument]:
        try:
            data = self._ppi.marketdata.search_instrument(
                ticker, name or "", market or "", instrument_type or ""
            )
            return [
                Instrument(
                    ticker=d.get("ticker", ""),
                    description=d.get("description", ""),
                    currency=d.get("currency", ""),
                    type=d.get("type", ""),
                    market=d.get("market", ""),
                )
                for d in data
            ]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_historical(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[MarketDataPoint]:
        try:
            data = self._ppi.marketdata.search(
                ticker, instrument_type, settlement, date_from, date_to
            )
            return [
                MarketDataPoint(
                    date=_parse_datetime(d.get("date")),
                    price=d.get("price", 0),
                    volume=d.get("volume", 0),
                    opening_price=d.get("openingPrice", 0),
                    max=d.get("max", 0),
                    min=d.get("min", 0),
                )
                for d in data
            ]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_current(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
    ) -> Optional[MarketDataPoint]:
        try:
            data = self._ppi.marketdata.current(
                ticker, instrument_type, settlement
            )
            if not data:
                return None
            return MarketDataPoint(
                date=_parse_datetime(data.get("date")),
                price=data.get("price", 0),
                volume=data.get("volume", 0),
                opening_price=data.get("openingPrice", 0),
                max=data.get("max", 0),
                min=data.get("min", 0),
            )
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_book(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
    ) -> Optional[Book]:
        try:
            data = self._ppi.marketdata.book(
                ticker, instrument_type, settlement
            )
            if not data:
                return None
            offers = [
                BookEntry(
                    position=e.get("position", 0),
                    price=e.get("price", 0),
                    quantity=e.get("quantity", 0),
                )
                for e in data.get("offers", [])
            ]
            bids = [
                BookEntry(
                    position=e.get("position", 0),
                    price=e.get("price", 0),
                    quantity=e.get("quantity", 0),
                )
                for e in data.get("bids", [])
            ]
            return Book(
                date=_parse_datetime(data.get("date")),
                offers=offers,
                bids=bids,
            )
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_intraday(
        self,
        ticker: str,
        instrument_type: str,
        settlement: str,
    ) -> list[IntradayPoint]:
        try:
            data = self._ppi.marketdata.intraday(
                ticker, instrument_type, settlement
            )
            return [
                IntradayPoint(
                    date=_parse_datetime(d.get("date")),
                    price=d.get("price", 0),
                    volume=d.get("volume", 0),
                )
                for d in data
            ]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def estimate_bonds(
        self,
        ticker: str,
        date: datetime,
        quantity_type: str,
        quantity: float,
        price: float,
    ) -> dict[str, Any]:
        try:
            ppi_estimate = EstimateBonds(
                ticker=ticker,
                date=date,
                quantity_type=quantity_type,
                quantity=quantity,
                price=price,
            )
            result = self._ppi.marketdata.estimate_bonds(ppi_estimate)
            return dict(result) if result else {}
        except Exception as e:
            raise BrokerError(str(e)) from e

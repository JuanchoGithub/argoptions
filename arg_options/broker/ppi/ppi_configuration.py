from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from arg_options.broker.exceptions import BrokerError
from arg_options.broker.interfaces import ConfigurationService
from arg_options.broker.models import Holiday


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class PpiConfigurationService(ConfigurationService):
    def __init__(self, ppi: Any) -> None:
        self._ppi = ppi

    def get_instrument_types(self) -> list[str]:
        try:
            return self._ppi.configuration.get_instrument_types()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_markets(self) -> list[str]:
        try:
            return self._ppi.configuration.get_markets()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_settlements(self) -> list[str]:
        try:
            return self._ppi.configuration.get_settlements()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_quantity_types(self) -> list[str]:
        try:
            return self._ppi.configuration.get_quantity_types()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_operation_terms(self) -> list[str]:
        try:
            return self._ppi.configuration.get_operation_terms()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_operation_types(self) -> list[str]:
        try:
            return self._ppi.configuration.get_operation_types()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_operations(self) -> list[str]:
        try:
            return self._ppi.configuration.get_operations()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_holidays(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        is_usa: bool = False,
    ) -> list[Holiday]:
        try:
            data = self._ppi.configuration.get_holidays(
                start_date, end_date, is_usa=is_usa
            )
            return [
                Holiday(
                    date=_parse_datetime(d.get("date")),
                    description=d.get("description", ""),
                    is_usa=d.get("isUSA", False),
                )
                for d in data
            ]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def is_local_holiday(self) -> bool:
        try:
            return self._ppi.configuration.is_local_holiday()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def is_usa_holiday(self) -> bool:
        try:
            return self._ppi.configuration.is_usa_holiday()
        except Exception as e:
            raise BrokerError(str(e)) from e

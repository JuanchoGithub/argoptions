from __future__ import annotations

from arg_options.broker.interfaces import Broker, BrokerConfig


def create_broker(config: BrokerConfig) -> Broker:
    backend = "ppi"
    if backend == "ppi":
        from arg_options.broker.ppi.ppi_broker import PpiBroker

        return PpiBroker(config)
    raise ValueError(f"Unknown broker backend: {backend}")

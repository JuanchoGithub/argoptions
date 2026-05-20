"""Shared service for option chain operations."""

from __future__ import annotations

import logging
from typing import Tuple

import pandas as pd

from arg_options.broker import create_broker
from arg_options.config.settings import load_settings
from arg_options.core.chain import build_full_chain, persist_chain

logger = logging.getLogger(__name__)


class ChainService:
    """Centralized service for building and persisting option chains."""

    def __init__(self, mode: str = "test"):
        self.mode = mode
        self.config = load_settings(mode)

    def build_and_save_chain(self) -> Tuple[int, str]:
        """Builds a full chain from the broker and persists it to disk."""
        logger.info("=== CHAIN BUILD STARTED ===")
        broker = create_broker(self.config)
        try:
            broker.connect()
            rows = build_full_chain(broker, self.config)
            count, ts = persist_chain(rows, self.config)
            logger.info("Chain saved: %d rows at %s", count, ts)
            return count, ts
        finally:
            try:
                broker.disconnect()
            except Exception:
                pass

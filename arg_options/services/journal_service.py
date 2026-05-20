"""Shared service for journal and P&L operations."""

from __future__ import annotations

import logging
from typing import Any

from arg_options.broker import create_broker
from arg_options.config.settings import load_settings
from arg_options.core.journal import sync_journal

logger = logging.getLogger(__name__)


class JournalService:
    """Centralized service for journal synchronization and P&L."""

    def __init__(self, mode: str = "test"):
        self.mode = mode
        self.config = load_settings(mode)

    def sync_and_summarize(self) -> str:
        """Syncs the journal and returns the P&L summary."""
        broker = create_broker(self.config)
        try:
            broker.connect()
            summary = sync_journal(broker, self.config)
            return summary
        finally:
            try:
                broker.disconnect()
            except Exception:
                pass

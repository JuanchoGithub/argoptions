"""Shared screening service for CLI and TUI."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from arg_options.config.settings import load_settings
from arg_options.core.screen import run_screen

logger = logging.getLogger(__name__)


class ScreeningService:
    """Centralized screening service used by both CLI and TUI."""
    
    def __init__(self, mode: str = "test", use_stored: bool = True):
        self.mode = mode
        self.use_stored = use_stored
        self.config = load_settings(mode)
    
    def run_screening(self) -> pd.DataFrame:
        """Run screening and return results."""
        logger.info("=== SCREENING SERVICE ===")
        logger.info("Mode: %s, Use stored: %s", self.mode, self.use_stored)
        
        df = run_screen(self.config, use_stored=self.use_stored)
        logger.info("Screen results: %d rows", len(df))
        return df
    
    def get_screening_stats(self, df: pd.DataFrame) -> dict:
        """Get statistics about screening results."""
        if df.empty:
            return {"total_rows": 0, "filtered_rows": 0}
        
        return {
            "total_rows": len(df),
            "filtered_rows": len(df),
            "has_data": not df.empty,
            "sample_ticker": df.iloc[0].get('ticker', 'N/A') if len(df) > 0 else 'N/A'
        }
from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, time as dtime
from typing import Any, Optional

from arg_options.broker import create_broker
from arg_options.broker.interfaces import Broker, BrokerConfig
from arg_options.config.settings import load_settings
from arg_options.db import log_event
from arg_options.engine.approval import queue_opportunity
from arg_options.engine.strategies import (
    ExecutionMode,
    StrategyConfig,
    get_enabled_strategies,
)


class TradingEngine:
    def __init__(self, mode: str = "test", tick_interval: int = 60):
        self.mode = mode
        self.tick_interval = tick_interval
        self.config: BrokerConfig = load_settings(mode)
        self.broker: Broker = create_broker(self.config)
        self.running = False
        self._last_run: dict[str, datetime] = {}

    def start(self) -> None:
        self.running = True
        try:
            self.broker.connect()
            log_event("engine", "Engine started", f"mode={self.mode}")
        except Exception as e:
            logging.error("Failed to connect broker: %s", e)
            log_event("engine_error", f"Connection failed: {e}")
            return

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        while self.running:
            try:
                self._tick()
            except Exception as e:
                logging.error("Engine tick failed: %s", e)
                log_event("engine_error", str(e))
            time.sleep(self.tick_interval)

    def stop(self) -> None:
        self.running = False
        try:
            self.broker.disconnect()
        except Exception as e:
            logging.warning("Error disconnecting broker: %s", e)
        log_event("engine", "Engine stopped")

    def _handle_signal(self, signum: int, frame: Any) -> None:
        signame = signal.Signals(signum).name
        logging.info("Received signal %s, stopping engine...", signame)
        self.stop()

    def _tick(self) -> None:
        now = datetime.now()

        if not self._in_trading_hours(now):
            return

        strategies = get_enabled_strategies()
        if not strategies:
            return

        for strategy in strategies:
            if not self._should_run(strategy, now):
                continue
            self._process_strategy(strategy)

    def _process_strategy(self, strategy: StrategyConfig) -> None:
        logging.info("Processing strategy: %s", strategy.name)
        try:
            from arg_options.core.chain import build_full_chain
            from arg_options.core.discovery import DiscoveryEngine
        except ImportError:
            logging.warning(
                "Core modules (chain/discovery) not available — skipping strategy %s",
                strategy.name,
            )
            return

        try:
            rows = build_full_chain(self.broker, self.config)
            if not rows:
                return

            discovery = DiscoveryEngine(self.config)
            opportunities = discovery.run()

            for opp in opportunities:
                if strategy.mode == ExecutionMode.AUTO:
                    self._execute_opportunity(opp, strategy)
                else:
                    self._queue_for_approval(opp, strategy)
        except Exception as e:
            logging.error(
                "Error processing strategy %s: %s", strategy.name, e
            )
            log_event("strategy_error", f"{strategy.name}: {e}")

    def _execute_opportunity(self, opp: Any, strategy: StrategyConfig) -> None:
        logging.info("Auto-executing opportunity for %s", strategy.name)
        log_event(
            "auto_execution",
            f"Executing {strategy.name}",
            str(opp),
        )

    def _queue_for_approval(self, opp: Any, strategy: StrategyConfig) -> None:
        details = {
            "strategy_id": 0,
            "ticker": strategy.spot_ticker,
            "root": strategy.root,
            "opportunity": str(opp),
        }
        try:
            opp_details = getattr(opp, "_asdict", None) or getattr(opp, "asdict", None)
            if opp_details:
                obj = opp_details()
                if isinstance(obj, dict):
                    details["ticker"] = obj.get("ticker", details["ticker"])
        except Exception:
            pass

        approval_id = queue_opportunity(
            strategy_name=strategy.name,
            strategy_type=strategy.type.value,
            details=details,
            confidence=0.0,
        )
        log_event(
            "queued_for_approval",
            f"Opportunity queued for {strategy.name} (id={approval_id})",
        )

    def _in_trading_hours(self, now: datetime) -> bool:
        if now.weekday() >= 5:
            return False
        earliest_hour = 10
        latest_hour = 17
        if get_enabled_strategies():
            first = get_enabled_strategies()[0]
            earliest_hour = min(
                first.active_trading_hours[0], earliest_hour
            )
            latest_hour = max(
                first.active_trading_hours[1], latest_hour
            )
        current = dtime(now.hour, now.minute)
        return dtime(earliest_hour, 0) <= current < dtime(latest_hour, 0)

    def _should_run(self, strategy: StrategyConfig, now: datetime) -> bool:
        if not strategy.enabled:
            return False
        start_hour, end_hour = strategy.active_trading_hours
        current = dtime(now.hour, now.minute)
        if current < dtime(start_hour, 0) or current >= dtime(end_hour, 0):
            return False
        last = self._last_run.get(strategy.name)
        if last is None:
            self._last_run[strategy.name] = now
            return True
        elapsed = (now - last).total_seconds()
        if elapsed >= strategy.run_interval_minutes * 60:
            self._last_run[strategy.name] = now
            return True
        return False

    def run_once(self) -> None:
        try:
            self.broker.connect()
            self._tick()
        except Exception as e:
            logging.error("run_once failed: %s", e)
            log_event("engine_error", f"run_once failed: {e}")
        finally:
            try:
                self.broker.disconnect()
            except Exception:
                pass

    def run_interval_loop(self) -> None:
        self.start()


def run_once(mode: str = "test") -> None:
    engine = TradingEngine(mode)
    engine.run_once()


def run_continuous(mode: str = "test", interval: int = 60) -> None:
    engine = TradingEngine(mode, tick_interval=interval)
    engine.start()

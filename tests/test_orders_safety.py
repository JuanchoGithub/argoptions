from __future__ import annotations

from arg_options.broker.interfaces import BrokerConfig


def test_broker_config_defaults():
    config = BrokerConfig()
    assert config.sandbox is True
    assert config.allow_live_orders is False
    assert config.max_contracts_per_order == 100
    assert config.daily_notional_cap_ars == 1_000_000
    assert config.contract_multiplier == 1


def test_config_validation():
    config = BrokerConfig()
    assert isinstance(config.sandbox, bool)
    assert isinstance(config.allow_live_orders, bool)
    assert config.max_contracts_per_order > 0
    assert config.daily_notional_cap_ars > 0
    assert config.contract_multiplier >= 1
    assert 0 <= config.risk_free_rate <= 1


def test_live_orders_blocked_by_default():
    config = BrokerConfig()
    assert config.sandbox is True
    assert config.allow_live_orders is False


def test_explicit_live_orders_flag():
    config = BrokerConfig(allow_live_orders=True)
    assert config.allow_live_orders is True


def test_sandbox_false_allows_live():
    config = BrokerConfig(sandbox=False, allow_live_orders=True)
    assert config.sandbox is False
    assert config.allow_live_orders is True


def test_sandbox_true_and_live_false_is_safe():
    config = BrokerConfig(sandbox=True, allow_live_orders=False)
    assert config.sandbox is True
    assert config.allow_live_orders is False


def test_order_notional_cap():
    config = BrokerConfig(daily_notional_cap_ars=100_000)
    assert config.daily_notional_cap_ars == 100_000


def test_max_contracts():
    config = BrokerConfig(max_contracts_per_order=10)
    assert config.max_contracts_per_order == 10


def test_custom_contract_multiplier():
    config = BrokerConfig(contract_multiplier=100)
    assert config.contract_multiplier == 100

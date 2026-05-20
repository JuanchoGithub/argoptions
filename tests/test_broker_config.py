from __future__ import annotations

from dataclasses import asdict, replace

from arg_options.broker.interfaces import BrokerConfig


def test_default_config():
    config = BrokerConfig()
    assert config.sandbox is True
    assert config.allow_live_orders is False
    assert config.api_key == ""
    assert config.api_secret == ""
    assert config.account_number == ""
    assert config.authorized_client == ""
    assert config.client_key == ""
    assert config.daily_notional_cap_ars == 1_000_000
    assert config.max_contracts_per_order == 100
    assert config.contract_multiplier == 1
    assert config.risk_free_rate == 0.05


def test_custom_config():
    config = BrokerConfig(
        api_key="test-key",
        api_secret="test-secret",
        account_number="ACC123",
        authorized_client="client-1",
        client_key="ck-1",
        sandbox=False,
        allow_live_orders=True,
        daily_notional_cap_ars=500_000,
        max_contracts_per_order=50,
        contract_multiplier=100,
        risk_free_rate=0.055,
    )
    assert config.api_key == "test-key"
    assert config.api_secret == "test-secret"
    assert config.account_number == "ACC123"
    assert config.authorized_client == "client-1"
    assert config.client_key == "ck-1"
    assert config.sandbox is False
    assert config.allow_live_orders is True
    assert config.daily_notional_cap_ars == 500_000
    assert config.max_contracts_per_order == 50
    assert config.contract_multiplier == 100
    assert config.risk_free_rate == 0.055


def test_config_immutability():
    config = BrokerConfig(sandbox=True, allow_live_orders=False)
    replaced = replace(config, sandbox=False, allow_live_orders=True)
    assert config.sandbox is True
    assert config.allow_live_orders is False
    assert replaced.sandbox is False
    assert replaced.allow_live_orders is True


def test_config_is_dataclass():
    config = BrokerConfig()
    d = asdict(config)
    assert isinstance(d, dict)
    assert d["sandbox"] is True
    assert d["allow_live_orders"] is False
    assert d["daily_notional_cap_ars"] == 1_000_000


def test_sandbox_disables_live_orders_by_default():
    config = BrokerConfig()
    assert config.sandbox is True
    assert config.allow_live_orders is False


def test_production_config():
    config = BrokerConfig(
        sandbox=False,
        allow_live_orders=True,
        api_key="prod-key",
        api_secret="prod-secret",
        account_number="PROD001",
    )
    assert config.sandbox is False
    assert config.allow_live_orders is True


def test_max_contracts_per_order_default():
    config = BrokerConfig()
    assert config.max_contracts_per_order == 100


def test_daily_notional_cap_default():
    config = BrokerConfig()
    assert config.daily_notional_cap_ars == 1_000_000


def test_risk_free_rate_default():
    config = BrokerConfig()
    assert config.risk_free_rate == 0.05


def test_contract_multiplier_default():
    config = BrokerConfig()
    assert config.contract_multiplier == 1

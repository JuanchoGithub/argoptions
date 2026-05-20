from __future__ import annotations

from arg_options.broker.exceptions import (
    AuthError,
    BrokerError,
    ConfigurationError,
    ConnectionError,
    InvalidInstrumentError,
    NotAuthenticatedError,
    OrderBudgetError,
    OrderRejectedError,
    RateLimitError,
)


def test_broker_error_is_base():
    assert issubclass(AuthError, BrokerError)
    assert issubclass(ConnectionError, BrokerError)
    assert issubclass(OrderRejectedError, BrokerError)
    assert issubclass(OrderBudgetError, BrokerError)
    assert issubclass(InvalidInstrumentError, BrokerError)
    assert issubclass(RateLimitError, BrokerError)
    assert issubclass(ConfigurationError, BrokerError)
    assert issubclass(NotAuthenticatedError, BrokerError)


def test_broker_error_message():
    err = BrokerError("something went wrong")
    assert str(err) == "something went wrong"


def test_auth_error_message():
    err = AuthError("invalid credentials")
    assert str(err) == "invalid credentials"


def test_connection_error_message():
    err = ConnectionError("timeout connecting to broker")
    assert str(err) == "timeout connecting to broker"


def test_order_rejected_error_message():
    err = OrderRejectedError("order rejected: insufficient funds")
    assert str(err) == "order rejected: insufficient funds"


def test_order_budget_error_message():
    err = OrderBudgetError("budget calculation failed")
    assert str(err) == "budget calculation failed"


def test_invalid_instrument_error_message():
    err = InvalidInstrumentError("unknown ticker")
    assert str(err) == "unknown ticker"


def test_rate_limit_error_message():
    err = RateLimitError("rate limit exceeded")
    assert str(err) == "rate limit exceeded"


def test_configuration_error_message():
    err = ConfigurationError("missing API key")
    assert str(err) == "missing API key"


def test_not_authenticated_error_message():
    err = NotAuthenticatedError("user not logged in")
    assert str(err) == "user not logged in"


def test_isinstance_checks():
    assert isinstance(AuthError("x"), BrokerError)
    assert isinstance(ConnectionError("x"), BrokerError)
    assert isinstance(OrderRejectedError("x"), BrokerError)
    assert isinstance(OrderBudgetError("x"), BrokerError)
    assert isinstance(InvalidInstrumentError("x"), BrokerError)
    assert isinstance(RateLimitError("x"), BrokerError)
    assert isinstance(ConfigurationError("x"), BrokerError)
    assert isinstance(NotAuthenticatedError("x"), BrokerError)


def test_broker_error_is_exception():
    assert issubclass(BrokerError, Exception)


def test_auth_error_is_not_broker_error_subclass():
    assert not issubclass(ConnectionError, AuthError)
    assert not issubclass(OrderRejectedError, AuthError)

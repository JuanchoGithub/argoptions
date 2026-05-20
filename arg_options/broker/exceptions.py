from __future__ import annotations


class BrokerError(Exception):
    """Base exception for all broker-related errors."""


class AuthError(BrokerError):
    """Raised when authentication with the broker fails."""


class ConnectionError(BrokerError):
    """Raised when unable to connect to the broker."""


class OrderRejectedError(BrokerError):
    """Raised when an order is rejected by the broker."""


class OrderBudgetError(BrokerError):
    """Raised when the budget calculation for an order fails."""


class InvalidInstrumentError(BrokerError):
    """Raised when an instrument ticker or type is invalid."""


class RateLimitError(BrokerError):
    """Raised when the broker API rate limit is hit."""


class ConfigurationError(BrokerError):
    """Raised when broker configuration is invalid or missing."""


class NotAuthenticatedError(BrokerError):
    """Raised when an operation is attempted without authentication."""

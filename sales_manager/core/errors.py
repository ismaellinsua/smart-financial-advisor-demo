"""Errors the store raises. Their messages are safe to show to the people using the app."""


class SaleError(Exception):
    """Raised when a sale cannot be completed (e.g. insufficient stock)."""


class FiscalDataError(ValueError):
    """Raised when an operation would delete or replace real sales, invoices or cash closings."""


class AuthError(Exception):
    """Raised when a login fails. The message is safe to show: it never reveals whether a user exists."""


class PermissionDenied(SaleError, ValueError):
    """Raised when the role given to a sensitive operation is not allowed to do it (a second check behind the pages)."""

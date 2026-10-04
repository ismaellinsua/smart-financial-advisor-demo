"""Business clock: the local wall time where the business is, whatever time zone the server runs in.

Cloud servers run in UTC, so `datetime.now()` would stamp tickets, invoices and cash closings hours off.
Times are stored as naive local wall time, as they always have been.
"""

import threading
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Europe/Madrid"

TIMEZONES = {
    "Europe/Madrid": "España peninsular y Baleares",
    "Atlantic/Canary": "Canarias",
    "Europe/Lisbon": "Portugal",
    "Europe/London": "Reino Unido",
    "America/Mexico_City": "México (centro)",
    "America/Bogota": "Colombia",
    "America/Lima": "Perú",
    "America/Santiago": "Chile",
    "America/Argentina/Buenos_Aires": "Argentina",
    "America/New_York": "EE. UU. (este)",
}

_DEFAULT_ZONE = ZoneInfo(DEFAULT_TIMEZONE)
# One app can serve several businesses in different time zones: each page run (its own thread in Streamlit)
# carries the zone of the business it is serving.
_local = threading.local()


def _current() -> ZoneInfo:
    return getattr(_local, "zone", _DEFAULT_ZONE)


def zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Zona horaria no válida: {name}.") from exc


def set_timezone(name: str | None) -> None:
    """Use the business's time zone; an unknown value falls back to the default instead of breaking the app."""
    try:
        _local.zone = zone(name)
    except ValueError:
        _local.zone = _DEFAULT_ZONE


def timezone_name() -> str:
    return _current().key


def now() -> datetime:
    return datetime.now(_current()).replace(tzinfo=None)


def today() -> date:
    return now().date()


def now_aware() -> datetime:
    """Now with the business's UTC offset, e.g. 2026-10-04T20:30:12+02:00 (VERI*FACTU records need it)."""
    return datetime.now(_current()).replace(microsecond=0)

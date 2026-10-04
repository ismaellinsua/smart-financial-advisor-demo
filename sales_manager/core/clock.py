"""Business clock: the local wall time where the business is, whatever time zone the server runs in.

Cloud servers run in UTC, so `datetime.now()` would stamp tickets, invoices and cash closings hours off.
Times are stored as naive local wall time, as they always have been.
"""

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

_zone = ZoneInfo(DEFAULT_TIMEZONE)


def zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Zona horaria no válida: {name}.") from exc


def set_timezone(name: str | None) -> None:
    """Use the business's time zone; an unknown value falls back to the default instead of breaking the app."""
    global _zone
    try:
        _zone = zone(name)
    except ValueError:
        _zone = ZoneInfo(DEFAULT_TIMEZONE)


def timezone_name() -> str:
    return _zone.key


def now() -> datetime:
    return datetime.now(_zone).replace(tzinfo=None)


def today() -> date:
    return now().date()


def now_aware() -> datetime:
    """Now with the business's UTC offset, e.g. 2026-10-04T20:30:12+02:00 (VERI*FACTU records need it)."""
    return datetime.now(_zone).replace(microsecond=0)

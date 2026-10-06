"""Emails about online bookings: the customer's confirmation (with a calendar file), the notice to the business
and the reminder the day before. Customers' replies go to the business's own email."""

from datetime import datetime, timedelta, UTC

from . import clock
from .mailer import Mailer, valid_email

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def when_text(starts_at) -> str:
    starts_at = datetime.fromisoformat(starts_at) if isinstance(starts_at, str) else starts_at
    return f"{WEEKDAYS[starts_at.weekday()]} {starts_at:%d/%m/%Y} a las {starts_at:%H:%M}"


def what_text(booking: dict) -> str:
    if booking.get("people"):
        return f"Mesa para {booking['people']} persona{'s' if booking['people'] != 1 else ''}"
    return booking.get("service") or "Cita"


def _ics_text(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar_file(booking: dict, settings: dict) -> bytes:
    """An .ics event in the business's time zone, so phones and calendars show it at the right time."""
    start = datetime.fromisoformat(booking["starts_at"]) if isinstance(booking["starts_at"], str) else booking["starts_at"]
    end = start + timedelta(minutes=int(booking.get("duration_min") or 60))
    zone = settings.get("timezone") or clock.DEFAULT_TIMEZONE
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NirKanA//Reservas//ES", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:reserva-{booking['id']}-{start:%Y%m%d%H%M}@nirkana.es", f"DTSTAMP:{stamp}",
        f"DTSTART;TZID={zone}:{start:%Y%m%dT%H%M%S}", f"DTEND;TZID={zone}:{end:%Y%m%dT%H%M%S}",
        f"SUMMARY:{_ics_text(what_text(booking) + ' · ' + settings.get('business_name', ''))}",
        f"LOCATION:{_ics_text(settings.get('address', ''))}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return ("\r\n".join(lines) + "\r\n").encode()


def _contact(settings: dict) -> str:
    bits = [settings.get("address", ""), settings.get("phone", "")]
    return " · ".join(b for b in bits if b)


def send_confirmation(mailer: Mailer, booking: dict, settings: dict, manage_url: str) -> None:
    name = settings.get("business_name", "")
    text = (f"Hola, {booking['customer_name']}:\n\n"
            f"Tu reserva en {name} está confirmada.\n\n"
            f"{what_text(booking)}\n{when_text(booking['starts_at']).capitalize()}\n"
            f"{_contact(settings)}\n\n"
            f"Si no puedes venir, cancélala aquí para dejar el hueco a otra persona:\n{manage_url}\n\n"
            "Te enviaremos un recordatorio el día antes.\n\n"
            f"{name}")
    mailer.send(booking["email"], f"Reserva confirmada · {name} · {when_text(booking['starts_at'])}", text,
                attachments=[("reserva.ics", calendar_file(booking, settings), "text/calendar")],
                reply_to=settings.get("email", ""))


def notify_business(mailer: Mailer, booking: dict, settings: dict) -> None:
    to = settings.get("email", "")
    if not valid_email(to):
        return
    mailer.send(to, f"Nueva reserva online · {when_text(booking['starts_at'])}",
                f"Hola:\n\nTienes una reserva nueva desde la web:\n\n{what_text(booking)}\n"
                f"{when_text(booking['starts_at']).capitalize()}\nA nombre de: {booking['customer_name']}\n\n"
                "La verás en la Agenda de la app, con su teléfono.\n\nNirKanA")


def send_reminders(store, mailer: Mailer, settings: dict, now: datetime) -> int:
    """Remind tomorrow's customers who left an email. Each one at most once. Returns how many were sent."""
    name = settings.get("business_name", "")
    sent = 0
    for booking in store.reminders_due(now):
        if not valid_email(booking["email"]):
            continue
        mailer.send(booking["email"], f"Recordatorio: mañana en {name}",
                    f"Hola, {booking['customer_name']}:\n\nTe recordamos tu reserva en {name}:\n\n"
                    f"{what_text(booking)}\n{when_text(booking['starts_at']).capitalize()}\n{_contact(settings)}\n\n"
                    "Si no puedes venir, usa el enlace de cancelación del correo de confirmación o responde a este "
                    f"mensaje.\n\n{name}", reply_to=settings.get("email", ""))
        store.mark_reminded(booking["id"], now)
        sent += 1
    return sent

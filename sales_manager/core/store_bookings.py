"""Online booking: customers pick a free time on a public page, cancel with their own link and get a reminder.

The business decides its opening hours, how far ahead and with how much notice people may book, and (one
person's diary) which services can be booked or (restaurant) how many diners fit at the same time. The public page
only ever learns which times are free: never who booked the others.

A customer's phone and email on an online booking are kept until CONTACT_DAYS after the appointment, then erased.
"""

import hashlib
import json
import re
import secrets
from datetime import date, datetime, time, timedelta

from . import clock
from .mailer import valid_email
from .presets import PRESETS
from .security import clean_text

AGENDA_LOCK = "__agenda__"  # counters row locked while a booking is checked and saved, so two can't take one slot
WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
CONTACT_DAYS = 90
UNKNOWN_PARTY = 2  # diners counted for a reservation saved without the number of people
MAX_PENDING_PER_PHONE = 2
MAX_PENDING_PER_EMAIL = 2
# The public page is open to anyone: a ceiling on online bookings per hour for the whole business keeps a script
# from filling the diary or making the business's email account send confirmations to strangers.
MAX_ONLINE_PER_HOUR = 20
# A name never contains a link or an address: it is quoted in the confirmation email.
_LINK_IN_NAME = re.compile(r"https?:|www\.|@|://|\.(com|net|org|io|es|ru|xyz|info|top)\b", re.I)
_RANGE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*[-–]\s*(\d{1,2})[:.](\d{2})\s*$")


def agenda_preset(business_type: str) -> dict:
    return PRESETS.get(business_type, {}).get("agenda") or {"title": "Agenda", "single": True, "duration": 60}


def parse_ranges(text: str) -> list[tuple[time, time]]:
    """«09:00-14:00, 16:00-20:00» → [(09:00, 14:00), (16:00, 20:00)]; empty means closed that day."""
    ranges = []
    for part in filter(str.strip, str(text or "").split(",")):
        m = _RANGE.match(part)
        if not m:
            raise ValueError(f"Horario no válido: «{part.strip()}». Escríbelo así: 09:00-14:00, 16:00-20:00.")
        h1, m1, h2, m2 = map(int, m.groups())
        if h1 > 23 or h2 > 24 or m1 > 59 or m2 > 59 or (h2 == 24 and m2):
            raise ValueError(f"Hora no válida en «{part.strip()}».")
        start = time(h1, m1)
        end = time(23, 59) if h2 == 24 else time(h2, m2)
        if end <= start:
            raise ValueError(f"En «{part.strip()}» la hora de cierre debe ser posterior a la de apertura.")
        ranges.append((start, end))
    ranges.sort()
    for (_, end), (start, _) in zip(ranges, ranges[1:]):
        if start < end:
            raise ValueError("Los tramos de horario se solapan.")
    return ranges


def parse_closed_days(text: str) -> set[date]:
    """«24/12/2026, 25/12/2026» → those dates."""
    days = set()
    for part in filter(str.strip, str(text or "").replace(";", ",").split(",")):
        try:
            days.add(datetime.strptime(part.strip(), "%d/%m/%Y").date())
        except ValueError:
            raise ValueError(f"Fecha no válida: «{part.strip()}». Escríbela como dd/mm/aaaa.") from None
    return days


def clean_phone(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", str(phone or ""))
    if not 9 <= len(digits.lstrip("+")) <= 15 or "+" in digits[1:]:
        raise ValueError("Escribe un teléfono válido (9 cifras, o con prefijo de país).")
    return digits


def _hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode()).hexdigest()


def _overlaps(start: datetime, minutes: int, other_start: datetime, other_minutes: int) -> bool:
    return start < other_start + timedelta(minutes=other_minutes) and other_start < start + timedelta(minutes=minutes)


class BookingMixin:
    # ------------------------------------------------------------------ rules
    def booking_rules(self, settings: dict | None = None) -> dict:
        s = settings or self.settings()
        preset = agenda_preset(s.get("business_type", "retail"))
        try:
            hours = {int(k): parse_ranges(v) for k, v in json.loads(s.get("booking_hours") or "{}").items()}
        except (ValueError, TypeError):
            hours = {}
        try:
            closed = parse_closed_days(s.get("booking_closed", ""))
        except ValueError:
            closed = set()
        number = lambda key, default: int(float(s.get(key) or default))  # noqa: E731
        services = [int(x) for x in str(s.get("booking_services") or "").split(",") if x.strip().isdigit()]
        return {
            "enabled": s.get("booking_online") == "si",
            "single": bool(preset.get("single", True)),
            "hours": hours,
            "closed": closed,
            "step": max(5, number("booking_step", 30)),
            "duration": max(5, number("booking_duration", preset.get("duration", 60))),
            "days_ahead": max(1, number("booking_days", 30)),
            "notice_hours": max(0, number("booking_notice_hours", 2)),
            "capacity": max(1, number("booking_capacity", 30)),
            "max_party": max(1, number("booking_max_party", 10)),
            "services": services,
        }

    def save_booking_rules(self, values: dict) -> None:
        """Validate and save what the business set in the Agenda (raises ValueError with a readable message)."""
        hours = {}
        for day, text in values.get("hours", {}).items():
            if parse_ranges(text):
                hours[str(int(day))] = ", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in parse_ranges(text))
        parse_closed_days(values.get("closed", ""))
        out = {"booking_hours": json.dumps(hours, sort_keys=True), "booking_closed": values.get("closed", "").strip(),
               "booking_services": ",".join(str(int(i)) for i in values.get("services", []))}
        limits = {"step": (5, 240), "duration": (5, 600), "days": (1, 365), "notice_hours": (0, 168),
                  "capacity": (1, 1000), "max_party": (1, 100)}
        for key, (low, high) in limits.items():
            if key in values:
                value = int(values[key])
                if not low <= value <= high:
                    raise ValueError(f"Valor fuera de rango ({low}–{high}).")
                out[f"booking_{key}"] = str(value)
        if "enabled" in values:
            if values["enabled"] and not hours:
                raise ValueError("Indica al menos un día con horario antes de abrir las reservas online.")
            out["booking_online"] = "si" if values["enabled"] else "no"
        self.save_settings(out)

    # ------------------------------------------------------------------ availability
    def _taken(self, cur, day: date) -> list[dict]:
        start = datetime.combine(day, time.min)
        return cur.execute(
            "SELECT starts_at, duration_min, people FROM appointments WHERE starts_at >= ? AND starts_at < ? "
            "AND status IN ('pendiente', 'completada')",
            (start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds")),
        ).fetchall()

    @staticmethod
    def _fits(rules: dict, taken: list[dict], start: datetime, people: int) -> bool:
        clash = [t for t in taken
                 if _overlaps(start, rules["duration"], datetime.fromisoformat(t["starts_at"]), t["duration_min"])]
        if rules["single"]:
            return not clash
        return sum(t["people"] or UNKNOWN_PARTY for t in clash) + max(1, people) <= rules["capacity"]

    @staticmethod
    def _candidates(rules: dict, day: date, now: datetime) -> list[datetime]:
        if day in rules["closed"] or not now.date() <= day <= now.date() + timedelta(days=rules["days_ahead"]):
            return []
        earliest = now + timedelta(hours=rules["notice_hours"])
        out = []
        for opens, closes in rules["hours"].get(day.weekday(), []):
            start, end = datetime.combine(day, opens), datetime.combine(day, closes)
            while start + timedelta(minutes=rules["duration"]) <= end:
                if start >= earliest:
                    out.append(start)
                start += timedelta(minutes=rules["step"])
        return out

    def free_slots(self, day: date, people: int = 0, now: datetime | None = None) -> list[datetime]:
        rules = self.booking_rules()
        now = now or clock.now()
        candidates = self._candidates(rules, day, now)
        if not candidates:
            return []
        with self.db.tx() as cur:
            taken = self._taken(cur, day)
        return [s for s in candidates if self._fits(rules, taken, s, people)]

    def bookable_days(self, now: datetime | None = None) -> list[date]:
        """Days that have opening hours within the booking window (free times are checked per day)."""
        rules = self.booking_rules()
        now = now or clock.now()
        days = (now.date() + timedelta(days=n) for n in range(rules["days_ahead"] + 1))
        return [d for d in days if self._candidates(rules, d, now)]

    # ------------------------------------------------------------------ booking
    def book_online(self, starts_at: datetime, name: str, phone: str, email: str = "", product_id: int | None = None,
                    people: int = 0, notes: str = "", now: datetime | None = None) -> dict:
        """Save a customer's own booking after checking again, under a lock, that the time is still free.
        Returns the appointment with its cancel token (shown to the customer once; only its hash is kept)."""
        rules = self.booking_rules()
        if not rules["enabled"]:
            raise ValueError("Este negocio no acepta reservas online ahora mismo.")
        now = now or clock.now()
        name = clean_text(name, "Nombre", "name")
        if not name:
            raise ValueError("Escribe tu nombre.")
        if _LINK_IN_NAME.search(name):
            raise ValueError("Escribe solo tu nombre, sin enlaces ni direcciones.")
        phone = clean_phone(phone)
        email = clean_text(email, "Email", "email").lower()
        if email and not valid_email(email):
            raise ValueError("El email no es válido.")
        notes = clean_text(notes, "Comentarios", "notes")
        people = int(people or 0)
        if rules["single"]:
            people = 0
            if rules["services"]:
                if product_id is None or int(product_id) not in rules["services"]:
                    raise ValueError("Elige un servicio.")
            else:
                product_id = None
        else:
            product_id = None
            if not 1 <= people <= rules["max_party"]:
                raise ValueError(f"Para más de {rules['max_party']} personas, llama al negocio.")
        starts_at = starts_at.replace(second=0, microsecond=0)
        if starts_at not in self._candidates(rules, starts_at.date(), now):
            raise ValueError("Esa hora ya no está disponible. Elige otra.")
        token = secrets.token_urlsafe(18)
        with self.db.tx() as cur:
            cur.execute("INSERT INTO counters(series, value) VALUES (?, 1) "
                        "ON CONFLICT(series) DO UPDATE SET value = counters.value + 1", (AGENDA_LOCK,))
            if product_id is not None and not cur.execute(
                    "SELECT 1 FROM products WHERE id = ? AND active = 1", (int(product_id),)).fetchone():
                raise ValueError("Ese servicio ya no está disponible.")
            pending = cur.execute(
                "SELECT COUNT(*) AS n FROM appointments WHERE phone = ? AND status = 'pendiente' AND starts_at >= ?",
                (phone, now.isoformat(timespec="seconds")),
            ).fetchone()["n"]
            if pending >= MAX_PENDING_PER_PHONE:
                raise ValueError("Ya tienes reservas pendientes con este teléfono. Si necesitas otra, llama al negocio.")
            if email and cur.execute(
                    "SELECT COUNT(*) AS n FROM appointments WHERE email = ? AND status = 'pendiente' AND starts_at >= ?",
                    (email, now.isoformat(timespec="seconds"))).fetchone()["n"] >= MAX_PENDING_PER_EMAIL:
                raise ValueError("Ya tienes reservas pendientes con este email. Si necesitas otra, llama al negocio.")
            recent = cur.execute("SELECT COUNT(*) AS n FROM appointments WHERE source = 'online' AND created_at >= ?",
                                 ((now - timedelta(hours=1)).isoformat(timespec="seconds"),)).fetchone()["n"]
            if recent >= MAX_ONLINE_PER_HOUR:
                raise ValueError("Ahora mismo no podemos aceptar más reservas online. Prueba en un rato o llama al "
                                 "negocio.")
            if not self._fits(rules, self._taken(cur, starts_at.date()), starts_at, people):
                raise ValueError("Esa hora se acaba de ocupar. Elige otra.")
            row = cur.execute(
                "INSERT INTO appointments(starts_at, duration_min, customer_name, product_id, notes, created_at, "
                "created_by, phone, email, people, source, cancel_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, 'Reserva online', ?, ?, ?, 'online', ?) RETURNING id",
                (starts_at.isoformat(timespec="seconds"), rules["duration"], name,
                 None if product_id is None else int(product_id), notes, now.isoformat(timespec="seconds"),
                 phone, email, people, _hash(token)),
            ).fetchone()
        return {**self.online_booking(token), "token": token, "id": row["id"]}

    def online_booking(self, token: str) -> dict | None:
        if not token or len(token) > 64:
            return None
        with self.db.tx() as cur:
            row = cur.execute(
                "SELECT a.id, a.starts_at, a.duration_min, a.customer_name, a.people, a.status, a.email, "
                "p.name AS service FROM appointments a LEFT JOIN products p ON p.id = a.product_id "
                "WHERE a.cancel_hash = ?", (_hash(token),),
            ).fetchone()
        return dict(row) if row else None

    def cancel_online_booking(self, token: str, now: datetime | None = None) -> dict:
        booking = self.online_booking(token)
        now = now or clock.now()
        if booking is None:
            raise ValueError("No encontramos esa reserva. Revisa el enlace.")
        if booking["status"] != "pendiente":
            raise ValueError("Esta reserva ya no se puede cancelar.")
        if datetime.fromisoformat(booking["starts_at"]) <= now:
            raise ValueError("La cita ya ha empezado. Llama al negocio.")
        with self.db.tx() as cur:
            cur.execute("UPDATE appointments SET status = 'cancelada' WHERE id = ? AND status = 'pendiente'",
                        (booking["id"],))
        return {**booking, "status": "cancelada"}

    # ------------------------------------------------------------------ reminders and retention
    def reminders_due(self, now: datetime | None = None) -> list[dict]:
        """Tomorrow's pending appointments with an email that have not been reminded yet."""
        now = now or clock.now()
        start = datetime.combine(now.date() + timedelta(days=1), time.min)
        with self.db.tx() as cur:
            rows = cur.execute(
                "SELECT a.id, a.starts_at, a.customer_name, a.email, a.people, p.name AS service "
                "FROM appointments a LEFT JOIN products p ON p.id = a.product_id "
                "WHERE a.starts_at >= ? AND a.starts_at < ? AND a.status = 'pendiente' AND a.email <> '' "
                "AND a.reminded_at = '' ORDER BY a.starts_at",
                (start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds")),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_reminded(self, appointment_id: int, now: datetime | None = None) -> None:
        with self.db.tx() as cur:
            cur.execute("UPDATE appointments SET reminded_at = ? WHERE id = ?",
                        ((now or clock.now()).isoformat(timespec="seconds"), int(appointment_id)))

    def forget_booking_contacts(self, now: datetime | None = None) -> int:
        """Erase the phone and email of appointments that ended more than CONTACT_DAYS ago. Returns how many."""
        before = (now or clock.now()) - timedelta(days=CONTACT_DAYS)
        with self.db.tx() as cur:
            return cur.execute(
                "UPDATE appointments SET phone = '', email = '', cancel_hash = '' "
                "WHERE starts_at < ? AND (phone <> '' OR email <> '' OR cancel_hash <> '')",
                (before.isoformat(timespec="seconds"),),
            ).rowcount

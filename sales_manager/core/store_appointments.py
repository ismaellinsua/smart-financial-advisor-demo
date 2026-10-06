"""Appointments for service businesses and charging them as sales. Mixed into `Store`."""

from datetime import datetime, timedelta

import pandas as pd

from . import clock
from .errors import SaleError
from .security import clean_text
from .store_bookings import AGENDA_LOCK, clean_phone


class AppointmentsMixin:
    # -------------------------------------------------------------- appointments
    def appointments(self, start: datetime, end: datetime) -> pd.DataFrame:
        df = self._frame(
            "SELECT a.*, COALESCE(c.name, a.customer_name) AS who, COALESCE(NULLIF(a.phone, ''), c.phone) "
            "AS customer_phone, "
            "p.name AS service, p.price AS price "
            "FROM appointments a LEFT JOIN customers c ON c.id = a.customer_id "
            "LEFT JOIN products p ON p.id = a.product_id "
            "WHERE a.starts_at >= ? AND a.starts_at < ? ORDER BY a.starts_at",
            (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
        )
        df["starts_at"] = pd.to_datetime(df["starts_at"])
        return df

    def create_appointment(
        self,
        starts_at: datetime,
        duration_min: int,
        product_id: int | None = None,
        customer_id: int | None = None,
        customer_name: str = "",
        notes: str = "",
        allow_overlap: bool = False,
        created_by: str = "",
        people: int = 0,
        phone: str = "",
    ) -> int:
        duration_min = int(duration_min)
        if not 0 < duration_min <= 24 * 60:
            raise ValueError("La duración debe estar entre 1 minuto y 24 horas.")
        customer_name = clean_text(customer_name, "Cliente", "name")
        notes = clean_text(notes, "Notas", "notes")
        if customer_id is None and not customer_name:
            raise ValueError("Indica el cliente de la cita.")
        people = int(people or 0)
        if not 0 <= people <= 1000:
            raise ValueError("Número de personas no válido.")
        phone = clean_phone(phone) if str(phone or "").strip() else ""
        starts_at = starts_at.replace(second=0, microsecond=0)
        ends_at = starts_at + timedelta(minutes=duration_min)
        with self.db.tx() as cur:
            # Same lock as online bookings: a customer booking from the web and the team can't take one slot twice.
            cur.execute("INSERT INTO counters(series, value) VALUES (?, 1) "
                        "ON CONFLICT(series) DO UPDATE SET value = counters.value + 1", (AGENDA_LOCK,))
            # Look at the same day only; a single agenda cannot hold two appointments at once.
            day_start = starts_at.replace(hour=0, minute=0)
            others = cur.execute(
                "SELECT a.starts_at, a.duration_min, COALESCE(c.name, a.customer_name) AS who "
                "FROM appointments a LEFT JOIN customers c ON c.id = a.customer_id "
                "WHERE a.starts_at >= ? AND a.starts_at < ? AND a.status IN ('pendiente', 'completada')",
                (day_start.isoformat(timespec="seconds"), (day_start + timedelta(days=1)).isoformat(timespec="seconds")),
            ).fetchall()
            for o in [] if allow_overlap else others:
                o_start = datetime.fromisoformat(o["starts_at"])
                o_end = o_start + timedelta(minutes=o["duration_min"])
                if starts_at < o_end and o_start < ends_at:
                    raise ValueError(
                        f"Ese hueco se solapa con la cita de {o['who']} "
                        f"({o_start:%H:%M}–{o_end:%H:%M}). Elige otra hora."
                    )
            row = cur.execute(
                "INSERT INTO appointments(starts_at, duration_min, customer_id, customer_name, product_id, notes, "
                "created_at, created_by, people, phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (starts_at.isoformat(timespec="seconds"), duration_min,
                 None if customer_id is None else int(customer_id), customer_name,
                 None if product_id is None else int(product_id), notes,
                 clock.now().isoformat(timespec="seconds"), created_by, people, phone),
            ).fetchone()
            return row["id"]

    APPOINTMENT_STATUSES = ("pendiente", "completada", "cancelada", "no_presentado")

    def set_appointment_status(self, appointment_id: int, status: str) -> None:
        if status not in self.APPOINTMENT_STATUSES:
            raise ValueError("Estado de cita no válido.")
        with self.db.tx() as cur:
            appt = cur.execute("SELECT sale_id FROM appointments WHERE id = ?", (int(appointment_id),)).fetchone()
            if appt is None:
                raise ValueError("Cita no encontrada.")
            if appt["sale_id"] is not None:
                raise ValueError("Esta cita ya está cobrada.")
            cur.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, int(appointment_id)))

    def charge_appointment(
        self, appointment_id: int, payment_method: str, discount_pct: float = 0.0, user_name: str = "",
        location_id: int | None = None,
    ) -> dict:
        """Charge an appointment's service: registers the sale and marks the appointment as done, atomically."""
        appointment_id = int(appointment_id)
        for attempt in range(3):
            try:
                with self.db.tx() as cur:
                    appt = cur.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
                    if appt is None or appt["status"] != "pendiente":
                        raise SaleError("Solo se pueden cobrar citas pendientes.")
                    if appt["product_id"] is None:
                        raise SaleError("La cita no tiene servicio asociado: cóbrala desde Vender.")
                    sale_id = self._insert_sale(
                        cur, [{"product_id": appt["product_id"], "quantity": 1}], payment_method,
                        appt["customer_id"], float(discount_pct), None, clock.now(), user_name,
                        location_id=location_id,
                    )
                    cur.execute(
                        "UPDATE appointments SET status = 'completada', sale_id = ? WHERE id = ?",
                        (sale_id, appointment_id),
                    )
                return self.sale(sale_id)
            except self.db.integrity_errors:
                if attempt == 2:
                    raise SaleError("No se pudo cobrar la cita. Inténtalo de nuevo.") from None
        raise AssertionError("unreachable")

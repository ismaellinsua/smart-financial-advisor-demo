"""Emails a business asked for: the weekly report every Monday and a notice when there are new important alerts;
and to its customers, a reminder the day before an appointment they left their email for.

Run by the scheduled job (ops/notify.py). Each business opts in from Configuración; nothing is sent in
demonstration mode or without a valid business email. What was last sent is remembered in the business's own
settings, so a job that runs twice never sends the same email twice.
"""

import hashlib
from datetime import datetime, timedelta

from . import clock
from .booking_mail import send_reminders
from .mailer import Mailer, valid_email
from .pdfs import weekly_report_pdf
from .presets import CURRENCIES
from .pricing import format_money
from .store_intel import week_start


def _week_label(start: datetime) -> str:
    end = start + timedelta(days=6)
    return f"{start:%d/%m} al {end:%d/%m/%Y}"


def send_due(store, mailer: Mailer, now: datetime | None = None) -> list[str]:
    """Send whatever is due for one business. Returns what was sent (for the job's log, without addresses)."""
    settings = store.settings()
    clock.set_timezone(settings.get("timezone"))
    now = now or clock.now()
    to = (settings.get("email") or "").strip()
    if settings.get("demo_mode") == "si":
        return []
    sent = []
    store.forget_booking_contacts(now)
    store.apply_retention(now)
    if reminded := send_reminders(store, mailer, settings, now):
        sent.append(f"{reminded} recordatorio(s) de cita")
    if not valid_email(to):
        return sent
    name = settings.get("business_name", "")

    last_week = week_start(now.date()) - timedelta(days=7)
    if (settings.get("email_weekly") == "si" and now.weekday() == 0
            and settings.get("email_weekly_last") != last_week.date().isoformat()):
        report = store.weekly_report(last_week, now=now)
        n = report["numbers"]["cur"]
        text = (f"Hola:\n\nAdjuntamos el informe de {name} de la semana del {_week_label(last_week)}: ventas, lo más "
                f"vendido, equipo, caja, beneficio estimado, alertas y recomendaciones.\n\n"
                f"Facturación: {format_money(n['revenue'], CURRENCIES.get(settings.get('currency', 'EUR'), '€'))} "
                f"en {n['count']} tickets.\n\n"
                "Lo tienes también en el Panel de la app.\n\nNirKanA")
        mailer.send(to, f"Informe semanal de {name} · {_week_label(last_week)}", text,
                    attachments=[(f"informe-{last_week:%Y-%m-%d}.pdf", weekly_report_pdf(report, settings),
                                  "application/pdf")])
        store.save_settings({"email_weekly_last": last_week.date().isoformat()})
        sent.append("informe semanal")

    if settings.get("email_alerts") == "si":
        important = [a for a in store.alerts(now) if a["level"] == "alta"]
        key = hashlib.sha256("|".join(sorted(a["title"] for a in important)).encode()).hexdigest()[:16]
        if important and key != settings.get("email_alerts_last"):
            lines = "\n".join(f"• {a['title']}: {a['detail']}" for a in important)
            mailer.send(to, f"{len(important)} aviso(s) importante(s) en {name}",
                        f"Hola:\n\nHay avisos que conviene mirar hoy:\n\n{lines}\n\nMás detalle en el Panel de la app."
                        "\n\nNirKanA")
            sent.append(f"{len(important)} aviso(s)")
        if key != settings.get("email_alerts_last"):
            store.save_settings({"email_alerts_last": key})  # also when they clear, so a return is news again
    return sent

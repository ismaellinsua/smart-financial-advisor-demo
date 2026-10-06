"""Appointments and online booking."""

from datetime import date, datetime, time, timedelta
from html import escape
from urllib.parse import quote

import pandas as pd
import streamlit as st

from core import clock
from core.db import SaleError
from core.presets import PAYMENT_METHODS
from core.receipts import (
    whatsapp_number,
)
from ui import context
from ui.context import ctx
from ui.pages_pos import sale_dialog
from ui.styles import page_header

# -------------------------------------------------------------------- agenda
STATUS_LABELS = {"pendiente": "Pendiente", "completada": "Hecha", "cancelada": "Cancelada",
                 "no_presentado": "No vino"}


def agenda_enabled(settings: dict, preset: dict) -> bool:
    choice = settings.get("agenda_enabled", "auto")
    return bool(preset.get("agenda")) if choice == "auto" else choice == "si"


def agenda_config(preset: dict) -> dict:
    return preset.get("agenda") or {"title": "Agenda", "single": True, "duration": 60}


def _shift_agenda_day(days: int | None) -> None:
    current = st.session_state.get("agenda_day", clock.today())
    st.session_state["agenda_day"] = clock.today() if days is None else current + timedelta(days=days)


def _set_appointment_status(appointment_id: int, status: str) -> None:
    try:
        context.get_store().set_appointment_status(appointment_id, status)
    except ValueError as exc:
        st.session_state["agenda_flash"] = ("error", str(exc))


def agenda_page() -> None:
    c = ctx()
    cfg = agenda_config(c.preset)
    page_header(cfg["title"], "Organiza el día, evita solapes y cobra cada cita con un toque.", eyebrow="Agenda")
    if "last_sale" in st.session_state:
        sale_dialog(st.session_state.pop("last_sale"))
    if "agenda_flash" in st.session_state:
        kind, msg = st.session_state.pop("agenda_flash")
        getattr(st, kind)(msg)

    if "agenda_goto" in st.session_state:
        st.session_state["agenda_day"] = st.session_state.pop("agenda_goto")
    st.session_state.setdefault("agenda_day", clock.today())
    b1, b2, b3, b4 = st.columns([1, 4, 1, 1.4], vertical_alignment="bottom")
    b1.button("", icon=":material/chevron_left:", on_click=_shift_agenda_day, args=(-1,), help="Día anterior",
              width="stretch")
    day = b2.date_input("Día", key="agenda_day", format="DD/MM/YYYY", label_visibility="collapsed")
    b3.button("", icon=":material/chevron_right:", on_click=_shift_agenda_day, args=(1,), help="Día siguiente",
              width="stretch")
    b4.button("Hoy", on_click=_shift_agenda_day, args=(None,), width="stretch")

    start = datetime.combine(day, time.min)
    df = c.store.appointments(start, start + timedelta(days=1))
    pending = df[df["status"] == "pendiente"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Citas del día" if cfg["single"] else "Reservas del día", len(df[df["status"] != "cancelada"]))
    m2.metric("Pendientes", len(pending))
    expected = pending["price"].fillna(0).astype(float).sum()
    m3.metric("Ingresos previstos", c.money_short(expected), help="Servicios pendientes, impuestos incluidos.")

    if c.can("encargado"):
        _online_booking_panel(c, cfg)

    left, right = st.columns([3, 2], gap="large")
    with left:
        if df.empty:
            st.info(f"No hay {'citas' if cfg['single'] else 'reservas'} este día. Crea una con el formulario.")
        for _, a in df.iterrows():
            _appointment_card(c, a)
    with right, st.container(border=True):
        _new_appointment_form(c, cfg, day)


def _appointment_card(c, a) -> None:
    end = a["starts_at"] + timedelta(minutes=int(a["duration_min"]))
    status = a["status"]
    people = int(a.get("people") or 0)
    phone = a["customer_phone"] if isinstance(a.get("customer_phone"), str) else ""
    detail = " · ".join(x for x in [
        "Online" if a.get("source") == "online" else "",
        f"{people} pers." if people else "",
        a["service"] if isinstance(a["service"], str) else "",
        c.money(float(a["price"])) if pd.notna(a["price"]) else "",
        phone,
        a["notes"],
    ] if x)
    with st.container(border=True):
        st.markdown(
            f"<div class='sm-appt {escape(status)}'><div class='when'>{a['starts_at']:%H:%M}<span>–{end:%H:%M}</span></div>"
            f"<div class='who'>{escape(str(a['who']))}<div class='what'>{escape(detail)}</div></div>"
            f"<span class='chip'>{escape(STATUS_LABELS.get(status, status))}</span></div>",
            unsafe_allow_html=True,
        )
        if status != "pendiente":
            return
        aid = int(a["id"])
        x, y, z = st.columns(3)
        if pd.notna(a["product_id"]):
            with x.popover("Cobrar", icon=":material/payments:", width="stretch"):
                method = st.segmented_control("Forma de pago", PAYMENT_METHODS, default=PAYMENT_METHODS[0],
                                              key=f"appt_pay_{aid}") or PAYMENT_METHODS[0]
                if st.button("Cobrar ahora", type="primary", key=f"appt_charge_{aid}", width="stretch"):
                    try:
                        sale = c.store.charge_appointment(aid, method, user_name=c.who, location_id=c.location_id)
                    except SaleError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["last_sale"] = sale["id"]
                        st.rerun()
        else:
            x.button("Hecha", key=f"appt_done_{aid}", on_click=_set_appointment_status, args=(aid, "completada"),
                     icon=":material/check:", width="stretch")
        y.button("No vino", key=f"appt_noshow_{aid}", on_click=_set_appointment_status,
                 args=(aid, "no_presentado"), width="stretch")
        z.button("Cancelar", key=f"appt_cancel_{aid}", on_click=_set_appointment_status, args=(aid, "cancelada"),
                 width="stretch")
        if phone and a["starts_at"] >= clock.now():
            business = c.settings.get("business_name", "")
            text = (f"Hola, {a['who']}: te recordamos tu reserva en {business} el {a['starts_at']:%d/%m} a las "
                    f"{a['starts_at']:%H:%M}. Si no puedes venir, avísanos respondiendo a este mensaje. ¡Gracias!")
            st.link_button("Recordar por WhatsApp", f"https://wa.me/{whatsapp_number(phone)}?text={quote(text)}",
                           icon=":material/chat:", width="stretch",
                           help="Abre WhatsApp con el recordatorio escrito, listo para enviar.")


def _new_appointment_form(c, cfg: dict, day: date) -> None:
    st.markdown("**Nueva cita**" if cfg["single"] else "**Nueva reserva**")
    customers = c.store.customers()
    names = {int(i): n for i, n in zip(customers["id"], customers["name"])}
    products = c.store.products()
    services = {int(i): n for i, n in zip(products["id"], products["name"])}
    with st.form("new_appointment", clear_on_submit=True, border=False):
        a, b = st.columns(2)
        when_day = a.date_input("Fecha", day, format="DD/MM/YYYY")
        when_time = b.time_input("Hora", time(10, 0), step=timedelta(minutes=15))
        duration = st.number_input("Duración (minutos)", min_value=15, max_value=600, step=15,
                                   value=int(cfg.get("duration", 60)))
        customer_id = st.selectbox("Cliente", [0, *names], format_func=lambda i: names.get(i, "Sin ficha (escribir nombre)"))
        walk_in = st.text_input("Nombre (si no tiene ficha)")
        phone = st.text_input("Teléfono (para recordarle la cita)", max_chars=20)
        people = 0 if cfg["single"] else st.number_input("Personas", min_value=1, max_value=200, value=2, step=1)
        product_id = st.selectbox(c.preset["item_label"], [0, *services],
                                  format_func=lambda i: services.get(i, "Sin servicio"),
                                  index=1 if cfg["single"] and services else 0)
        notes = st.text_input("Notas", placeholder="Ej.: mesa para 4, alergia a frutos secos…")
        if st.form_submit_button("Guardar", type="primary", width="stretch", icon=":material/event:"):
            try:
                c.store.create_appointment(
                    datetime.combine(when_day, when_time), duration,
                    product_id=product_id or None, customer_id=customer_id or None,
                    customer_name=walk_in, notes=notes, allow_overlap=not cfg["single"], created_by=c.who,
                    people=people, phone=phone,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["agenda_flash"] = ("success", f"Guardada para el {when_day:%d/%m} a las {when_time:%H:%M}.")
                st.session_state["agenda_goto"] = when_day  # applied before the date picker is drawn
                st.rerun()


def _online_booking_panel(c, cfg: dict) -> None:
    """Opening hours and rules for the public booking page, its link and a QR to print for the counter."""
    from core.store_bookings import WEEKDAYS as DAY_NAMES
    from ui.booking import booking_url

    rules = c.store.booking_rules(c.settings)
    state = "abiertas" if rules["enabled"] else "cerradas"
    with st.expander(f"Reservas online · {state}", icon=":material/language:"):
        if rules["enabled"]:
            url = booking_url()
            st.markdown("Comparte este enlace (web, Instagram, Google, WhatsApp) o imprime el código QR:")
            st.code(url, language=None)
            import io

            import segno

            png = io.BytesIO()
            segno.make_qr(url, error="m").save(png, kind="png", scale=8, border=2)
            q1, q2 = st.columns([1, 3], vertical_alignment="center")
            q1.image(png.getvalue(), width=140)
            q2.download_button("Descargar QR", png.getvalue(), file_name="qr-reservas.png", mime="image/png",
                               icon=":material/qr_code_2:")
        with st.form("booking_rules"):
            enabled = st.toggle("Aceptar reservas online", value=rules["enabled"])
            st.markdown("**Horario** (vacío = cerrado). Ejemplo: `09:00-14:00, 16:00-20:00`")
            hours = {}
            cols = st.columns(2)
            for day, label in enumerate(DAY_NAMES):
                current = ", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in rules["hours"].get(day, []))
                hours[day] = cols[day % 2].text_input(label, current, max_chars=80, key=f"booking_h_{day}")
            closed = st.text_input("Días cerrados (festivos, vacaciones)", c.settings.get("booking_closed", ""),
                                   placeholder="24/12/2026, 25/12/2026", max_chars=1000)
            a, b = st.columns(2)
            values = {"enabled": enabled, "hours": hours, "closed": closed}
            if cfg["single"]:
                products = c.store.products()
                names = {int(i): n for i, n in zip(products["id"], products["name"])}
                values["services"] = st.multiselect(
                    "Servicios que se pueden reservar", list(names), [i for i in rules["services"] if i in names],
                    format_func=names.get, help="Si no eliges ninguno, la persona reserva una cita sin elegir servicio.")
                values["duration"] = a.number_input("Duración de cada cita (min)", 5, 600, rules["duration"], 5)
            else:
                values["services"] = []
                values["duration"] = a.number_input("Tiempo de mesa (min)", 5, 600, rules["duration"], 5)
                values["capacity"] = b.number_input("Comensales a la vez", 1, 1000, rules["capacity"], 1,
                                                    help="Suma de personas que caben al mismo tiempo.")
                values["max_party"] = a.number_input("Máximo de personas por reserva", 1, 100, rules["max_party"], 1)
            values["step"] = b.number_input("Una hora de inicio cada (min)", 5, 240, rules["step"], 5)
            values["days"] = a.number_input("Se puede reservar con hasta (días)", 1, 365, rules["days_ahead"], 1)
            values["notice_hours"] = b.number_input("Antelación mínima (horas)", 0, 168, rules["notice_hours"], 1)
            values["hourly_limit"] = a.number_input(
                "Máximo de reservas online por hora", 1, 500, rules["hourly_limit"], 1,
                help="Frena a quien intente llenar la agenda con reservas falsas. Si lo alcanzas, queda en el "
                     "registro de actividad; súbelo si tu negocio recibe más reservas reales en una hora.")
            st.caption("Si el envío de emails está configurado, la persona recibe la confirmación y un recordatorio "
                       "el día antes, y tú un aviso de cada reserva nueva en el email del negocio.")
            if st.form_submit_button("Guardar", type="primary"):
                try:
                    c.store.save_booking_rules(values)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    c.store.audit(c.username, "reservas_online", "abiertas" if enabled else "cerradas")
                    st.session_state["agenda_flash"] = ("success", "Reservas online guardadas.")
                    st.rerun()

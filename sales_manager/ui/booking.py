"""The public booking page (…/?reservar): customers book a free time themselves, and cancel with their own link.

Nobody signs in here. The page only ever shows which times are free, never who has the others; each visitor
can make a few bookings and then has to wait, and a phone can hold at most two pending bookings.
"""

from urllib.parse import urlencode, urlsplit

import streamlit as st

from core import clock, logs
from core.booking_mail import calendar_file, notify_business, send_confirmation, what_text, when_text
from core.mailer import valid_email
from core.pricing import format_money
from core.presets import CURRENCIES
from ui.auth import client_blocked_minutes, client_failed, client_key, mailer
from ui.context import tenant_code
from ui.styles import page_header

PARAM, CANCEL = "reservar", "cancelar"
WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
log = logs.get("booking")


def wanted() -> bool:
    return PARAM in st.query_params


def booking_url(token: str = "") -> str:
    """The public page's address (as the visitor reaches the app), with the business and a cancel token if given."""
    try:
        parts = urlsplit(st.context.url or "")
        base = f"{parts.scheme}://{parts.netloc}/" if parts.netloc else ""
    except Exception:  # no browser context (tests)
        base = ""
    query = {**({"negocio": tenant_code()} if tenant_code() else {}), PARAM: "", **({CANCEL: token} if token else {})}
    return base + "?" + urlencode(query).replace(f"{PARAM}=&", f"{PARAM}&").rstrip("=")


def public_page(store, settings: dict) -> None:
    # Free times wrap onto several lines instead of a sideways scroll that hides them on phones.
    st.html("<style>[data-testid='stButtonGroup'] > div { flex-wrap: wrap; overflow-x: visible; }"
            ".st-key-booking_web { position: absolute; left: -10000px; height: 1px; overflow: hidden; }</style>")
    _, center, _ = st.columns([1, 2.4, 1])
    with center:
        page_header(settings.get("business_name", ""), _contact(settings), eyebrow="Reservar")
        if token := st.query_params.get(CANCEL):
            _cancel(store, settings, token)
        elif done := st.session_state.get("booking_done"):
            _confirmation(settings, done)
        else:
            _book(store, settings)


def _contact(settings: dict) -> str:
    return " · ".join(x for x in (settings.get("address", ""), settings.get("phone", "")) if x)


def _book(store, settings: dict) -> None:
    rules = store.booking_rules(settings)
    if not rules["enabled"]:
        st.info("Este negocio no tiene reservas online ahora mismo. Llama o escríbele para pedir cita.",
                icon=":material/event_busy:")
        return
    product_id, people = None, 0
    if rules["single"] and rules["services"]:
        products = store.products()
        products = products[products["id"].isin(rules["services"]) & (products["active"] == 1)]
        if products.empty:
            st.info("Ahora mismo no hay servicios para reservar online.")
            return
        symbol = CURRENCIES.get(settings.get("currency", "EUR"), "€")
        names = {int(r.id): f"{r.name} · {format_money(float(r.price), symbol)}" for r in products.itertuples()}
        product_id = st.selectbox("Servicio", list(names), format_func=names.get)
    elif not rules["single"]:
        people = st.number_input("Personas", min_value=1, max_value=rules["max_party"], value=2, step=1)

    days = store.bookable_days()
    if not days:
        st.info("No hay días disponibles para reservar. Prueba más adelante o llama al negocio.")
        return
    day = st.selectbox("Día", days, format_func=lambda d: f"{WEEKDAYS[d.weekday()]} {d:%d/%m}")
    slots = store.free_slots(day, people)
    if not slots:
        st.warning("Ese día ya no quedan horas libres. Elige otro día.", icon=":material/event_busy:")
        return
    labels = {f"{s:%H:%M}": s for s in slots}
    chosen = st.pills("Hora", list(labels), key=f"booking_time_{day}")

    with st.form("booking"):
        name = st.text_input("Nombre", max_chars=120, autocomplete="name")
        phone = st.text_input("Teléfono", max_chars=20, autocomplete="tel")
        email = st.text_input("Email (opcional)", max_chars=254, autocomplete="email",
                              help="Para enviarte la confirmación y un recordatorio el día antes.")
        notes = st.text_input("Comentarios (opcional)", max_chars=500)
        # Hidden from people (CSS below), filled in by bots that complete every field: such bookings are dropped.
        trap = st.text_input("Web de tu empresa", max_chars=100, key="booking_web", autocomplete="off")
        st.caption(f"{settings.get('business_name', 'El negocio')} usará tu nombre, teléfono y email solo para "
                   "gestionar esta reserva y avisarte de ella. Se borran 90 días después de la cita.")
        agreed = st.checkbox("Acepto que se usen mis datos para esta reserva")
        submitted = st.form_submit_button("Confirmar reserva", type="primary", width="stretch",
                                          icon=":material/event_available:")
    if not submitted:
        return
    if trap:
        st.error("No hemos podido guardar la reserva. Llama al negocio.")
        return
    if not chosen:
        st.error("Elige una hora.")
        return
    if not agreed:
        st.error("Para reservar tienes que aceptar el uso de tus datos para esta reserva.")
        return
    key = "reserva:" + client_key()
    if minutes := client_blocked_minutes(key, store=store):
        st.error(f"Has hecho varias reservas seguidas. Vuelve a probar en {minutes} min o llama al negocio.")
        return
    try:
        booking = store.book_online(labels[chosen], name, phone, email, product_id=product_id, people=people,
                                    notes=notes)
    except ValueError as exc:
        st.error(str(exc))
        return
    client_failed(key, store=store)  # counts bookings from this visitor, so nobody can fill the diary in a loop
    booking["emailed"] = _send_emails(store, settings, booking)
    st.session_state["booking_done"] = booking
    st.rerun()


def _send_emails(store, settings: dict, booking: dict) -> bool:
    sender = mailer()
    if sender is None or settings.get("demo_mode") == "si":
        return False
    emailed = False
    try:
        if valid_email(booking.get("email", "")):
            send_confirmation(sender, booking, settings, booking_url(booking["token"]))
            emailed = True
        notify_business(sender, booking, settings)
    except Exception as exc:  # noqa: BLE001 - the booking is saved; email is a courtesy
        ref = store.record_error(exc, "Reserva online")
        log.warning("email_not_sent purpose=booking ref=%s error=%s", ref, type(exc).__name__)
    return emailed


def _confirmation(settings: dict, booking: dict) -> None:
    st.success("**Reserva confirmada.** Te esperamos.", icon=":material/check_circle:")
    with st.container(border=True):
        st.markdown(f"**{what_text(booking)}**  \n{when_text(booking['starts_at']).capitalize()}  \n"
                    f"A nombre de {booking['customer_name']}")
    if booking.get("emailed"):
        st.caption("Te hemos enviado la confirmación por email, con un enlace para cancelar.")
    st.markdown("Guarda este enlace: sirve para **cancelar** la reserva si no puedes venir.")
    st.code(booking_url(booking["token"]), language=None, wrap_lines=True)
    a, b = st.columns(2)
    a.download_button("Añadir al calendario", calendar_file(booking, settings), file_name="reserva.ics",
                      mime="text/calendar", icon=":material/calendar_add_on:", width="stretch")
    if b.button("Hacer otra reserva", width="stretch"):
        st.session_state.pop("booking_done", None)
        st.rerun()


def _cancel(store, settings: dict, token: str) -> None:
    booking = store.online_booking(token)
    if booking is None:
        st.error("No encontramos esa reserva. Revisa el enlace o llama al negocio.")
        return
    with st.container(border=True):
        st.markdown(f"**{what_text(booking)}**  \n{when_text(booking['starts_at']).capitalize()}  \n"
                    f"A nombre de {booking['customer_name']}")
    if booking["status"] == "cancelada":
        st.info("Esta reserva está cancelada.", icon=":material/event_busy:")
        return
    if booking["status"] != "pendiente" or booking["starts_at"] <= clock.now().isoformat(timespec="seconds"):
        st.info("Esta reserva ya no se puede cancelar desde aquí. Llama al negocio.")
        return
    if st.button("Cancelar la reserva", type="primary", icon=":material/event_busy:"):
        try:
            store.cancel_online_booking(token)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.rerun()

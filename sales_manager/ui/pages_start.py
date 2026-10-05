"""First run, switching business and the demo banner."""

from html import escape

import streamlit as st

from core import clock
from core.db import FiscalDataError
from core.fiscal_id import normalize as normalize_tax_id
from core.fiscal_id import tax_id_problem
from core.presets import PRESETS
from ui import context
from ui.context import ctx, logged_download
from ui.styles import page_header

# ---------------------------------------------------------------- onboarding
ONBOARDING_STEPS = ["Tu negocio", "Datos fiscales", "Empezar"]


def onboarding() -> None:
    """First run: a three-step setup that leaves the business ready to sell and invoice, with real data."""
    store = context.get_store()
    data = st.session_state.setdefault("onboarding", {"step": 0})
    step = data["step"]
    _, center, _ = st.columns([1, 2, 1])
    with center:
        page_header("Bienvenido a NirKanA", "Deja tu negocio listo para vender en tres pasos. Todo se puede cambiar "
                    "después en Configuración.", eyebrow=f"Paso {step + 1} de 3 · {ONBOARDING_STEPS[step]}")
        st.progress((step + 1) / 3)
        if step == 0:
            _onboarding_business(data)
        elif step == 1:
            _onboarding_fiscal(data)
        else:
            _onboarding_start(store, data)


def _onboarding_business(data: dict) -> None:
    with st.form("onboarding_business"):
        name = st.text_input("Nombre del negocio *", data.get("business_name", ""), placeholder="Ej.: Café Aurora",
                             help="Sale en tickets, facturas y en la cabecera de la app.")
        types = list(PRESETS)
        business_type = st.radio("Tipo de negocio", types, index=types.index(data.get("business_type", types[0])),
                                 format_func=lambda k: PRESETS[k]["label"],
                                 captions=[PRESETS[k]["description"] for k in types])
        zones = list(clock.TIMEZONES)
        zone = st.selectbox("Zona horaria", zones, zones.index(data.get("timezone", clock.DEFAULT_TIMEZONE)),
                            format_func=lambda z: clock.TIMEZONES[z],
                            help="La hora de tus tickets, facturas y cierres de caja.")
        if st.form_submit_button("Siguiente", type="primary", width="stretch", icon=":material/arrow_forward:"):
            if not name.strip():
                st.error("Escribe el nombre del negocio.")
                return
            data.update(business_name=name.strip(), business_type=business_type, timezone=zone, step=1)
            st.rerun()


def _onboarding_fiscal(data: dict) -> None:
    preset = PRESETS[data["business_type"]]
    st.caption("Son obligatorios en toda factura. Si ahora no los tienes a mano, puedes seguir y completarlos "
               "después: hasta entonces la app no emitirá facturas.")
    with st.form("onboarding_fiscal"):
        a, b = st.columns(2)
        tax_id = a.text_input("NIF / CIF", data.get("tax_id", ""), placeholder="B12345674")
        phone = b.text_input("Teléfono", data.get("phone", ""))
        address = st.text_input("Dirección fiscal", data.get("address", ""),
                                placeholder="Calle, número, código postal y ciudad")
        email = st.text_input("Email de contacto", data.get("email", ""))
        rates = [21.0, 10.0, 5.0, 4.0, 0.0]
        default_rate = float(data.get("tax_rate", preset["tax_rate"]))
        rate = st.selectbox("IVA habitual de lo que vendes", rates, rates.index(default_rate) if default_rate in rates
                            else 0, format_func=lambda r: f"{r:g} %",
                            help="21 % general, 10 % hostelería y alimentación, 4 % pan, leche, libros… Cada producto "
                                 "puede tener el suyo. Los precios se escriben con el IVA incluido, como en la carta.")
        back, forward = st.columns(2)
        go_back = back.form_submit_button("Atrás", width="stretch", icon=":material/arrow_back:")
        go_on = forward.form_submit_button("Siguiente", type="primary", width="stretch", icon=":material/arrow_forward:")
    if go_back:
        data["step"] = 0
        st.rerun()
    if go_on:
        problem = tax_id_problem(tax_id) if tax_id.strip() else None
        data.update(tax_id=normalize_tax_id(tax_id) if tax_id.strip() else "", address=address.strip(),
                    email=email.strip(), phone=phone.strip(), tax_rate=rate, tax_id_warning=problem, step=2)
        st.rerun()


def _onboarding_start(store, data: dict) -> None:
    preset = PRESETS[data["business_type"]]
    with st.container(border=True):
        st.markdown(f"**{escape(data['business_name'])}** · {preset['label']}")
        fiscal = " · ".join(escape(v) for v in (data.get("tax_id"), data.get("address")) if v)
        st.caption(fiscal or "Sin datos fiscales todavía: complétalos en Configuración antes de facturar.")
        st.caption(f"IVA habitual {data['tax_rate']:g} % · precios con IVA incluido · {clock.TIMEZONES[data['timezone']]}")
    if data.get("tax_id_warning"):
        st.warning(f"{data['tax_id_warning']} Revísalo si es un NIF español: saldrá en todas tus facturas.",
                   icon=":material/warning:")
    st.markdown("Para no partir de cero empezarás con un catálogo de ejemplo de tu tipo de negocio: cambia nombres "
                "y precios (con IVA incluido) antes de vender.")
    demo = st.toggle("Solo quiero probar la app con ventas de ejemplo", value=False,
                     help="Añade 60 días de ventas inventadas. Se borran al empezar de verdad.")
    back, create = st.columns(2)
    if back.button("Atrás", width="stretch", icon=":material/arrow_back:"):
        data["step"] = 1
        st.rerun()
    if create.button("Crear mi negocio", type="primary", width="stretch", icon=":material/rocket_launch:"):
        with st.spinner("Preparando tu negocio…"):
            store.load_preset(data["business_type"], with_demo_sales=demo)
            store.save_settings({k: data[k] for k in ("business_name", "timezone", "tax_id", "address", "email",
                                                      "phone", "tax_rate")})
        clock.set_timezone(data["timezone"])
        st.session_state.pop("onboarding", None)
        st.rerun()


@st.dialog("Cambiar de negocio")
def switch_business_dialog() -> None:
    c = ctx()
    types = list(PRESETS)
    business_type = st.radio(
        "¿Qué tipo de negocio quieres?", types, index=types.index(c.settings["business_type"]),
        format_func=lambda k: PRESETS[k]["label"],
        captions=[PRESETS[k]["description"] for k in types], key="switch_type",
    )
    # Keep the current name for the current type; other types suggest a ready-made demo name.
    default_name = (c.settings["business_name"] if business_type == c.settings["business_type"]
                    else PRESETS[business_type]["demo_name"])
    name = st.text_input("Nombre del negocio", default_name, key=f"switch_name_{business_type}")
    demo = st.toggle("Cargar datos de ejemplo para probar", value=c.store.is_demo(), key="switch_demo")
    st.warning("Se reemplazarán el catálogo, los clientes y las ventas actuales por los del nuevo negocio.",
               icon=":material/warning:")
    logged_download(
        st, "Antes, descargar una copia de mis datos", c.store.backup_bytes, f"ventas-{clock.today():%Y-%m-%d}.db",
        "application/octet-stream", icon=":material/download:", width="stretch",
    )
    confirmed = _identity_confirmed(c, "switch_secret")
    if st.button(f"Cambiar a «{PRESETS[business_type]['label']}»", type="primary", width="stretch",
                 icon=":material/swap_horiz:", disabled=not confirmed):
        if not c.can("admin"):
            st.error("Solo el administrador puede cambiar de negocio.")
            return
        try:
            with st.spinner("Preparando el nuevo negocio…"):
                c.store.load_preset(business_type, with_demo_sales=demo)
        except FiscalDataError as exc:
            st.error(str(exc))
            return
        c.store.save_settings({"business_name": name.strip() or c.settings["business_name"]})
        c.store.audit(c.username, "negocio_cambiado", f"{PRESETS[business_type]['label']} · {name}")
        st.session_state.pop("cart", None)
        st.rerun()


def _identity_confirmed(c, key: str) -> bool:
    """Ask again for the PIN or password before replacing data: a device left signed in is not enough."""
    secret = st.text_input("Tu PIN o contraseña, para confirmar", type="password", max_chars=128, key=key)
    if not secret:
        return False
    if c.user and c.store.confirm_secret(c.user["id"], secret):
        return True
    st.error("El PIN o contraseña no es correcto.")
    return False


def demo_banner(c) -> None:
    """Demonstration data is disposable: say so on every page and let the administrator start for real."""
    text, action = st.columns([5, 2], vertical_alignment="center")
    text.warning("**Modo demostración.** Los datos son de ejemplo y todo lo que vendas aquí se borrará al empezar "
                 "de verdad.", icon=":material/science:")
    if c.can("admin") and action.button("Empezar a vender de verdad", type="primary", width="stretch",
                                        icon=":material/rocket_launch:"):
        _start_for_real_dialog()


@st.dialog("Empezar a vender de verdad")
def _start_for_real_dialog() -> None:
    st.write("Se borrarán los datos de ejemplo (productos, clientes, ventas, facturas y cierres) y configurarás tu "
             "negocio desde cero. A partir de ahí, las ventas y facturas reales **no se podrán borrar**: la ley obliga "
             "a conservarlas.")
    c = ctx()
    if st.checkbox("Entiendo que se borrarán los datos de ejemplo", key="start_real_confirm") and \
            _identity_confirmed(c, "start_real_secret") and st.button(
            "Borrar ejemplos y empezar", type="primary", width="stretch"):
        if not c.can("admin"):
            st.error("Solo el administrador puede hacerlo.")
            return
        c.store.reset()
        c.store.audit(c.username, "datos_de_ejemplo_borrados")
        st.session_state.pop("cart", None)
        st.rerun()

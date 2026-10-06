"""Business settings, locations, backups and the billing register."""

import streamlit as st

from core import clock
from core.db import FISCAL_DATA_MESSAGE, FiscalDataError
from core.fiscal_id import tax_id_problem
from core.presets import CURRENCIES, PRESETS
from core.receipts import RECEIPT_PAPERS
from ui.context import ctx, logged_download
from ui.pages_common import _csv, _require
from ui.pages_start import _identity_confirmed
from ui.styles import page_header


# ------------------------------------------------------------------ settings
def _billing_register_section(c, s: dict) -> None:
    st.markdown("##### Registro de facturación (VERI*FACTU, en preparación)")
    with st.container(border=True):
        st.caption("Cada ticket, factura, rectificativa y anulación queda en un registro encadenado con la huella "
                   "SHA-256 que exige la AEAT: no se puede modificar ni borrar, y tickets y facturas llevan el código QR "
                   "tributario. **Todavía no se envía a Hacienda**: esa parte llega en una próxima versión, así que "
                   "NirKanA aún no es un sistema VERI*FACTU completo y no imprime esa leyenda.")
        if s.get("verifactu") != "si":
            ready = s.get("demo_mode") != "si" and bool((s.get("tax_id") or "").strip())
            if not ready:
                st.info("Para activarlo hace falta vender de verdad (sin datos de ejemplo) y tener el NIF del "
                        "negocio en «Datos del negocio».", icon=":material/info:")
            confirm = st.checkbox("Entiendo que, una vez activado, el registro no se puede desactivar",
                                  disabled=not ready)
            if st.button("Activar el registro de facturación", disabled=not (ready and confirm),
                         icon=":material/verified:"):
                try:
                    c.store.enable_billing_register(c.username)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["settings_flash"] = "Registro de facturación activado."
                    st.rerun()
            return
        records = c.store.billing_records()
        st.success(f"Registro activo: {len(records)} registros encadenados.", icon=":material/link:")
        a, b = st.columns(2)
        if a.button("Comprobar la cadena", width="stretch", icon=":material/fact_check:"):
            check = c.store.verify_billing_chain()
            if check["ok"]:
                st.success(f"Cadena correcta: {check['checked']} registros comprobados.")
            else:
                st.error(f"Problema en el registro nº {check['broken_at']}: {check['reason']}.")
        logged_download(b, "Descargar registros (CSV)", _csv(records), f"registro-facturacion-{clock.today():%Y-%m-%d}.csv",
                          "text/csv", width="stretch", icon=":material/download:", disabled=records.empty)


def _locations_settings(c) -> None:
    """Shops or premises of the business. With one place there's nothing to set up; the second one adds a
    location picker to the menu and splits sales, cash, tables and stock by location."""
    st.markdown("##### Locales")
    every = c.store.locations(include_inactive=True)
    with st.container(border=True):
        if not every:
            st.caption("Tu negocio tiene un solo local. Si abres otro, añádelo aquí: el actual pasará a llamarse "
                       "«Principal» y conservará todo su stock, ventas y cierres.")
        else:
            st.caption("Cada local vende de su propio stock, cierra su caja y tiene sus mesas. Las personas fijadas "
                       "a un local (en Equipo y seguridad) solo trabajan en él.")
            main = every[0]["id"]
            for loc in every:
                with st.expander(f"{loc['name']}{'' if loc['active'] else ' · cerrado'}", icon=":material/storefront:"):
                    with st.form(f"location_{loc['id']}"):
                        name = st.text_input("Nombre", loc["name"], max_chars=60)
                        address = st.text_input("Dirección (sale en sus tickets)", loc["address"], max_chars=250)
                        phone = st.text_input("Teléfono", loc["phone"], max_chars=60)
                        active = st.checkbox("Abierto", bool(loc["active"]), disabled=loc["id"] == main)
                        if st.form_submit_button("Guardar"):
                            try:
                                c.store.update_location(loc["id"], name, address, phone, active)
                            except ValueError as exc:
                                st.error(str(exc))
                            else:
                                c.store.audit(c.username, "local_guardado", name)
                                st.session_state["settings_flash"] = f"Local «{name}» guardado."
                                st.rerun()
        with st.form("new_location", clear_on_submit=True):
            st.markdown("**Añadir un local**")
            a, b = st.columns(2)
            name = a.text_input("Nombre del local", max_chars=60, placeholder="Ej.: Centro, Playa, Calle Mayor")
            phone = b.text_input("Teléfono del local", max_chars=60)
            address = st.text_input("Dirección del local", max_chars=250)
            if st.form_submit_button("Añadir local", icon=":material/add_business:"):
                try:
                    c.store.add_location(name, address, phone)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    c.store.audit(c.username, "local_creado", name)
                    st.session_state["settings_flash"] = (f"Local «{name}» creado. Elige en el menú en qué local "
                                                          "trabajas y pásale stock desde el catálogo.")
                    st.rerun()


def settings_page() -> None:
    c = ctx()
    if not _require(c, "admin"):
        return
    s = c.settings
    page_header("Configuración", "Identidad del negocio, impuestos, numeración y tipo de negocio.", eyebrow="Ajustes")
    if "settings_flash" in st.session_state:
        st.success(st.session_state.pop("settings_flash"))
    if "settings_warning" in st.session_state:
        st.warning(st.session_state.pop("settings_warning"), icon=":material/warning:")

    with st.form("settings"):
        st.markdown("##### Datos del negocio")
        a, b = st.columns(2)
        values = {
            "business_name": a.text_input("Nombre comercial", s["business_name"]),
            "tax_id": b.text_input("Identificación fiscal", s["tax_id"]),
            "address": a.text_input("Dirección", s["address"]),
            "phone": b.text_input("Teléfono", s["phone"]),
            "email": a.text_input("Email", s["email"]),
            "accent_color": b.color_picker("Color de marca", s["accent_color"]),
        }
        st.markdown("##### Ventas e impuestos")
        a, b, d = st.columns(3)
        currencies = list(CURRENCIES)
        values["currency"] = a.selectbox("Moneda", currencies, currencies.index(s["currency"]))
        zones = list(clock.TIMEZONES)
        current_zone = s.get("timezone") if s.get("timezone") in zones else clock.DEFAULT_TIMEZONE
        values["timezone"] = st.selectbox(
            "Zona horaria", zones, zones.index(current_zone), format_func=lambda z: f"{clock.TIMEZONES[z]} ({z})",
            help="Hora de tickets, facturas, caja, agenda y promociones por franja horaria.")
        values["tax_rate"] = b.number_input("IVA por defecto (%)", 0.0, 100.0, float(s["tax_rate"]), step=0.5,
                                            help="El de los productos que no tengan un IVA propio.")
        values["invoice_prefix"] = d.text_input("Prefijo de tickets", s["invoice_prefix"], max_chars=8)
        f, g = st.columns([3, 2])
        values["receipt_footer"] = f.text_input("Pie del ticket", s["receipt_footer"])
        papers = list(RECEIPT_PAPERS)
        values["receipt_paper"] = g.selectbox(
            "Papel del ticket", papers, papers.index(s.get("receipt_paper", "a4")) if s.get("receipt_paper") in papers
            else 0, format_func=RECEIPT_PAPERS.get,
            help="Térmico: impresoras de tickets de 80 o 58 mm (conectadas por USB, red o Bluetooth al equipo).")
        a, b = st.columns(2)
        values["invoice_series"] = a.text_input("Serie de facturas", s["invoice_series"], max_chars=8,
                                                help="Las facturas se numeran aparte: SERIE-AÑO-0001.")
        values["opening_float"] = b.number_input(f"Fondo de caja habitual ({c.symbol})", 0.0, 100000.0,
                                                 float(s["opening_float"] or 0), step=10.0)
        agenda_options = {"auto": "Automática según el tipo de negocio", "si": "Sí", "no": "No"}
        a, b = st.columns(2)
        values["agenda_enabled"] = a.selectbox(
            "Mostrar agenda de citas y reservas", list(agenda_options), list(agenda_options).index(
                s["agenda_enabled"] if s["agenda_enabled"] in agenda_options else "auto"),
            format_func=agenda_options.get)
        values["tables_enabled"] = b.selectbox(
            "Mostrar mesas, comandas y cocina", list(agenda_options), list(agenda_options).index(
                s.get("tables_enabled") if s.get("tables_enabled") in agenda_options else "auto"),
            format_func=agenda_options.get)
        st.markdown("##### Automatizaciones")
        a, b = st.columns(2)
        values["inactive_days"] = a.number_input("Días para considerar un cliente inactivo", 7, 365,
                                                 int(s["inactive_days"]))
        values["reorder_lead_days"] = b.number_input("Días de cobertura al reponer", 1, 120,
                                                     int(s["reorder_lead_days"]))
        st.markdown("##### Avisos por email")
        st.caption("Llegan al email del negocio (arriba). El envío lo activa quien gestiona la app: hasta entonces "
                   "estas opciones no envían nada.")
        a, b = st.columns(2)
        values["email_weekly"] = "si" if a.toggle("Informe semanal cada lunes (PDF)",
                                                  value=s.get("email_weekly") == "si") else "no"
        values["email_alerts"] = "si" if b.toggle("Avisos importantes del día",
                                                  value=s.get("email_alerts") == "si",
                                                  help="Solo cuando aparecen avisos nuevos de nivel alto: caída de "
                                                       "ventas, productos agotados, pérdidas…") else "no"
        st.markdown("##### Seguridad")
        values["max_discount_staff"] = st.number_input(
            "Descuento máximo de los empleados sin autorización (%)", 0.0, 100.0,
            float(s.get("max_discount_staff") or 10), step=5.0,
            help="Por encima, un encargado o el administrador lo autoriza con su usuario y PIN, y queda registrado.")
        values["session_minutes"] = st.number_input(
            "Cerrar la sesión tras estos minutos sin uso", 5, 1440, int(s.get("session_minutes") or 480), step=15,
            help="En tablets o móviles compartidos conviene un valor bajo, por ejemplo 15.")
        if st.form_submit_button("Guardar configuración", type="primary"):
            values["invoice_prefix"] = values["invoice_prefix"].strip().upper().replace("-", "") or "VTA"
            values["invoice_series"] = values["invoice_series"].strip().upper().replace("-", "") or "FAC"
            if values["invoice_series"] == values["invoice_prefix"]:
                st.error("La serie de facturas debe ser distinta del prefijo de tickets.")
            else:
                c.store.save_settings(values)
                c.store.audit(c.username, "configuracion_guardada")
                st.session_state["settings_flash"] = "Configuración guardada."
                if values.get("tax_id", "").strip() and (problem := tax_id_problem(values["tax_id"])):
                    st.session_state["settings_warning"] = f"{problem} Revísalo: saldrá en todas tus facturas."
                st.rerun()

    _locations_settings(c)

    replaceable = c.store.can_replace_data()
    st.markdown("##### Tipo de negocio y plantillas")
    with st.container(border=True):
        types = list(PRESETS)
        business_type = st.selectbox("Tipo de negocio", types, types.index(s["business_type"]),
                                     format_func=lambda k: PRESETS[k]["label"])
        if replaceable:
            st.caption("Cambiar solo el tipo adapta el vocabulario de la aplicación. Cargar la plantilla reemplaza "
                       "catálogo, clientes y ventas por los de ejemplo.")
            demo = st.toggle("Incluir 60 días de ventas de ejemplo", value=c.store.is_demo())
            confirm = st.checkbox("Entiendo que se borrarán los datos actuales")
            if not confirm:
                st.caption("Marca la casilla de arriba para activar «Cargar plantilla» y «Empezar desde cero».")
        else:
            st.caption("Cambiar el tipo adapta el vocabulario de la aplicación. " + FISCAL_DATA_MESSAGE)
            demo = confirm = False
        if replaceable and confirm:
            confirm = _identity_confirmed(c, "template_secret")
        a, b, d = st.columns(3)
        if a.button("Cambiar solo el tipo", width="stretch"):
            c.store.save_settings({"business_type": business_type})
            c.store.audit(c.username, "tipo_negocio_cambiado", PRESETS[business_type]["label"])
            st.session_state["settings_flash"] = f"Tipo cambiado a «{PRESETS[business_type]['label']}»."
            st.rerun()
        if replaceable and b.button("Cargar plantilla", type="primary", disabled=not confirm,
                                    width="stretch"):
            try:
                with st.spinner("Cargando plantilla…"):
                    c.store.load_preset(business_type, with_demo_sales=demo)
            except FiscalDataError as exc:
                st.error(str(exc))
                return
            c.store.audit(c.username, "plantilla_cargada", PRESETS[business_type]["label"])
            st.session_state.pop("cart", None)
            st.session_state["settings_flash"] = "Plantilla cargada."
            st.rerun()
        if replaceable and d.button("Empezar desde cero", disabled=not confirm, width="stretch"):
            try:
                c.store.reset()
            except FiscalDataError as exc:
                st.error(str(exc))
                return
            c.store.audit(c.username, "datos_borrados")
            st.session_state.pop("cart", None)
            st.rerun()

    _billing_register_section(c, s)

    st.markdown("##### Copia de seguridad")
    with st.container(border=True):
        if c.store.persistent_in_cloud:
            st.success(f"Tus datos se guardan en **{c.store.backend_label}** y no se pierden aunque la app se "
                       "reinicie.", icon=":material/cloud_done:")
            st.caption("Aun así, descarga una copia de vez en cuando. También sirve para pasar a esta base de datos "
                       "los datos que tenías antes: descarga la copia en la app antigua y restáurala aquí.")
        else:
            st.warning(f"Tus datos se guardan en un **{c.store.backend_label}**. En Streamlit Community "
                       "Cloud se pierden cuando la app se reinicia o se actualiza: descarga copias a menudo o "
                       "conecta una base de datos gratuita (ver README).", icon=":material/warning:")
        logged_download(
            st, "Descargar copia de seguridad", c.store.backup_bytes, f"ventas-{clock.today():%Y-%m-%d}.db",
            "application/octet-stream", icon=":material/download:", type="primary",
        )
        if not replaceable:
            st.caption("Restaurar una copia solo es posible en un negocio sin ventas (por ejemplo, al pasar a una base "
                       "de datos nueva): sobre datos reales borraría todo lo emitido después de la copia.")
            return
        upload = st.file_uploader("Restaurar desde una copia", type=["db"])
        confirm_restore = st.checkbox("Entiendo que se reemplazarán los datos actuales por los de la copia")
        if upload and confirm_restore:
            confirm_restore = _identity_confirmed(c, "restore_secret")
        if st.button("Restaurar copia", disabled=not (upload and confirm_restore), icon=":material/restore:"):
            try:
                c.store.restore(upload.getvalue())
                c.store.audit(c.username, "copia_restaurada", upload.name[:80])
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("cart", None)
                st.session_state["settings_flash"] = "Copia restaurada correctamente."
                st.rerun()

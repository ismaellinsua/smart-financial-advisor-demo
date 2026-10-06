"""Cash closing and the offline till."""

from datetime import date, datetime
from functools import partial

import pandas as pd
import streamlit as st

from core import clock
from core.pdfs import cash_closing_pdf
from ui.context import ctx, logged_download
from ui.pages_common import csv_bytes, require_role
from ui.styles import page_header

# ---------------------------------------------------------------------- cash
OFFLINE_TILL_URL = "https://nirkana.es/caja/"


def _offline_till_panel(c) -> None:
    """The till that works without internet: its catalogue file goes out from here and its sales come back."""
    from core.store_offline import DEVICES, OfflineImportError

    with st.expander("Caja sin conexión", icon=":material/wifi_off:"):
        st.markdown(
            "Si se cae internet, sigue cobrando con la **caja sin conexión**: se instala en el móvil o la tablet y "
            "funciona sin red. Guarda las ventas en el dispositivo y aquí las importas cuando vuelva la conexión.")
        a, b = st.columns([1, 2], vertical_alignment="bottom")
        device = a.selectbox("Número de caja", list(DEVICES),
                             help="Uno distinto por dispositivo: cada caja numera sus tickets en su propia serie.")
        logged_download(b, "Descargar archivo de catálogo", c.store.offline_package(device, c.location_id),
                        f"catalogo-caja{device}.json", mime="application/json", icon=":material/download:")
        st.link_button("Abrir la caja sin conexión", OFFLINE_TILL_URL, icon=":material/open_in_new:")
        st.caption("1) Abre la caja en el dispositivo e **instálala** (menú del navegador → Instalar o Añadir a pantalla "
                   "de inicio). 2) Carga el archivo de catálogo. 3) Vuelve a descargarlo y cargarlo cuando cambies "
                   "precios o productos. La caja sin conexión no aplica promociones, puntos ni clientes.")
        st.markdown("**Importar ventas**")
        upload = st.file_uploader("Archivo de ventas de la caja sin conexión", type=["json"], key="offline_upload")
        if upload is not None and st.button("Importar", type="primary", icon=":material/upload:"):
            try:
                result = c.store.import_offline_sales(upload.getvalue(), c.who)
            except OfflineImportError as exc:
                st.error(str(exc))
            else:
                text = (f"{result['imported']} ventas importadas ({c.money(result['total'])})"
                        + (f", {result['repeated']} ya estaban" if result["repeated"] else "")
                        + (f", {result['rejected']} sin importar" if result["rejected"] else "") + ".")
                (st.warning if result["rejected"] else st.success)(
                    text + ("" if result["rejected"] else " Ya puedes borrarlas de la caja sin conexión."))
                for note in result["notes"]:
                    st.caption(note)


def cash_page() -> None:
    c = ctx()
    if not require_role(c, "encargado"):
        return
    page_header("Cierre de caja" + (f" · {c.location_name}" if c.multi_location else ""),
                "Cuadra el efectivo al final del día y guarda el informe firmado.", eyebrow="Caja")
    if "cash_flash" in st.session_state:
        st.success(st.session_state.pop("cash_flash"))
    _offline_till_panel(c)
    day = st.date_input("Día", clock.today(), max_value=clock.today(), format="DD/MM/YYYY", key="cash_day")
    summary = c.store.day_summary(day, c.location_id)
    closing = c.store.cash_closing(day, c.location_id)

    m1, m2, m3 = st.columns(3)
    m1.metric("Vendido", c.money_short(summary["total"]))
    m2.metric("Ventas", summary["count"])
    m3.metric("Cobrado en efectivo", c.money_short(summary["cash"]))

    left, right = st.columns([3, 2], gap="large")
    with left, st.container(border=True):
        st.markdown("**Por forma de pago**")
        if summary["breakdown"]:
            df = pd.DataFrame(
                [{"method": m, "count": e["count"], "refunded": e.get("refunded", 0.0), "total": e["total"]}
                 for m, e in summary["breakdown"].items()]
            ).sort_values("total", ascending=False)
            st.dataframe(df, hide_index=True, width="stretch",
                         column_order=["method", "count", *(["refunded"] if summary["refunded"] else []), "total"],
                         column_config={
                             "method": "Forma de pago", "count": "Cobros",
                             "refunded": st.column_config.NumberColumn("Devuelto", format=f"%.2f {c.symbol}"),
                             "total": st.column_config.NumberColumn("Neto", format=f"%.2f {c.symbol}"),
                         })
        else:
            st.caption("No hay ventas este día.")
        if summary["cancelled"]:
            st.caption(f"{summary['cancelled']} venta(s) anulada(s) no se cuentan.")

    with right, st.container(border=True):
        if closing:
            _closed_cash_panel(c, day, closing, summary)
        else:
            _open_cash_panel(c, day, summary)

    st.markdown("#### Cierres anteriores")
    history = c.store.cash_closings(c.location_id if c.multi_location else None)
    if history.empty:
        st.caption("Todavía no has cerrado ninguna caja.")
    else:
        st.dataframe(history.drop(columns=["closed_at"]), hide_index=True, width="stretch",
                     column_config={
                         "day": st.column_config.DateColumn("Día", format="DD/MM/YYYY"),
                         "total_sales": st.column_config.NumberColumn("Vendido", format=f"%.2f {c.symbol}"),
                         "sales_count": "Ventas",
                         "expected_cash": st.column_config.NumberColumn("Esperado", format=f"%.2f {c.symbol}"),
                         "counted_cash": st.column_config.NumberColumn("Contado", format=f"%.2f {c.symbol}"),
                         "difference": st.column_config.NumberColumn("Diferencia", format=f"%+.2f {c.symbol}"),
                     })
        logged_download(st, "Exportar cierres a CSV", csv_bytes(history), "cierres_de_caja.csv", "text/csv",
                        icon=":material/download:")
    reopened = c.store.cash_reopenings(c.location_id if c.multi_location else None)
    if not reopened.empty:
        with st.expander(f"Cierres reabiertos ({len(reopened)})", icon=":material/lock_open:"):
            st.dataframe(reopened, hide_index=True, width="stretch", column_config={
                "day": st.column_config.DateColumn("Día", format="DD/MM/YYYY"),
                "reopened_by": "Reabierto por", "reopened_at": "Cuándo",
                "counted_cash": st.column_config.NumberColumn("Contado entonces", format=f"%.2f {c.symbol}"),
                "difference": st.column_config.NumberColumn("Diferencia entonces", format=f"%+.2f {c.symbol}"),
                "closed_by": "Cerrado por"})


def _difference_message(c, difference: float):
    if abs(difference) < 0.005:
        st.success("La caja cuadra.", icon=":material/check_circle:")
    elif difference > 0:
        st.warning(f"Sobran {c.money(difference)}.", icon=":material/info:")
    else:
        st.error(f"Faltan {c.money(-difference)}.", icon=":material/error:")


def _open_cash_panel(c, day: date, summary: dict) -> None:
    st.markdown("**Arqueo de efectivo**")
    opening = st.number_input(f"Fondo inicial ({c.symbol})", min_value=0.0, step=10.0,
                              value=float(c.settings.get("opening_float") or 0), key=f"cash_open_{day}")
    expected = round(opening + summary["cash"], 2)
    st.markdown(f"Efectivo esperado en el cajón: **{c.money(expected)}**")
    counted = st.number_input(f"Efectivo contado ({c.symbol})", min_value=0.0, step=1.0, value=None,
                              placeholder="Cuenta el cajón y escribe el total", key=f"cash_count_{day}")
    if counted is not None:
        _difference_message(c, round(counted - expected, 2))
    notes = st.text_area("Notas", placeholder="Ej.: retirada de 200 € para el banco", key=f"cash_notes_{day}",
                         height=70)
    if st.button("Cerrar caja", type="primary", width="stretch", disabled=counted is None,
                 icon=":material/lock:"):
        try:
            closing = c.store.close_cash(day, opening, counted, notes, closed_by=c.who, location_id=c.location_id)
            c.store.audit(c.username, "caja_cerrada", f"{day:%d/%m/%Y} · diferencia {closing['difference']:+.2f}")
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["cash_flash"] = f"Caja del {day:%d/%m/%Y} cerrada."
            st.rerun()


def _closed_cash_panel(c, day: date, closing: dict, summary: dict) -> None:
    closed_at = datetime.fromisoformat(closing["closed_at"])
    st.markdown(f"**Caja cerrada** · {closed_at:%d/%m/%Y %H:%M}")
    st.markdown(f"Esperado **{c.money(closing['expected_cash'])}** · Contado **{c.money(closing['counted_cash'])}**")
    _difference_message(c, closing["difference"])
    if summary["count"] != closing["sales_count"] or abs(summary["total"] - closing["total_sales"]) >= 0.005:
        st.warning("Ha habido ventas o anulaciones después del cierre. Reabre la caja y ciérrala de nuevo "
                   "para incluirlas.", icon=":material/warning:")
    logged_download(st, "Descargar informe (PDF)",
                    partial(cash_closing_pdf, closing, c.ticket_settings(closing.get("location_id"))),
                    f"cierre-{day:%Y-%m-%d}.pdf", "application/pdf", type="primary",
                    width="stretch", icon=":material/picture_as_pdf:")
    if st.button("Reabrir caja", width="stretch", icon=":material/lock_open:"):
        c.store.reopen_cash(day, c.location_id, by=c.who)
        c.store.audit(c.username, "caja_reabierta", f"{day:%d/%m/%Y}")
        st.rerun()

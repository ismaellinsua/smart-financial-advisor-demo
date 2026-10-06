"""Products, stock and the online shop."""

import pandas as pd
import streamlit as st

from core.presets import PAYMENT_METHODS
from ui.context import ctx, logged_download
from ui.pages_common import require_role
from ui.styles import page_header


# ------------------------------------------------------------------ products
def editor_key(name: str) -> str:
    return f"{name}_{st.session_state.get(name + '_v', 0)}"


def bump_editor(name: str) -> None:
    st.session_state[name + "_v"] = st.session_state.get(name + "_v", 0) + 1


def _same(a, b) -> bool:
    """Equal cells of the table editor, counting two empty cells as equal."""
    return (pd.isna(a) and pd.isna(b)) if (pd.isna(a) or pd.isna(b)) else a == b


SHOP_TEMPLATE = ("pedido;fecha;sku;cantidad;precio;descuento;envio;total;estado\n"
                 "1001;05/10/2026 10:30;CAM-001;2;39,90;0;4,90;84,70;pagado\n")


def _online_shop_panel(c) -> None:
    """Shopify, WooCommerce or any shop, by files: catalogue out, orders in."""
    from core.store_ecommerce import ShopImportError

    with st.expander("Tienda online (Shopify, WooCommerce…)", icon=":material/shopping_cart:"):
        st.markdown("**1. Sube tu catálogo a la tienda** (productos, precios con IVA y stock"
                    + (f" de {c.location_name}" if c.multi_location else "") + ")")
        a, b = st.columns(2)
        logged_download(a, "Catálogo para Shopify", c.store.shop_catalog_csv("shopify", c.location_id),
                        "catalogo-shopify.csv", mime="text/csv", icon=":material/download:", width="stretch")
        logged_download(b, "Catálogo para WooCommerce", c.store.shop_catalog_csv("woocommerce", c.location_id),
                        "catalogo-woocommerce.csv", mime="text/csv", icon=":material/download:", width="stretch")
        st.caption("En Shopify: Productos → Importar (marca «Sobrescribir productos» para actualizar precios y stock). "
                   "En WooCommerce: Productos → Importar (marca «Actualizar productos existentes»). Los productos se "
                   "relacionan por su código (SKU).")
        st.markdown("**2. Trae los pedidos de la tienda** (se registran como ventas y descuentan stock)")
        upload = st.file_uploader("Exportación de pedidos (CSV)", type=["csv"], key="shop_orders",
                                  help="Shopify: Pedidos → Exportar → CSV para Excel. Otras tiendas: la plantilla.")
        products = c.store.products()
        no_stock = products[products["track_stock"] == 0]
        options = {0: "No incluir el envío", **dict(zip(no_stock["id"].astype(int), no_stock["name"]))}
        guess = next((pid for pid, name in options.items() if pid and "env" in name.lower()), 0)
        x, y = st.columns(2)
        method = x.selectbox("Cobrados con", PAYMENT_METHODS, key="shop_method")
        shipping = y.selectbox("Producto para los envíos", list(options), index=list(options).index(guess),
                               format_func=options.get, key="shop_shipping",
                               help="Un producto sin control de stock (p. ej. «Envío»). Créalo en «Nuevo» si no lo tienes.")
        if upload is not None and st.button("Importar pedidos", type="primary", icon=":material/upload:"):
            try:
                result = c.store.import_shop_orders(upload.getvalue(), method, c.location_id, shipping or None, c.who)
            except (ShopImportError, ValueError) as exc:
                st.error(str(exc))
            else:
                text = (f"{result['imported']} pedidos importados ({c.money(result['total'])})"
                        + (f", {result['repeated']} ya estaban" if result["repeated"] else "")
                        + (f", {result['skipped']} sin cobrar" if result["skipped"] else "")
                        + (f", {result['rejected']} con problemas" if result["rejected"] else "") + ".")
                (st.warning if result["rejected"] else st.success)(text)
                for note in result["notes"][:50]:
                    st.caption(note)
        st.download_button("Plantilla para otras tiendas (CSV)", SHOP_TEMPLATE.encode("utf-8-sig"),
                           "plantilla-pedidos.csv", "text/csv", icon=":material/description:")
        st.caption("Solo se leen el número de pedido, la fecha, los productos, el descuento, el envío y el total: "
                   "los datos personales de tus clientes en el archivo no se importan. Importar dos veces el mismo "
                   "archivo no duplica pedidos.")


def _stock_by_location(c) -> None:
    with st.expander("Stock por local y traspasos", icon=":material/swap_horiz:"):
        table = c.store.stock_by_location()
        names = [loc["name"] for loc in c.store.locations(include_inactive=True)]
        st.dataframe(table, hide_index=True, width="stretch", column_order=["sku", "name", *names, "Total"],
                     column_config={"sku": "Código", "name": "Artículo"})
        products = dict(zip(table["id"].astype(int), table["name"]))
        places = {loc["id"]: loc["name"] for loc in c.locations}
        with st.form("transfer_stock", clear_on_submit=True):
            st.markdown("**Traspasar stock**")
            product = st.selectbox("Artículo", list(products), format_func=products.get)
            a, b, d = st.columns(3)
            origin = a.selectbox("Desde", list(places), format_func=places.get)
            target = b.selectbox("Hasta", list(places), index=min(1, len(places) - 1), format_func=places.get)
            quantity = d.number_input("Unidades", min_value=1, value=1, step=1)
            if st.form_submit_button("Traspasar", type="primary", icon=":material/swap_horiz:"):
                try:
                    c.store.transfer_stock(product, quantity, origin, target, c.who)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    c.store.audit(c.username, "traspaso_stock",
                                  f"{quantity} × {products[product]}: {places[origin]} → {places[target]}")
                    st.session_state["products_flash"] = (f"Traspasadas {quantity} unidades de «{products[product]}» "
                                                          f"de {places[origin]} a {places[target]}.")
                    bump_editor("products_editor")
                    st.rerun()


def products_page() -> None:
    c = ctx()
    if not require_role(c, "encargado"):
        return
    label, plural = c.preset["item_label"], c.preset["item_label_plural"]
    page_header(plural, "Edita directamente en la tabla y guarda. Desactiva en lugar de borrar para "
                "conservar el historial.", eyebrow="Gestión")
    if "products_flash" in st.session_state:
        st.success(st.session_state.pop("products_flash"))

    df = c.store.products(include_inactive=True)
    if c.multi_location:  # the table shows (and adjusts) the stock at the location chosen in the menu
        here = c.store.stock_at(c.location_id)
        df["stock"] = df["id"].map(here).fillna(0).astype(int)
    vat_labels = {None: f"Por defecto ({c.tax_rate:g} %)", **{r: f"{r:g} %" for r in (21.0, 10.0, 5.0, 4.0, 0.0)}}
    vat_rates = {label: rate for rate, label in vat_labels.items()}
    categories = sorted(set(c.preset["categories"]) | set(df["category"]))
    tab_list, tab_new = st.tabs([f"Catálogo ({len(df)})", f"Nuevo {label.lower()}"])

    with tab_list:
        df = df.assign(
            track_stock=df["track_stock"].astype(bool), active=df["active"].astype(bool),
            margin=((df["net_price"] - df["cost"]) / df["net_price"].where(df["net_price"] > 0) * 100).round(1),
            iva=[vat_labels[None] if pd.isna(r) else vat_labels.get(float(r), f"{float(r):g} %") for r in df["tax_rate"]],
            state=[("—" if not t else "Bajo mínimo" if s <= m else "Correcto")
                   for t, s, m in zip(df["track_stock"], df["stock"], df["min_stock"])],
        )
        edited = st.data_editor(
            df, key=editor_key("products_editor"), hide_index=True, width="stretch",
            disabled=["id", "margin", "state"],
            column_order=["sku", "name", "category", "price", "iva", "cost", "margin", "stock", "min_stock", "state",
                          "track_stock", "active"],
            column_config={
                "sku": "Código", "name": "Nombre",
                "category": st.column_config.SelectboxColumn("Categoría", options=categories, required=True),
                "price": st.column_config.NumberColumn("Precio (IVA incl.)", min_value=0, format=f"%.2f {c.symbol}",
                                                       help="El precio final, como en la carta o la etiqueta."),
                "iva": st.column_config.SelectboxColumn(
                    "IVA", options=list(vat_rates), required=True,
                    help="El del producto, o el IVA por defecto del negocio (se cambia en Configuración)."),
                "cost": st.column_config.NumberColumn("Coste (sin IVA)", min_value=0, format=f"%.2f {c.symbol}"),
                "margin": st.column_config.NumberColumn("Margen", format="%.1f %%",
                                                        help="Sobre el precio sin IVA, que es lo que te queda."),
                "stock": st.column_config.NumberColumn(f"Stock en {c.location_name}" if c.multi_location else "Stock",
                                                       step=1),
                "min_stock": st.column_config.NumberColumn("Mínimo", min_value=0, step=1),
                "state": "Estado",
                "track_stock": st.column_config.CheckboxColumn("Controlar stock"),
                "active": st.column_config.CheckboxColumn("Activo"),
            },
        )
        st.caption("Si cambias el stock, la diferencia se suma o resta a las existencias reales de ese momento "
                   "(aunque se haya vendido mientras editabas) y queda en «Ajustes de stock».")
        if st.button("Guardar cambios", type="primary", icon=":material/save:"):
            changed = 0
            try:
                for (_, before), (_, after) in zip(df.iterrows(), edited.iterrows()):
                    pid = int(after["id"])
                    changes = {f: after[f] for f in c.store.PRODUCT_EDITABLE
                               if f != "tax_rate" and not _same(before[f], after[f])}
                    if before["iva"] != after["iva"]:
                        changes["tax_rate"] = vat_rates.get(after["iva"])
                    delta = int(after["stock"]) - int(before["stock"])
                    if changes:
                        c.store.update_product(pid, changes)
                        c.store.audit(c.username, "producto_modificado", f"{after['sku']} · " + ", ".join(
                            f"{k}: {before[k]} → {after[k]}" for k in changes))
                    if delta:
                        c.store.adjust_stock(pid, delta, "Ajuste en el catálogo", user_name=c.who, location_id=c.location_id)
                    changed += bool(changes or delta)
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
            else:
                st.session_state["products_flash"] = f"{changed} cambio(s) guardado(s)."
                bump_editor("products_editor")
                st.rerun()

        if c.multi_location:
            _stock_by_location(c)
        _online_shop_panel(c)
        with st.expander("Ajustes de stock", icon=":material/history:"):
            moves = c.store.stock_moves()
            if moves.empty:
                st.caption("Todavía no hay ajustes manuales de stock.")
            else:
                st.dataframe(moves, hide_index=True, width="stretch", column_config={
                    "created_at": st.column_config.DatetimeColumn("Cuándo", format="DD/MM/YYYY HH:mm"),
                    "sku": "Código", "name": "Artículo", "delta": "Cambio", "stock_after": "Queda",
                    "reason": "Motivo", "user_name": "Quién"})

    with tab_new:
        with st.form("new_product", clear_on_submit=True):
            a, b = st.columns(2)
            sku = a.text_input("Código / SKU")
            name = b.text_input("Nombre")
            category = a.selectbox("Categoría", categories)
            new_category = b.text_input("…o nueva categoría")
            p1, p2, p3, p4 = st.columns(4)
            price = p1.number_input(f"Precio de venta ({c.symbol}, IVA incluido)", 0.0, step=0.5)
            cost = p2.number_input(f"Coste ({c.symbol})", 0.0, step=1.0)
            stock = p3.number_input("Stock inicial", 0, step=1)
            min_stock = p4.number_input("Stock mínimo", 0, step=1)
            vat_options = [None, 21.0, 10.0, 5.0, 4.0, 0.0]
            vat = st.selectbox("IVA", vat_options, format_func=lambda r: f"Por defecto ({c.tax_rate:g} %)"
                               if r is None else f"{r:g} %")
            track = st.toggle("Controlar stock", value=bool(c.preset["track_stock"]))
            if st.form_submit_button(f"Crear {label.lower()}", type="primary"):
                try:
                    c.store.upsert_product({
                        "sku": sku.strip(), "name": name.strip(), "category": new_category.strip() or category,
                        "price": price, "cost": cost, "tax_rate": vat, "stock": stock if track else 0,
                        "min_stock": min_stock if track else 0, "track_stock": int(track), "active": 1,
                    })
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["products_flash"] = f"«{name}» añadido al catálogo."
                    bump_editor("products_editor")
                    st.rerun()

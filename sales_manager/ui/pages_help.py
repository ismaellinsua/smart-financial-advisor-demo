"""Help and frequently asked questions."""

import streamlit as st

from ui.context import ctx
from ui.styles import page_header

# -------------------------------------------------------------------- help
HELP = [
    # (who can do it, title, steps)
    ("empleado", "Cobrar una venta", [
        "Abre **Vender** y toca los productos (o búscalos por nombre o código).",
        "En el móvil, toca **Ver ticket y cobrar**; en el ordenador el ticket está a la derecha.",
        "Elige la forma de pago (con efectivo, escribe lo entregado y verás el cambio) y toca **Cobrar**.",
        "Desde la ventana de la venta puedes **imprimir** el ticket o enviarlo por **WhatsApp** o **email**.",
    ]),
    ("empleado", "Si recargas o se cierra la pestaña", [
        "No pierdes nada: sigues dentro y el ticket que estabas haciendo sigue ahí.",
        "La sesión se cierra sola tras el tiempo sin uso que fije el administrador.",
    ]),
    ("empleado", "Buscar o reimprimir un ticket", [
        "Abre **Historial**, busca por número o cliente y selecciona la venta.",
        "En «Imprimir o enviar el ticket» tienes de nuevo impresión, WhatsApp y email.",
    ]),
    ("empleado", "Descuentos", [
        "Puedes aplicar hasta el máximo que fije el negocio. Por encima, un encargado lo autoriza con su usuario y PIN "
        "en tu misma caja.",
    ]),
    ("encargado", "Devolver productos o anular una venta", [
        "En **Historial**, selecciona la venta y toca **Devolver productos**: elige las unidades y el motivo.",
        "Si la venta estaba facturada, la factura rectificativa se emite sola.",
        "**Anular** solo es posible si la venta no tiene factura ni devoluciones.",
    ]),
    ("encargado", "Facturar a un cliente", [
        "En **Historial**, selecciona la venta y toca **Emitir factura**. Hacen falta el nombre y el NIF del cliente.",
        "Para facturar, el negocio debe tener su NIF y su dirección en **Configuración**.",
    ]),
    ("encargado", "Cerrar la caja", [
        "Al final del día abre **Caja**, cuenta el efectivo y escribe lo contado: verás si hay descuadre.",
        "Descarga el cierre en PDF si lo necesitas para tu gestoría.",
    ]),
    ("admin", "Varios locales", [
        "En **Configuración → Locales** añade tu segundo local: el actual pasa a llamarse «Principal» y conserva "
        "todo su stock, ventas y cierres.",
        "Elige en el menú lateral en qué local trabajas: ventas, caja, mesas y ajustes de stock son de ese local. "
        "En **Equipo y seguridad** puedes fijar a cada persona en su local.",
        "Pasa mercancía entre locales en **Catálogo → Stock por local y traspasos**. El Panel muestra la "
        "facturación por local, y el Historial se filtra por local.",
    ]),
    ("empleado", "Instalar la app en el móvil o el ordenador", [
        "Android o Chrome: menú del navegador → **Instalar aplicación** (o «Añadir a pantalla de inicio»).",
        "iPhone o iPad (Safari): botón Compartir → **Añadir a pantalla de inicio**.",
        "Se abre con su icono y en su propia ventana, sin la barra del navegador.",
    ]),
    ("encargado", "Tienda online (Shopify, WooCommerce…)", [
        "En **Catálogo → Tienda online** descarga tu catálogo en el formato de Shopify o de WooCommerce y súbelo "
        "a tu tienda: productos, precios con IVA y stock, relacionados por su código (SKU).",
        "Para registrar las ventas de la web, exporta los pedidos de la tienda (en Shopify: Pedidos → Exportar) e "
        "impórtalos ahí mismo: cada pedido cobrado se convierte en una venta y descuenta stock. Para otras tiendas, "
        "usa la plantilla.",
    ]),
    ("encargado", "Si se cae internet", [
        "Prepáralo antes: en **Caja → Caja sin conexión** descarga el archivo de catálogo, abre la caja sin conexión "
        "en el móvil o la tablet, instálala y carga el archivo.",
        "Sin internet, cobra desde esa caja: guarda las ventas en el dispositivo con su propia numeración.",
        "Con internet otra vez: en la caja, «Guardar archivo de ventas»; en la app, **Caja → Importar ventas**; y "
        "después bórralas de la caja. Importar dos veces el mismo archivo no duplica nada.",
    ]),
    ("encargado", "Reservas online", [
        "En **Agenda → Reservas online**, pon tu horario y los días cerrados, y activa «Aceptar reservas online».",
        "Comparte el enlace o imprime el QR: tus clientes eligen hora libre sin llamarte y reciben un enlace para "
        "cancelar. Las reservas aparecen en la Agenda marcadas como «Online», con su teléfono.",
        "La víspera, cada cita con email recibe un recordatorio; las demás, envíalo con «Recordar por WhatsApp».",
    ]),
    ("encargado", "Papeles para la gestoría", [
        "Abre **Gestoría**, elige el trimestre y descarga el Excel: libro de facturas emitidas, IVA por tipo, "
        "retenciones, tickets anulados y gastos.",
        "Envíaselo a tu gestoría antes del día 20 del mes siguiente al trimestre (plazo del IVA trimestral).",
    ]),
    ("encargado", "Stock y precios", [
        "En el catálogo, cambia precios (con IVA incluido) y el IVA de cada producto.",
        "Para el stock usa **ajustes** (+ o −) con su motivo: nunca se pisan las ventas hechas mientras tanto.",
    ]),
    ("encargado", "Datos de un cliente (RGPD)", [
        "En **Clientes → Protección de datos** puedes descargar todos sus datos, marcar si acepta ofertas o borrar "
        "sus datos personales cuando lo pida (las facturas se conservan, como obliga la ley).",
    ]),
    ("admin", "Equipo y seguridad", [
        "En **Equipo y seguridad** das de alta a cada persona con su rol: empleado, encargado o administrador.",
        "Genera tus **códigos de recuperación** y guárdalos: sirven si olvidas tu contraseña.",
        "El registro de actividad muestra accesos, anulaciones, facturas, cierres y cada descarga de datos.",
    ]),
    ("admin", "Copias de seguridad", [
        "En **Configuración → Copia de seguridad** descargas una copia completa cuando quieras.",
        "Con las copias automáticas configuradas (ver README), cada noche se guarda una copia cifrada y se comprueba "
        "que se puede restaurar.",
    ]),
]


def help_page() -> None:
    c = ctx()
    page_header("Ayuda", "Lo esencial para trabajar con NirKanA, según lo que puedes hacer en este negocio.",
                eyebrow="Guía rápida")
    for role, title, steps in HELP:
        if not c.can(role):
            continue
        with st.expander(title):
            st.markdown("\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1)))
    st.caption("¿Algo no funciona como esperas? Escribe a nirkana.oficial@gmail.com.")

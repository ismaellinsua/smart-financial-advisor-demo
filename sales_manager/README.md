# 💼 Gestor de Ventas

Aplicación de ventas elegante y profesional, construida con **Streamlit**, que se adapta a distintos tipos de negocio:
tienda física, restaurante/cafetería, servicios profesionales o e-commerce.

## Capturas

| Panel | Punto de venta |
|---|---|
| ![Panel](../docs/screenshots/02-panel.png) | ![Punto de venta](../docs/screenshots/03-punto-de-venta.png) |
| **Venta registrada** | **Historial** |
| ![Venta registrada](../docs/screenshots/04-venta-registrada.png) | ![Historial](../docs/screenshots/05-historial.png) |
| **Catálogo / Carta** | **Clientes** |
| ![Carta](../docs/screenshots/06-carta.png) | ![Clientes](../docs/screenshots/07-clientes.png) |
| **Reposición inteligente** | **Seguimiento de clientes** |
| ![Reposición](../docs/screenshots/08-reposicion.png) | ![Seguimiento](../docs/screenshots/09-seguimiento-clientes.png) |
| **Configuración** | **Bienvenida** |
| ![Configuración](../docs/screenshots/10-configuracion.png) | ![Bienvenida](../docs/screenshots/01-bienvenida.png) |

En el móvil:

<p><img src="../docs/screenshots/13-movil-acceso.png" width="240" alt="Acceso con contraseña en móvil"> <img src="../docs/screenshots/11-movil-panel.png" width="240" alt="Panel en móvil"> <img src="../docs/screenshots/12-movil-vender.png" width="240" alt="Vender en móvil"></p>

## Funcionalidades

| Módulo | Qué hace |
|---|---|
| **Panel** | Facturación, nº de ventas, ticket medio y margen bruto con comparación frente al periodo anterior; gráficos de ventas diarias, artículos más vendidos, formas de pago y categorías; recomendaciones automáticas. |
| **Vender (TPV)** | Catálogo con búsqueda y filtros, ticket con cantidades, cliente, forma de pago, descuento e impuestos. Al cobrar descuenta stock, numera el ticket (`VTA-2026-00001`) y genera un ticket HTML imprimible. |
| **Historial** | Búsqueda por fechas, estado, ticket o cliente; reimpresión de tickets; anulación con devolución de stock (las ventas nunca se borran, para no romper la numeración); exportación CSV. |
| **Catálogo** | Edición directa en tabla: precio, coste, margen, stock, mínimo, control de stock y activación. |
| **Clientes** | Cartera ordenada por valor acumulado, nº de compras y última compra. |
| **Automatizaciones** | Reposición inteligente según la demanda real (orden de compra en CSV), alertas de stock bajo, seguimiento de clientes inactivos con mensaje de reactivación listo para enviar por email, e informes por periodo. |
| **Configuración** | Datos fiscales, moneda, impuesto, prefijo de tickets, color de marca, pie del ticket, plantillas por tipo de negocio y copias de seguridad (descargar y restaurar). |
| **Acceso privado** | Contraseña opcional (`app_password` en los secrets de Streamlit) para proteger la app cuando se publica en internet. |

Cada tipo de negocio adapta el vocabulario (Productos / Carta / Servicios / Catálogo), las categorías, el impuesto por
defecto y si se controla stock (los servicios no lo necesitan).

## Puesta en marcha

```bash
pip install -r requirements.txt
streamlit run sales_manager/app.py
```

La primera vez aparece un asistente para elegir el nombre y el tipo de negocio, con la opción de cargar 60 días de
ventas de ejemplo. Los datos se guardan en `sales_manager/data/ventas.db` (SQLite).

## Publicar en Streamlit Community Cloud (para usarla desde el móvil)

1. Entra en [share.streamlit.io](https://share.streamlit.io) con tu cuenta de GitHub.
2. Crea una app nueva desde GitHub con estos datos:
   - **Repositorio:** `ismaellinsua/smart-financial-advisor-demo`
   - **Rama:** `main`
   - **Archivo principal:** `sales_manager/app.py`
   - **URL:** la que quieras, por ejemplo `cafe-aurora.streamlit.app`
3. En **Advanced settings**, elige Python 3.12 y escribe en **Secrets** tu contraseña:
   ```toml
   app_password = "elige-una-contraseña-segura"
   ```
   Con esto la app pide contraseña al entrar. Sin ella, cualquiera con el enlace podría ver y cambiar tus datos.
4. Pulsa **Deploy**. Abre la URL en el móvil y usa «Añadir a pantalla de inicio» para tenerla como una app.

**Importante sobre los datos:** en Streamlit Community Cloud el almacenamiento es temporal. Los datos se borran cuando
la app se reinicia, se actualiza o se duerme por inactividad. Descarga a menudo la copia desde
**Configuración → Copia de seguridad** y restáurala si hace falta.

## Estructura

```
sales_manager/
├── app.py              # Navegación y arranque
├── core/               # Lógica sin dependencias de interfaz
│   ├── db.py           # Almacenamiento SQLite, ventas atómicas, datos de ejemplo
│   ├── pricing.py      # Cálculo de totales (Decimal, redondeo comercial)
│   ├── automation.py   # KPIs, reposición, alertas, clientes inactivos, recomendaciones
│   ├── receipts.py     # Tickets HTML imprimibles
│   └── presets.py      # Plantillas por tipo de negocio
├── ui/                 # Páginas y estilo visual
└── tests/              # Pruebas de la lógica y de todas las páginas
```

## Pruebas

```bash
cd sales_manager && python -m pytest -q
```

# 💼 Gestor de Ventas

Aplicación de ventas elegante y profesional, construida con **Streamlit**, que se adapta a distintos tipos de negocio:
tienda física, restaurante/cafetería, servicios profesionales o e-commerce.

## Funcionalidades

| Módulo | Qué hace |
|---|---|
| **Panel** | Facturación, nº de ventas, ticket medio y margen bruto con comparación frente al periodo anterior; gráficos de ventas diarias, artículos más vendidos, formas de pago y categorías; recomendaciones automáticas. |
| **Vender (TPV)** | Catálogo con búsqueda y filtros, ticket con cantidades, cliente, forma de pago, descuento e impuestos. Al cobrar descuenta stock, numera el ticket (`VTA-2026-00001`) y genera un ticket HTML imprimible. |
| **Historial** | Búsqueda por fechas, estado, ticket o cliente; reimpresión de tickets; anulación con devolución de stock (las ventas nunca se borran, para no romper la numeración); exportación CSV. |
| **Catálogo** | Edición directa en tabla: precio, coste, margen, stock, mínimo, control de stock y activación. |
| **Clientes** | Cartera ordenada por valor acumulado, nº de compras y última compra. |
| **Automatizaciones** | Reposición inteligente según la demanda real (orden de compra en CSV), alertas de stock bajo, seguimiento de clientes inactivos con mensaje de reactivación listo para enviar por email, e informes por periodo. |
| **Configuración** | Datos fiscales, moneda, impuesto, prefijo de tickets, color de marca, pie del ticket y plantillas por tipo de negocio. |

Cada tipo de negocio adapta el vocabulario (Productos / Carta / Servicios / Catálogo), las categorías, el impuesto por
defecto y si se controla stock (los servicios no lo necesitan).

## Puesta en marcha

```bash
pip install -r requirements.txt
streamlit run sales_manager/app.py
```

La primera vez aparece un asistente para elegir el nombre y el tipo de negocio, con la opción de cargar 60 días de
ventas de ejemplo. Los datos se guardan en `sales_manager/data/ventas.db` (SQLite).

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

# 💼 Gestor de Ventas

Aplicación de ventas elegante y profesional, construida con **Streamlit**, que se adapta a distintos tipos de negocio:
tienda física, restaurante/cafetería, servicios profesionales o e-commerce.

## Capturas

| Panel | Punto de venta |
|---|---|
| ![Panel](../docs/screenshots/02-panel.png) | ![Punto de venta](../docs/screenshots/03-punto-de-venta.png) |
| **Venta registrada** | **Historial** | Búsqueda por fechas, estado, ticket o cliente; reimpresión de tickets; **facturas en PDF** con serie propia (`FAC-2026-0001`), datos fiscales del cliente e IVA desglosado; anulación con devolución de stock (las ventas facturadas no se anulan); exportación CSV. |
| **Caja** | Cierre diario: ventas por forma de pago, fondo inicial, efectivo esperado frente a contado, descuadre, notas e informe en PDF para firmar. |
| **Agenda** | Citas (autónomos) o reservas (restaurantes): vista por día, sin solapes en agendas personales, cobro de la cita con un toque y estados «No vino» o «Cancelada». Se activa sola según el tipo de negocio o desde Configuración. |
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
| **Equipo y seguridad** | Cuentas por persona (nombre + PIN o contraseña) con tres roles: administrador, encargado y empleado. Varias personas a la vez desde sus móviles; cada venta, factura, cita y cierre queda firmado. Registro de actividad con accesos fallidos. |

Arriba de cada pantalla hay una cabecera discreta con el negocio, lo vendido hoy y la próxima cita.

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
   Es la contraseña de instalación: la app la pide una sola vez, para crear la cuenta del administrador. Sin ella,
   una app publicada no deja crear el administrador. Después cada persona del equipo entra con su usuario y su PIN
   (**Equipo y seguridad**).
4. Pulsa **Deploy**. Abre la URL en el móvil y usa «Añadir a pantalla de inicio» para tenerla como una app.

**Importante sobre los datos:** sin base de datos externa, Streamlit Community Cloud guarda los datos en un archivo
temporal que se borra cuando la app se reinicia, se actualiza o se duerme. Para que no se pierdan nunca, conecta una
base de datos gratuita (siguiente apartado).

## Base de datos permanente y gratuita (Neon)

La app usa PostgreSQL cuando encuentra `database_url` en los *Secrets*; si no, usa el archivo local SQLite.

1. **Guarda tus datos actuales:** en la app, **Configuración → Copia de seguridad → Descargar copia de seguridad**.
2. Crea una cuenta gratuita en [neon.tech](https://neon.tech) (puedes entrar con GitHub o Google; no pide tarjeta).
3. Crea un proyecto, por ejemplo `gestor-ventas`, en una región cercana (para España: *AWS Europe Central 1 (Frankfurt)*).
4. En el panel del proyecto pulsa **Connect**, muestra la contraseña y copia la cadena de conexión.
   Empieza por `postgresql://` y termina en algo como `?sslmode=require`.
5. En Streamlit: tu app → **⋮ → Settings → Secrets**, y deja estas dos líneas:
   ```toml
   app_password = "tu-contraseña"
   database_url = "postgresql://usuario:clave@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require"
   ```
   Guarda: la app se reinicia sola y crea las tablas.
6. Entra en la app, ve a **Configuración → Copia de seguridad → Restaurar** y sube el archivo del paso 1.
   En Configuración verás «Tus datos se guardan en PostgreSQL en la nube».

El plan gratuito de Neon basta para un negocio pequeño. La base se duerme tras unos minutos sin uso y tarda uno o dos
segundos en despertar la primera vez; la app se reconecta sola.

## Seguridad

| Medida | Detalle |
|---|---|
| Cuentas individuales | Cada persona entra con su usuario y su PIN o contraseña. Las contraseñas se guardan cifradas con PBKDF2-SHA256 (600.000 iteraciones y sal aleatoria), nunca en claro. |
| Roles | **Administrador:** todo. **Encargado:** panel, caja, catálogo, clientes, facturas y anulaciones. **Empleado:** vender, agenda y consultar tickets. Cada página comprueba el rol en el servidor, no solo el menú. |
| Fuerza bruta | 5 intentos fallidos bloquean la cuenta 5 minutos; los fallos se retrasan y quedan registrados. Un usuario inexistente tarda lo mismo que uno real. |
| Primer acceso | En una app publicada, crear el administrador exige `app_password` de los *Secrets*. Sin ella, la app se niega, para que nadie se apropie de ella tras un reinicio. |
| Sesiones | Se cierran tras un tiempo sin uso (configurable, 12 h por defecto) y al desactivar a una persona. Recargar la página pide de nuevo el PIN. |
| Registro de actividad | Accesos, intentos fallidos, anulaciones, facturas, cierres y reaperturas de caja, cambios de configuración, restauraciones y cambios en el equipo. |
| Copias de seguridad | No incluyen usuarios ni registro: las credenciales no salen del servidor. Al restaurar solo se aceptan tablas y columnas conocidas (sin inyección SQL por nombres de columna) y se valida el archivo. |
| Exportaciones | Los CSV neutralizan fórmulas de hoja de cálculo (`=`, `+`, `-`, `@`). Los textos de usuario se escapan en pantallas, tickets y PDF. |
| Base de datos | Consultas siempre parametrizadas. Conexión a PostgreSQL remoto con TLS obligatorio (`sslmode=require`). Límites de longitud en todos los textos. |
| Servidor | Subidas limitadas a 20 MB, protección XSRF activa y errores sin detalles internos para el usuario. |

**Lo que no depende de la app:** la seguridad de la cuenta de Streamlit y de GitHub (activa la verificación en dos pasos en ambas), la de Neon y la custodia de los *Secrets*. En la versión gratuita de Streamlit sin base de datos externa, un reinicio borra datos **y cuentas**: para un equipo real usa Neon.

## Estructura

```
sales_manager/
├── app.py              # Navegación y arranque
├── core/               # Lógica sin dependencias de interfaz
│   ├── db.py           # Almacenamiento SQLite o PostgreSQL, ventas atómicas, copias, datos de ejemplo
│   ├── pricing.py      # Cálculo de totales (Decimal, redondeo comercial)
│   ├── automation.py   # KPIs, reposición, alertas, clientes inactivos, recomendaciones
│   ├── receipts.py     # Tickets HTML imprimibles
│   ├── pdfs.py         # Facturas e informes de cierre de caja en PDF
│   └── presets.py      # Plantillas por tipo de negocio
├── ui/                 # Páginas y estilo visual
└── tests/              # Pruebas de la lógica y de todas las páginas
```

## Pruebas

```bash
cd sales_manager && python -m pytest -q
# Para probar también contra PostgreSQL:
TEST_DATABASE_URL=postgresql://usuario:clave@localhost:5432/pruebas python -m pytest -q
```

## Licencia

Software propietario. © 2025-2026 Ismael Linsua. Todos los derechos reservados.
Prohibido copiar, modificar, distribuir, vender o alojar para terceros sin permiso por escrito del titular.
Consulta el archivo [`LICENSE`](../LICENSE) para las condiciones completas.

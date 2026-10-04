# 💼 Gestor de Ventas

Aplicación de ventas elegante y profesional, construida con **Streamlit**, que se adapta a distintos tipos de negocio:
tienda física, restaurante/cafetería, servicios profesionales o e-commerce.

## Capturas

| Panel | Punto de venta |
|---|---|
| ![Panel](../docs/screenshots/02-panel.png) | ![Punto de venta](../docs/screenshots/03-punto-de-venta.png) |
| **Mesas y comandas** | **Pantalla de cocina** |
| ![Mesas](../docs/screenshots/23-mesas.png) | ![Cocina](../docs/screenshots/24-cocina.png) |
| **Cobro de una mesa por productos** | **Promociones y fidelización** |
| ![Cobro dividido](../docs/screenshots/25-cobro-comanda.png) | ![Promociones](../docs/screenshots/26-promociones.png) |
| **Compras a proveedores** | **Gastos y beneficio neto** |
| ![Compras](../docs/screenshots/27-compras.png) | ![Gastos](../docs/screenshots/28-gastos-y-beneficio.png) |
| **Alertas inteligentes** | **Análisis ABC** |
| ![Alertas](../docs/screenshots/29-alertas.png) | ![ABC](../docs/screenshots/30-analisis-abc.png) |
| **Precios con margen objetivo** | **Informe semanal** |
| ![Precios](../docs/screenshots/31-precios.png) | ![Informe semanal](../docs/screenshots/32-informe-semanal.png) |
| **Historial** | **Agenda** |
| ![Historial](../docs/screenshots/05-historial.png) | ![Agenda](../docs/screenshots/18-agenda.png) |
| **Cierre de caja** | **Equipo y seguridad** |
| ![Caja](../docs/screenshots/19-cierre-de-caja.png) | ![Equipo](../docs/screenshots/22-equipo-y-seguridad.png) |

En el móvil:

<p><img src="../docs/screenshots/13-movil-acceso.png" width="240" alt="Acceso en móvil"> <img src="../docs/screenshots/11-movil-panel.png" width="240" alt="Panel en móvil"> <img src="../docs/screenshots/12-movil-vender.png" width="240" alt="Vender en móvil"></p>

## Funcionalidades

### Operación

| Módulo | Qué hace |
|---|---|
| **Panel** | Facturación, ventas, ticket medio y margen frente al periodo anterior (netos de devoluciones); ventas diarias, lo más vendido, formas de pago, categorías y ventas por persona; alertas inteligentes y el informe semanal listo para descargar. |
| **Vender (TPV)** | Catálogo con búsqueda, ticket, cliente, descuento, **promociones automáticas** y **canje de puntos**. Cobro en **un pago con cálculo del cambio**, **pago mixto** (parte tarjeta, parte efectivo…) o **cuenta dividida** entre varias personas. En el móvil, catálogo y ticket se alternan con una barra fija y «Cobrar» siempre está a la vista. Tras cobrar: **imprimir** (A4 o ticket térmico de 80/58 mm) o enviar por **WhatsApp** o **email**. |
| **Mesas y comandas** | Plano de mesas por zonas, comandas compartidas entre camareros (cada línea firmada), notas para cocina, comensales, cambio de mesa y pedidos para llevar. Se cobra toda la mesa o **solo los productos que paga cada persona**. |
| **Cocina** | Pantalla que se actualiza sola: pendiente → preparando → listo → servido, con aviso de los platos que esperan demasiado. |
| **Agenda** | Citas (autónomos) o reservas (restaurantes), sin solapes, cobro de la cita con un toque. |
| **Caja** | Cierre diario por forma de pago (pagos mixtos repartidos), devoluciones descontadas, arqueo de efectivo e informe PDF. |
| **Historial** | Tickets, **facturas en PDF** (`FAC-2026-0001`), **devoluciones parciales** con su ticket y **facturas rectificativas** automáticas (`FACR-2026-0001`), anulaciones y exportación CSV. |

### Gestión

| Módulo | Qué hace |
|---|---|
| **Catálogo / Carta** | Edición en tabla: precio, coste, margen, stock, mínimo y proveedor habitual. |
| **Clientes** | Cartera por valor, compras, última visita y puntos. **Protección de datos (RGPD):** descargar todos los datos de una persona, consentimiento para ofertas (el seguimiento solo muestra a quien aceptó) y borrado de datos personales conservando las facturas. |
| **Promociones** | Descuentos en % o 2x1 / 3x2, para todo, una categoría o un producto, por días y franja horaria (*happy hour*). Se aplican solas al cobrar, siempre la mejor para el cliente. |
| **Fidelización** | Puntos por cada euro, canje como descuento, ranking de clientes. Las devoluciones y anulaciones restan los puntos. |
| **Compras** | Proveedores, pedidos en PDF, recepción parcial o total: el stock y el **coste medio** se actualizan solos y el gasto queda apuntado. La reposición inteligente crea los pedidos por proveedor con un clic. |
| **Gastos y beneficio** | Gastos por categoría, gastos fijos mensuales que se apuntan solos y beneficio neto real: ventas netas − coste de lo vendido − gastos, con la evolución de 6 meses. |

### Inteligencia

| Módulo | Qué hace |
|---|---|
| **Alertas inteligentes** | Se vigilan solas y se ven en el Panel y como aviso en la barra superior: caída de ventas, descuadres de caja, productos que se agotan en pocos días, clientes habituales que dejan de venir, mesas olvidadas, personas con anulaciones o devoluciones fuera de lo normal, pérdidas o gastos excesivos, márgenes bajos y productos sin ventas. |
| **Análisis ABC** | Qué productos sostienen el margen (A: el 80 %, B: el 15 %, C: el resto) con gráfico de Pareto y exportación. |
| **Precios** | Propuesta de precio para alcanzar el margen objetivo del sector, redondeada a importes cómodos; se revisa y se aplica con un clic (queda en el registro). |
| **Informe semanal** | PDF de la semana frente a la anterior: ventas por día, lo más vendido, equipo, ABC, cajas, beneficio estimado, alertas y recomendaciones. Cada lunes aparece listo en el Panel. |
| **Automatizaciones** | Reposición según la demanda real, stock bajo mínimos, mensajes para reactivar clientes e informes por periodo. |

### Ajustes

| Módulo | Qué hace |
|---|---|
| **Precios e IVA** | Los precios se escriben **con IVA incluido**, como en la carta o la etiqueta, y cada producto puede tener su IVA (21, 10, 5, 4 o 0 %) o usar el del negocio. El ticket siempre coincide con la carta; tickets, facturas y rectificativas desglosan base y cuota por tipo. Facturas con **retención de IRPF** opcional para profesionales, y solo con NIF y dirección del negocio. Los catálogos antiguos (precios sin IVA) se convierten solos una vez. |
| **Configuración** | Datos fiscales, moneda, **zona horaria** (España por defecto: los servidores en la nube van en UTC), impuesto, series de tickets y facturas, color de marca, mesas y agenda, fidelización, tiempo de sesión y copias de seguridad. |
| **Registro de facturación (VERI\*FACTU, en preparación)** | Al activarlo, cada ticket (F2), factura (F3), rectificativa (R1/R5) y anulación queda en un registro encadenado con la huella SHA-256 de la AEAT, que la propia base de datos impide modificar o borrar. Tickets, facturas y rectificativas llevan el **código QR tributario** (35 mm, al principio del documento). Se comprueba y exporta desde Configuración. **Aún no se envía a Hacienda**: hasta entonces la app funciona como sistema «no VERI\*FACTU» (el QR apunta al cotejo de la AEAT para ese modo y no se imprime la leyenda «VERI\*FACTU»), y no es un sistema VERI\*FACTU completo. |
| **Equipo y seguridad** | Cuentas por persona (PIN o contraseña) con roles administrador, encargado y empleado; varias personas a la vez desde sus móviles; registro de actividad. |
| **Cambiar de negocio** | Cambia en segundos entre tienda, restaurante, autónomo o e-commerce con datos de ejemplo: ideal para enseñar la app a cada cliente. |

Arriba de cada pantalla hay una cabecera discreta con el negocio, lo vendido hoy y la próxima cita.

Cada tipo de negocio adapta el vocabulario (Productos / Carta / Servicios / Catálogo), las categorías, el impuesto por
defecto y si se controla stock (los servicios no lo necesitan).

## Puesta en marcha

```bash
pip install -r requirements.txt
streamlit run sales_manager/app.py
```

La primera vez, un asistente de tres pasos pide el negocio (nombre, tipo y zona horaria), los datos fiscales (NIF,
que se comprueba, dirección e IVA habitual) y deja el negocio listo para vender; las ventas de ejemplo solo se cargan
si las pides. Los datos se guardan en `sales_manager/data/ventas.db` (SQLite). Dentro de la app, **Ayuda** tiene una
guía corta para cada rol.

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
   Es la contraseña de instalación: la app la pide una sola vez, para crear la cuenta del administrador. Si no la
   pones, la app pide en su lugar un código que aparece en «Manage app → Logs». Después cada persona del equipo entra
   con su usuario y su PIN (**Equipo y seguridad**).
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

## Varios negocios en una sola app (modo multinegocio)

En vez de una app y una base de datos por cliente, una sola app y una sola base de datos pueden atender a muchos
negocios. Cada negocio vive en su propio esquema de PostgreSQL: sus ventas, clientes, facturas, cuentas y numeración
no se mezclan con los de ningún otro, y nada de un negocio puede leer o cambiar lo de otro.

1. En los *Secrets* de la app (con una base Neon, apartado anterior):
   ```toml
   database_url = "postgresql://…"
   multi_tenant = true
   operator_password = "una-contraseña-larga-solo-para-ti"
   ```
2. Abre `https://tu-app.streamlit.app/?operador`, entra con `operator_password` y **da de alta el negocio**: código
   (va en la dirección, p. ej. `cafe-aurora`), nombre y contacto. Se muestra **una sola vez** su código de instalación.
3. Envía al negocio su dirección (`…/?negocio=cafe-aurora`) y el código. Con él crea su administrador; después el
   asistente de primera configuración deja el negocio listo.
4. Desde el panel ves cada negocio (personas, ventas, última venta), puedes **suspender o reactivar** su acceso y
   generar un código nuevo si lo perdió antes de crear su administrador. Todo queda en el registro del operador.

Quien entra sin código ve «Entra en tu negocio»: la lista de negocios no se muestra nunca. Si en la misma pestaña se
abre otro negocio, la sesión anterior se borra entera. Las copias automáticas detectan este modo y guardan **una copia
cifrada por negocio** (más el directorio), cada una restaurable por separado.

Sin `multi_tenant`, la app funciona como siempre: un negocio por app.

## Copias de seguridad automáticas

Cada noche, GitHub Actions (gratis) hace una copia cifrada de la base de datos de cada negocio, la **restaura en una
base de pruebas y comprueba** que tiene las mismas ventas, facturas y cierres que producción, y la guarda 30 días.
Si algo falla, GitHub te avisa por email. Solo lee la base de producción: nunca la modifica.

**Activarlas (una vez):** en GitHub, repositorio → **Settings → Secrets and variables → Actions → New repository
secret**:

| Secreto | Qué poner |
|---|---|
| `BACKUP_DATABASES` | Una línea por negocio: `nombre=postgresql://…` (la cadena de conexión de Neon). Ej.: `cafe-aurora=postgresql://usuario:clave@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require` |
| `BACKUP_PASSPHRASE` | Una frase larga (16+ caracteres) para cifrar. **Guárdala en tu gestor de contraseñas: sin ella las copias no se pueden abrir.** |
| `BACKUP_S3_*` (opcional) | Para guardar además una copia fuera de GitHub (Cloudflare R2, Backblaze B2 o S3): `BACKUP_S3_BUCKET`, `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY`, `BACKUP_S3_ENDPOINT` y `BACKUP_S3_REGION`. |

Después, en **Actions → Copias de seguridad → Run workflow**, lánzala una vez para comprobar que va.

Cada negocio tiene dos archivos cifrados: `…dump.enc` (la base completa, con cuentas y registro de actividad) y
`…db.enc` (la copia de la app, sin cuentas).

**Recuperar datos:** descarga el artefacto de la ejecución que quieras (Actions → la ejecución → *Artifacts*) y:

```bash
export BACKUP_PASSPHRASE="tu frase"
python ops/backup.py --decrypt cafe-aurora-20261004-0217.db.enc     # → Configuración → Restaurar, en un negocio sin ventas
python ops/backup.py --decrypt cafe-aurora-20261004-0217.dump.enc   # todo, en una base nueva:
pg_restore --no-owner --no-privileges --dbname="postgresql://…/base_nueva" cafe-aurora-20261004-0217.dump
```

Mientras el repositorio sea público, cualquiera con cuenta de GitHub puede descargar los artefactos: están cifrados,
pero es mejor hacer el repositorio privado.

## Seguridad

| Medida | Detalle |
|---|---|
| Cuentas individuales | Cada persona entra escribiendo su usuario y su PIN (mínimo 6 cifras, sin series como 123456) o contraseña; la pantalla de acceso no muestra quién trabaja en el negocio. Los PIN antiguos más cortos se cambian al entrar, y cada persona puede cambiar el suyo. Las contraseñas se guardan cifradas con PBKDF2-SHA256 (600.000 iteraciones y sal aleatoria), nunca en claro. |
| Roles | **Administrador:** todo. **Encargado:** panel, caja, gestión, inteligencia, facturas, devoluciones y anulaciones. **Empleado:** mesas, vender, agenda y consultar sus propios tickets de los últimos 7 días. Cada página comprueba el rol en el servidor, no solo el menú. |
| Fuerza bruta | Quien falla muchas veces desde un mismo dispositivo espera cada vez más (15 min, 30, 1 h… hasta 24 h) sin afectar al resto. La cuenta solo se bloquea 15 minutos tras 10 fallos, para que nadie pueda dejar al negocio fuera de su propia caja. Un usuario inexistente tarda lo mismo que uno real. |
| Recuperación y dos pasos | El administrador recibe 8 códigos de recuperación de un solo uso (al crear la cuenta y en «Equipo y seguridad»): sirven para entrar si olvida la contraseña, pierde el móvil o le bloquean la cuenta. Puede activar la verificación en dos pasos con Google Authenticator o similar. |
| Primer acceso | Crear el administrador exige `app_password` de los *Secrets* o, si no existe, un código de un solo uso que solo aparece en el registro del servidor (terminal o «Manage app → Logs»). Así nadie puede apropiarse de la app tras un reinicio. |
| Sesiones | Recargar la página o reabrir la pestaña no saca de la sesión ni pierde el ticket en curso: el navegador guarda un token aleatorio (cookie `SameSite=Strict`, `Secure` con HTTPS) y la base de datos solo su huella SHA-256. Se cierran tras un tiempo sin uso (configurable, 12 h por defecto), al salir, al cambiar el PIN (en todos los dispositivos) y al desactivar a una persona. |
| Descuentos | Los empleados pueden dar hasta el descuento máximo fijado en Configuración (10 % por defecto); por encima, un encargado o el administrador lo autoriza con su usuario y PIN y queda firmado en la venta y en el registro. |
| Stock | Editar el catálogo solo guarda lo que cambias. Los cambios de stock se suman o restan a las existencias reales del momento y quedan en «Ajustes de stock» con quién, cuándo y cuánto. |
| Registro de actividad | Accesos, intentos fallidos, anulaciones, facturas, cierres y reaperturas de caja, cambios de configuración, restauraciones, cambios en el equipo y **cada descarga de datos** (exportaciones, copias y datos de clientes). Se puede filtrar. |
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
│   ├── db.py              # Almacenamiento SQLite o PostgreSQL, ventas atómicas, copias, datos de ejemplo
│   ├── store_refunds.py   # Devoluciones y facturas rectificativas
│   ├── store_orders.py    # Mesas, comandas y cocina
│   ├── store_purchases.py # Proveedores, pedidos, gastos y beneficio
│   ├── store_intel.py     # Datos para alertas, precios e informe semanal
│   ├── intelligence.py    # ABC, sugerencias de precio, alertas y recomendaciones
│   ├── pricing.py         # Totales, promociones y reparto de cuentas (Decimal, redondeo comercial)
│   ├── automation.py      # KPIs, reposición, clientes inactivos, recomendaciones
│   ├── receipts.py        # Tickets HTML imprimibles
│   ├── pdfs.py            # Facturas, rectificativas, cierres, pedidos e informe semanal en PDF
│   ├── security.py        # Contraseñas, roles y saneado de datos
│   └── presets.py         # Plantillas por tipo de negocio
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

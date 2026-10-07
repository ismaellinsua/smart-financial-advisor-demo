# 💼 Gestor de Ventas

Aplicación de ventas elegante y profesional, construida con **Streamlit**, que se adapta a distintos tipos de negocio:
tienda física, restaurante/cafetería, servicios profesionales o e-commerce.

## Capturas

| Panel | Punto de venta |
|---|---|
| ![Panel](../capturas/02-panel.png) | ![Punto de venta](../capturas/03-punto-de-venta.png) |
| **Mesas y comandas** | **Pantalla de cocina** |
| ![Mesas](../capturas/23-mesas.png) | ![Cocina](../capturas/24-cocina.png) |
| **Cobro de una mesa por productos** | **Promociones y fidelización** |
| ![Cobro dividido](../capturas/25-cobro-comanda.png) | ![Promociones](../capturas/26-promociones.png) |
| **Compras a proveedores** | **Gastos y beneficio neto** |
| ![Compras](../capturas/27-compras.png) | ![Gastos](../capturas/28-gastos-y-beneficio.png) |
| **Alertas inteligentes** | **Análisis ABC** |
| ![Alertas](../capturas/29-alertas.png) | ![ABC](../capturas/30-analisis-abc.png) |
| **Precios con margen objetivo** | **Informe semanal** |
| ![Precios](../capturas/31-precios.png) | ![Informe semanal](../capturas/32-informe-semanal.png) |
| **Historial** | **Agenda** |
| ![Historial](../capturas/05-historial.png) | ![Agenda](../capturas/18-agenda.png) |
| **Cierre de caja** | **Equipo y seguridad** |
| ![Caja](../capturas/19-cierre-de-caja.png) | ![Equipo](../capturas/22-equipo-y-seguridad.png) |

En el móvil:

<p><img src="../capturas/13-movil-acceso.png" width="240" alt="Acceso en móvil"> <img src="../capturas/11-movil-panel.png" width="240" alt="Panel en móvil"> <img src="../capturas/12-movil-vender.png" width="240" alt="Vender en móvil"></p>

## Funcionalidades

### Operación

| Módulo | Qué hace |
|---|---|
| **Panel** | Facturación, ventas, ticket medio y margen frente al periodo anterior (netos de devoluciones); ventas diarias, lo más vendido, formas de pago, categorías y ventas por persona; alertas inteligentes y el informe semanal listo para descargar. |
| **Vender (TPV)** | Catálogo con búsqueda, ticket, cliente, descuento, **promociones automáticas** y **canje de puntos**. Cobro en **un pago con cálculo del cambio**, **pago mixto** (parte tarjeta, parte efectivo…) o **cuenta dividida** entre varias personas. En el móvil, catálogo y ticket se alternan con una barra fija y «Cobrar» siempre está a la vista. Tras cobrar: **imprimir** (A4 o ticket térmico de 80/58 mm) o enviar por **WhatsApp** o **email**. |
| **Mesas y comandas** | Plano de mesas por zonas, comandas compartidas entre camareros (cada línea firmada), notas para cocina, comensales, cambio de mesa y pedidos para llevar. Se cobra toda la mesa o **solo los productos que paga cada persona**. |
| **Cocina** | Pantalla que se actualiza sola: pendiente → preparando → listo → servido, con aviso de los platos que esperan demasiado. |
| **Agenda** | Citas (autónomos) o reservas (restaurantes), sin solapes, cobro de la cita con un toque. |
| **Tienda online** | Sin cuentas ni cuotas, por archivos: el catálogo (precio con IVA y stock) sale en el CSV que importan **Shopify** y **WooCommerce**, y los pedidos entran desde la exportación de pedidos de Shopify o una plantilla genérica para cualquier tienda. Cada pedido cobrado es una venta con el precio cobrado, su descuento y su envío; descuenta stock del local elegido y no se duplica al importar otra vez. No se leen los datos personales de los clientes. |
| **Varios locales** | En **Configuración → Locales** se añaden tiendas o locales: cada uno vende de su propio stock (con traspasos entre locales), cierra su caja, tiene sus mesas y su cocina, y su dirección sale en los tickets. Selector de local en el menú, personas fijadas a un local, facturación por local en el Panel y filtro en el Historial. Con un solo local no cambia nada. |
| **App instalable** | Se instala en el móvil o el ordenador desde el navegador («Instalar aplicación» / «Añadir a pantalla de inicio»), con su icono y su propia ventana. Con varios negocios en una app, recuerda el último negocio usado en ese dispositivo. |
| **Caja sin conexión** | Si se cae internet, se cobra desde una caja instalable en el móvil o la tablet ([`docs/caja`](../docs/caja/), publicada con la web) que funciona sin red: carga el catálogo desde **Caja → Caja sin conexión**, numera sus tickets en su propia serie (`VTA-SC1-000001`, una por dispositivo) y exporta las ventas a un archivo que se importa en la app sin duplicados, con el precio cobrado y el desglose de IVA. No aplica promociones, puntos ni clientes. |
| **Reservas online** | Página pública (`…/?reservar`, o `…/?negocio=código&reservar` con varios negocios) donde el cliente elige una hora libre según tu horario, recibe confirmación con archivo de calendario y un enlace para cancelar, y un recordatorio por email la víspera (el trabajo diario «Avisos por email»). Recordatorio por WhatsApp con un toque. Teléfono y email se borran 90 días después de la cita. |
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

## Publicar en un servidor propio en la UE (Render, Frankfurt)

Para clientes de pago: la app en Frankfurt, junto a la base de Neon (también en Frankfurt), sin que se duerma y con
cabeceras de seguridad. El `Dockerfile` de la raíz pone [Caddy](https://caddyserver.com) delante de Streamlit, que solo
escucha dentro del contenedor, y añade HSTS, `X-Frame-Options`/`frame-ancestors` (nadie puede incrustar la app en otra
web), una política de contenido (CSP) que solo deja cargar y enviar datos a la propia app y solo ejecuta sus propios scripts (por su huella SHA-256: un script inyectado no se ejecuta), `nosniff`, `Referrer-Policy` y `Permissions-Policy`. La app no corre como administrador del sistema. La cookie
de sesión la escribe el propio servidor como **HttpOnly** (ningún script de la página puede leerla). **Para clientes
reales usa solo este contenedor:** en Streamlit Community Cloud no hay Caddy, así que faltan esas cabeceras y la cookie
de sesión la escribe la página.

1. Crea la base en Neon (sección anterior) y copia su cadena de conexión.
2. En [render.com](https://render.com): **New → Blueprint** y elige este repositorio. Lee `render.yaml`: servicio
   `nirkana` en **Frankfurt**, plan *Starter* (de pago, no se duerme).
3. Render te pide las variables marcadas como secretas: `DATABASE_URL` (la de Neon), `APP_PASSWORD` (la contraseña de
   instalación), `DATA_KEY` (una frase larga y aleatoria con la que se cifran las claves de verificación en dos pasos;
   guárdala también fuera de Render) y, si quieres emails, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` y `SMTP_FROM`. Se
   guardan en Render, nunca en el repositorio.
4. Cuando el despliegue diga *Live*, en el servicio → **Settings → Custom Domains** añade, por ejemplo,
   `app.nirkana.es`. Render te dirá qué registro **CNAME** crear en IONOS; el HTTPS lo pone Render.
5. Los despliegues son manuales (`autoDeploy: false`): pulsa **Manual Deploy** cuando los tests de GitHub estén en verde.

Sin `DATABASE_URL` el contenedor **no arranca la app**: muestra un aviso en lugar de guardar los datos en su propio disco,
que Render borra en cada despliegue. Los límites de intentos de acceso se cuentan por la IP real de cada visitante
(la app salta las direcciones internas de Render y Caddy) y se guardan en la base de datos. Si algún día pones delante
otro proxy con IP pública (Cloudflare…), declara sus redes en `TRUSTED_PROXIES`.

**Pasar de Streamlit Community Cloud a Render sin perder nada:**

1. En la app actual: **Configuración → Copia de seguridad → Descargar copia de seguridad**. Guarda el archivo.
   Si esa app ya usaba Neon, basta con poner la misma `DATABASE_URL` en Render y te saltas los pasos 1 y 3.
2. Despliega en Render (pasos de arriba) con una base de Neon **nueva** en Frankfurt.
3. Entra en `app.nirkana.es`, crea el administrador y completa el asistente (da igual lo que elijas: la copia lo
   sustituye todo, configuración incluida). Después, en **Configuración → Copia de seguridad → Restaurar**, sube el
   archivo del paso 1. Solo se puede en un negocio sin ventas reales: hazlo antes de vender. Tu equipo no viaja en la
   copia (por seguridad): vuelve a dar de alta a cada persona en **Equipo y seguridad**.
4. Comprueba ventas, clientes y facturas. Después, en Streamlit Cloud, apaga la app antigua (**⋮ → Delete**) o déjala
   solo como demostración, sin datos reales.
5. Cambia `UPTIME_URLS` (secreto de GitHub Actions) a `https://app.nirkana.es`.

Probarlo en tu ordenador: `docker build -t nirkana . && docker run -p 8080:8080 -e DATABASE_URL=postgresql://… \
-e APP_PASSWORD=... nirkana` y abre http://localhost:8080.

## Varios negocios en una sola app (modo multinegocio)

En vez de una app y una base de datos por cliente, una sola app y una sola base de datos pueden atender a muchos
negocios. Cada negocio vive en su propio esquema de PostgreSQL: sus ventas, clientes, facturas, cuentas y numeración
no se mezclan con los de ningún otro, y nada de un negocio puede leer o cambiar lo de otro.

1. En los *Secrets* de la app (con una base Neon, apartado anterior):
   ```toml
   database_url = "postgresql://…"
   multi_tenant = true
   operator_password = "una-contraseña-larga-solo-para-ti"
   operator_totp_secret = "…"   # verificación en dos pasos: el propio panel te propone una clave
   ```
2. Abre `https://tu-app.streamlit.app/?operador`, entra con `operator_password` (y el código de 6 cifras de tu app de
   autenticación, en cuanto pongas `operator_totp_secret`) y **da de alta el negocio**: código
   (va en la dirección, p. ej. `cafe-aurora`), nombre y contacto. Se muestra **una sola vez** su código de instalación.
3. Envía al negocio su dirección (`…/?negocio=cafe-aurora`) y el código. Con él crea su administrador; después el
   asistente de primera configuración deja el negocio listo.
4. Desde el panel ves cada negocio (personas, ventas, última venta), puedes **suspender o reactivar** su acceso y
   generar un código nuevo si lo perdió antes de crear su administrador. Todo queda en el registro del operador.

Quien entra sin código ve «Entra en tu negocio»: la lista de negocios no se muestra nunca. Si en la misma pestaña se
abre otro negocio, la sesión anterior se borra entera. Las copias automáticas detectan este modo y guardan **una copia
cifrada por negocio** (más el directorio), cada una restaurable por separado.

Los intentos fallidos de acceso (equipo y operador) se cuentan en la base de datos, por dirección y cifrados, así
que valen para todos los servidores y sobreviven a un reinicio. Todos los negocios y el directorio comparten un único
grupo de conexiones por base de datos (`DB_POOL_SIZE`, 5 por defecto).

Sin `multi_tenant`, la app funciona como siempre: un negocio por app.

## Textos legales (modo multinegocio)

Para vender el servicio hacen falta tres textos, ya redactados en `legal/` como **borrador para que lo revise un
abogado**, ajustados a lo que la app hace de verdad (prueba gratuita, cobro con Stripe, 7 días de gracia, solo
consulta sin borrar datos, exportaciones, plazos de borrado, subencargados y medidas de seguridad):

| Texto | Para qué |
|---|---|
| `aviso-legal.html` | Datos del titular que exige la LSSI (nombre, NIF, domicilio, email). |
| `condiciones.html` | Condiciones del servicio que acepta cada negocio. |
| `encargado.html` | Contrato de encargado del tratamiento (RGPD art. 28): qué datos tratas por cuenta de cada negocio, subencargados, brechas, fin del servicio y medidas de seguridad. |

**Publicarlos:**

1. Copia `legal/datos.example.json` a `legal/datos.json` (no se sube al repositorio) y rellena lo que pone
   `PENDIENTE`: nombre, NIF, domicilio, fecha y el proveedor de email que uses. Revisa la lista de subencargados:
   deja solo los que uses de verdad.
2. `python ops/legal.py --check` dice qué falta; `python ops/legal.py` escribe las páginas en `docs/` y añade los
   enlaces «Aviso legal» y «Condiciones del servicio» al pie de toda la web. Con un hueco sin rellenar no escribe nada.
3. Sube los cambios de `docs/` y define `TERMS_URL = https://nirkana.es` en el servidor (Render). Desde entonces, al
   crear su administrador cada negocio acepta las condiciones y el contrato de encargado, y el panel de operador
   muestra qué versión aceptó y cuándo.

**Cambiar los textos:** edita `legal/`, sube `TERMS_VERSION` en `sales_manager/core/legal.py` y vuelve a
publicar. El administrador de cada negocio tendrá que aceptar la nueva versión al entrar (el resto del equipo sigue
trabajando). Las condiciones prometen avisar con 30 días de antelación de los cambios importantes.

El aviso de privacidad de la web (`docs/privacidad.html`) ya explica también los datos que NirKanA trata de los
negocios clientes (cuenta, cobro, soporte).

## Cobrar el servicio con Stripe (modo multinegocio)

Mientras no haya claves de Stripe, nadie paga y todo funciona como siempre. Con ellas:

| Momento | Qué pasa |
|---|---|
| Alta | Cada negocio nuevo empieza con **30 días de prueba** (`trial_days` para cambiarlo). Los negocios que ya existían empiezan su prueba el día que se activa el cobro. |
| Suscribirse | El administrador del negocio va a **Ajustes → Suscripción → Suscribirme** y paga en la página segura de Stripe (tarjeta, datos fiscales y NIF). NirKanA nunca ve la tarjeta. |
| Gestionar | En la misma página, **Gestionar tarjeta, facturas o baja** abre el portal de cliente de Stripe. |
| Pago fallido | Stripe reintenta el cobro y el negocio ve un aviso. Si la suscripción termina (o acaba la prueba sin suscribirse), quedan **7 días de margen**. |
| Sin pagar | Después solo se puede **consultar el historial y descargar los datos**. Nunca se borra nada; al suscribirse vuelve todo. |
| Operador | En `?operador` ves el estado de pago de cada negocio y puedes dejarlo **sin cargo (cortesía)**, **ampliar la prueba** o **comprobarlo en Stripe**. |

Configuración (primero en **modo de prueba** de Stripe, con la tarjeta 4242 4242 4242 4242):

1. En Stripe, **Catálogo de productos → Añadir producto**: «NirKanA», precio **recurrente mensual**. Copia el ID del
   precio (`price_…`). Decide si el precio lleva el IVA incluido o se suma (*Comportamiento fiscal*) y configura el
   IVA (Stripe Tax o un tipo del 21 %): las facturas que Stripe envía son tus facturas emitidas, revísalas con tu
   gestor (NIF, domicilio, numeración).
2. **Desarrolladores → Claves de API**: crea una **clave restringida** (`rk_…`) con permiso de escritura en
   *Checkout Sessions*, *Customer portal* y *Customers*, y de lectura en *Subscriptions* y *Charges*. Mejor que la
   clave secreta completa.
3. **Configuración → Facturación → Portal de clientes**: actívalo (cambiar tarjeta, ver facturas, cancelar). **No**
   permitas cambiar de plan: la app da acceso a cualquier suscripción activa, sea del precio que sea. Por lo mismo,
   no crees códigos promocionales del 100 % «para siempre» salvo que quieras regalar el servicio (para eso está
   «Sin cargo (cortesía)» en el panel de operador).
4. **Desarrolladores → Webhooks → Añadir destino**: `https://app.nirkana.es/stripe/webhook`, con los eventos
   `checkout.session.completed`, `customer.subscription.created`, `.updated` y `.deleted`, y `charge.refunded`,
   `charge.dispute.created` y `.closed` (reembolsos y contracargos: Stripe no cancela la suscripción por ellos, así
   que quedan en el registro del operador para que decidas). Copia el secreto (`whsec_…`). Los avisos solo llegan con
   el contenedor (`Dockerfile`, Render); en Streamlit Cloud la app consulta a Stripe al volver del pago y cada 6
   horas, sin webhook.
5. Secrets (o variables de entorno en Render, en mayúsculas):
   ```toml
   stripe_secret_key = "rk_test_…"
   stripe_price_id = "price_…"
   app_url = "https://app.nirkana.es"
   ```
   En el contenedor, además, `STRIPE_WEBHOOK_SECRET` con el `whsec_…` del paso 4. Con `STRIPE_SECRET_KEY` también
   allí, cada aviso hace que el servidor pregunte a Stripe el estado real: los avisos que llegan tarde o
   desordenados no devuelven un estado antiguo.

Qué protege la app: el precio y la cantidad los pone el servidor; quien está en su prueba gratuita no paga hasta que
termina (Stripe recibe la fecha); antes de abrir un pago pregunta a Stripe si el negocio ya tiene suscripción (y los
clics repetidos durante 15 minutos reciben la misma página de pago), así que nadie paga dos veces; si aun así hay dos
suscripciones cobrando, el registro del operador lo avisa (`suscripcion_duplicada`) para que canceles y reembolses
una en Stripe. Cuando Stripe deja de cobrar por impago, los días de gracia se cuentan desde que terminó la
suscripción, no desde el final del mes que no se pagó.
**Comprobarlo:** en el panel de operador, **Configuración de Stripe → Comprobar ahora** revisa la clave (modo y si es
restringida), el precio (que exista, sea mensual, en euros y diga si lleva IVA), los permisos de la clave (también la
escritura en *Customers*, sin la que «Suscribirme» falla), el webhook y sus eventos, el portal de clientes, los
códigos promocionales que regalan el servicio y que el servidor tenga `STRIPE_WEBHOOK_SECRET` y `STRIPE_SECRET_KEY`
como variables de entorno. Solo lee: no crea nada en Stripe. Si algo sale en rojo o amarillo, dice qué cambiar.

Cuando todo funcione en modo de prueba, repite los pasos 1-4 en **modo real** y cambia las claves.

## Copias de seguridad automáticas

Cada noche (02:17 UTC), GitHub Actions hace una copia **cifrada** de cada negocio, la **restaura en una base de
pruebas y comprueba** que tiene las mismas ventas, facturas y cierres que producción, la guarda 30 días y la anota en
el **panel de operador** («Última copia verificada hace X h»). Solo lee producción: nunca la modifica.

**Nunca están apagadas sin que lo sepas:**

- Sin configurar, la ejecución sale en **rojo** y GitHub te avisa por email cada noche. Solo la variable de Actions
  `BACKUPS_DISABLED = true` las apaga, y eso tiene que ser una decisión consciente (una demo sin datos reales).
- El panel de operador muestra la última copia verificada en verde, o un aviso en rojo si no hay ninguna o si la
  última tiene más de 26 horas.
- Si una noche falla, además del email de GitHub llega otro a `OPERATOR_EMAIL` (con los `SMTP_*` configurados).

### Activarlas (10 minutos, una vez)

1. **Usuario de solo lectura** (recomendado): ejecuta `ops/deploy/roles.sql` como dice su cabecera. Crea
   `nirkana_backup`, que lee todos los negocios (también los que se den de alta después), no puede cambiar nada y
   solo puede anotar en el panel que una copia se ha verificado.
2. **Frase de cifrado:** genera una en tu ordenador y **guárdala en tu gestor de contraseñas** (sin ella las copias no
   se pueden abrir, ni por ti):

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. **Secretos** en GitHub → repositorio → **Settings → Secrets and variables → Actions → New repository secret**:

   | Secreto | Qué poner |
   |---|---|
   | `BACKUP_DATABASES` | Una línea por base: `nombre=postgresql://…`. Con el modo multinegocio basta una línea: cada negocio se copia por separado. Ej.: `nube=postgresql://nirkana_backup:clave@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require` |
   | `BACKUP_PASSPHRASE` | La frase del paso 2 (32 caracteres o más). |
   | `OPERATOR_EMAIL` y `SMTP_*` (opcional) | Para recibir también por email el aviso de una noche fallida. |
   | `BACKUP_S3_*` (muy recomendable) | Una segunda copia fuera de GitHub, que además dura más de 30 días (Cloudflare R2, Backblaze B2 o S3): `BACKUP_S3_BUCKET`, `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY`, `BACKUP_S3_ENDPOINT` y `BACKUP_S3_REGION`. Pon al *bucket* una regla de borrado a los 90 días o más. |
4. **Probar:** Actions → **Copias de seguridad** → **Run workflow**. Debe salir en verde y el panel de operador debe
   decir «Última copia verificada hace menos de una hora». Si algo falta, el primer paso («Comprobar la
   configuración») dice qué. También puedes comprobarlo desde tu ordenador sin hacer copias:

   ```bash
   export BACKUP_DATABASES="nube=postgresql://…" BACKUP_PASSPHRASE="tu frase"
   python ops/backup.py --check
   ```

**Segunda red, sin hacer nada:** Neon guarda el historial de la base y permite volver a cualquier momento reciente
(*Restore* / *Branches → New branch* desde una fecha y hora). Comprueba en tu plan cuántas horas o días cubre: sirve
para un error de hace un rato; las copias nocturnas, para todo lo demás.

### Recuperar datos

Descarga el artefacto de la noche que quieras (Actions → la ejecución → *Artifacts*). Cada negocio tiene dos archivos
cifrados: `…dump.enc` (completo: cuentas, registro de actividad, todo) y `…db.enc` (la copia de la app, sin cuentas).

- **Un negocio que ha perdido o estropeado datos:** `python ops/backup.py --decrypt …db.enc` y, en la app, carga el
  archivo en *Configuración → Restaurar* (en un negocio sin ventas).
- **Desastre (la base entera):** crea una base **vacía** (en Neon, una rama o base nueva) y:

  ```bash
  export BACKUP_PASSPHRASE="tu frase" RESTORE_TARGET_URL="postgresql://…/base_vacia"
  python ops/backup.py --restore nube-cafe-aurora-20261004-0217.dump.enc   # uno por negocio, y nube-operador-…
  ```

  El script se niega a restaurar sobre una base con datos (podrían ser más nuevos que la copia). La contraseña va
  en una variable, no en la línea de comandos. Comprueba la base restaurada y, si está bien, apunta `DATABASE_URL`
  a ella en Render.

Mientras el repositorio sea público, cualquiera con cuenta de GitHub puede descargar los artefactos: están cifrados
(AES-256, clave derivada con 600.000 iteraciones), pero es mejor hacer el repositorio privado. Si lo haces privado,
ten en cuenta que el plan gratuito de GitHub tiene 500 MB para artefactos: con la copia en R2 o B2 puedes bajar la
retención de los artefactos.

## Avisos por email

Gratis con una cuenta de Gmail (por ejemplo nirkana.oficial@gmail.com):

1. En esa cuenta de Google activa la verificación en dos pasos y crea una **contraseña de aplicación**
   (Cuenta de Google → Seguridad → Contraseñas de aplicaciones).
2. **Para la app** (recuperar la contraseña del administrador por email y confirmar las reservas online), en los
   *Secrets* de Streamlit:
   ```toml
   smtp_host = "smtp.gmail.com"
   smtp_port = 587
   smtp_user = "nirkana.oficial@gmail.com"
   smtp_password = "la contraseña de aplicación"
   ```
3. **Para los envíos programados**, los mismos datos como secretos de GitHub Actions: `SMTP_HOST`, `SMTP_PORT`,
   `SMTP_USER`, `SMTP_PASSWORD` (y opcional `SMTP_FROM`). Usa las bases de `BACKUP_DATABASES`, o
   `NOTIFY_DATABASES` si quieres otra lista. Cada mañana, el flujo **Avisos por email** envía:
   - el **informe semanal en PDF** cada lunes, a los negocios que lo activen;
   - un aviso cuando aparecen **alertas importantes nuevas** (caída de ventas, productos agotados, pérdidas…);
   - el **recordatorio de cita** a los clientes que reservaron para el día siguiente y dejaron su email.
4. Cada negocio decide en **Configuración → Avisos por email** si los quiere, y los recibe en el email del negocio.
   Nunca se envía nada en modo demostración ni dos veces lo mismo, aunque el flujo se ejecute de nuevo.

Con el correo configurado, la pantalla de acceso ofrece al administrador recibir un **código de 8 cifras** en el
email del negocio para cambiar su contraseña: caduca en 15 minutos, sirve una vez, admite 5 intentos y como mucho se
piden 3 por hora. La respuesta es la misma exista o no el usuario.

## Salir a producción en 4 pasos

1. **Secretos:** `python ops/preparar_produccion.py` genera en tu ordenador todo lo que hay que inventar
   (`DATA_KEY`, `BACKUP_PASSPHRASE`, contraseña y verificación en dos pasos del operador, con su QR) y escribe
   `.env.produccion` (git lo ignora) con cada valor agrupado por dónde va: Render, GitHub Secrets o GitHub Variables, y
   huecos para lo que solo dan los proveedores (Neon, Stripe, SMTP, la copia externa). Nunca sobrescribe ese archivo:
   `DATA_KEY` y `BACKUP_PASSPHRASE` no deben cambiar una vez en uso.
2. **Despliegue:** Render → New → Blueprint con este repositorio (`render.yaml`) y pega los valores.
3. **Comprobación:** `python ops/comprobar_produccion.py https://tu-app --web https://nirkana.es` revisa desde fuera
   HTTPS, `/_nk/salud`, las cabeceras de seguridad, la CSP, la cookie de sesión, el webhook de Stripe y los textos
   legales, y dice qué falla. No cambia ningún dato.
4. **Repositorio:** protege `main` importando `ops/github/ruleset-main.json` (`ops/REPOSITORIO.md`, paso 1).

## Errores y caídas

**Errores:** si una pantalla falla, la persona ve un aviso con una **referencia** (p. ej. `A3F09C`) en vez de un
error técnico, y queda registrado el tipo de error, la pantalla, el usuario y la línea del código donde ocurrió. Nunca
se guarda el mensaje del error, porque puede contener datos de clientes o de ventas. El administrador los ve en
**Equipo y seguridad → Errores de la app**, y el operador, en su panel (errores de 7 días por negocio).

**Aviso en el momento:** con `OPERATOR_EMAIL` y los `SMTP_*` en el servidor, cada error llega por email al operador al
instante: negocio, referencia, tipo y línea del código (nunca datos). El mismo error no se repite más de una vez por
hora, y nunca salen más de 20 avisos por hora.

**Registro del servidor:** con `LOG_FORMAT=json`, cada línea es un objeto JSON con sus campos (`ref`, `page`,
`tenant`…), listo para enviarlo a un servicio de logs (Better Stack, Grafana Cloud…) desde Render → *Log Streams*, y
buscar o crear alertas allí.

**Caídas:** usa un **monitor externo** gratuito (UptimeRobot o Better Stack) que compruebe cada 5 minutos
`https://tu-app/_nk/salud`: responde `ok` solo si la app **y su base de datos** funcionan, y `no` (503) si no. Es mejor
que `/_stcore/health`, que dice «ok» aunque la base de datos esté caída y nadie pueda vender. Como reserva, el flujo
**Disponibilidad** de GitHub Actions hace lo mismo cada 10 minutos (usa `/_nk/salud` si existe):

| Secreto | Qué poner |
|---|---|
| `UPTIME_URLS` | Una dirección por línea, p. ej. `https://app.nirkana.es` |
| `OPERATOR_EMAIL` | Opcional: tu email, para recibir también el aviso de caída y, cada mañana, el resumen de errores de las últimas 24 h (necesita los `SMTP_*`). |

Los cron de GitHub se retrasan a veces y se desactivan tras 60 días sin cambios en el repositorio: por eso el monitor
externo es el principal. En un repositorio privado, desactiva este flujo (gasta minutos; ver `ops/REPOSITORIO.md`).

**La web (nirkana.es):** el flujo **Web** (`ops/web_check.py`) la comprueba desde fuera cada día y tras cada cambio en
`docs/`: que el dominio y `www` apunten a GitHub Pages, que el certificado HTTPS sea válido y le queden al menos 14
días (GitHub lo renueva solo, pero no si el DNS cambia), que `http://` y `www.` lleven a `https://nirkana.es/` y que
cada página responda. Si algo falla, el flujo sale en rojo y GitHub te avisa por email.

## Escalar

Un servidor de Render *Starter* atiende con holgura decenas de negocios a la vez (cada clic cuesta entre 25 y 180 ms
de servidor con 200.000 ventas). Cuando no baste (clics lentos en horas punta, CPU alta en el panel de Render):

1. **Más CPU:** un plan mayor del mismo servicio. Es lo más sencillo.
2. **Más instancias:** `numInstances` en `render.yaml` (o en el panel). Todo lo que una persona necesita vive en la
   base de datos (sesión, ticket en curso, límites de intentos, avisos de Stripe, códigos del operador), así que si
   al reconectar entra en otro servidor sigue donde estaba. Cada servidor solo guarda cachés de 2 a 90 segundos.
3. **Conexiones:** cada servidor abre hasta `DB_POOL_SIZE` (5) conexiones. Con varias instancias usa la cadena
   *pooled* de Neon (el host con `-pooler`).
4. **Muchos negocios:** cada servidor mantiene abiertos hasta `TENANT_CACHE_SIZE` (1.000) negocios y cierra los que
   llevan más tiempo sin usarse. Al desplegar solo se migran los negocios que no están al día (una consulta para
   saber cuáles, y 4 a la vez).

**Aislamiento entre negocios:** cada negocio tiene su esquema y además su propio rol de base de datos (`nk_<huella de la base de datos>_n_…`), que
solo puede leer y escribir ese esquema: aunque una consulta nombrara otro negocio, PostgreSQL la rechazaría. La app
crea los roles sola si el usuario de la base de datos puede crear roles (`CREATEROLE`, el propietario de Neon
puede); si no, cada negocio sigue aislado por su esquema y el panel de operador lo avisa.

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
| Base de datos | Consultas siempre parametrizadas. Conexión a PostgreSQL remoto con TLS obligatorio (`sslmode=require`). Límites de longitud en todos los textos. En PostgreSQL los importes se guardan como decimales exactos (`NUMERIC`), y los cambios de estructura se aplican una sola vez, numerados y registrados en `schema_migrations`. |
| Servidor | Subidas limitadas a 20 MB, protección XSRF activa y errores sin detalles internos para el usuario. En el contenedor (`Dockerfile`), Caddy añade HSTS, protección contra incrustar la app en otras webs (*clickjacking*), `nosniff`, `Referrer-Policy` y `Permissions-Policy`. |

**Lo que no depende de la app:** la seguridad de la cuenta de Streamlit y de GitHub (activa la verificación en dos pasos en ambas), la de Neon y la custodia de los *Secrets*. En la versión gratuita de Streamlit sin base de datos externa, un reinicio borra datos **y cuentas**: para un equipo real usa Neon.

### Repositorio y despliegue (ajustes que solo puede hacer el dueño)

La guía completa, en orden, está en [`ops/REPOSITORIO.md`](../ops/REPOSITORIO.md): proteger `main`, separar la web
en su propio repositorio sin que nirkana.es se caiga (`ops/separar_web.sh`), hacer privado este (y qué cambia en los
minutos de Actions) y, si quieres, limpiar el historial (`ops/limpiar_historial.sh`). Resumen:

1. **Proteger `main`** (Settings → Rules → Rulesets → New branch ruleset, objetivo `main`): exigir pull request,
   exigir que pase la comprobación **Tests**, y bloquear *force push* y borrado. Así nada llega a producción sin
   pasar los tests.
2. **Secretos** (Settings → Code security): activar *Secret scanning* y *Push protection* (GitHub rechaza un push que
   contenga una clave) y *Dependabot alerts*. El CI ya revisa todo el historial con gitleaks y las dependencias con
   pip-audit.
3. **Producción declarada:** variable de Actions `PRODUCTION = true` (Settings → Secrets and variables → Actions →
   Variables). Desde entonces, si falta el secreto de vigilancia (`UPTIME_URLS`), esa ejecución sale en **rojo**. Las
   copias de seguridad salen en rojo sin configurar siempre, sin necesidad de esta variable.
4. **Volver atrás un despliegue:** en Render, *Events* → el despliegue anterior → *Rollback*. Los cambios de base de
   datos solo añaden (tablas, columnas, índices), así que la versión anterior sigue funcionando con la base ya
   migrada. Si un cambio rompiera datos, se restaura la copia cifrada de la noche (`python ops/backup.py --restore`, ver
   «Copias de seguridad automáticas → Recuperar datos»).
5. **Autoría de los commits:** en GitHub → Settings → Emails, «Keep my email addresses private» y «Block command line
   pushes that expose my email», para que los commits nuevos usen la dirección `noreply` de GitHub.

## Estructura

```
sales_manager/
├── app.py              # Navegación y arranque
├── core/               # Lógica sin dependencias de interfaz
│   ├── db.py              # `Store`: arranque, ajustes y ventas atómicas; reúne los demás módulos store_*
│   ├── schema.py          # Tablas, columnas añadidas y migraciones versionadas
│   ├── engines.py         # Motores SQLite y PostgreSQL (pool, TLS, caché de lecturas)
│   ├── errors.py          # Errores que ve el usuario (venta, acceso, datos fiscales)
│   ├── store_users.py     # Cuentas, inicio de sesión, bloqueo, 2FA y recuperación
│   ├── store_demo.py      # Plantillas y datos de ejemplo
│   ├── store_catalog.py   # Productos, clientes y promociones
│   ├── store_invoices.py  # Facturas completas
│   ├── store_appointments.py # Citas y su cobro
│   ├── store_cash.py      # Resumen del día y cierre de caja
│   ├── store_backup.py    # Copias de seguridad y restauración
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
├── ui/                 # Páginas y estilo visual (sin SQL)
│   ├── pages.py           # Reúne las páginas que registra app.py
│   ├── pages_*.py         # Una por zona: vender, historial, caja, agenda, equipo, productos, clientes, ajustes…
│   └── context.py         # Negocio activo, usuario y base de datos de la sesión
└── tests/              # Pruebas de la lógica y de todas las páginas
```

## Pruebas

```bash
cd sales_manager && python -m pytest -q
# Para probar también contra PostgreSQL:
TEST_DATABASE_URL=postgresql://usuario:clave@localhost:5432/pruebas python -m pytest -q
```

La CI además pasa `ruff check` y exige al menos un 80 % de cobertura (`--cov=core --cov=ui`). Herramientas de
desarrollo: `pip install -r requirements-dev.txt`.

**Configuración:** todos los ajustes que lee la app y los scripts están en `core/config.py`, con su descripción y valor
por defecto; `.env.example` (en la raíz) se genera de ahí con `python -m core.config` y un test comprueba que está al
día. **Dependencias:** `requirements.txt` dice qué necesita la app; `requirements.lock` fija esas y todas las demás
con versión y hash, y es lo que instalan el contenedor y la CI (cómo regenerarlo, en su cabecera). Python 3.12
(`.python-version`); imágenes del contenedor fijadas por digest; Dependabot propone las actualizaciones cada semana.
Al arrancar, el contenedor pone al día las tablas de todos los negocios (`ops/deploy/migrate.py`) antes de atender a
nadie. El registro del servidor (`core/logs.py`, nivel con `LOG_LEVEL`) no guarda datos de clientes.

## Capturas de pantalla

Las capturas del README, de la web y de los anuncios se rehacen solas, con negocios y personas ficticios (Café Aurora,
Ana García · Consultoría; Marta y Lucía), sobre una base de datos de PostgreSQL que se pueda vaciar:

```bash
python ops/capturas.py postgresql://usuario:clave@localhost:5432/capturas
python marketing/anuncios/generar.py && python marketing/anuncios/video.py && python marketing/anuncios/tresd.py
```

## Licencia

Software propietario. © 2025-2026 NirKanA. Todos los derechos reservados.
Prohibido copiar, modificar, distribuir, vender o alojar para terceros sin permiso por escrito del titular.
Consulta el archivo [`LICENSE`](../LICENSE) para las condiciones completas.

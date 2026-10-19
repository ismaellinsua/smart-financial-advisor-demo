# Web de NirKanA

Página de presentación para ofrecer NirKanA a los clientes: soluciones por tipo de negocio, funciones, preguntas
frecuentes y contacto. Está en esta carpeta `docs/`:

| Archivo | Qué es |
|---|---|
| `index.html` | La página principal |
| `demo/index.html` | La demo: NirKanA entera con un negocio de ejemplo, en un solo archivo (ver «La demo») |
| `privacidad.html` | Aviso de privacidad (RGPD) |
| `tpv-restaurantes/`, `programa-peluquerias-estetica/`, `tpv-tiendas/`, `programa-facturacion-autonomos/`, `tpv-tienda-online/` | Una página por sector, para buscadores (están en `sitemap.xml`; `tests/web-claims.test.mjs` revisa que digan solo lo que la app hace) |
| `404.html` | Lo que ve quien abre una dirección que no existe |
| `assets/site.css` | Diseño (claro y oscuro, efectos 3D) |
| `assets/site.js` | Contacto, formulario y efectos 3D |
| `assets/img/` | Capturas de la app optimizadas (`shots/`: `*-c.webp` recortadas para tarjetas, `*.webp` completas para ampliar). Se regeneran con `python ops/capturas_web.py` desde `demo/index.html`, así que siempre enseñan el aspecto actual de la app |

## Cambiar tus datos de contacto

Todo está al principio de `assets/site.js`:

```js
const CONTACT = {
  email: "nirkana.oficial@gmail.com",  // botón «Escribir por email» y respaldo del formulario
  whatsapp: "",      // tu número con prefijo y solo cifras, p. ej. "34600111222"
  formspreeId: "mbgdrbyg",   // el código de tu formulario de Formspree (ya puesto)
};
```

El formulario **ya está conectado** a tu formulario de Formspree (`mbgdrbyg`): cada solicitud sale del navegador del visitante
directamente a Formspree (sin cookies, solo los campos del formulario) y Formspree te la reenvía **al correo con el que creaste
la cuenta**. Probado en navegador con un Formspree simulado: envía los campos esperados (el `email` del visitante queda como
dirección de respuesta), enseña «¡Gracias!…» si sale bien y, si falla, un mensaje con tu email de respaldo.

### Comprobar que te llegan los mensajes (2 minutos, cuando la web esté publicada)

Desde aquí no se puede ver tu cuenta de Formspree, así que esta comprobación la haces tú **una vez**:

1. Abre `https://nirkana.es`, rellena el formulario con un email tuyo distinto y envíalo.
2. **La primera vez** Formspree te manda un correo para **confirmar el formulario**: ábrelo (mira también en *spam*) y pulsa el
   enlace. Hasta entonces no reenvía nada.
3. Vuelve a enviar otro mensaje de prueba: debe llegar a tu bandeja con el nombre, el negocio y el mensaje.
4. En formspree.io → tu formulario → **Settings** comprueba que el correo de destino es `nirkana.oficial@gmail.com` (puedes
   añadir más destinatarios) y, si quieres, limita el formulario a tu dominio (*Restrict to domain*: `nirkana.es`).
5. El plan gratuito tiene un tope mensual de envíos: míralo en tu cuenta. Si se agota, los visitantes ven el mensaje de error
   con tu email de respaldo, así que no pierdes el contacto.

Si dejas `formspreeId` vacío, el formulario prepara el mensaje en WhatsApp (si hay número) o en el correo del visitante.
Para usar **otro** formulario: crea uno en [formspree.io](https://formspree.io) (**New form**), copia el código de
`https://formspree.io/f/XXXXXXX` y pega solo `XXXXXXX` en `formspreeId`.

### Enlace «Entrar» para tus clientes

Cuando la app esté publicada (p. ej. en `https://app.nirkana.es`), pon su dirección en `assets/site.js`:
`const APP_URL = "https://app.nirkana.es";`. Aparece «Entrar» en el menú; vacío, no se muestra.

### Botón «Probar NirKanA» (prueba gratuita de 24 horas)

Mientras `TRIAL_URL` esté vacío, la web enseña «Quiero NirKanA» (lleva al formulario de contacto) y nunca enlaza a
una prueba que aún no funciona. Cuando la prueba esté publicada (p. ej. en `https://prueba.nirkana.es`), pon en
`assets/site.js`:

```js
const TRIAL_URL = "https://prueba.nirkana.es";
```

y aparecen solos «Probar gratis» en la cabecera, «Probar NirKanA gratis» en la portada y en cada página de sector,
el primer paso «Pruébala gratis», la pregunta «¿Puedo probarla antes de decidir?» y el enlace del bloque de contacto.
«Quiero NirKanA» y «Contactar» siguen llevando al formulario y al email. Si GoatCounter está activo, cuenta cuántas
personas abren la prueba.

**Estado (14/10/2026):** activado con `https://nirkana-prueba.onrender.com`, comprobada desde fuera ese día. Cuando
`prueba.nirkana.es` tenga su candado en Render, cambia aquí la dirección (la prueba `web-boundaries` solo admite esas dos).
Si algún día lo vacías, quita también `has-trial` de la etiqueta `<html>` de cada página.

**Vigilancia de la prueba.** Con la prueba activa, `web-boundaries` exige (antes de publicar) que la cabecera y los botones de
la portada ofrezcan «Probar gratis», y el flujo **Web** (`ops/web_check.py`) comprueba lo mismo en la página ya publicada y que
la prueba responde en modo prueba (le da hasta 3 minutos para despertar). Si el botón desaparece o la prueba cae, el flujo
sale en rojo y GitHub avisa por email. El rediseño del 17/10 dejó el botón solo más abajo y nadie lo vio hasta el 18/10.

**La espera del primer clic.** El plan gratuito de Render duerme el servicio tras 15 minutos sin visitas y tarda en despertar
entre medio minuto y varios minutos (el 14/10: 38 s con el navegador de la propietaria; 3 min 19 s con peticiones de imagen desde
GitHub, que contestan «502» mientras tanto). Para que el visitante no se quede ante la pantalla de espera de Render, `site.js`
(`openTrial`) pide primero una imagen pequeña de la app (`/icons/simbolo.svg`) y, si falla, una página oculta del servicio (un
`<iframe sandbox>` invisible: es lo que hace abrir la prueba), enseña su pantalla «Preparando tu prueba gratuita» y abre la prueba
sola cuando la imagen carga. **A los 50 segundos lleva al visitante a la prueba pase lo que pase** (la pantalla de Render sigue
desde ahí): nunca hay callejón sin salida. Por eso la CSP de cada página admite imágenes y un marco del servicio de la prueba
(`img-src` y `frame-src`), y `web-boundaries` exige que coincidan con `TRIAL_URL`: si cambias la dirección, cambia las dos cosas.
El arreglo de fondo es el plan de pago de Render (siempre encendido): con él esa pantalla casi no se ve.

### La demo («Probar la demo»)

`demo/index.html` es **NirKanA entera en un solo archivo** (la app con un negocio de ejemplo: bar, tienda, peluquería o
tienda online). La web enseña «Probar la demo» en la cabecera, la portada, el bloque de contacto, las preguntas y cada
página de sector, que abre directamente ese tipo de negocio (`/demo/?negocio=hosteleria`, `tienda`, `servicios` u
`online`). No hace falta registrarse ni hay servidor detrás: los datos son inventados y se quedan en el navegador.

- El archivo viene de `nirkana-app` (`demo/`, ver su `LEEME.md`). Para actualizarlo tras cambiar la app:
  `python demo/exportar.py && node demo/construir.mjs` y copiar `demo/dist/NirKanA-demo.html` a `docs/demo/index.html`
  (la CI de `nirkana-app` también lo guarda como descarga).
- La dirección está en `DEMO_URL` (`assets/site.js`); si la dejas vacía, los enlaces a la demo desaparecen.
- No sale en Google (`noindex`) ni en `sitemap.xml`.

### Precio y dirección de email visibles

La home tiene una sección propia, **Precio** (`#precio`, enlazada desde el menú y el pie), con «Desde 60 € al mes + IVA» (el 14/10 la
propietaria decidió subirlo desde 20 y luego eligió 60: «mínimo desde 40 o 60»; el 15/10, «con IVA aparte») y las mismas condiciones que ya decía la pregunta «¿Cuánto cuesta?»;
el aviso bajo el botón de la cabecera también lo menciona. **El precio sale en 8 cifras de `index.html`**: seis frases (cabecera,
sección de precio, calculadora, pregunta frecuente y su copia en los datos `FAQPage`, y la descripción de `Offer`) y los dos
precios de los datos estructurados `Offer`. Si cambias el precio, cámbialas todas: en el repositorio `nirkana-web` lo hace
`python ops/precio.py 60`. `web-boundaries` comprueba que todas dicen lo mismo. **El precio de cobro con tarjeta es el de Stripe**
(Product → Price): hay que cambiarlo allí también, o la web y el pago no coincidirán.

La dirección de email sale escrita en la página (no solo detrás de un botón) y con «Copiar dirección», porque quien lee el correo en
una web no puede usar un enlace `mailto:`. Se rellena desde `CONTACT.email` de `site.js`: no está escrita en el HTML.

### Contar visitas sin cookies (GoatCounter)

La web puede contar visitas, páginas vistas y formularios enviados **sin cookies ni datos personales**, así que no
necesita banner de cookies. **Activo desde el 15/10/2026** con la cuenta `nirkana` (panel en
`https://nirkana.goatcounter.com`): `const ANALYTICS = { goatcounter: "nirkana" };` en `assets/site.js`. La web no carga
el `<script>` de GoatCounter (la CSP no lo permite y no hace falta): cuenta con su propia imagen de 1 píxel, sin cookies.

Si algún día hay que repetirlo con otra cuenta:

1. Crea una cuenta gratuita en [goatcounter.com](https://www.goatcounter.com) y elige un código.
2. En el panel: **Settings → Data collection**, deja desmarcado guardar la IP y marca «Ignore IPs» con la tuya si no
   quieres contarte.
3. En `assets/site.js`, pon `const ANALYTICS = { goatcounter: "tu-código" };` y publica (y cambia el código que fija la
   prueba de `tests/web-boundaries.test.mjs`).

Solo cuenta en `nirkana.es` (no en copias locales) y no cuenta a quien tenga activado «no rastrear» en su navegador.
El aviso de privacidad ya lo explica.

**Qué cuenta** (en el panel salen como «eventos»; no guardan nada del visitante):

| Evento | Significa |
|---|---|
| `/` y demás rutas | Visitas y páginas vistas |
| `precio-visto` | Llegó a la sección de precio (una vez por visita) |
| `prueba-abierta` | Pulsó «Probar gratis» |
| `prueba-espera` | La prueba estaba dormida y vio la pantalla «Preparando tu prueba» |
| `prueba-lista` | La prueba abrió sola cuando estuvo lista |
| `prueba-lenta` | Pasaron 50 s y se le llevó a la prueba sin que estuviera lista |
| `prueba-cancelada` | Cerró la pantalla de espera |
| `demo-abierta` | Pulsó «Ver la demo» |
| `contacto-email`, `contacto-copiar` | Pulsó el botón o la dirección de email, o la copió |
| `contacto-enviado` | Envió el formulario |

Cómo leerlo: de las visitas, cuántas llegan a `precio-visto`; de `prueba-abierta`, cuántas ven `prueba-espera` (así sabes si el plan
gratis de Render se nota) y cuántas acaban en `prueba-lenta`; y al final cuántas escriben (`contacto-enviado` + `contacto-email`
+ `contacto-copiar`). Compara las páginas de sector entre sí: la que más escribe es la que mejor vende.

**Activarlo es un cambio de una línea**, pero el código **tiene que ser el de una cuenta que ya hayas creado**: si apuntara a un
código sin registrar, esas cifras caerían en la cuenta de quien lo registre después. Por eso no se pone hasta que la cuenta exista.

## Las capturas y los textos: solo lo que la app hace

Las imágenes de `assets/img/` son capturas de la **app real** (la demo es su front-end con datos inventados), no
dibujos. Se regeneran con un script, así que no pueden enseñar una pantalla que el producto no tenga:

```bash
python ops/capturas_web.py    # necesita Playwright con Chromium y Pillow; usa docs/demo/index.html
```

Tras actualizar `docs/demo/index.html` con una versión nueva de la app, ejecútalo y revisa las imágenes antes de
publicar. Cada vez que cambies un texto de la web, `node --test tests/web-claims.test.mjs` comprueba que no vuelve a
prometer lo que NirKanA no hace (informes semanales en PDF, precios recomendados, verificación en dos pasos, conexión
automática con Shopify…), que no hay cifras de clientes ni certificaciones, que VERI*FACTU no se presenta como
cumplido, que todas las imágenes y enlaces existen y que los datos estructurados (JSON-LD) son válidos y coinciden
con las preguntas visibles. La CI lo ejecuta en cada cambio de `docs/`.

`docs/caja/` es la «caja sin conexión» de la versión anterior (Streamlit); no está enlazada desde la web y lleva
`noindex`. Se conserva porque `sales_manager/` aún la genera.

## Diseño: lo que conviene saber antes de tocarlo

- **La cabecera se vuelve de cristal oscuro mientras pasa sobre una sección oscura** (la portada, la historia de funciones y la
  banda del móvil). Lo decide `assets/site.js` (clase `on-dark` en la cabecera) mirando las secciones `.hero`, `.dark` y
  `.mobile-band`: si añades otra sección de fondo oscuro, dale una de esas clases o la cabecera se verá clara sobre ella.
- **En el móvil (hasta 560 px) la galería de la portada es un carrusel** que se desliza con el dedo (`.bento`, con el aviso
  «Desliza para ver más»); en pantallas grandes sigue siendo una cuadrícula. Así la portada del móvil mide unos 3.000 px menos.
- **Cada página de sector abre con una captura de la app** (`.sub-hero-shot`, imágenes `shots/*-c.webp`): el texto a la
  izquierda y la pantalla de ese tipo de negocio a la derecha; en el móvil, una debajo de la otra.
- **La tarjeta de precio** lleva una franja de color arriba y el botón dentro de un panel propio, para que se vea como
  «lo que cuesta» y no como una tarjeta más. El texto «Desde N € al mes + IVA» no se toca a mano: `ops/precio.py` lo mantiene.
- `ops/capturas_web.py` oculta el aviso de cookies de la demo (`#nk-cookie-notice`) para que no salga tapando las capturas.

## Publicarla gratis con GitHub Pages

1. En GitHub, abre el repositorio → **Settings → Pages**.
2. En **Source** elige **Deploy from a branch**; rama **main** y carpeta **/docs**. Pulsa **Save**.
3. Cuando los registros DNS del paso 4 ya estén creados, en **Custom domain** escribe `nirkana.es` y pulsa **Save**
   (GitHub añade solo el archivo `CNAME`; hacerlo antes dejaría la web sin abrir hasta que el DNS apunte bien).
4. En tu proveedor del dominio crea estos registros DNS:
   - `@` tipo **A**: `185.199.108.153`, `185.199.109.153`, `185.199.110.153` y `185.199.111.153`.
   - `@` tipo **AAAA**: `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153` y `2606:50c0:8003::153`.
   - `www` tipo **CNAME**: `ismaellinsua.github.io`.
5. Cuando GitHub muestre el dominio como comprobado (de minutos a 24 h), marca **Enforce HTTPS**.
   La web quedará en `https://nirkana.es/`.

También puedes subir la carpeta `docs/` tal cual a Netlify, Cloudflare Pages o cualquier alojamiento estático.

## Aviso legal (cuando tengas tus datos)

La web todavía **no tiene aviso legal**: la ley (LSSI-CE, art. 10) pide que quien tiene una web con actividad económica
publique su nombre, NIF, domicilio y email. Todo está listo para generarlo el día que tengas esos datos, y mientras
tanto no se publica nada con huecos:

1. `cp legal/datos.example.json legal/datos.json` (ese archivo no se sube a Git) y rellena `titular`, `nif`, `domicilio`
   y `fecha` (la de publicación). El resto ya está: `email`, `web` y `url_condiciones` (las condiciones que aceptan los
   clientes son las de la app, `https://app.nirkana.es/legal/condiciones.html`).
2. `python ops/legal.py --check` dice qué falta; mientras falte algo o quede un «PENDIENTE», no escribe nada.
3. `python ops/legal.py` crea `docs/aviso-legal.html`, añade «Aviso legal» al pie de todas las páginas y completa el
   párrafo «Responsable» de `privacidad.html` con el mismo titular, NIF y domicilio (y su fecha de actualización).
4. Pruebas (`node --test tests/web-boundaries.test.mjs tests/web-claims.test.mjs`), subir los cambios y pedir a tu
   gestoría que lea el texto: es un modelo estándar, no asesoramiento jurídico.

Por defecto solo se publica el aviso legal. `legal/condiciones.html` y `legal/encargado.html` son de la app anterior
(un único medio de pago, prueba «de la duración que te indiquemos», copias diarias prometidas): no los publiques con
`--todas` mientras la app de venta tenga los suyos (`nirkana-app/app/static/legal/`), para que nadie vea dos textos
distintos.

## Seguridad

- Sin cookies, analítica, publicidad ni código de terceros: nada que rastree a tus visitantes.
- Política de seguridad de contenidos (CSP): solo se ejecuta el código propio de la web y el formulario solo puede
  enviar a Formspree (la página también puede leer sus propios archivos, p. ej. `robots.txt`, que las herramientas de
  medición piden desde la propia página).
- Formulario con límites de longitud, validación, casilla de consentimiento y un campo trampa contra robots.
- El único dato de contacto publicado es el email de contacto; los mensajes llegan por Formspree, WhatsApp o email.
- Los enlaces externos se abren sin pasar datos de la página (`noopener`, `noreferrer`).

## Rendimiento

Medido con Lighthouse 12.8 (móvil, red y CPU simuladas) contra una copia local, 13 de octubre de 2026: las cinco páginas
sacan 100 en accesibilidad, buenas prácticas y SEO; rendimiento 99–100, sin desplazamientos de diseño (CLS 0) y con
menos de 10 ms de bloqueo en la portada. Son medidas de laboratorio: en tu conexión y tu móvil el resultado variará.

Tres cosas lo mantienen así y conviene no deshacerlas:

- **Las clases `js` y `has-demo` van en la etiqueta `<html>` de cada página.** Si las añadiera solo el script, los botones
  y el menú cambiarían después de pintar y la página «saltaría». Si algún día activas la prueba de 24 horas (`TRIAL_URL`
  en `site.js`), añade también `has-trial`; `tests/web-boundaries.test.mjs` avisa si no coinciden. Para quien navega sin
  JavaScript, `<noscript>` carga `assets/sin-js.css`, que devuelve el menú de secciones al encabezado.
- **La esfera de partículas dibuja por grupos, a 30 imágenes por segundo y con un lienzo acotado**: antes pintaba 1.300
  trazos por imagen y bloqueaba el móvil más de un segundo en total.
- **El título de las capturas ampliables (`data-title`) sale del CSS**, para que el texto visible del botón sea solo
  «Ampliar» y su nombre accesible («Ampliar captura: …») lo contenga.

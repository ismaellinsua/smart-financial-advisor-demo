# Anuncios de NirKanA

Todo listo para publicar cuando tengas la web y el contacto activos. Las imágenes están en `img/`.

| Formato | Tamaño | Dónde se usa |
|---|---|---|
| `*-feed.png` | 1080 × 1350 | Publicación de Instagram y Facebook |
| `*-historia.png` | 1080 × 1920 | Historias de Instagram/Facebook, estados de WhatsApp, TikTok |
| `*-horizontal.png` | 1200 × 628 | Facebook, LinkedIn, Google y anuncios con enlace |

Campañas por tipo de negocio: `general`, `restaurante`, `tienda`, `autonomo` y `online`.
Campañas por función: `cobro`, `cocina`, `caja`, `equipo`, `promociones` e `informe`.

### Vídeos (carpeta `video/`)

| Archivo | Tamaño | Dónde se usa |
|---|---|---|
| `*-reel.mp4` | 1080 × 1920, 17 s | Reels, TikTok, historias, estados de WhatsApp, Shorts de YouTube |
| `*-feed.mp4` | 1080 × 1350, 17 s | Publicación con vídeo en Instagram, Facebook y LinkedIn |
| `*.html` | — | El mismo anuncio animado: ábrelo en el navegador para verlo o enseñarlo en una visita (botón «Ver otra vez») |

Vídeos: `general`, `restaurante`, `autonomo` y `tienda`. Van **sin música** a propósito: añádela al publicar desde
la biblioteca de Instagram o TikTok, que ya tiene los derechos. Usar una canción cualquiera puede hacer que bloqueen el vídeo.

### Anuncios 3D (carpeta `3d/`)

Un portátil y un móvil con la app que entran girando, con notificaciones de la app flotando alrededor. Hay 4 campañas: `general`,
`restaurante`, `tienda` y `autonomo`.

| Archivo | Qué es | Dónde se usa |
|---|---|---|
| `3d/*.html` | **Interactivo**: se gira arrastrando con el dedo o el ratón, y el botón «Pide tu demo gratuita» abre un formulario de contacto | Envíalo por WhatsApp o email, ábrelo en una tablet en una visita, o ponlo en la web. Es un solo archivo y funciona sin internet |
| `3d/video/*-reel.mp4` | Vídeo vertical de 12 s | Reels, TikTok, historias |
| `3d/video/*-feed.mp4` | Vídeo de 12 s | Publicaciones de Instagram, Facebook y LinkedIn |
| `3d/imagenes/*.png` | Imagen fija | Publicación, historia y horizontal |

Para verlo todo junto y descargarlo, abre **`galeria.html`** en el navegador.

**El formulario de los anuncios 3D** pide nombre, negocio, tipo de negocio, email, teléfono (opcional) y mensaje, con la
casilla de consentimiento que exige el RGPD y un enlace a tu aviso de privacidad. Hasta que rellenes `WHATSAPP` o
`FORMSPREE_ID`, al enviarlo avisa de que aún no está activo y ofrece el formulario de tu web.

En Instagram, Facebook o TikTok las imágenes y los vídeos no se pueden pulsar: al crear el anuncio elige el botón
«Más información» o «Contactar» y pon como enlace el formulario de tu web (`WEB` + `#contacto`) o tu WhatsApp.

## Antes de publicar

1. Abre `generar.py` y rellena:
   - `CONTACTO`: el texto que se ve en los anuncios (por ejemplo `"WhatsApp 600 111 222 · nirkana.es"`).
   - `WHATSAPP` o `FORMSPREE_ID`: a dónde llegan las solicitudes del formulario de los anuncios 3D. Con Formspree te
     llegan al email sin que tu dirección aparezca en ningún sitio; con WhatsApp se abre un mensaje ya escrito.
   - `WEB`: la dirección de tu web (el botón de los vídeos animados lleva a su formulario de contacto).
2. Vuelve a crear todo: `python marketing/anuncios/generar.py`, `python marketing/anuncios/video.py`,
   `python marketing/anuncios/tresd.py` y `python marketing/anuncios/galeria.py`
   (los vídeos tardan unos 40 segundos cada uno; necesitas también ffmpeg). Si estás en un entorno con Playwright y Chromium ya instalados en otra ruta, usa `CHROMIUM_PATH=/ruta/a/chromium`.
3. En los textos de abajo, cambia **[ENLACE]** por la dirección de tu web.

## Textos para cada red

### General (todas las redes)

**Instagram / Facebook**
> ¿Sabes cuánto has ganado hoy de verdad? 📊
>
> NirKanA reúne en una sola app tus cobros, tu stock, tu caja y tus clientes. Y te avisa antes de que algo vaya mal: un producto que se agota, una caja que no cuadra o unas ventas que bajan.
>
> ✅ Desde el móvil, la tablet o el ordenador
> ✅ Sin instalar nada
> ✅ Un informe de tu negocio cada lunes
>
> Pide tu demo gratuita de 20 minutos 👉 [ENLACE]
>
> #gestiondeventas #pymes #emprendedores #negocioslocales #autonomos #comercio

**LinkedIn**
> Muchos negocios pequeños siguen llevando las ventas entre una caja registradora, una libreta y una hoja de Excel. Así es imposible saber a tiempo qué está pasando.
>
> NirKanA junta todo en una sola app: cobros, stock, caja, clientes y equipo. Y lo más útil: te avisa de lo importante antes de que sea un problema, y cada lunes te deja un informe con cómo va tu negocio.
>
> Funciona en el navegador del móvil, la tablet o el ordenador, sin instalar nada.
>
> Si tienes un restaurante, una tienda o trabajas por tu cuenta, te enseño cómo quedaría con tus productos en una demo de 20 minutos: [ENLACE]

### Restaurantes y cafeterías

> Tu sala, tu cocina y tu caja, en el móvil 🍽️
>
> Con NirKanA tus camareros toman nota desde el móvil y la cocina ve el pedido al momento. Varias personas pueden pedir en la misma mesa, y al cobrar puedes dividir la cuenta o mezclar efectivo y tarjeta.
>
> ✅ Mesas y comandas compartidas
> ✅ Pantalla de cocina en tiempo real
> ✅ Cuenta dividida, pago mixto y happy hour
>
> Pide tu demo gratuita 👉 [ENLACE]
>
> #hosteleria #restaurantes #cafeterias #bares #hosteleriaespaña

### Tiendas y comercios

> Que no se te agote lo que más vendes 🛍️
>
> NirKanA vigila tu stock y te avisa antes de que falte un producto. Haces el pedido al proveedor en un clic, y el stock se actualiza solo cuando llega la mercancía.
>
> ✅ Venta rápida con control de stock
> ✅ Pedidos a proveedores en un clic
> ✅ Puntos para tus clientes fieles
>
> Pide tu demo gratuita 👉 [ENLACE]
>
> #comerciolocal #tiendas #pequeñocomercio #retail #emprendedores

### Autónomos y servicios

> Tu agenda y tus facturas, sin papeles 💼
>
> Organiza tus citas sin solapes, cobra cada cita con un toque y envía la factura en PDF en el momento. Todo desde el móvil.
>
> ✅ Agenda de citas
> ✅ Cobro con un toque
> ✅ Facturas en PDF al instante
>
> Pide tu demo gratuita 👉 [ENLACE]
>
> #autonomos #freelance #emprendedores #peluqueria #estetica #consultoria

### Tiendas online

> Descubre qué producto te da dinero de verdad 📦
>
> NirKanA te dice qué productos sostienen tu negocio, cuáles apenas aportan, qué precio deberías poner y qué clientes han dejado de comprar.
>
> ✅ Ventas por canal y forma de pago
> ✅ Márgenes y precios por producto
> ✅ Aviso de clientes que se van
>
> Pide tu demo gratuita 👉 [ENLACE]
>
> #ecommerce #tiendaonline #vendeonline #emprendedores

### Cobrar rápido (`cobro`)

> Cobra en segundos, sin líos con el cambio 💳
>
> Toca los productos, elige la forma de pago y listo: tarjeta, efectivo, Bizum o pago mixto. La app calcula el cambio, divide la cuenta y te da el ticket o la factura en PDF.
>
> Pide tu demo gratuita 👉 [ENLACE]

### Cocina (`cocina`)

> Pedidos a cocina, sin papelitos ni gritos 👨‍🍳
>
> Cada comanda aparece en la pantalla de cocina en el orden en que llega, con sus notas («poco hecho», «para compartir»). Y la sala ve al momento qué platos están listos.
>
> Pide tu demo gratuita 👉 [ENLACE]

### Cierre de caja (`caja`)

> Cierra la caja en un minuto 🧾
>
> La app sabe cuánto efectivo debería haber en el cajón. Tú solo lo cuentas, y si no cuadra te avisa. El cierre queda guardado y firmado.
>
> Pide tu demo gratuita 👉 [ENLACE]

### Equipo (`equipo`)

> Un PIN por empleado. Cada venta, firmada 🔐
>
> Cada persona entra con su PIN y solo ve lo que le toca: administrador, encargado o empleado. Sabes quién ha vendido, anulado o cerrado la caja.
>
> Pide tu demo gratuita 👉 [ENLACE]

### Promociones (`promociones`)

> Happy hour y 2x1 que se aplican solos 🎉
>
> Crea la promoción una vez (por día, por horario o «lleva 2, paga 1») y la app la aplica sola al cobrar. Y tus clientes fieles acumulan puntos.
>
> Pide tu demo gratuita 👉 [ENLACE]

### Informe semanal (`informe`)

> Cada lunes, cómo va tu negocio 📈
>
> Cuánto has vendido, cuál ha sido tu mejor día, qué productos te sostienen y qué deberías cambiar. Explicado en claro, y en PDF para guardarlo.
>
> Pide tu demo gratuita 👉 [ENLACE]

## Textos para los vídeos (Reels y TikTok)

Pon poco texto: el vídeo ya lo cuenta.

- **General:** ¿Libreta, Excel y calculadora? Hay una forma más fácil 👇 Demo gratuita en [ENLACE] #pymes #emprendedores #negocios
- **Restaurante:** Sala, cocina y caja conectadas desde el móvil 🍽️ Demo gratuita en [ENLACE] #hosteleria #restaurantes #bares
- **Autónomo:** Tu agenda y tus facturas, sin papeles 💼 Demo gratuita en [ENLACE] #autonomos #freelance #emprendedores
- **Tienda:** Que no se te agote lo que más vendes 🛍️ Demo gratuita en [ENLACE] #comerciolocal #tiendas #retail

## Mensaje para enviar por WhatsApp (a conocidos y negocios cercanos)

> ¡Hola! Te escribo porque he creado NirKanA, una app para llevar las ventas de un negocio desde el móvil: cobros, stock, caja, clientes y facturas, con avisos cuando algo va mal. Si te apetece, te la enseño en 20 minutos con productos como los tuyos, sin compromiso. Aquí la tienes: [ENLACE]

## Anuncios de Google (búsqueda)

**Títulos** (máximo 30 caracteres cada uno):
- Gestor de ventas NirKanA
- Programa para tu restaurante
- TPV en el móvil sin instalar
- Controla stock y caja
- Facturas en PDF al instante
- Agenda y cobros para autónomos
- Pide tu demo gratuita

**Descripciones** (máximo 90 caracteres cada una):
- Cobros, stock, caja y clientes en una sola app. Desde el móvil, sin instalar nada.
- Mesas, comandas y cocina conectadas. Cuenta dividida y pago mixto. Pide tu demo.
- Avisos antes de que algo vaya mal e informe de tu negocio cada lunes. Pide tu demo.

## Para hacerlo bien (y legal)

- **No prometas resultados** que no puedas demostrar (por ejemplo «vende un 30 % más»). Los textos de aquí solo describen lo que la app hace de verdad.
- **«Demo gratuita»** quiere decir eso: la demo no se cobra. Si más adelante ofreces una prueba gratis de la app, dilo con sus condiciones (cuántos días, qué pasa después).
- Los datos que aparecen en las capturas son **de ejemplo**: si alguien pregunta, dilo con naturalidad.
- **Cumplimiento fiscal (VeriFactu):** no anuncies la app como «software de facturación homologado» hasta tenerlo adaptado.
- Si pagas por promocionar una publicación, Instagram y Facebook ya la marcan como «Publicidad».
- Para escribir por WhatsApp o por email a negocios que no te conocen, hazlo de uno en uno y de forma personal. Los envíos masivos sin permiso pueden ir contra la ley.

# Que te encuentren en Google: lo que está hecho y lo que solo puedes hacer tú

Objetivo: que la gente encuentre nirkana.es, **pruebe NirKanA 24 horas** y **te escriba por correo**. Este documento separa lo que ya
está en la web de lo que depende de cuentas tuyas (Google, Bing, redes), que quedaron para noviembre.

## 1. Qué hay hecho en la web

| Qué | Estado |
|---|---|
| Etiquetas básicas (título, descripción, canonical, Open Graph, Twitter, idioma, icono) | En todas las páginas; títulos de menos de 70 caracteres y descripciones propias, con la prueba de 24 horas |
| Datos estructurados (JSON-LD) | `SoftwareApplication`, `Organization`, `WebSite`, `FAQPage` en la portada; `BreadcrumbList` + `FAQPage` en cada sector; `BreadcrumbList` + `Article` + `FAQPage` en cada guía; `BreadcrumbList` + `WebApplication` (gratis) + `FAQPage` en cada calculadora; `CollectionPage` en el índice de guías |
| `robots.txt` y `sitemap.xml` | Mapa con 22 páginas (portada, 6 sectores, índice de guías y 11 guías, índice de herramientas y 2 calculadoras), cada una con su fecha de última modificación. La demo, la pantalla «demostración finalizada», la entrada de TikTok, el aviso de privacidad y el 404 no se indexan |
| Contenido que responde a búsquedas | 11 guías de unas 640 a 1.400 palabras, con ejemplos y listas de comprobación, enlazadas desde la portada, el menú, el pie y cada sector. Cada guía sale con su fecha de publicación (y de actualización si se toca) |
| Herramientas gratis | 2 calculadoras que se pueden compartir y enlazar: **arqueo de caja** (billetes y monedas en euros, con plantilla de Excel) y **margen y precio de venta** (con IVA, recargo y descuento). Todo se calcula en el navegador: no se envía ni se guarda nada. Salen en el pie de todas las páginas y en la portada |
| Sector «pequeñas empresas» | `programa-gestion-pequenas-empresas/`: la tarjeta «Pymes» de la portada tenía solo un botón de contacto; ahora tiene su página, con lo que ya dice la web (roles, registro de actividad, caja, stock, gestoría) y sin prometer varios locales |
| Entrada de TikTok | `nirkana.es/tiktok/`: página corta para el enlace de la biografía; no se indexa y cuenta sus visitas y sus tres botones (ver 5) |
| Enlaces internos | Todas las páginas enlazan al índice de guías y al de herramientas; cada guía enlaza a su sector y a otras guías (y, si toca, a su calculadora); cada sector enlaza a tres guías; el pie de todas las páginas lista los seis sectores |
| Velocidad y accesibilidad | Lighthouse (móvil simulado, copia local, 21 y 22/10/2026): 100 en SEO, accesibilidad y buenas prácticas en las guías, las calculadoras, el sector de pequeñas empresas y los dos índices; rendimiento 99–100. La entrada de TikTok saca 69 en SEO **a propósito** (lleva `noindex`). axe-core: 0 infracciones en las páginas nuevas o cambiadas (las calculadoras, en cuatro estados: vacía, con resultado, que cuadra y con un error) × móvil/escritorio × claro/oscuro (en la portada, esperando a que acaben sus animaciones de entrada: si axe mide a mitad de la transición ve un contraste que no es el final) |
| Conversión | «Probar gratis 24 horas» en la cabecera, en el cuerpo y al final de cada guía y sector; el correo a la vista (con el asunto de la página de origen); eventos de medición sin cookies |
| Veracidad | Las pruebas `tests/web-claims.test.mjs` y `tests/web-guias.test.mjs` impiden prometer lo que la app no hace, inventar cifras o reseñas, o publicar una página sin su prueba y su correo |

Lo que **no** está en tu mano ni en la mía: la posición en Google. Depende de que los buscadores descubran la web, de la
competencia (Holded, Quipu, Square, Zettle, Revo, Last.app…), de cuántos sitios la enlacen y del tiempo. Lo razonable es empezar por
búsquedas concretas (las guías) y no por «TPV» a secas.

## 2. Qué esperar (orientativo)

- **Aparecer en el índice:** de unos días a un par de semanas después de enviar el mapa del sitio en Search Console.
- **Primeras impresiones y clics:** de semanas a un par de meses. Al principio, sobre todo por búsquedas largas y concretas
  («cómo cuadrar la caja de un bar», «agenda de citas peluquería»).
- **Buenas posiciones para búsquedas genéricas:** meses, y solo con contenido nuevo cada mes y enlaces de otros sitios.

## 3. Pasos que solo puedes dar tú (noviembre)

Haz primero el 1 y el 2: sin ellos los buscadores tardan mucho más en enterarse de las guías.

1. **Google Search Console** (https://search.google.com/search-console)
   - *Añadir propiedad → Dominio* → `nirkana.es`. Te da un registro **TXT** (`google-site-verification=…`).
   - En IONOS: *Dominios y SSL → nirkana.es → DNS → Añadir registro → TXT*, host `@`, el valor que te ha dado Google. Vuelve a
     Search Console y pulsa *Verificar* (puede tardar de minutos a unas horas).
   - *Sitemaps → Añadir* `sitemap.xml`.
   - *Inspección de URLs*: pega cada dirección (portada, 6 sectores, `/guias/`, las 11 guías, `/herramientas/` y las 2 calculadoras) y pulsa *Solicitar indexación*. La entrada de TikTok **no** hay que enviarla.
2. **Bing Webmaster Tools** (https://www.bing.com/webmasters): *Importar desde Google Search Console* (un clic). También alimenta a
   DuckDuckGo y a otros buscadores.
3. **Perfiles con enlace a la web:** TikTok (cuenta Business con **`nirkana.es/tiktok/`** en la biografía: es la página hecha para eso), LinkedIn
   (página de empresa), Instagram. Cuando existan, dime las direcciones y las añado como `sameAs` a los datos estructurados.
4. **Enlaces de otros sitios (los que más pesan, y los que más cuestan):** ficha gratuita en directorios de software (Capterra y
   GetApp, AlternativeTo, Crunchbase); que tu gestoría o tus primeros clientes enlacen una guía; colaboraciones con
   asociaciones de comercio u hostelería de tu zona. **No compres enlaces ni uses granjas de enlaces**: Google penaliza la web entera.
5. **Aviso legal** (`python ops/legal.py`, cuando tengas tus datos): da confianza y es obligatorio con actividad económica.
6. **Opiniones de clientes:** cuando haya clientes reales, pídeles una reseña (Google, Trustpilot). La web no puede enseñar
   valoraciones inventadas y las pruebas lo impiden.
7. **Google Business Profile:** solo si tienes local abierto al público o atiendes en una zona concreta; para un software sin
   dirección pública no corresponde.

## 4. Cómo medirlo

- **GoatCounter** (https://nirkana.goatcounter.com, sin cookies): visitas por página (las guías salen con su dirección), sitios de los
  que llegan (google, bing, tiktok…) y los eventos `prueba-abierta`, `contacto-email`, `contacto-copiar`, `contacto-enviado`.
  Lectura útil: de las visitas a cada guía, cuántas abren la prueba o escriben. Las calculadoras suman `herramienta-arqueo`,
  `herramienta-margen` y `plantilla-arqueo` (quién las usa de verdad y quién baja la hoja de Excel); la entrada de TikTok, la ruta
  `/tiktok/` y los eventos `tiktok-prueba`, `tiktok-demo` y `tiktok-correo`.
- **Search Console**: consultas con las que sales, impresiones, clics y posición media, y si alguna página tiene errores de
  datos estructurados o de indexación.
- Mira ambos una vez a la semana durante el primer mes y después una vez al mes.

## 5. TikTok, guías y calculadoras se ayudan

**Enlace de la biografía: `https://nirkana.es/tiktok/`.** TikTok no deja enlaces en la descripción, así que todo el mundo llega por la
biografía; esa página está pensada para quien viene de un vídeo de 12 segundos y no conoce NirKanA: qué es en dos líneas, «Probar
gratis 24 horas», la demo, el correo, las calculadoras y las guías, y un enlace por tipo de negocio. No se indexa, no sale en el mapa
del sitio y ninguna otra página la enlaza (las pruebas lo vigilan), así que no compite con la portada en Google.

Cada vídeo del calendario puede llevar además en el comentario fijado la guía o la herramienta que lo amplía (los comentarios admiten
texto; si lo escribes como `nirkana.es/guias/…`, el que quiera lo copia):

| Vídeo (día) | Guía o herramienta que lo amplía |
|---|---|
| 1 · ¿Libreta, papel y Excel? | `/herramientas/` (las dos calculadoras gratis) |
| 2 · ¿Citas por WhatsApp y una libreta? | `/guias/agenda-de-citas-para-peluquerias/` |
| 3 · ¿Cuánto vendiste? ¿Qué stock te queda? ¿Cuánto ganas? | `/guias/calcular-el-margen-de-un-producto/` y `/herramientas/calculadora-de-margen/` |
| 4 · ¿Facturas el último día del trimestre? | `/guias/documentos-del-trimestre-para-la-gestoria/` y `/guias/que-debe-llevar-una-factura/` |
| 5 · Sala, cocina y caja, ¿hablan entre sí? | `/guias/comandas-y-pantalla-de-cocina-en-un-bar/` |
| 6 · ¿Se cae internet y dejas de cobrar? | `/guias/que-es-un-tpv/` |
| 7 · ¿Todo el equipo ve todo? | `/programa-gestion-pequenas-empresas/` |
| 9 · ¿Cuadrar la caja te lleva media hora? | `/guias/arqueo-y-cierre-de-caja/` y `/herramientas/calculadora-de-arqueo-de-caja/` |
| 11 · ¿Haces promociones a ojo? | `/guias/calcular-el-margen-de-un-producto/` (la parte de los descuentos) |
| 12 · ¿Sabes lo que de verdad ganas? | `/guias/calcular-el-margen-de-un-producto/` |
| 15 · ¿Sabes qué stock te queda? | `/guias/control-de-stock-en-una-tienda/` y `/guias/stock-de-tienda-online-y-tienda-fisica/` |

Las guías de **devoluciones y cambios** y de **impresoras de tickets** todavía no tienen vídeo: son buenas candidatas para los días
que quedan.

**Cómo medir lo que traen los vídeos, sin cookies ni parámetros:** en GoatCounter, la ruta `/tiktok/` son las visitas que llegan de la
biografía, y `tiktok-prueba`, `tiktok-demo` y `tiktok-correo` son los clics en cada botón de esa página. Los días en que publicas un
vídeo suben las visitas a `/tiktok/`: compara día con día. No se usa `?utm_source=` porque cambiaría lo que cuenta la web y exigiría
actualizar el aviso de privacidad.

## 6. Cómo seguir

- **Una guía nueva al mes**, sobre lo que más te pregunten (el formulario y el correo dicen qué). Cada guía: una duda concreta,
  ejemplos inventados, una lista de comprobación y lo que NirKanA hace **y lo que no**. Ya están las de comandas, stock online y
  físico, devoluciones e impresoras de tickets. Ideas para las siguientes: programa de puntos para clientes, cómo hacer un
  presupuesto, inventario de fin de año en una tienda, cuenta dividida en una mesa, quién puede hacer qué en un equipo (permisos).
- **Más herramientas gratis** (atraen enlaces y gente que luego prueba NirKanA): precio por hora de un servicio, punto de equilibrio,
  calculadora de IVA, reparto de propinas. Se añaden como las dos primeras (ver `docs/WEB.md`).
- **Cómo se añade:** `ops/guias_texto.py` (texto) → `python ops/guias.py` → `node --test tests/web-*.test.mjs` y
  `pytest sales_manager/tests/test_guias.py` → publicar. Detalles en `docs/WEB.md`.
- **Fechas:** una guía nueva lleva `published="AAAA-MM-DD"`; si cambias el texto de una antigua, pon `updated` (y sube `DATE` en
  `ops/guias.py` al día en que publicas). El mapa del sitio y los datos estructurados usan esas mismas fechas.
- Si una función de la app cambia (por ejemplo, llegan los recordatorios automáticos), actualiza **a la vez** la guía, el sector y
  la pregunta frecuente que lo menciona: las pruebas no saben si una frase dejó de ser cierta.

# Que te encuentren en Google: lo que está hecho y lo que solo puedes hacer tú

Objetivo: que la gente encuentre nirkana.es, **pruebe NirKanA 24 horas** y **te escriba por correo**. Este documento separa lo que ya
está en la web de lo que depende de cuentas tuyas (Google, Bing, redes), que quedaron para noviembre.

## 1. Qué hay hecho en la web

| Qué | Estado |
|---|---|
| Etiquetas básicas (título, descripción, canonical, Open Graph, Twitter, idioma, icono) | En todas las páginas; títulos de menos de 70 caracteres y descripciones propias, con la prueba de 24 horas |
| Datos estructurados (JSON-LD) | `SoftwareApplication`, `Organization`, `WebSite`, `FAQPage` en la portada; `BreadcrumbList` + `FAQPage` en cada sector; `BreadcrumbList` + `Article` + `FAQPage` en cada guía; `CollectionPage` en el índice de guías |
| `robots.txt` y `sitemap.xml` | Mapa con 14 páginas (portada, 5 sectores, índice de guías y 7 guías), con fecha de última modificación. La demo, la pantalla «demostración finalizada», el aviso de privacidad y el 404 no se indexan |
| Contenido que responde a búsquedas | 7 guías de unas 650 a 1.100 palabras, con ejemplos y listas de comprobación, enlazadas desde la portada, el menú, el pie y cada sector |
| Enlaces internos | Todas las páginas enlazan al índice de guías; cada guía enlaza a su sector y a otras dos guías; cada sector enlaza a tres guías |
| Velocidad y accesibilidad | Lighthouse (móvil simulado, copia local, 21/10/2026): 100 en SEO, accesibilidad y buenas prácticas en todas las guías; rendimiento 99–100. axe-core: 0 infracciones en 14 páginas × móvil/escritorio × claro/oscuro |
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
   - *Inspección de URLs*: pega cada dirección (portada, 5 sectores, `/guias/` y las 7 guías) y pulsa *Solicitar indexación*.
2. **Bing Webmaster Tools** (https://www.bing.com/webmasters): *Importar desde Google Search Console* (un clic). También alimenta a
   DuckDuckGo y a otros buscadores.
3. **Perfiles con enlace a la web:** TikTok (cuenta Business con `nirkana.es` en la biografía, como en el calendario), LinkedIn
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
  Lectura útil: de las visitas a cada guía, cuántas abren la prueba o escriben.
- **Search Console**: consultas con las que sales, impresiones, clics y posición media, y si alguna página tiene errores de
  datos estructurados o de indexación.
- Mira ambos una vez a la semana durante el primer mes y después una vez al mes.

## 5. TikTok y guías se ayudan

Cada vídeo del calendario puede llevar en el comentario fijado la guía que lo amplía (TikTok no deja enlaces en la descripción;
sí se pueden escribir en un comentario o dejar `nirkana.es/guias/` en la biografía):

| Vídeo (día) | Guía que lo amplía |
|---|---|
| 2 · ¿Citas por WhatsApp y una libreta? | `/guias/agenda-de-citas-para-peluquerias/` |
| 3 · ¿Sabes qué stock te queda? | `/guias/control-de-stock-en-una-tienda/` |
| 4 · ¿Facturas el último día del trimestre? | `/guias/documentos-del-trimestre-para-la-gestoria/` y `/guias/que-debe-llevar-una-factura/` |
| 5 · Sala, cocina y caja, ¿hablan entre sí? | `/guias/que-es-un-tpv/` |
| 9 · ¿Cuadrar la caja te lleva media hora? | `/guias/arqueo-y-cierre-de-caja/` |
| 12 · ¿Sabes lo que de verdad ganas? | `/guias/calcular-el-margen-de-un-producto/` |

Hoy la medición de la web no distingue las visitas que vienen de TikTok si el navegador de TikTok no envía referencia. Si quieres
medirlo, se puede contar la etiqueta `?utm_source=tiktok` del enlace, pero eso cambia lo que cuenta la web y exige actualizar el
aviso de privacidad: no se ha hecho sin tu visto bueno.

## 6. Cómo seguir

- **Una guía nueva al mes**, sobre lo que más te pregunten (el formulario y el correo dicen qué). Cada guía: una duda concreta,
  ejemplos inventados, una lista de comprobación y lo que NirKanA hace **y lo que no**. Ideas: elegir impresora de tickets, cómo
  organizar mesas y turnos en un bar, programa de puntos para clientes, cómo hacer un presupuesto, devoluciones y cambios en una
  tienda.
- **Cómo se añade:** `ops/guias_texto.py` (texto) → `python ops/guias.py` → `node --test tests/web-*.test.mjs` y
  `pytest sales_manager/tests/test_guias.py` → publicar. Detalles en `docs/WEB.md`.
- **Revisar la fecha** («Actualizada el…») cada vez que cambie el contenido de una guía (`DATE` en `ops/guias.py`).
- Si una función de la app cambia (por ejemplo, llegan los recordatorios automáticos), actualiza **a la vez** la guía, el sector y
  la pregunta frecuente que lo menciona: las pruebas no saben si una frase dejó de ser cierta.

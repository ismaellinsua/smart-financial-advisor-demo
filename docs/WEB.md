# Web de NirKanA

Página de presentación para ofrecer NirKanA a los clientes: soluciones por tipo de negocio, funciones, preguntas
frecuentes y contacto. Está en esta carpeta `docs/`:

| Archivo | Qué es |
|---|---|
| `index.html` | La página principal |
| `privacidad.html` | Aviso de privacidad (RGPD) |
| `tpv-restaurantes/`, `tpv-tiendas/`, `programa-facturacion-autonomos/`, `tpv-tienda-online/` | Una página por sector, para buscadores (están en `sitemap.xml`) |
| `404.html` | Lo que ve quien abre una dirección que no existe |
| `assets/site.css` | Diseño (claro y oscuro, efectos 3D) |
| `assets/site.js` | Contacto, formulario y efectos 3D |
| `assets/img/` | Capturas de la app optimizadas (`shots/`: `*-c.webp` recortadas para tarjetas, `*.webp` completas para ampliar) |

## Cambiar tus datos de contacto

Todo está al principio de `assets/site.js`:

```js
const CONTACT = {
  email: "nirkana.oficial@gmail.com",  // botón «Escribir por email» y respaldo del formulario
  whatsapp: "",      // tu número con prefijo y solo cifras, p. ej. "34600111222"
  formspreeId: "",   // el código de tu formulario de Formspree
};
```

Con solo el email, el formulario abre el programa de correo del visitante con el mensaje ya escrito. Mejor aún:

- **WhatsApp:** pon tu número y aparece el botón «Hablar por WhatsApp» con un mensaje preparado.
- **Formulario:** con `formspreeId`, los mensajes te llegan a tu correo sin que tu dirección aparezca en la web.
  Sin él, el formulario prepara el mensaje en WhatsApp (si hay número) o en el correo. Para activarlo:
  1. Crea una cuenta gratuita en [formspree.io](https://formspree.io) con tu email.
  2. Crea un formulario (**New form**) y copia el código que aparece en la dirección `https://formspree.io/f/XXXXXXX`.
  3. Pega solo `XXXXXXX` en `formspreeId`.

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

### Contar visitas sin cookies (GoatCounter)

La web puede contar visitas, páginas vistas y formularios enviados **sin cookies ni datos personales**, así que no
necesita banner de cookies. Hasta que pongas tu código no cuenta nada.

1. Crea una cuenta gratuita en [goatcounter.com](https://www.goatcounter.com) y elige un código, p. ej. `nirkana`
   (tu panel quedará en `https://nirkana.goatcounter.com`).
2. En el panel: **Settings → Data collection**, deja desmarcado guardar la IP y marca «Ignore IPs» con la tuya si no
   quieres contarte.
3. En `assets/site.js`, pon `const ANALYTICS = { goatcounter: "nirkana" };` y publica.

Solo cuenta en `nirkana.es` (no en copias locales) y no cuenta a quien tenga activado «no rastrear» en su navegador.
El aviso de privacidad ya lo explica.

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

## Seguridad

- Sin cookies, analítica, publicidad ni código de terceros: nada que rastree a tus visitantes.
- Política de seguridad de contenidos (CSP): solo se ejecuta el código propio de la web y el formulario solo puede
  enviar a Formspree.
- Formulario con límites de longitud, validación, casilla de consentimiento y un campo trampa contra robots.
- El único dato de contacto publicado es el email de contacto; los mensajes llegan por Formspree, WhatsApp o email.
- Los enlaces externos se abren sin pasar datos de la página (`noopener`, `noreferrer`).

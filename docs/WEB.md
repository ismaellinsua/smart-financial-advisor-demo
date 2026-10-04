# Web de NirKanA

Página de presentación para ofrecer NirKanA a los clientes: soluciones por tipo de negocio, funciones, preguntas
frecuentes y contacto. Está en esta carpeta `docs/`:

| Archivo | Qué es |
|---|---|
| `index.html` | La página principal |
| `privacidad.html` | Aviso de privacidad (RGPD) |
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

## Publicarla gratis con GitHub Pages

1. En GitHub, abre el repositorio → **Settings → Pages**.
2. En **Source** elige **Deploy from a branch**; rama **main** y carpeta **/docs**. Pulsa **Save**.
3. En un par de minutos estará en `https://ismaellinsua.github.io/smart-financial-advisor-demo/`, con HTTPS.
4. Si compras un dominio (por ejemplo `nirkana.es`), ponlo en **Custom domain** y marca **Enforce HTTPS**.

También puedes subir la carpeta `docs/` tal cual a Netlify, Cloudflare Pages o cualquier alojamiento estático.

## Seguridad

- Sin cookies, analítica, publicidad ni código de terceros: nada que rastree a tus visitantes.
- Política de seguridad de contenidos (CSP): solo se ejecuta el código propio de la web y el formulario solo puede
  enviar a Formspree.
- Formulario con límites de longitud, validación, casilla de consentimiento y un campo trampa contra robots.
- El único dato de contacto publicado es el email de contacto; los mensajes llegan por Formspree, WhatsApp o email.
- Los enlaces externos se abren sin pasar datos de la página (`noopener`, `noreferrer`).

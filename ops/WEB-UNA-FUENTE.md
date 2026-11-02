# nirkana.es desde un solo repositorio

Plan para que solo un repositorio publique la web. El cambio final está en los ajustes de GitHub y lo hace el dueño;
este documento no cambia nada por sí mismo.

## Cómo está hoy (2/11/2026)

| Repositorio | Qué tiene | Publica nirkana.es |
|---|---|---|
| `smart-financial-advisor-demo` (este) | `docs/` al día, el generador de guías (`ops/guias.py`), las pruebas de la web y los flujos «Web», «IndexNow» y «Web boundaries» | **Sí** (GitHub Pages, `main` / `docs`) |
| `nirkana-web` | Copia de `docs/` del 22/10/2026 con `docs/CNAME` = `nirkana.es`, y los flujos que vigilan la prueba gratuita («Despertar la prueba», «Comprobar la prueba publicada», «Probar la prueba como un visitante») | No debería |

Cómo se sabe cuál publica: las páginas añadidas después del 22/10 (por ejemplo `/programa-entrenadores-personales/`)
solo existen en este repositorio y nirkana.es las sirve.

El riesgo de tener dos: alguien (o un agente) cambia la web en `nirkana-web` creyendo que se publica, o, si un día se
desactiva Pages aquí, GitHub puede dar el dominio a la copia vieja.

`ops/REPOSITORIO.md` (paso 3) planteaba mover la web a `nirkana-web` para poder hacer privado este repositorio. Ese paso
se quedó a medias: se copió `docs/` el 22/10, pero el dominio siguió aquí y la web se ha seguido cambiando aquí.

## Recomendación: este repositorio es la única fuente

No hay caída, no hay que tocar el DNS y todo lo que genera y prueba la web ya vive aquí.

### Lo que haces tú en GitHub (unos 3 minutos)

1. **`nirkana-web` → Settings → Pages.**
   - Si en *Custom domain* aparece `nirkana.es`, pulsa **Remove**.
   - En *Build and deployment › Source* elige **None** (o *Unpublish site* si lo ofrece).
   - No toques **Actions**: los flujos de la prueba gratuita siguen funcionando igual.
2. **Este repositorio → Settings → Pages**: comprueba que sigue *Custom domain* = `nirkana.es` con la comprobación de
   DNS en verde y **Enforce HTTPS** marcado. No cambies nada aquí.

### Comprobación (1 minuto)

- Abre https://nirkana.es/programa-entrenadores-personales/: debe cargar (solo existe en este repositorio).
- Aquí: **Actions → Web → Run workflow**. Debe salir en verde (DNS, certificado, redirecciones y cada página).

### Después (lo preparo yo en un PR de `nirkana-web` cuando lo pidas)

- Quitar `docs/CNAME` y el flujo «Web» de `nirkana-web` (comprueba una copia que ya no se publica).
- Poner en su README: «La web se publica desde `smart-financial-advisor-demo/docs`. Aquí solo quedan los flujos que
  vigilan la prueba gratuita».

### Si algo sale mal

Desactivar Pages en `nirkana-web` no toca este repositorio. Si nirkana.es no carga tras el paso 1, revisa el paso 2
(dominio y HTTPS en este repositorio) y lanza «Web» para ver qué falla. Volver atrás es activar de nuevo Pages en
`nirkana-web`, pero no hace falta para que la web funcione.

## La otra opción: mover la web a `nirkana-web`

Solo merece la pena si quieres hacer privado este repositorio (GitHub Pages gratis exige que sea público). Implica:

1. Volver a copiar `docs/` con `bash ops/separar_web.sh https://github.com/ismaellinsua/nirkana-web.git`.
2. Llevar también a `nirkana-web` lo que genera y prueba la web: `ops/guias.py` y sus textos, `ops/legal.py` y `legal/`,
   las pruebas `tests/web-*.test.mjs` y los flujos «Web», «IndexNow» y «Web boundaries».
3. Cambiar el dominio de repositorio (pasos 3 y 4 de `ops/REPOSITORIO.md`): unos minutos sin web.

Es más trabajo y tiene una caída corta. Mi propuesta es la recomendación de arriba ahora y decidir esto aparte.

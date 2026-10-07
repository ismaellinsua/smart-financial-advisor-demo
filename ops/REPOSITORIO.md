# Repositorio: proteger `main`, separar la web, hacerlo privado y limpiar el historial

Pasos que solo puede dar el dueño del repositorio en GitHub. Hazlos **en este orden**: así nirkana.es no se cae y
ningún flujo deja de funcionar. Tiempo total: unos 30 minutos.

## 1. Proteger `main` (1 minuto)

GitHub → repositorio → **Settings → Rules → Rulesets → New ruleset ▾ → Import a ruleset** → elige
`ops/github/ruleset-main.json` (descárgalo antes desde GitHub o tu copia local) → **Create**.

Aplica a la rama principal: impide borrarla y reescribir su historia (*force push*), obliga a que todo llegue por un
pull request y exige que pase el check **tests** del CI. Desde entonces nada llega a `main` sin pasar los tests. (Para
el paso 5, si lo haces, desactiva un momento el ruleset y vuelve a activarlo al terminar).

## 2. Secretos y dependencias (1 minuto)

**Settings → Code security** (o *Advanced Security*): activa **Secret Protection** (*Secret scanning* y *Push
protection*: GitHub rechaza un push que contenga una clave) y **Dependabot alerts**. El CI ya revisa todo el
historial con gitleaks y las dependencias con pip-audit.

### Tu email, fuera de los commits (2 minutos)

Hoy 42 commits muestran tu email personal (los «Merge pull request» que haces desde la web y los primeros). Para que
no salga en ninguno más: GitHub → tu foto → **Settings → Emails** → marca **Keep my email addresses private** y
**Block command line pushes that expose my email**. Ahí verás tu dirección privada, del tipo
`12345678+ismaellinsua@users.noreply.github.com`: desde entonces las fusiones hechas en la web la usan. Si haces commits
desde tu ordenador: `git config --global user.email "esa-dirección"`. Para los commits que ya existen, paso 5.

## 3. Separar la web en su propio repositorio (10 minutos)

La web (`docs/`) se publica con GitHub Pages, que en un repositorio privado necesita un plan de pago. Por eso va a un
repositorio público propio, `nirkana-web`, antes de hacer privado este.

1. Crea en GitHub el repositorio **público y vacío** `nirkana-web` (sin README, sin licencia).
2. Desde este repositorio, en tu ordenador:

   ```bash
   bash ops/separar_web.sh https://github.com/ismaellinsua/nirkana-web.git
   ```

   Copia `docs/` y la sube a `main` (las capturas en PNG del README están fuera, en `capturas/`).
3. **En este repositorio**: Settings → Pages → en *Custom domain* pulsa **Remove** y después, en *Build and
   deployment*, elige **None** para desactivar Pages. Un dominio solo puede estar en un repositorio a la vez: desde
   aquí hasta el paso 4, nirkana.es no responde (unos minutos).
4. **En `nirkana-web`**: Settings → Pages → *Deploy from a branch* → `main` / `(root)` → **Save**. En *Custom domain*
   escribe `nirkana.es` → **Save**. Cuando la comprobación de DNS salga en verde, marca **Enforce HTTPS** (el
   certificado puede tardar hasta una hora). No hay que tocar el DNS: sigue apuntando a GitHub Pages.
5. Abre https://nirkana.es y https://nirkana.es/privacidad.html para comprobarlo, y en este repositorio lanza
   Actions → **Web** → *Run workflow*: comprueba el DNS, el certificado, las redirecciones y cada página (también se
   ejecuta solo cada día y avisa por email si algo falla, p. ej. un certificado que GitHub no ha podido renovar).

Desde entonces **la web se cambia en `nirkana-web`**. Para publicar los textos legales allí:
`python ops/legal.py --docs ../nirkana-web` (y subir los cambios de ese repositorio).

## 4. Hacer privado este repositorio (2 minutos)

Antes, ten en cuenta lo que cambia en un repositorio privado con el plan gratuito:

| Qué | Público | Privado (gratis) |
|---|---|---|
| Minutos de GitHub Actions | Ilimitados | **2.000 al mes** |
| Almacenamiento de artefactos (copias) | Sin límite práctico | **500 MB** |
| GitHub Pages | Sí | No (por eso el paso 3) |

Los minutos dan para lo esencial: los tests (unos 8 minutos por ejecución) y las copias nocturnas (unos 5 al día, unos
150 al mes). Pero la **vigilancia de disponibilidad** se ejecuta cada 10 minutos: unas 4.300 ejecuciones al mes, más
de lo que da el plan gratuito. Antes de hacerlo privado:

- pon un monitor externo gratuito (UptimeRobot o Better Stack) que compruebe `https://tu-app/_nk/salud` cada
  5 minutos (responde `ok` solo si la app y su base de datos funcionan) y te avise por email, y
- desactiva el flujo en GitHub: Actions → **Disponibilidad** → `···` → **Disable workflow**.

Para las copias, configura la copia externa (`BACKUP_S3_*`, README → «Copias de seguridad automáticas») y, si hace
falta, baja la retención de los artefactos en `.github/workflows/backup.yml` (`retention-days`).

Después: **Settings → General → Danger Zone → Change repository visibility → Make private**.

## 5. Limpiar el historial (opcional, 10 minutos)

En el historial siguen `NEGOCIO.md` y `NirKanA-negocio.pdf` (commit `c49b504`): el plan de negocio con precios,
previsiones y gastos, y tu email personal en 42 commits. Con el repositorio privado ya no los ve nadie más, pero si en
algún momento lo compartes o lo vuelves público, conviene quitarlos de todos los commits:

```bash
pip install git-filter-repo
bash ops/limpiar_historial.sh https://github.com/ismaellinsua/smart-financial-advisor-demo.git \
     TU-DIRECCION@users.noreply.github.com
```

El script guarda antes una copia completa (`copia-antes-de-limpiar.git`), reescribe el historial sin esos archivos y con
tu dirección privada en lugar de tu email (sin la dirección, solo quita los archivos), comprueba que no queda nada y
**pregunta antes de subir nada** (hay que escribir `SI`). La subida reescribe todas las
ramas: después hay que volver a clonar el repositorio en cada equipo, y los PR abiertos se pierden (ciérralos antes).
GitHub puede conservar un tiempo vistas en caché de commits antiguos: pide a GitHub Support que las purgue
(«Remove sensitive data»).

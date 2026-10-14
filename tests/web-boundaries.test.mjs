// Ejecutar: node --test tests/web-boundaries.test.mjs
// Verifica que la web no exponga enlaces a despliegues aún no comprobados.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const site = readFileSync(resolve(root, 'docs/assets/site.js'), 'utf8');
const home = readFileSync(resolve(root, 'docs/index.html'), 'utf8');

test('la demo ficticia está disponible sin conectar con producción', () => {
  assert.match(site, /const DEMO_URL = "\/demo\/";/);
  assert.match(home, /data-demo/);
});

// The trial was validated from outside on 14/10/2026 (nirkana-app → Actions → comprobar-despliegue, modo prueba): only that
// address or its future own domain may be linked; anything else (an http:// address, another host) is a mistake.
test('el enlace de la prueba de 24 horas solo apunta a la prueba ya comprobada', () => {
  const url = site.match(/const TRIAL_URL = "([^"]*)";/)[1];
  assert.ok(['', 'https://nirkana-prueba.onrender.com', 'https://prueba.nirkana.es'].includes(url), `TRIAL_URL inesperado: ${url}`);
});

test('el acceso de clientes permanece desactivado hasta validar el despliegue', () => {
  assert.match(site, /const APP_URL = "";/);
});

test('la web comercial mantiene el correo de contacto', () => {
  assert.match(site, /email: "nirkana\.oficial@gmail\.com"/);
});

test('la demo y la prueba de 24 horas son botones distintos', () => {
  assert.match(home, /data-demo/);
  assert.match(home, /data-trial/);
});

// ---- rendimiento: las clases que el script añadiría ya vienen en el HTML (si no, los botones cambian tras pintar)
import { readdirSync, statSync } from 'node:fs';

const pagesWithScript = (dir = resolve(root, 'docs')) =>
  readdirSync(dir).flatMap((name) => {
    const full = resolve(dir, name);
    if (statSync(full).isDirectory()) return name === 'demo' || name === 'caja' ? [] : pagesWithScript(full);
    return name.endsWith('.html') && readFileSync(full, 'utf8').includes('assets/site.js') ? [full] : [];
  });

test('cada página trae en <html> las clases js / has-demo / has-trial que corresponden a la configuración', () => {
  const trial = /^https:\/\/[a-z0-9.-]+(\/.*)?$/i.test(site.match(/const TRIAL_URL = "([^"]*)";/)[1]);
  const demoUrl = site.match(/const DEMO_URL = "([^"]*)";/)[1];
  const demo = /^\/[a-z0-9\/_-]*$/i.test(demoUrl) || /^https:\/\/[a-z0-9.-]+(\/.*)?$/i.test(demoUrl);
  const pages = pagesWithScript();
  assert.ok(pages.length >= 6, `se esperaban al menos 6 páginas con site.js, hay ${pages.length}`);
  for (const file of pages) {
    const html = readFileSync(file, 'utf8');
    const classes = (html.match(/<html[^>]*\bclass="([^"]*)"/) || [, ''])[1].split(/\s+/);
    assert.ok(classes.includes('js'), `${file}: falta class="js" en <html>`);
    assert.equal(classes.includes('has-demo'), demo, `${file}: has-demo no coincide con DEMO_URL`);
    assert.equal(classes.includes('has-trial'), trial, `${file}: has-trial no coincide con TRIAL_URL`);
    assert.match(html, /<noscript><link rel="stylesheet" href="\/?assets\/sin-js\.css"><\/noscript>/,
      `${file}: sin la hoja para visitantes sin JavaScript el menú quedaría inservible`);
  }
});

test('la hoja sin JavaScript devuelve el menú de secciones al encabezado', () => {
  const css = readFileSync(resolve(root, 'docs/assets/sin-js.css'), 'utf8');
  assert.match(css, /html\.js \.top nav \{ display: flex/);
  assert.match(css, /html\.js \.menu-btn \{ display: none/);
});

test('la CSP solo admite el origen propio y Formspree para conexiones', () => {
  for (const file of pagesWithScript()) {
    const csp = readFileSync(file, 'utf8').match(/Content-Security-Policy"\s+content="([^"]*)"/)[1];
    const connect = csp.split(';').map((d) => d.trim()).find((d) => d.startsWith('connect-src'));
    assert.equal(connect, "connect-src 'self' https://formspree.io", `${file}: ${connect}`);
  }
});

// The trial sleeps when nobody uses it; the site wakes it with a request for one image of the app plus, if that fails, one
// hidden page request, and shows its own waiting screen (see openTrial in site.js). The CSP lets through exactly that.
test('la CSP deja cargar imágenes y un marco solo del servicio de la prueba (y GoatCounter para imágenes)', () => {
  const trial = site.match(/const TRIAL_URL = "([^"]*)";/)[1];
  const origin = trial && new URL(trial).origin;
  const img = ["img-src 'self' data: https://*.goatcounter.com", origin].filter(Boolean).join(' ');
  const frame = origin ? `frame-src ${origin}` : undefined;
  for (const file of pagesWithScript()) {
    const csp = readFileSync(file, 'utf8').match(/Content-Security-Policy"\s+content="([^"]*)"/)[1];
    const directives = csp.split(';').map((d) => d.trim());
    assert.equal(directives.find((d) => d.startsWith('img-src')), img, `${file}: img-src`);
    assert.equal(directives.find((d) => d.startsWith('frame-src')), frame, `${file}: frame-src`);
  }
});

test('despertar la prueba pide una imagen y una página ocultas del propio servicio y nunca deja al visitante sin salida', () => {
  assert.match(site, /\$\{new URL\(target\)\.origin\}\/icons\/simbolo\.svg\?despertar=/);
  assert.match(site, /waker\.setAttribute\("sandbox", ""\)/);                  // la página oculta no puede hacer nada
  assert.match(site, /const TRIAL_GIVE_UP_MS = \d{4,5};/);                       // pasado ese tiempo, se lleva al visitante a la prueba
  assert.match(site, /TRIAL_GIVE_UP_MS\)\);/);                                     // el temporizador final lleva al visitante a la prueba
  assert.match(site, /open\("prueba-lenta"/);
  assert.match(site, /event\.button !== 0 \|\| event\.metaKey \|\| event\.ctrlKey/); // nueva pestaña / ventana: comportamiento normal
  const giveUp = Number(site.match(/const TRIAL_GIVE_UP_MS = (\d+);/)[1]);
  assert.ok(giveUp >= 30000 && giveUp <= 60000, `espera total fuera de lo razonable: ${giveUp} ms`);
});

// Price and contact: the home page shows the price as a section of its own, linked from the menu and the footer, and the
// e-mail address itself is visible (not only behind a mailto: button) and can be copied.
test('el precio tiene sección propia, enlazada desde el menú y el pie, y la cabecera de la home lo menciona', () => {
  assert.match(home, /<section id="precio">/);
  assert.match(home, /<h2>Desde 20 € al mes<\/h2>/);
  assert.equal((home.match(/href="#precio"/g) || []).length, 2, 'enlace en el menú y en el pie');
  assert.match(home, /Después, desde 20 € al mes\./);
  assert.match(home, /schema\.org[\s\S]*"price": "20"/);   // los datos estructurados dicen lo mismo que la página
});

test('la dirección de email se ve y se puede copiar, y se rellena desde la configuración (no está escrita en el HTML)', () => {
  assert.match(home, /id="email-copy"/);
  assert.match(home, /id="email-text" data-email/);
  const visible = home.replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/g, '');   // los datos estructurados para buscadores sí lo llevan
  assert.doesNotMatch(visible, /nirkana\.oficial@gmail\.com/);
  assert.match(site, /querySelectorAll\("a\[data-email\]"\)/);
  assert.match(site, /navigator\.clipboard\.writeText\(email\)/);
});

// Counting (GoatCounter, no cookies): the events that tell a visit from a lead. They only count once ANALYTICS has a code.
test('los eventos de medición cubren los botones que importan y la espera de la prueba', () => {
  for (const event of ['prueba-abierta', 'demo-abierta', 'contacto-email', 'contacto-copiar', 'contacto-enviado',
                       'precio-visto', 'prueba-espera', 'prueba-cancelada']) {
    assert.match(site, new RegExp(`countVisit\\("${event}"`), `falta el evento ${event}`);
  }
  for (const event of ['prueba-lista', 'prueba-lenta']) { // los dos finales de la espera salen por open(), que cuenta y luego navega
    assert.match(site, new RegExp(`open\\("${event}"`), `falta el evento ${event}`);
  }
  assert.match(site, /countVisit\(event, title, true\);\s*\n\s*setTimeout\(\(\) => window\.location\.assign\(target\), 150\)/);
});

test('la medición solo cuenta en la web publicada y respeta «no rastrear»', () => {
  assert.match(site, /navigator\.doNotTrack !== "1" && !navigator\.globalPrivacyControl/);
  assert.match(site, /\(\^\|\\\.\)nirkana\\\.es\$\/\.test\(location\.hostname\)/);
  const code = site.match(/const ANALYTICS = \{ goatcounter: "([^"]*)" \};/)[1];
  assert.match(code, /^([a-z0-9][a-z0-9-]{1,49})?$/, `código de GoatCounter no válido: ${code}`);
});

test('el nombre accesible de cada captura ampliable contiene el texto visible del botón', () => {
  const buttons = [...home.matchAll(/<button class="browser zoomable"[^>]*aria-label="([^"]*)"[\s\S]*?<\/button>/g)];
  assert.ok(buttons.length >= 4);
  for (const [block, label] of buttons) {
    // todo el texto del botón cuenta, también el de adornos aria-hidden (así lo mide Lighthouse)
    const visible = block.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    assert.ok(label.toLowerCase().includes(visible.toLowerCase()), `«${label}» no contiene «${visible}»`);
  }
});

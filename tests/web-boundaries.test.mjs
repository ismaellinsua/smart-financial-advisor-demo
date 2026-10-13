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

test('el enlace de la prueba de 24 horas permanece desactivado hasta validar el despliegue', () => {
  assert.match(site, /const TRIAL_URL = "";/);
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

test('el nombre accesible de cada captura ampliable contiene el texto visible del botón', () => {
  const buttons = [...home.matchAll(/<button class="browser zoomable"[^>]*aria-label="([^"]*)"[\s\S]*?<\/button>/g)];
  assert.ok(buttons.length >= 4);
  for (const [block, label] of buttons) {
    // todo el texto del botón cuenta, también el de adornos aria-hidden (así lo mide Lighthouse)
    const visible = block.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    assert.ok(label.toLowerCase().includes(visible.toLowerCase()), `«${label}» no contiene «${visible}»`);
  }
});

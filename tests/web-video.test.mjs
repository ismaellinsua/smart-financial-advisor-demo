// Ejecutar: node --test tests/web-video.test.mjs
// El vídeo de marca de la portada y la letra de los títulos (Sora, la de los vídeos y los anuncios). Los dos se sirven desde
// la propia web y no molestan: en el ordenador el vídeo va arriba del todo, justo debajo de la cabecera; en el móvil en
// vertical, después del titular y sus botones, en su versión 4:3. No tapa nada, no se descarga hasta que hace falta, va sin
// sonido, solo se mueve mientras se ve, se puede pausar, y nunca arranca solo si el visitante pide menos movimiento o ahorro
// de datos.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, statSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname, join } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docs = resolve(root, 'docs');
const read = (rel) => readFileSync(resolve(docs, rel), 'utf8');
const home = read('index.html');
const css = read('assets/site.css');
const js = read('assets/site.js');
const VIDEO = 'assets/video/nirkana-marca.mp4';
const POSTER = 'assets/video/nirkana-marca.webp';
const PHONE = 'assets/video/nirkana-marca-movil.mp4';
const PHONE_MEDIA = '(max-width: 600px) and (orientation: portrait)';

test('en el ordenador el vídeo va arriba del todo, justo debajo de la cabecera, y no quita ni tapa nada de la portada', () => {
  const main = home.indexOf('<main id="contenido">');
  const at = home.indexOf('<section class="film" id="video"');
  assert.ok(main > 0 && at > main, 'dentro del contenido');
  assert.match(home.slice(main + '<main id="contenido">'.length, at), /^\s*(<!--[^]*?-->\s*)*$/, 'es lo primero del contenido');
  assert.ok(at < home.indexOf('<section class="hero" id="inicio">'), 'el inicio (el titular y «Probar gratis») va justo después');
  assert.match(home, /<div class="film-frame">/, 'arriba del todo se ve al momento: no espera a aparecer al bajar');
  assert.match(css, /\.film \+ \.hero \{ padding-top: /, 'el titular sigue al vídeo de cerca');
  assert.match(js, /querySelectorAll\("\.film, \.hero, \.topics-stage"\)/, 'la cabecera sigue oscura sobre el vídeo');
  // Everything else is still there, in its place.
  for (const part of ['<section class="hero" id="inicio">', '<aside class="promo-strip"', '<div class="trust"', '<section id="soluciones"',
    '<section id="temas"', '<section id="contacto"']) assert.ok(home.includes(part), `falta ${part}`);
  assert.doesNotMatch(home, /nirkana-en-12-segundos|reel-band/, 'el vídeo de 12 segundos lo sustituye este');
  assert.doesNotMatch(css, /\.film[^{]*\{[^}]*position: fixed/, 'el vídeo no flota sobre la página');
  // From edge to edge of the screen and always whole on the first screen, under the 68 px header (the film is panoramic:
  // nothing is cut on a normal screen).
  assert.match(css, /\.film-frame \{ position: relative; width: 100%;/);
  assert.match(css, /\.film-video \{[^}]*aspect-ratio: 848 \/ 370; max-height: calc\(100vh - 68px\);\s*max-height: calc\(100svh - 68px\);/);
});

test('la ventana de la portada: nada encima de sus tres puntos y las capturas siguen marcadas como datos de ejemplo', () => {
  // The line above the window and the card that sat on its title bar (on a phone, right on the three dots) are gone.
  assert.doesNotMatch(home, /preview-label|chip c1/);
  assert.doesNotMatch(css, /\.preview-label|\.c1\b/);
  assert.match(home, /<div class="chrome" aria-hidden="true"><i><\/i><i><\/i><i><\/i><span>nirkana · datos de ejemplo<\/span><\/div>/);
  assert.match(home, /<img src="assets\/img\/panel\.webp"[^>]*alt="Resumen de NirKanA con datos de ejemplo: /);
  for (const chip of ['chip c2', 'chip c3']) assert.ok(home.includes(`class="${chip}"`), `sigue ${chip}`);
});

test('ningún vídeo se descarga ni suena por su cuenta', () => {
  const tags = home.match(/<video class="film-video"[^>]*>/g);
  assert.equal(tags.length, 2, 'el del ordenador (arriba) y el del móvil (tras el titular)');
  for (const tag of tags) {
    for (const attr of [' controls', ' muted', ' loop', ' playsinline', ' preload="none"', ` poster="${POSTER}"`,
      ' aria-describedby="video-descripcion"']) {
      assert.ok(tag.includes(attr), `falta ${attr.trim()}`);
    }
    assert.doesNotMatch(tag, /autoplay/, 'lo arranca site.js solo cuando se ve, nunca el navegador al cargar');
  }
  assert.ok(tags[0].includes(' width="848" height="370"') && tags[1].includes(' width="640" height="480"'));
  assert.match(home, /<p class="sr-only" id="video-descripcion">Vídeo sin diálogos, con música\./);
});

test('en el móvil en vertical el vídeo va después del titular y sus botones, en su versión 4:3', () => {
  // Each film carries only its own cut: the panoramic one above, the 4:3 one inside the hero.
  const top = home.slice(home.indexOf('<section class="film" id="video"'), home.indexOf('<section class="hero" id="inicio">'));
  assert.ok(top.includes(`<source src="${VIDEO}" type="video/mp4">`) && !top.includes(PHONE));
  const copy = home.indexOf('<div class="hero-copy">'), at = home.indexOf('<div class="film-frame film-phone">');
  assert.ok(copy > 0 && at > copy && at < home.indexOf('<div class="scene" data-tilt'), 'entre el titular con sus botones y la captura');
  const phone = home.slice(at, home.indexOf('<div class="scene" data-tilt'));
  assert.ok(phone.includes(`<source src="${PHONE}" type="video/mp4">`) && !phone.includes(VIDEO));
  for (const button of ['data-film-sound', 'data-film-toggle']) assert.ok(phone.includes(button), `falta ${button}`);
  // Only one of the two is ever shown: the phone one on a phone held upright, the one above everywhere else.
  assert.match(css, /\.film-phone \{ display: none; \}/);
  assert.match(css, /\.film-phone \.film-video \{ aspect-ratio: 4 \/ 3; max-height: none; object-position: 6\.8% 50%; \}/);
  const block = css.slice(css.indexOf(`@media ${PHONE_MEDIA} {`));
  assert.ok(block.length < css.length, 'falta el bloque del móvil en vertical');
  assert.match(block, /^@media[^{]*\{\s*\.film \{ display: none; \}\s*\.film \+ \.hero \{ padding-top: 48px; \}\s*\.film-phone \{ display: block;/);
  // Both are driven by the same code: each plays only while it is on screen (a hidden one never is).
  assert.match(js, /document\.querySelectorAll\("\.film-frame"\)\.forEach/);
});

test('el vídeo y su portada pesan poco', () => {
  assert.ok(statSync(resolve(docs, VIDEO)).size < 2_500_000, 'el vídeo debe quedar por debajo de 2,5 MB');
  assert.ok(statSync(resolve(docs, PHONE)).size < 2_500_000, 'el del móvil, también');
  assert.ok(statSync(resolve(docs, POSTER)).size < 60_000, 'la portada debe quedar por debajo de 60 KB');
});

test('se ve solo mientras está en pantalla, se puede pausar y activar el sonido, y sin JavaScript quedan los controles del navegador', () => {
  assert.match(js, /document\.querySelectorAll\("\.film-frame"\)/);
  assert.match(js, /let wanted = !reduceMotion && !\(navigator\.connection && navigator\.connection\.saveData\);/);
  assert.match(js, /new IntersectionObserver\(/);
  assert.match(js, /film\.controls = false;/);
  assert.match(js, /started\.catch\(stop\)/);
  assert.match(js, /lastSource\.addEventListener\("error", stop\)/);
  assert.match(js, /"Pausar el vídeo"/);
  assert.match(js, /"Activar sonido" : "Silenciar"/);
  // The page's own buttons start hidden: without JavaScript only the browser's controls are there.
  assert.match(home, /data-film-sound aria-label="Activar sonido" hidden>/);
  assert.match(home, /data-film-toggle aria-label="Reproducir el vídeo" hidden>/);
  for (const icon of ['i-play', 'i-pause', 'i-sound', 'i-mute']) assert.match(home, new RegExp(`<symbol id="${icon}"`));
});

test('el vídeo tiene sus datos estructurados (VideoObject) y apuntan a archivos que existen', () => {
  const blocks = [...home.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));
  const video = blocks.filter((b) => b['@type'] === 'VideoObject');
  assert.equal(video.length, 1, 'un solo bloque VideoObject');
  assert.equal(video[0].duration, 'PT40S');
  assert.equal(video[0].contentUrl, `https://nirkana.es/${VIDEO}`);
  assert.equal(video[0].thumbnailUrl, `https://nirkana.es/${POSTER}`);
});

test('los títulos grandes usan Sora servida desde la web, sin saltos al llegar, y la portada la precarga', () => {
  // One file only: a second preload delayed the first paint of the home page in Lighthouse.
  const file = 'sora-latin-800.woff2';
  assert.ok(statSync(resolve(docs, 'assets/fonts', file)).size < 30_000, `${file} debe ser ligera`);
  assert.deepEqual(readdirSync(resolve(docs, 'assets/fonts')), [file]);
  assert.ok(css.includes(`@font-face { font-family: "Sora"; src: url("fonts/${file}") format("woff2"); font-weight: 800 900; font-display: optional; }`),
    `falta la @font-face de ${file} con font-display: optional`);
  assert.equal((css.match(/@font-face/g) || []).length, 1);
  assert.ok(home.includes(`<link rel="preload" href="assets/fonts/${file}" as="font" type="font/woff2" crossorigin>`), `la portada debe precargar ${file}`);
  assert.equal((home.match(/rel="preload"[^>]*as="font"/g) || []).length, 1);
  assert.match(css, /h1, h2, \.brand[^{]*\{\s*font-family: "Sora", ui-sans-serif, system-ui/);
  assert.match(css, /SIL Open Font License 1\.1/, 'el aviso de la licencia de la fuente');
});

const files = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? files(join(dir, e.name)) : [join(dir, e.name)]));

test('todas las páginas con la hoja de estilos precargan la fuente (con «optional», sin precarga no se vería en la primera visita)', () => {
  const pages = files(docs).filter((f) => f.endsWith('.html')).filter((f) => /<link rel="stylesheet" href="\/?assets\/site\.css">/.test(readFileSync(f, 'utf8')));
  assert.ok(pages.length > 20, `solo ${pages.length} páginas con site.css`);
  const missing = pages.filter((f) => {
    const html = readFileSync(f, 'utf8');
    const prefix = html.match(/<link rel="stylesheet" href="(\/?)assets\/site\.css">/)[1];
    return !html.includes(`<link rel="preload" href="${prefix}assets/fonts/sora-latin-800.woff2" as="font" type="font/woff2" crossorigin>\n  <link rel="stylesheet" href="${prefix}assets/site.css">`);
  });
  assert.deepEqual(missing, [], 'cada página debe precargar la fuente justo antes de la hoja de estilos');
});

test('ninguna página carga fuentes de fuera (Google Fonts u otras)', () => {
  const offenders = files(docs).filter((f) => /\.(html|css)$/.test(f))
    .filter((f) => /fonts\.googleapis|fonts\.gstatic|use\.typekit|fonts\.bunny/.test(readFileSync(f, 'utf8')));
  assert.deepEqual(offenders, []);
});

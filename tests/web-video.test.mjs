// Ejecutar: node --test tests/web-video.test.mjs
// El vídeo de 12 segundos de la portada y la letra de los títulos (Sora, la de los vídeos y los anuncios). Los dos se sirven
// desde la propia web y no molestan: el vídeo no se descarga hasta que hace falta, va sin sonido, solo se mueve mientras se
// ve, se puede pausar, y nunca arranca solo si el visitante pide menos movimiento o ahorro de datos.
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
const VIDEO = 'assets/video/nirkana-en-12-segundos.mp4';
const POSTER = 'assets/video/nirkana-en-12-segundos.webp';

test('el vídeo está en la portada, después de lo esencial y antes de las soluciones', () => {
  const at = home.indexOf('<section id="video" class="reel-band"');
  assert.ok(at > home.indexOf('<div class="trust"'), 'después de la franja de lo esencial');
  assert.ok(at < home.indexOf('<section id="soluciones"'), 'antes de las soluciones');
  assert.match(home, /<h2 id="video-titulo">Mira NirKanA en marcha<\/h2>/);
  assert.match(home, /<figcaption>Pantallas reales con datos de ejemplo<\/figcaption>/);
});

test('el vídeo no se descarga ni suena por su cuenta', () => {
  const tag = home.match(/<video class="reel-video"[^>]*>/)[0];
  for (const attr of [' muted', ' loop', ' playsinline', ' preload="none"', ` poster="${POSTER}"`, ' controls', ' width="720" height="1280"']) {
    assert.ok(tag.includes(attr), `falta ${attr.trim()}`);
  }
  assert.doesNotMatch(tag, /autoplay/, 'lo arranca site.js solo cuando se ve, nunca el navegador al cargar');
  assert.match(home, new RegExp(`<source src="${VIDEO.replace(/\./g, '\\.')}" type="video/mp4">`));
});

test('el vídeo y su portada pesan poco', () => {
  assert.ok(statSync(resolve(docs, VIDEO)).size < 2_000_000, 'el vídeo debe quedar por debajo de 2 MB');
  assert.ok(statSync(resolve(docs, POSTER)).size < 80_000, 'la portada debe quedar por debajo de 80 KB');
});

test('se ve solo cuando está en pantalla, se puede pausar y activar el sonido, y sin JavaScript quedan los controles del navegador', () => {
  assert.match(js, /document\.querySelectorAll\("\.reel"\)/);
  assert.match(js, /let wanted = !reduceMotion && !\(navigator\.connection && navigator\.connection\.saveData\);/);
  assert.match(js, /new IntersectionObserver\(/);
  assert.match(js, /started\.catch\(\(\) => \{ video\.pause\(\); sync\(\); \}\)/);
  assert.match(js, /lastSource\.addEventListener\("error", \(\) => \{ video\.pause\(\); sync\(\); \}\)/);
  assert.match(js, /video\.controls = false;/);
  assert.match(js, /"Pausar el vídeo"/);
  assert.match(js, /"Activar sonido" : "Silenciar"/);
  // The page's own buttons start hidden: without JavaScript only the browser's controls are there.
  assert.match(home, /data-reel-toggle aria-label="Reproducir el vídeo" hidden>/);
  assert.match(home, /data-reel-sound hidden>/);
  for (const icon of ['i-pause', 'i-sound', 'i-mute']) assert.match(home, new RegExp(`<symbol id="${icon}"`));
});

test('el vídeo tiene sus datos estructurados (VideoObject) y apuntan a archivos que existen', () => {
  const blocks = [...home.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));
  const video = blocks.find((b) => b['@type'] === 'VideoObject');
  assert.ok(video, 'falta el bloque VideoObject');
  assert.equal(video.duration, 'PT12S');
  assert.equal(video.contentUrl, `https://nirkana.es/${VIDEO}`);
  assert.equal(video.thumbnailUrl, `https://nirkana.es/${POSTER}`);
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

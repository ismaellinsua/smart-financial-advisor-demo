// Ejecutar: node --test tests/web-guias.test.mjs
// Las guías (docs/guias/, generadas por ops/guias.py) existen para que la gente encuentre la web y llegue a probar NirKanA o a
// escribir: cada una tiene que ser una página completa y bien enlazada, con la prueba de 24 horas y el correo a la vista.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docs = resolve(root, 'docs');
const read = (rel) => readFileSync(resolve(docs, rel), 'utf8');
const slugs = readdirSync(resolve(docs, 'guias'), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name).sort();
const hub = read('guias/index.html');
const guides = slugs.map((slug) => [slug, read(`guias/${slug}/index.html`)]);
const SECTORS = ['tpv-restaurantes', 'programa-peluquerias-estetica', 'tpv-tiendas', 'programa-facturacion-autonomos', 'tpv-tienda-online'];
const text = (html) => html.replace(/<script[\s\S]*?<\/script>/g, ' ').replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<svg[\s\S]*?<\/svg>/g, ' ')
  .replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/g, ' ').replace(/\s+/g, ' ').trim();
const blocks = (html) => [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));

test('hay siete guías o más y todas salen en el índice, en el mapa del sitio y en la portada o en un sector', () => {
  assert.ok(slugs.length >= 7, `solo hay ${slugs.length} guías`);
  const sitemap = read('sitemap.xml');
  const home = read('index.html');
  for (const slug of slugs) {
    assert.ok(hub.includes(`href="/guias/${slug}/"`), `${slug}: no está en el índice`);
    assert.ok(sitemap.includes(`<loc>https://nirkana.es/guias/${slug}/</loc>`), `${slug}: no está en el mapa del sitio`);
    const linkedFrom = [home, ...SECTORS.map((s) => read(`${s}/index.html`))].filter((html) => html.includes(`href="/guias/${slug}/"`));
    assert.ok(linkedFrom.length >= 1, `${slug}: ninguna página principal la enlaza`);
  }
  assert.ok(sitemap.includes('<loc>https://nirkana.es/guias/</loc>'));
});

test('cada guía tiene un único h1, canonical propio, migas de pan, Article con fechas y FAQPage con preguntas visibles', () => {
  for (const [slug, html] of guides) {
    assert.equal((html.match(/<h1[ >]/g) || []).length, 1, `${slug}: h1`);
    assert.match(html, new RegExp(`<link rel="canonical" href="https://nirkana\\.es/guias/${slug}/">`), `${slug}: canonical`);
    assert.match(html, /<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">/, slug);
    assert.match(html, /<meta property="og:type" content="article">/, slug);
    for (const tag of ['twitter:title', 'twitter:description', 'twitter:image', 'twitter:image:alt']) assert.ok(html.includes(`name="${tag}"`), `${slug}: ${tag}`);
    const [crumbs, article, faq] = blocks(html);
    assert.equal(crumbs['@type'], 'BreadcrumbList');
    assert.deepEqual(crumbs.itemListElement.map((i) => i.position), [1, 2, 3]);
    assert.equal(crumbs.itemListElement[2].item, `https://nirkana.es/guias/${slug}/`);
    assert.equal(article['@type'], 'Article');
    assert.match(article.datePublished, /^\d{4}-\d{2}-\d{2}$/);
    assert.match(article.dateModified, /^\d{4}-\d{2}-\d{2}$/);
    assert.equal(article.author.name, 'NirKanA');
    assert.ok(article.headline && article.description && article.image.length === 1, slug);
    assert.equal(faq['@type'], 'FAQPage');
    assert.ok(faq.mainEntity.length >= 3, `${slug}: pocas preguntas`);
    const visible = text(html);
    for (const q of faq.mainEntity) {
      assert.ok(visible.includes(q.name), `${slug}: «${q.name}» no está visible`);
      assert.ok(visible.includes(q.acceptedAnswer.text), `${slug}: la respuesta de «${q.name}» no coincide con la visible`);
    }
  }
});

test('cada guía ofrece la prueba de 24 horas y el correo a la vista, y enlaza a su sector y a otras guías', () => {
  for (const [slug, html] of guides) {
    assert.ok((html.match(/data-trial href="\/#contacto"/g) || []).length >= 3, `${slug}: la prueba debe estar en la cabecera, en el cuerpo y al final`);
    assert.ok((html.match(/data-email data-subject="[^"]+"/g) || []).length >= 2, `${slug}: el correo debe estar en el cuerpo y al final`);
    assert.doesNotMatch(html.replace(/<script[\s\S]*?<\/script>/g, ''), /nirkana\.oficial@gmail\.com/, `${slug}: el correo no se escribe en el HTML, lo pone site.js`);
    assert.ok(SECTORS.some((s) => html.includes(`href="/${s}/"`)), `${slug}: no enlaza a ningún sector`);
    const others = new Set([...html.matchAll(/href="\/guias\/([a-z0-9-]+)\/"/g)].map((m) => m[1]).filter((s) => s !== slug));
    assert.ok(others.size >= 2, `${slug}: debe enlazar al menos a dos guías más`);
    assert.match(html, /<a class="here" href="\/guias\/" aria-current="page">Guías<\/a>/, `${slug}: «Guías» debe verse como la sección actual`);
  }
});

test('el índice «En esta guía» apunta a secciones que existen y las secciones tienen identificadores únicos', () => {
  for (const [slug, html] of guides) {
    const toc = [...html.match(/<nav class="toc"[\s\S]*?<\/nav>/)[0].matchAll(/href="#([a-z0-9-]+)"/g)].map((m) => m[1]);
    const ids = [...html.matchAll(/<section class="guide-sec[^"]*" id="([a-z0-9-]+)"/g)].map((m) => m[1]);
    assert.equal(new Set(ids).size, ids.length, `${slug}: identificadores repetidos`);
    for (const id of toc) assert.ok(ids.includes(id), `${slug}: #${id} no existe`);
    assert.ok(toc.length >= 5, `${slug}: índice demasiado corto`);
  }
});

test('cada guía tiene contenido de verdad (más de 600 palabras) y no repite el de otra', () => {
  const bodies = new Map();
  for (const [slug, html] of guides) {
    // el bloque «Sigue leyendo» y la llamada a la prueba son comunes a todas: se comparan solo los textos de cada guía
    const article = html.match(/<article class="guide">[\s\S]*?<\/article>/)[0]
      .replace(/<section class="guide-sec" id="relacionadas">[\s\S]*?<\/section>/, '').replace(/<aside class="guide-cta"[\s\S]*?<\/aside>/, '');
    const body = text(article);
    assert.ok(body.split(' ').length >= 600, `${slug}: solo ${body.split(' ').length} palabras`);
    bodies.set(slug, body);
  }
  const paragraphs = [...bodies.entries()].flatMap(([slug, body]) => body.split(/(?<=[.!?])\s+/).filter((p) => p.length > 140).map((p) => [p, slug]));
  const seen = new Map();
  for (const [p, slug] of paragraphs) {
    if (seen.has(p) && seen.get(p) !== slug) assert.fail(`la frase «${p.slice(0, 60)}…» está en ${seen.get(p)} y en ${slug}`);
    seen.set(p, slug);
  }
});

test('«Guías» está en la navegación y en el pie de todas las páginas indexables, y las guías cumplen la CSP', () => {
  const pages = ['index.html', ...SECTORS.map((s) => `${s}/index.html`), 'guias/index.html', ...slugs.map((s) => `guias/${s}/index.html`)];
  for (const rel of pages) {
    const html = read(rel);
    assert.match(html, /<nav aria-label="Principal" id="menu">[\s\S]*?href="\/guias\/"[^>]*>Guías<\/a>[\s\S]*?<\/nav>/, `${rel}: falta «Guías» en el menú`);
    assert.match(html, /<footer class="foot">[\s\S]*href="\/guias\/">Guías<\/a>[\s\S]*<\/footer>/, `${rel}: falta «Guías» en el pie`);
  }
  for (const rel of ['guias/index.html', ...slugs.map((s) => `guias/${s}/index.html`)]) {
    const html = read(rel);
    assert.doesNotMatch(html, /\sstyle="|\son(click|load|error)=/i, `${rel}: estilos o eventos en línea`);
    const scripts = html.replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/g, '').match(/<script\b[^>]*>/g) || [];
    assert.ok(scripts.every((tag) => /\ssrc="\/assets\/site\.js"/.test(tag)), `${rel}: scripts en línea`);
  }
});

test('cada página de sector enlaza a tres guías y enseña el correo en su llamada final', () => {
  for (const s of SECTORS) {
    const html = read(`${s}/index.html`);
    const section = html.match(/<p class="eyebrow">Guías<\/p>[\s\S]*?<\/section>/)[0];
    assert.equal((section.match(/href="\/guias\/[a-z0-9-]+\/"/g) || []).length, 3, `${s}: guías relacionadas`);
    assert.match(html, /<p class="mail-line" data-email-wrap hidden><span>O escríbenos a <a data-email data-subject="[^"]+"><\/a><\/span><\/p>/, `${s}: correo en la llamada final`);
  }
});

test('la portada enlaza al índice de guías y declara el sitio con datos estructurados WebSite', () => {
  const home = read('index.html');
  assert.match(home, /<section id="guias">[\s\S]*href="\/guias\/">Ver todas las guías/);
  const site = blocks(home).find((b) => b['@type'] === 'WebSite');
  assert.ok(site && site.url === 'https://nirkana.es/' && site.name === 'NirKanA' && site.inLanguage === 'es');
});

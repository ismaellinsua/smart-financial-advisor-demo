// Ejecutar: node --test tests/web-claims.test.mjs
// La web solo puede prometer lo que la app hace: sin funciones de otro producto, sin cifras inventadas,
// sin conformidad fiscal sin validar, y con todo lo que enlaza o muestra realmente presente.
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docs = resolve(root, 'docs');
const PAGES = ['', 'tpv-restaurantes/', 'programa-peluquerias-estetica/', 'tpv-tiendas/', 'programa-facturacion-autonomos/', 'tpv-tienda-online/'];
const read = (rel) => readFileSync(resolve(docs, rel, rel.endsWith('.html') ? '' : 'index.html'), 'utf8');
const pages = PAGES.map((p) => [p || 'index.html', p ? read(p) : readFileSync(resolve(docs, 'index.html'), 'utf8')]);

// Funciones que tuvo el producto anterior (o que nunca existieron) y que la app de hoy no tiene.
const FORBIDDEN = [
  /informe semanal/i, /informe en pdf/i, /cada lunes/i, /precios recomendados/i, /an[aá]lisis abc/i,
  /rest[aá]uralo|rest[aá]urala/i, /verificaci[oó]n en dos pasos/i, /\bdos pasos\b/i, /automatizaciones/i,
  /traspasos? de stock/i, /formato de shopify/i, /exporta(r)? (tu )?cat[aá]logo a/i,
  /sin (errores|fallos)/i, /nunca (falla|se equivoca)/i, /certificad[oa] (por|de)/i, /homologad[oa]/i, /iso ?27001/i, /\b(?:cumple|conforme)\b(?! con VERI)/i,
  /\b\d[\d.]*\s*\+?\s*(clientes|negocios|usuarios|comercios)\b/i, /\b4[,.]\d\s*\/\s*5\b/, /★{3,}/,
];

const visible = (html) => html.replace(/<script[\s\S]*?<\/script>/g, ' ').replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<[^>]+>/g, ' ');

test('ninguna página promete funciones que la app no tiene ni cifras inventadas', () => {
  for (const [name, html] of pages) {
    const text = visible(html);
    for (const rx of FORBIDDEN) assert.doesNotMatch(text, rx, `${name}: «${text.match(rx)?.[0]}»`);
  }
});

test('VERI*FACTU solo aparece como pregunta con respuesta honesta (sin afirmar conformidad)', () => {
  const home = visible(pages[0][1]);
  assert.match(home, /todav[ií]a no afirmamos\s+conformidad/);
  for (const [name, html] of pages.slice(1)) assert.doesNotMatch(visible(html), /veri\*?factu/i, name);
});

test('todas las imágenes y enlaces internos de cada página existen', () => {
  for (const [name, html] of pages) {
    const refs = [...html.matchAll(/(?:src|href)="(\/[^"#?]*)(?:[#?][^"]*)?"/g)].map((m) => m[1]);
    for (const ref of refs) {
      const file = resolve(docs, '.' + ref);
      const ok = existsSync(file) && (ref.endsWith('/') ? existsSync(resolve(file, 'index.html')) : true) || existsSync(resolve(file, 'index.html'));
      assert.ok(ok, `${name}: ${ref} no existe`);
    }
  }
});

test('toda imagen tiene texto alternativo, ancho y alto (sin saltos de maquetación)', () => {
  for (const [name, html] of pages) {
    for (const tag of (html.match(/<img\b[^>]*>/g) ?? []).filter((t) => /\bsrc=/.test(t))) {
      assert.match(tag, /\balt="[^"]*"/, `${name}: ${tag}`);
      assert.match(tag, /\bwidth="\d+"/, `${name}: ${tag}`);
      assert.match(tag, /\bheight="\d+"/, `${name}: ${tag}`);
    }
  }
});

test('cada página tiene título, descripción, canonical, Open Graph y datos estructurados válidos', () => {
  const titles = new Set();
  const descriptions = new Set();
  for (const [name, html] of pages) {
    const title = html.match(/<title>([^<]+)<\/title>/)?.[1];
    const description = html.match(/<meta name="description" content="([^"]+)"/)?.[1];
    assert.ok(title && title.length <= 70, `${name}: título`);
    assert.ok(description && description.length >= 50 && description.length <= 200, `${name}: descripción (${description?.length})`);
    assert.ok(!titles.has(title) && !descriptions.has(description), `${name}: título o descripción repetidos`);
    titles.add(title);
    descriptions.add(description);
    assert.match(html, /<link rel="canonical" href="https:\/\/nirkana\.es\//, name);
    assert.match(html, /<meta property="og:image" content="https:\/\/nirkana\.es\/assets\/img\/og\.jpg"/, name);
    const blocks = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));
    assert.ok(blocks.length >= 2, `${name}: JSON-LD`);
    const faq = blocks.find((b) => b['@type'] === 'FAQPage');
    assert.ok(faq, `${name}: FAQPage`);
    const text = visible(html).replace(/\s+/g, ' ');
    for (const q of faq.mainEntity) assert.ok(text.includes(q.name), `${name}: «${q.name}» no está visible`);
  }
});

test('el sitemap lista exactamente las páginas públicas', () => {
  const xml = readFileSync(resolve(docs, 'sitemap.xml'), 'utf8');
  const urls = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]).sort();
  const expected = PAGES.map((p) => `https://nirkana.es/${p}`).sort();
  assert.deepEqual(urls, expected);
  assert.match(readFileSync(resolve(docs, 'robots.txt'), 'utf8'), /Sitemap: https:\/\/nirkana\.es\/sitemap\.xml/);
});

test('ningún dato personal ni secreto en el código de la web', () => {
  const files = ['assets/site.js', ...PAGES.map((p) => p + 'index.html')];
  for (const f of files) {
    const s = readFileSync(resolve(docs, f), 'utf8');
    assert.doesNotMatch(s, /(?:api[_-]?key|secret|passw(?:or)?d|token)\s*[:=]\s*["'][^"']{8,}/i, f);
    assert.doesNotMatch(s, /\b\d{8}[A-Z]\b|\b[A-HJNPQRSUVW]\d{7}[0-9A-J]\b/, `${f}: NIF/CIF`);
    const code = f.endsWith('.js') ? s.replace(/^\s*\/\/.*$/gm, '') : s;
    assert.doesNotMatch(code, /(?:\+34|0034)?\s?[6-9]\d{2}[ -]?\d{3}[ -]?\d{3}\b/, `${f}: teléfono`);
  }
  assert.match(readFileSync(resolve(docs, 'assets/site.js'), 'utf8'), /whatsapp: "",/);
});

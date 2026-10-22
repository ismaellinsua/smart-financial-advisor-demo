// Ejecutar: node --test tests/web-publico.test.mjs
// GitHub Pages sirve cada archivo de docs/ tal cual: lo que se guarde ahí lo puede abrir cualquiera en nirkana.es. Por eso docs/ solo
// puede llevar archivos de la web (páginas, estilos, scripts, imágenes, la plantilla de Excel, robots.txt y sitemap.xml). Las notas
// internas, el código de apoyo, la configuración y los datos viven fuera, en notas/, ops/, tests/…; esta prueba falla si algo de eso
// acaba en docs/ (por ejemplo, una nota .md que se guarda en la carpeta equivocada).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname, extname, relative, sep } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docs = resolve(root, 'docs');

const files = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? files(resolve(dir, e.name)) : [resolve(dir, e.name)]));
const all = files(docs).map((f) => relative(docs, f).split(sep).join('/'));

const EXTENSIONS = new Set(['.html', '.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.ico', '.webmanifest', '.xlsx', '.xml', '.txt']);
const NAMES = new Set(['CNAME', '.nojekyll']);

test('docs/ solo lleva archivos de la web: ninguna nota, ningún código de apoyo, ninguna configuración ni datos', () => {
  const intruders = all.filter((f) => !NAMES.has(f) && !EXTENSIONS.has(extname(f).toLowerCase()));
  assert.deepEqual(intruders, [], `estos archivos se publicarían en nirkana.es y no son de la web (muévelos fuera de docs/): ${intruders.join(', ')}`);
});

test('las notas internas no están en docs/ (viven en notas/)', () => {
  assert.deepEqual(all.filter((f) => /\.md$/i.test(f)), [], 'una nota .md en docs/ se publica en nirkana.es');
  assert.ok(existsSync(resolve(root, 'notas')), 'las notas internas deben vivir en notas/');
});

test('solo hay un .txt (robots.txt) y un .xml (sitemap.xml), y ningún archivo oculto salvo .nojekyll', () => {
  assert.deepEqual(all.filter((f) => f.endsWith('.txt')), ['robots.txt']);
  assert.deepEqual(all.filter((f) => f.endsWith('.xml')), ['sitemap.xml']);
  const hidden = all.filter((f) => f.split('/').some((part) => part.startsWith('.') && part !== '.nojekyll'));
  assert.deepEqual(hidden, [], `archivos ocultos en docs/: ${hidden.join(', ')}`);
});

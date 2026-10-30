// Ejecutar: node --test tests/web-herramientas.test.mjs
// Las calculadoras gratuitas de la web (docs/herramientas/, generadas por ops/guias.py) calculan en el navegador con
// docs/assets/herramientas.js: aquí se prueban las cuentas y que cada página es completa, enlazada y cumple la CSP.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import vm from 'node:vm';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docs = resolve(root, 'docs');
const read = (rel) => readFileSync(resolve(docs, rel), 'utf8');
const source = read('assets/herramientas.js');
const C = (() => { const module = { exports: {} }; vm.runInNewContext(source, { module, Intl, CustomEvent: class {}, document: {}, window: {}, setTimeout }, { filename: 'herramientas.js' }); return module.exports; })();
const near = (actual, expected, digits = 2) => assert.ok(Math.abs(actual - expected) < 0.5 * 10 ** -digits, `${actual} ≠ ${expected}`);
// Los espacios de los importes en euros son «no separables»: se comparan sin ellos.
const plain = (s) => s.replace(/\s/g, '');
const pick = ({ base, cuota, total }) => ({ base, cuota, total });
const slugs = readdirSync(resolve(docs, 'herramientas'), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name).sort();
const text = (html) => html.replace(/<script[\s\S]*?<\/script>/g, ' ').replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<svg[\s\S]*?<\/svg>/g, ' ').replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/g, ' ').replace(/\s+/g, ' ').trim();

test('los números se leen como se escriben en España y lo que no es un número no pasa', () => {
  const casos = [['12,5', 12.5], ['12.5', 12.5], ['1.234,56', 1234.56], ['1,234.56', 1234.56], ['1.234', 1234], ['12.500', 12500], ['1.234.567', 1234567], ['1,234,567', 1234567],
    ['1,234', 1.234], ['0.125', 0.125], ['0,125', 0.125], ['  7 € ', 7], ['.5', 0.5], ['5,', 5], ['-3,5', -3.5]];
  for (const [entrada, esperado] of casos) assert.equal(C.leerNumero(entrada), esperado, entrada);
  assert.equal(C.leerNumero(''), null);
  assert.equal(C.leerNumero('   '), null);
  assert.equal(C.leerNumero('€'), null);
  for (const mala of ['abc', '12a', '1,2,3,x', '--4', '1..2', '1.2.3', '1.23.456', '12,34,56']) assert.ok(Number.isNaN(C.leerNumero(mala)), mala);
  assert.equal(C.leerEntero(''), 0);
  assert.equal(C.leerEntero(' 12 '), 12);
  for (const mala of ['-1', '1,5', '2.0', 'x', '1234567']) assert.ok(Number.isNaN(C.leerEntero(mala)), mala);
  assert.equal(C.leerCentimos('10,10'), 1010);
  assert.equal(C.leerCentimos('0,1') + C.leerCentimos('0,2'), 30, 'sin errores de coma flotante');
  assert.equal(C.leerCentimos(''), 0);
  assert.ok(Number.isNaN(C.leerCentimos('-3')));
});

test('el arqueo suma por denominaciones, calcula lo esperado y dice si cuadra, sobra o falta', () => {
  const filas = [[5000, 3], [2000, 7], [1000, 4], [500, 6], [200, 9], [100, 11], [50, 8], [10, 12]]; // 150+140+40+30+18+11+4+1,20 = 394,20 €
  const r = C.arqueo({ filas, fondo: 15000, ventas: 25000, entradas: 0, salidas: 0 });
  assert.equal(r.contado, 39420);
  assert.equal(r.esperado, 40000);
  assert.equal(r.diferencia, -580);
  assert.equal(r.estado, 'falta');
  assert.equal(C.arqueo({ filas, fondo: 14420, ventas: 25000 }).estado, 'cuadra');
  assert.equal(C.arqueo({ filas, fondo: 10000, ventas: 25000 }).estado, 'sobra');
  // entradas suman y salidas restan
  const e = C.arqueo({ filas: [[1000, 10]], fondo: 5000, ventas: 6000, entradas: 1000, salidas: 2000 });
  assert.equal(e.esperado, 10000);
  assert.equal(e.estado, 'cuadra');
  // fondo para mañana
  assert.equal(C.arqueo({ filas: [[1000, 30]], dejar: 10000 }).retirar, 20000);
  assert.equal(C.arqueo({ filas: [[1000, 5]], dejar: 10000 }).retirar, -5000);
  assert.equal(C.arqueo({ filas: [[1000, 5]] }).retirar, null);
});

test('el margen parte del coste y del margen deseado (no es un recargo) y añade el IVA al final', () => {
  const r = C.margen({ modo: 'margen', coste: 10, margenPct: 40, ivaPct: 21 });
  near(r.neto, 16.6667, 4);
  near(r.iva, 3.5, 2);
  near(r.pvp, 20.1667, 4);
  near(r.beneficio, 6.6667, 4);
  near(r.margenPct, 40, 6);
  near(r.recargoPct, 66.6667, 4); // el mismo producto, visto como recargo sobre el coste
  assert.equal(C.eurosDeImporte(r.pvp).replace(/\s/g, ''), '20,17€');
  assert.equal(C.porcentaje(r.recargoPct).replace(/\s/g, ''), '66,7%');
  // con un recargo del 40 % el margen real es del 28,6 %
  const recargo = C.margen({ modo: 'precio', coste: 10, precio: 14, precioConIva: false });
  near(recargo.margenPct, 28.5714, 4);
  near(recargo.recargoPct, 40, 6);
});

test('con el precio de venta con IVA incluido se saca el margen sin contar el IVA', () => {
  const r = C.margen({ modo: 'precio', coste: 11, precio: 24.99, precioConIva: true, ivaPct: 21 });
  near(r.neto, 20.6529, 4);
  near(r.beneficio, 9.6529, 4);
  near(r.margenPct, 46.74, 2);
  near(r.recargoPct, 87.75, 2);
  near(r.pvp, 24.99, 6);
  // lo mismo con el IVA reducido y el precio sin IVA
  const reducido = C.margen({ modo: 'precio', coste: 2, precio: 3, precioConIva: false, ivaPct: 10 });
  near(reducido.pvp, 3.3, 6);
  near(reducido.iva, 0.3, 6);
  near(reducido.margenPct, 33.3333, 4);
  // exento
  near(C.margen({ modo: 'precio', coste: 2, precio: 3, precioConIva: true, ivaPct: 0 }).neto, 3, 6);
});

test('un descuento se aplica al precio con IVA y se dice cuántas unidades más hay que vender para ganar lo mismo', () => {
  const d = C.margen({ modo: 'margen', coste: 10, margenPct: 40, ivaPct: 21, descuentoPct: 20 }).descuento;
  near(d.neto, 13.3333, 4);
  near(d.beneficio, 3.3333, 4);
  near(d.margenPct, 25, 4);
  near(d.masUnidadesPct, 100, 4); // beneficio 6,67 → 3,33: hay que vender el doble
  assert.equal(d.pierde, false);
  near(d.pvp, 16.1333, 4);
  // un descuento que se come todo el margen
  const sinGanancia = C.margen({ modo: 'margen', coste: 10, margenPct: 20, ivaPct: 21, descuentoPct: 20 }).descuento;
  assert.equal(sinGanancia.pierde, true);
  assert.equal(sinGanancia.masUnidadesPct, null);
  assert.equal(C.margen({ modo: 'margen', coste: 10, margenPct: 20, ivaPct: 21, descuentoPct: 0 }).descuento, undefined);
});

test('el IVA se añade multiplicando y se quita dividiendo, nunca restando el porcentaje, al céntimo', () => {
  assert.deepEqual(pick(C.iva({ modo: 'anadir', importe: 10000, ivaPct: 21 })), { base: 10000, cuota: 2100, total: 12100 });
  const quitar = C.iva({ modo: 'quitar', importe: 12100, ivaPct: 21 });
  assert.deepEqual(pick(quitar), { base: 10000, cuota: 2100, total: 12100 });
  assert.equal(quitar.restarMal, 9559);                         // lo que sale restando el 21 %: no es la base
  assert.deepEqual(pick(C.iva({ modo: 'quitar', importe: 1000, ivaPct: 10 })), { base: 909, cuota: 91, total: 1000 });
  assert.deepEqual(pick(C.iva({ modo: 'anadir', importe: 1999, ivaPct: 4 })), { base: 1999, cuota: 80, total: 2079 });
  assert.deepEqual(pick(C.iva({ modo: 'anadir', importe: 0, ivaPct: 21 })), { base: 0, cuota: 0, total: 0 });
  for (const importe of [12100, 1000, 1, 99999, 123456789]) {      // al quitar, base + IVA es siempre el importe exacto
    for (const ivaPct of [21, 10, 4]) {
      const r = C.iva({ modo: 'quitar', importe, ivaPct });
      assert.equal(r.base + r.cuota, importe);
    }
  }
  assert.ok(C.iva({ modo: 'anadir', importe: -1, ivaPct: 21 }).error);
  assert.ok(C.iva({ modo: 'anadir', importe: 10.5, ivaPct: 21 }).error);
  assert.ok(C.iva({ modo: 'quitar', importe: 100, ivaPct: -4 }).error);
});

test('la calculadora de IVA deja elegir añadir o quitar, los tres tipos, y explica el error de restar el porcentaje', () => {
  const html = read('herramientas/calculadora-de-iva/index.html');
  assert.match(html, /data-calc="iva"/);
  assert.match(html, /value="anadir"[^>]*checked/);
  assert.match(html, /value="quitar"/);
  for (const pct of ['21', '10', '4']) assert.match(html, new RegExp(`<option value="${pct}"`));
  assert.match(html, /<label for="i-importe">/);
  assert.match(html, /divide entre 1,21/i);
  assert.match(html, /95,59/);
});

test('los datos que no valen se rechazan en vez de dar una cifra rara', () => {
  assert.equal(C.margen({ modo: 'margen', coste: 10, margenPct: 100 }).error, 'margen');
  assert.equal(C.margen({ modo: 'margen', coste: 10, margenPct: -5 }).error, 'margen');
  assert.equal(C.margen({ modo: 'precio', coste: 10, precio: 0 }).error, 'precio');
  assert.equal(C.margen({ modo: 'margen', coste: -1, margenPct: 10 }).error, 'coste');
  // coste cero: hay precio y margen del 100 %, pero el recargo no existe
  const gratis = C.margen({ modo: 'precio', coste: 0, precio: 5, precioConIva: false });
  near(gratis.margenPct, 100, 6);
  assert.ok(Number.isNaN(gratis.recargoPct));
  assert.equal(C.porcentaje(gratis.recargoPct), '—');
});

test('el script no escribe en el DOM con HTML de nadie, no usa red ni almacenamiento', () => {
  assert.doesNotMatch(source, /innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(|new Function/);
  assert.doesNotMatch(source, /fetch\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie/);
});

test('hay al menos dos herramientas, con índice, y cada una está en el mapa del sitio y enlazada desde el índice y desde una guía', () => {
  assert.ok(slugs.length >= 2, `solo hay ${slugs.length} herramientas`);
  const hub = read('herramientas/index.html');
  const sitemap = read('sitemap.xml');
  assert.ok(sitemap.includes('<loc>https://nirkana.es/herramientas/</loc>'));
  const guides = readdirSync(resolve(docs, 'guias'), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => read(`guias/${d.name}/index.html`));
  for (const slug of slugs) {
    assert.ok(hub.includes(`href="/herramientas/${slug}/"`), `${slug}: no está en el índice`);
    assert.ok(sitemap.includes(`<loc>https://nirkana.es/herramientas/${slug}/</loc>`), `${slug}: no está en el mapa del sitio`);
    assert.ok(guides.some((html) => html.includes(`href="/herramientas/${slug}/"`)), `${slug}: ninguna guía la enlaza`);
  }
});

test('cada herramienta es una página completa: un único h1, datos estructurados, prueba de 24 h, correo y la CSP', () => {
  for (const slug of slugs) {
    const html = read(`herramientas/${slug}/index.html`);
    assert.equal((html.match(/<h1[ >]/g) || []).length, 1, `${slug}: h1`);
    assert.match(html, new RegExp(`<link rel="canonical" href="https://nirkana\\.es/herramientas/${slug}/">`), `${slug}: canonical`);
    const blocks = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));
    assert.deepEqual(blocks.map((b) => b['@type']), ['BreadcrumbList', 'WebApplication', 'FAQPage'], slug);
    const app = blocks[1];
    assert.equal(app.isAccessibleForFree, true);
    assert.equal(app.offers.price, '0');
    assert.ok(blocks[2].mainEntity.length >= 4, `${slug}: pocas preguntas`);
    assert.ok((html.match(/data-trial href="\/#contacto"/g) || []).length >= 2, `${slug}: prueba de 24 h`);
    assert.ok((html.match(/data-email data-subject="[^"]+"/g) || []).length >= 1, `${slug}: correo`);
    assert.doesNotMatch(html.replace(/<script[\s\S]*?<\/script>/g, ''), /nirkana\.oficial@gmail\.com/, `${slug}: el correo lo pone site.js`);
    assert.doesNotMatch(html, /\sstyle="|\son(click|load|error|input|change)=/i, `${slug}: estilos o eventos en línea`);
    const scripts = html.replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/g, '').match(/<script\b[^>]*>/g) || [];
    assert.deepEqual(scripts.map((t) => t.match(/src="([^"]+)"/)?.[1]).sort(), ['/assets/herramientas.js', '/assets/site.js'], `${slug}: scripts`);
    assert.match(html, /<noscript>[\s\S]*?JavaScript[\s\S]*?<\/noscript>/, `${slug}: aviso sin JavaScript`);
    assert.match(html, /No se envía ni se guarda nada/, `${slug}: debe decir que no se guarda nada`);
    assert.ok(text(html).split(' ').length >= 450, `${slug}: poco texto`);
  }
});

test('la calculadora de arqueo tiene todas las denominaciones del euro, etiquetas y una plantilla de Excel que existe', () => {
  const html = read('herramientas/calculadora-de-arqueo-de-caja/index.html');
  const valores = [...html.matchAll(/data-valor="(\d+)"/g)].map((m) => Number(m[1]));
  assert.deepEqual(valores, [50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1]);
  for (const v of valores) {
    assert.match(html, new RegExp(`<label for="den-${v}">`), `falta la etiqueta de ${v}`);
    assert.match(html, new RegExp(`id="den-${v}"[^>]*inputmode="numeric"`), `falta el teclado numérico de ${v}`);
    assert.match(html, new RegExp(`data-sub="${v}"`), `falta el subtotal de ${v}`);
  }
  for (const nombre of ['fondo', 'ventas', 'entradas', 'salidas', 'dejar']) assert.match(html, new RegExp(`data-in="${nombre}"`), nombre);
  for (const nombre of ['contado', 'esperado', 'estado', 'estado-titulo', 'estado-detalle', 'retirar']) assert.match(html, new RegExp(`data-out="${nombre}"`), nombre);
  assert.match(html, /<div class="tc-estado"[^>]*role="status"[^>]*aria-live="polite"/);
  const enlace = html.match(/<a class="btn[^"]*" href="(\/descargas\/[^"]+\.xlsx)"[^>]*data-evento="plantilla-arqueo"/)?.[1];
  assert.ok(enlace && existsSync(resolve(docs, '.' + enlace)), 'falta el enlace a la plantilla de Excel o no existe');
  assert.ok(statSync(resolve(docs, '.' + enlace)).size < 60000, 'la plantilla debe ser pequeña');
  assert.equal(readFileSync(resolve(docs, '.' + enlace)).subarray(0, 2).toString(), 'PK', 'un .xlsx es un ZIP');
});

test('la calculadora de margen pide lo necesario, explica la diferencia entre margen y recargo y lleva la fórmula', () => {
  const html = read('herramientas/calculadora-de-margen/index.html');
  for (const nombre of ['coste', 'margen', 'precio', 'iva-incluido', 'iva', 'descuento']) assert.match(html, new RegExp(`data-in="${nombre}"`), nombre);
  assert.match(html, /name="modo" value="margen" checked/);
  assert.match(html, /name="modo" value="precio"/);
  for (const nombre of ['resultados', 'aviso', 'neto', 'iva', 'pvp', 'beneficio', 'margen', 'recargo', 'descuento', 'd-pvp', 'd-beneficio', 'd-margen', 'd-texto']) assert.match(html, new RegExp(`data-out="${nombre}"`), nombre);
  for (const rate of ['21', '10', '4', '0']) assert.match(html, new RegExp(`<option value="${rate}"`), `IVA ${rate}`);
  const visible = text(html);
  assert.match(visible, /precio sin IVA = coste ÷ \(1 − margen\)/i);
  assert.match(visible, /margen y recargo no son lo mismo/i);
});

test('el cálculo de la calculadora de arqueo coincide con la plantilla de Excel (mismos conceptos y fórmulas)', () => {
  // la plantilla la genera ops/plantillas.py; aquí solo se comprueba que el fichero publicado es el que describe la página
  const html = read('herramientas/calculadora-de-arqueo-de-caja/index.html');
  assert.match(text(html), /plantilla de Excel/i);
  assert.match(html, /\/descargas\/plantilla-arqueo-de-caja\.xlsx/);
});

test('el resultado se anuncia a los lectores de pantalla y los campos inválidos se marcan', () => {
  assert.match(source, /aria-invalid/);
  const arqueo = read('herramientas/calculadora-de-arqueo-de-caja/index.html');
  const margen = read('herramientas/calculadora-de-margen/index.html');
  for (const html of [arqueo, margen]) {
    // todo campo de texto tiene su etiqueta
    for (const id of [...html.matchAll(/<input[^>]*\bid="([^"]+)"[^>]*type="text"|<input[^>]*type="text"[^>]*\bid="([^"]+)"/g)].map((m) => m[1] || m[2])) {
      assert.match(html, new RegExp(`<label[^>]*for="${id}"`), `el campo ${id} no tiene etiqueta`);
    }
  }
});

// Ejecutar: node --test tests/web-rediseno.test.mjs
// La portada ofrece seis soluciones por tipo de negocio y un formulario que las entiende: lo que enlaza, lo que se
// preselecciona y lo que promete tienen que coincidir.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const home = readFileSync(resolve(root, 'docs/index.html'), 'utf8');
const site = readFileSync(resolve(root, 'docs/assets/site.js'), 'utf8');
const visible = home.replace(/<script[\s\S]*?<\/script>/g, ' ').replace(/<svg[\s\S]*?<\/svg>/g, ' ').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

const formOptions = (name) => {
  const select = home.match(new RegExp(`<select name="${name}"[^>]*>([\\s\\S]*?)</select>`))[1];
  return [...select.matchAll(/<option(?: value="([^"]*)")?[^>]*>([^<]*)<\/option>/g)].map((m) => ({ value: m[1] ?? m[2], label: m[2] }));
};

const SECTORS = ['hosteleria', 'belleza', 'comercio', 'autonomo', 'pyme', 'otros'];

test('hay seis soluciones por tipo de negocio, cada una con su pestaña y su panel', () => {
  assert.match(home, /<h2>Una solución para cada tipo de negocio<\/h2>/);
  for (const id of SECTORS) {
    assert.match(home, new RegExp(`role="tab" id="tab-${id}" aria-controls="p-${id}"`), id);
    assert.match(home, new RegExp(`role="tabpanel" id="p-${id}" aria-labelledby="tab-${id}"`), id);
  }
  assert.equal((home.match(/role="tab"/g) || []).length, SECTORS.length);
  assert.equal((home.match(/aria-selected="true"/g) || []).length, 1, 'solo una pestaña seleccionada');
  assert.equal((home.match(/role="tabpanel"[^>]*\bhidden\b/g) || []).length, SECTORS.length - 1, 'solo un panel visible');
});

test('cada solución cuenta el problema, la solución y el beneficio, y tiene su botón hacia el formulario', () => {
  const panels = home.split('role="tabpanel"').slice(1);
  assert.equal(panels.length, SECTORS.length);
  for (const panel of panels) {
    for (const part of ['El problema', 'La solución', 'Lo que ganas']) assert.ok(panel.includes(`<dt>${part}</dt>`), part);
    assert.match(panel, /<a class="btn magnet" href="#contacto" data-sector="[^"]+"/);
  }
});

test('los sectores del selector, de los botones y del script son exactamente las opciones del formulario', () => {
  const types = formOptions('tipo').map((o) => o.value).filter(Boolean);
  assert.deepEqual(types, ['Hostelería', 'Belleza y estética', 'Comercio', 'Autónomo', 'Pyme', 'Otro']);
  for (const [, value] of home.matchAll(/data-sector="([^"]+)"/g)) assert.ok(types.includes(value), `data-sector «${value}» no es una opción`);
  const map = site.match(/const TAB_TYPES = \{([\s\S]*?)\};/)[1];
  const pairs = [...map.matchAll(/"tab-([a-z]+)": "([^"]+)"/g)];
  assert.deepEqual(pairs.map((m) => m[1]), SECTORS);
  for (const [, , value] of pairs) assert.ok(types.includes(value), `TAB_TYPES «${value}» no es una opción`);
});

test('los botones de petición preseleccionan una solicitud que existe', () => {
  const requests = formOptions('solicitud').map((o) => o.label);
  for (const wanted of ['Solicitar información', 'Pedir presupuesto', 'Consultar una solución']) assert.ok(requests.includes(wanted), wanted);
  for (const [, label] of home.matchAll(/data-request="([^"]+)"/g)) assert.ok(requests.includes(label), `data-request «${label}» no es una opción`);
});

test('el formulario pide solo lo necesario: nombre, email, tipo de negocio, qué necesita y teléfono opcional', () => {
  const form = home.match(/<form id="contact-form"[\s\S]*?<\/form>/)[0];
  const names = [...form.matchAll(/\bname="([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(names, ['_gotcha', 'consentimiento', 'email', 'mensaje', 'nombre', 'solicitud', 'telefono', 'tipo']);
  assert.match(form, /name="consentimiento" required/);
  assert.match(form, /<a href="privacidad\.html">aviso de privacidad<\/a>/);
  assert.doesNotMatch(form.match(/<input name="telefono"[^>]*>/)[0], /required/);
  assert.match(form, /class="hp"[^>]*aria-hidden="true"/);
  assert.doesNotMatch(site, /fields\.negocio/);
});

test('el mensaje principal, la demostración y «Así trabajamos» dicen lo que deben', () => {
  assert.match(home, /<h1>Soluciones digitales para <span class="grad">hacer crecer tu negocio\.<\/span><\/h1>/);
  assert.match(visible, /Desarrollamos herramientas digitales para autónomos, comercios y empresas que quieren simplificar su gestión y trabajar de forma más eficiente\./);
  assert.match(home, /href="#soluciones">Descubrir soluciones/);
  assert.match(home, /data-demo href="\/demo\/">Probar demostración/);
  assert.match(visible, /Cuéntanos cómo funciona tu negocio y estudiaremos qué solución digital puede adaptarse a tus necesidades\./);
  const demo = home.match(/<section id="demostracion"[\s\S]*?<\/section>/)[0];
  for (const word of ['Qué puedes comprobar', 'Cómo se entra', 'Límites', 'Duración', '24 horas', 'data-demo', 'data-trial', 'Cuéntanos tu caso']) assert.ok(demo.includes(word), word);
  assert.equal([...home.match(/<ol class="timeline four">[\s\S]*?<\/ol>/)[0].matchAll(/<li /g)].length, 4);
  for (const step of ['Cuéntanos qué necesita tu negocio', 'Analizamos tu situación', 'Proponemos una solución', 'Acordamos cómo ponerlo en marcha']) assert.ok(home.includes(step), step);
});

test('las preguntas frecuentes incluyen las cinco de la propuesta', () => {
  for (const q of ['¿NirKanA sirve para mi tipo de negocio?', '¿Puedo solicitar una solución personalizada?', '¿Cómo puedo conocer el producto?',
                   '¿Cómo solicito un presupuesto?', '¿Necesito conocimientos informáticos?']) assert.ok(visible.includes(q), q);
});

test('no promete soporte, mantenimiento, garantías, clientes ni opiniones que no existen', () => {
  assert.doesNotMatch(visible, /\b(soporte|mantenimiento|(?<!no una )garant[ií]a|testimonios?|casos de [eé]xito|nuestros clientes|clientes satisfechos|proyectos (terminados|realizados))\b/i);
  // la calculadora plegada usa los números que el propio visitante mueve (25 % de partida), no una cifra nuestra
  const claims = home.replace(/<details class="calc-box"[\s\S]*?<\/details>\s*<\/div>\s*<\/section>/, '').replace(/<[^>]+>/g, ' ');
  assert.doesNotMatch(claims, /\b\d+\s*%/, 'ninguna cifra de ahorro o productividad inventada');
});

test('la portada cumple la CSP (sin estilos ni scripts en línea), tiene un único h1 y conserva los anclajes antiguos', () => {
  assert.doesNotMatch(home, /\sstyle="/);
  const scripts = home.replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/g, '').match(/<script\b[^>]*>/g) || [];
  assert.ok(scripts.every((tag) => /\ssrc="assets\/site\.js"/.test(tag)), `scripts en línea: ${scripts}`);
  assert.doesNotMatch(home, /\son(click|load|error)=/i);
  assert.equal((home.match(/<h1[ >]/g) || []).length, 1);
  for (const anchor of ['sectores', 'soluciones', 'funciones', 'demostracion', 'recorrido', 'seguridad', 'como', 'precio', 'calculadora', 'preguntas', 'contacto'])
    assert.match(home, new RegExp(`id="${anchor}"`), anchor);
});

test('la medición cuenta sectores consultados y peticiones desde cada sector, sin cookies', () => {
  assert.match(site, /countVisit\("soluciones-vistas"/);
  assert.match(site, /countVisit\(`sector-\$\{tab\.id\.replace\("tab-", ""\)\}`/);
  assert.match(site, /countVisit\(`contacto-\$\{slug\(sector\)\}`/);
  assert.doesNotMatch(site, /document\.cookie|localStorage|sessionStorage/);
});

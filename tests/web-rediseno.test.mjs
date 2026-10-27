// Ejecutar: node --test tests/web-rediseno.test.mjs
// La portada ofrece seis soluciones por tipo de negocio y un formulario que las entiende: lo que enlaza, lo que se
// preselecciona y lo que promete tienen que coincidir.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
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

const sectorsBlock = home.match(/<section id="soluciones"[\s\S]*?<\/section>/)[0];

test('hay seis soluciones por tipo de negocio, cada una con su pestaña y su panel', () => {
  assert.match(sectorsBlock, /<h2>Una solución para cada tipo de negocio<\/h2>/);
  for (const id of SECTORS) {
    assert.match(sectorsBlock, new RegExp(`role="tab" id="tab-${id}" aria-controls="p-${id}"`), id);
    assert.match(sectorsBlock, new RegExp(`role="tabpanel" id="p-${id}" aria-labelledby="tab-${id}"`), id);
  }
  assert.equal((sectorsBlock.match(/role="tab"/g) || []).length, SECTORS.length);
  assert.equal((sectorsBlock.match(/aria-selected="true"/g) || []).length, 1, 'solo una pestaña seleccionada');
  assert.equal((sectorsBlock.match(/role="tabpanel"[^>]*\bhidden\b/g) || []).length, SECTORS.length - 1, 'solo un panel visible');
});

test('cada solución cuenta el problema, la solución y el beneficio, y tiene su botón hacia el formulario', () => {
  const panels = sectorsBlock.split('role="tabpanel"').slice(1);
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
  assert.deepEqual(names, ['_gotcha', 'consentimiento', 'email', 'mensaje', 'nombre', 'promocion', 'solicitud', 'telefono', 'tipo']);
  assert.match(form, /name="consentimiento" required/);
  assert.match(form, /<a href="privacidad\.html">aviso de privacidad<\/a>/);
  assert.doesNotMatch(form.match(/<input name="telefono"[^>]*>/)[0], /required/);
  assert.match(form, /class="hp"[^>]*aria-hidden="true"/);
  assert.doesNotMatch(site, /fields\.negocio/);
});

test('el mensaje principal, la demostración y «Así trabajamos» dicen lo que deben', () => {
  assert.match(home, /<h1>Soluciones digitales para <span class="grad">hacer crecer tu negocio\.<\/span><\/h1>/);
  assert.match(visible, /Cobra, organiza las citas, controla el stock y haz las facturas desde el móvil o la tablet\. Para bares, tiendas, peluquerías, autónomos y pymes, sin instalar nada\./);
  assert.match(home, /href="#soluciones">Descubrir soluciones/);
  assert.match(home, /data-demo href="\/demo\/">Probar demostración/);
  assert.match(visible, /Cuéntanos cómo funciona tu negocio y estudiaremos qué solución digital puede adaptarse a tus necesidades\./);
  const demo = home.match(/<section id="demostracion"[\s\S]*?<\/section>/)[0];
  for (const word of ['Qué incluye', 'Cómo se entra', 'Límites', '24 horas', 'ficticios', 'data-demo', 'data-trial']) assert.ok(demo.includes(word), word);
  assert.equal([...home.match(/<ol class="timeline four">[\s\S]*?<\/ol>/)[0].matchAll(/<li /g)].length, 4);
  for (const step of ['Cuéntanos qué necesita tu negocio', 'Analizamos tu situación', 'Proponemos una solución', 'Acordamos cómo ponerlo en marcha']) assert.ok(home.includes(step), step);
});

test('las preguntas frecuentes incluyen las cinco de la propuesta', () => {
  for (const q of ['¿NirKanA sirve para mi tipo de negocio?', '¿Puedo solicitar una solución personalizada?', '¿Cómo puedo conocer el producto?',
                   '¿Cómo solicito un presupuesto?', '¿Necesito conocimientos informáticos?']) assert.ok(visible.includes(q), q);
});

test('no promete soporte, mantenimiento, garantías, clientes ni opiniones que no existen', () => {
  // las condiciones de la promoción nombran el mantenimiento para EXCLUIRLO del descuento, no para ofrecerlo
  const offers = visible.replace(/No se aplica a cuotas mensuales, mantenimiento, desarrollos adicionales ni otros conceptos\./, '');
  assert.doesNotMatch(offers, /\b(soporte|mantenimiento|(?<!no una )garant[ií]a|testimonios?|casos de [eé]xito|nuestros clientes|clientes satisfechos|proyectos (terminados|realizados))\b/i);
  // la calculadora plegada usa los números que el propio visitante mueve (25 % de partida), no una cifra nuestra
  const claims = home.replace(/<details class="calc-box"[\s\S]*?<\/details>\s*<\/div>\s*<\/section>/, '').replace(/<[^>]+>/g, ' ');
  const percents = [...claims.matchAll(/\b\d+\s*%/g)].map((m) => m[0].replace(/\s/g, ''));
  assert.ok(percents.length > 0 && percents.every((p) => p === '20%'), `solo el 20 % de la promoción: ${percents}`);
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

test('la demostración de 24 horas se presenta con su texto, su captura real y sus dos botones', () => {
  const demo = home.match(/<section id="demostracion"[\s\S]*?<\/section>/)[0];
  assert.match(demo, /<h2>Descubre NirKanA durante 24 horas<\/h2>/);
  assert.match(demo, /Conoce nuestra tecnología, explora las funcionalidades disponibles y descubre cómo podemos ayudarte a digitalizar tu negocio\./);
  assert.match(demo, /data-trial href="#contacto">Probar gratis 24 horas/);
  assert.match(demo, /data-request="Solicitar información">Solicitar información<\/a>/);
  assert.match(demo, /<img src="assets\/img\/shots\/resumen-c\.webp" width="1200" height="750" alt="[^"]+"/);
});

test('la promoción del 20 % solo habla de la puesta en marcha y no inventa fechas, urgencia ni precios originales', () => {
  assert.match(visible, /Oferta especial: 20 % de descuento en la puesta en marcha de tu solución NirKanA\./);
  assert.match(visible, /Contacta ahora con nosotros para solicitar información y aprovechar la promoción\./);
  assert.match(visible, /Contactar y conseguir mi 20 % de descuento/);
  assert.match(home, /data-promo data-request="Solicitar información">/);
  const terms = home.match(/<details class="more-box" id="promocion-condiciones">[\s\S]*?<\/details>/)[0].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
  assert.match(terms, /solo al precio de la puesta en marcha/);
  assert.match(terms, /No se aplica a cuotas mensuales, mantenimiento, desarrollos adicionales ni otros conceptos/);
  const promo = [home.match(/<aside class="promo-strip"[\s\S]*?<\/aside>/)[0], home.match(/<div class="promo-card"[\s\S]*?<\/details>/)[0]].join(' ').replace(/<[^>]+>/g, ' ');
  assert.doesNotMatch(promo, /(hasta el|hasta (?:el )?\d|últimas?|solo hoy|solo por tiempo|tiempo limitado|quedan|antes\b.*€|acumulable|\d+ ?€)/i);
  assert.equal((home.match(/class="promo-card"/g) || []).length, 1, 'un solo mensaje principal; la franja de la portada es breve y enlaza a él');
  assert.match(home, /<input type="checkbox" name="promocion"/);
});

test('el formulario conoce la promoción y el sector que llegan por la dirección, solo con valores conocidos', () => {
  assert.match(site, /params\.get\("promo"\) === "20"/);
  assert.match(site, /params\.get\("solicitud"\) === "presupuesto"/);
  assert.match(site, /TAB_TYPES\[`tab-\$\{wanted\}`\]/);
  assert.match(site, /\/\^\[a-z\]\{3,12\}\$\/\.test\(wanted/);
  assert.match(site, /countVisit\("promo-clic"/);
  assert.match(site, /countVisit\("promo-solicitada"/);
});

test('la pantalla «Tu demostración ha finalizado» existe, no se indexa y lleva al formulario con la promoción', () => {
  const end = readFileSync(resolve(root, 'docs/demo-finalizada/index.html'), 'utf8');
  assert.match(end, /<meta name="robots" content="noindex, follow">/);
  assert.match(end, /<link rel="canonical" href="https:\/\/nirkana\.es\/demo-finalizada\/">/);
  assert.match(end, /<h1>Tu demostración ha finalizado<\/h1>/);
  assert.match(end, /Gracias por conocer NirKanA\. Si quieres implementar una solución digital en tu negocio, podemos ayudarte\./);
  assert.match(end.replace(/<[^>]+>/g, ''), /Contacta ahora y aprovecha un 20 % de descuento en la puesta en marcha\./);
  assert.match(end, /data-forward href="\/\?promo=20&amp;solicitud=presupuesto#contacto">Solicitar mi presupuesto con descuento/);
  assert.doesNotMatch(end, /\sstyle="|\son(click|load)=/i);
  assert.doesNotMatch(readFileSync(resolve(root, 'docs/sitemap.xml'), 'utf8'), /demo-finalizada/, 'no se indexa');
});

test('ninguna etiqueta <meta> ni <link> de ninguna página lleva marcas dentro de sus atributos, y todas declaran su icono', () => {
  for (const rel of ['index.html', 'demo-finalizada/index.html', 'tpv-tiendas/index.html']) {
    const page = readFileSync(resolve(root, 'docs', rel), 'utf8');
    const head = page.slice(0, page.indexOf('</head>'));
    for (const [tag] of head.matchAll(/<(?:meta|link)\b[^>]*>/g)) assert.doesNotMatch(tag, /="[^"]*<[a-z]/i, `${rel}: ${tag}`);
    assert.match(head, /<link rel="icon" href="\/?assets\/favicon\.svg"/, `${rel}: falta el icono`);
  }
});

test('el pie de todas las páginas enseña Instagram y TikTok solo con el usuario, y la portada los declara como suyos', () => {
  const PROFILES = [
    { href: 'https://www.instagram.com/nirkana.oficial/', user: '@nirkana.oficial', icon: 'i-instagram', event: 'red-instagram' },
    { href: 'https://www.tiktok.com/@nirkkana', user: '@nirkkana', icon: 'i-tiktok', event: 'red-tiktok' },
  ];
  const pages = readdirSync(resolve(root, 'docs'), { recursive: true }).filter((rel) => rel.endsWith('.html'))
    .filter((rel) => readFileSync(resolve(root, 'docs', rel), 'utf8').includes('<div class="foot-brand">'));
  assert.ok(pages.length >= 20, `solo ${pages.length} páginas con el pie completo`);
  for (const rel of pages) {
    const page = readFileSync(resolve(root, 'docs', rel), 'utf8');
    const social = page.match(/<p class="social">([\s\S]*?)<\/p>/);
    assert.ok(social, `${rel}: el pie no tiene las redes`);
    for (const { href, user, icon, event } of PROFILES) {
      const link = social[1].match(new RegExp(`<a href="${href.replace(/[.]/g, '\\.')}"([^>]*)>([\\s\\S]*?)</a>`));
      assert.ok(link, `${rel}: falta ${href}`);
      assert.match(link[1], /target="_blank" rel="me noopener noreferrer"/, `${rel}: ${href} sin rel seguro`);
      assert.match(link[1], new RegExp(`data-evento="${event}"`), `${rel}: ${href} no se cuenta`);
      assert.equal(link[2].replace(/<span\s+class="sr-only">[^<]*<\/span>/, '').replace(/<[^>]+>/g, '').trim(), user, `${rel}: solo el usuario`);
      assert.match(page, new RegExp(`<symbol id="${icon}" `), `${rel}: falta el icono ${icon}`);
      assert.ok(page.includes(`<use href="#${icon}"/>`), `${rel}: no usa el icono ${icon}`);
    }
  }
  const organization = [...home.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)]
    .map((m) => JSON.parse(m[1])).find((data) => data['@type'] === 'Organization');
  assert.deepEqual(organization.sameAs, PROFILES.map((p) => p.href));
});

test('la portada se organiza por temas: cada visitante abre lo que quiere saber y no se pierde nada', () => {
  const TOPICS = ['funciones', 'demostracion', 'precio', 'seguridad', 'preguntas', 'guias', 'historia'];
  const topics = home.match(/<section id="temas" class="topics">[\s\S]*?<div class="topic-tiles" role="tablist" aria-label="Temas"[\s\S]*?<\/button>\s*<\/div>/)[0];
  assert.match(topics, /<h2>¿Qué quieres saber\?<\/h2>/);
  for (const id of TOPICS) {
    assert.match(topics, new RegExp(`role="tab" id="t-${id}" aria-controls="${id}"`), id);
    assert.match(home, new RegExp(`<section id="${id}" class="topic-panel" role="tabpanel" aria-labelledby="t-${id}"`), id);
  }
  // one topic open when the page loads: «La app por dentro»; the rest open with a tap or from a link like /#precio
  const panels = [...home.matchAll(/<section id="([a-z]+)" class="topic-panel" role="tabpanel"[^>]*>/g)];
  assert.deepEqual(panels.map((m) => m[1]), TOPICS);
  assert.deepEqual(panels.filter((m) => !/\bhidden\b/.test(m[0])).map((m) => m[1]), ['funciones']);
  assert.match(site, /const revealTarget = \(\) =>/);
  assert.match(site, /target\.closest\('\[role="tabpanel"\]'\)/);
  assert.match(site, /countVisit\(`tema-\$\{tab\.id\.replace\("t-", ""\)\}`/);
  // without JavaScript every topic shows
  assert.match(readFileSync(resolve(root, 'docs/assets/sin-js.css'), 'utf8'), /\.topic-panel\[hidden\] \{ display: block !important; \}/);
  // the price tile says the same price as the price section
  const price = home.match(/<h2>Desde (\d+) € al mes \+ IVA<\/h2>/)[1];
  assert.match(topics, new RegExp(`<span class="tt-big"><small>desde</small> ${price} €</span>`));
  // the app's screenshots appear once; the old anchors still lead somewhere (/#recorrido, /#como, /#calculadora)
  assert.equal((home.match(/class="bento"/g) || []).length, 1, 'un solo bloque de capturas');
  assert.match(home, /<div class="bento" id="recorrido">/);
  assert.match(home, /<div class="steps" id="como"/);
  for (const gone of ['id="cambio"', 'id="movil"']) assert.ok(!home.includes(gone), gone);
});

test('nuestra historia: un texto breve, sin fechas ni cifras, con el lema del vídeo', () => {
  const panel = home.match(/<section id="historia" class="topic-panel"[\s\S]*?<\/section>/)[0];
  assert.match(home, /<button class="tt-wide" role="tab" id="t-historia" aria-controls="historia"/);
  assert.match(panel, /<article class="story">/);
  assert.match(panel, /<h2>No es solo un negocio\.<\/h2>/);
  const paragraphs = panel.match(/<p(?: class="story-lead")?>/g) || [];
  assert.ok(paragraphs.length >= 2 && paragraphs.length <= 4, 'breve: entre 2 y 4 párrafos');
  assert.match(panel, /<p class="story-motto"><span>Tu ambición\.<\/span> <span>Nuestra tecnología\.<\/span><\/p>/);
  // Text, not a timeline: no dates, no list of milestones, no figures.
  assert.doesNotMatch(panel, /<time|<ol|<dl|\b20\d\d\b/);
  // Nothing that is not live yet: the online booking is not in the public trial.
  assert.doesNotMatch(panel, /reserva online/i);
});

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

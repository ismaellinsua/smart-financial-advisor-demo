// Escena 3D de los anuncios de NirKanA. Se compila a ../nirkana3d.js con esbuild (ver tresd.py).
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const CFG = window.NIRKANA;
const captura = new URLSearchParams(location.search).has("captura");
const lienzo = document.getElementById("lienzo");

const renderer = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true, alpha: true, preserveDrawingBuffer: captura });
renderer.setPixelRatio(captura ? 1 : Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const escena = new THREE.Scene();
escena.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
const camara = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
const luz = new THREE.DirectionalLight(0xffffff, 1.6);
luz.position.set(3, 5, 4);
escena.add(luz, new THREE.AmbientLight(0x8ea2ff, 0.4));

const cargador = new THREE.TextureLoader();
const textura = (src) => new Promise((ok, mal) => cargador.load(src, (t) => {
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; ok(t);
}, undefined, mal));
const facil = (x) => 1 - Math.pow(1 - Math.min(Math.max(x, 0), 1), 3);
const rebote = (x) => {
  x = Math.min(Math.max(x, 0), 1);
  const c = 1.70158 + 1; return 1 + c * Math.pow(x - 1, 3) + 1.70158 * Math.pow(x - 1, 2);
};

const modelo = new THREE.Group();
escena.add(modelo);
const metal = new THREE.MeshPhysicalMaterial({ color: 0x2a3247, metalness: 0.75, roughness: 0.32, clearcoat: 0.6 });
const negro = new THREE.MeshStandardMaterial({ color: 0x05080f, roughness: 0.4 });

// ---------------------------------------------------------------- portátil
const portatil = new THREE.Group();
const base = new THREE.Mesh(new RoundedBoxGeometry(3.2, 0.11, 2.1, 4, 0.05), metal);
base.position.y = 0.055;
const teclado = new THREE.Mesh(new THREE.PlaneGeometry(2.8, 1.0), new THREE.MeshStandardMaterial({ color: 0x141a28, roughness: 0.8 }));
teclado.rotation.x = -Math.PI / 2; teclado.position.set(0, 0.112, -0.35);
const raton = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 0.55), new THREE.MeshStandardMaterial({ color: 0x323b52, roughness: 0.5 }));
raton.rotation.x = -Math.PI / 2; raton.position.set(0, 0.112, 0.6);
const bisagra = new THREE.Group();
bisagra.position.set(0, 0.11, -1.03);
const tapa = new THREE.Mesh(new RoundedBoxGeometry(3.2, 2.06, 0.07, 4, 0.04), metal);
tapa.position.set(0, 1.03, 0);
const marco = new THREE.Mesh(new THREE.PlaneGeometry(3.12, 1.98), negro);
marco.position.set(0, 1.03, 0.036);
const pantalla = new THREE.Mesh(new THREE.PlaneGeometry(3.0, 1.875), new THREE.MeshBasicMaterial({ toneMapped: false }));
pantalla.position.set(0, 1.05, 0.037);
bisagra.add(tapa, marco, pantalla);
portatil.add(base, teclado, raton, bisagra);
modelo.add(portatil);

// ---------------------------------------------------------------- móvil
const movil = new THREE.Group();
const cuerpo = new THREE.Mesh(new RoundedBoxGeometry(0.92, 1.94, 0.09, 6, 0.12),
  new THREE.MeshPhysicalMaterial({ color: 0x0b1222, metalness: 0.8, roughness: 0.25, clearcoat: 1 }));
const pantallaMovil = new THREE.Mesh(new THREE.PlaneGeometry(0.84, 1.82), new THREE.MeshBasicMaterial({ toneMapped: false }));
pantallaMovil.position.z = 0.046;
movil.add(cuerpo, pantallaMovil);
modelo.add(movil);

// ---------------------------------------------------------------- sombra suave bajo los aparatos
const sombraCanvas = document.createElement("canvas");
sombraCanvas.width = sombraCanvas.height = 256;
const sc = sombraCanvas.getContext("2d");
const g = sc.createRadialGradient(128, 128, 0, 128, 128, 128);
g.addColorStop(0, "rgba(0,0,0,.55)"); g.addColorStop(1, "rgba(0,0,0,0)");
sc.fillStyle = g; sc.fillRect(0, 0, 256, 256);
const sombra = new THREE.Mesh(new THREE.PlaneGeometry(5.2, 3.2),
  new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sombraCanvas), transparent: true, depthWrite: false }));
sombra.rotation.x = -Math.PI / 2; sombra.position.y = -0.01;
modelo.add(sombra);

// ---------------------------------------------------------------- esfera de partículas (como en la web)
const N = 1400, pos = new Float32Array(N * 3), col = new Float32Array(N * 3);
const oro = Math.PI * (3 - Math.sqrt(5));
for (let i = 0; i < N; i++) {
  const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), a = oro * i;
  pos.set([Math.cos(a) * r * 3.4, y * 3.4, Math.sin(a) * r * 3.4], i * 3);
  const c = new THREE.Color().lerpColors(new THREE.Color(0x8ea2ff), new THREE.Color(0x5eead4), (y + 1) / 2);
  col.set([c.r, c.g, c.b], i * 3);
}
const geoP = new THREE.BufferGeometry();
geoP.setAttribute("position", new THREE.BufferAttribute(pos, 3));
geoP.setAttribute("color", new THREE.BufferAttribute(col, 3));
const particulas = new THREE.Points(geoP, new THREE.PointsMaterial({ size: 0.045, vertexColors: true, transparent: true, opacity: 0.7, depthWrite: false }));
particulas.position.set(0, 1.1, -1.2);
escena.add(particulas);
const anillo = new THREE.Mesh(new THREE.TorusGeometry(4.4, 0.006, 8, 160), new THREE.MeshBasicMaterial({ color: 0x8ea2ff, transparent: true, opacity: 0.35 }));
anillo.rotation.set(1.05, 0.35, 0); anillo.position.copy(particulas.position);
escena.add(anillo);

// ---------------------------------------------------------------- tarjetas flotantes
function tarjeta(texto, color) {
  const c = document.createElement("canvas"); c.width = 900; c.height = 200;
  const x = c.getContext("2d");
  x.font = "700 54px Jakarta, sans-serif";
  const ancho = Math.min(900, x.measureText(texto).width + 190);
  c.width = Math.ceil(ancho);
  const k = c.getContext("2d");
  k.fillStyle = "rgba(255,255,255,.96)";
  k.beginPath(); k.roundRect(4, 4, c.width - 8, 192, 96); k.fill();
  k.fillStyle = color; k.beginPath(); k.arc(100, 100, 26, 0, Math.PI * 2); k.fill();
  k.fillStyle = color + "33"; k.beginPath(); k.arc(100, 100, 44, 0, Math.PI * 2); k.fill();
  k.fillStyle = "#0E1726"; k.font = "700 54px Jakarta, sans-serif"; k.textBaseline = "middle";
  k.fillText(texto, 160, 104);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  const h = 0.36, m = new THREE.Mesh(new THREE.PlaneGeometry(h * c.width / 200, h),
    new THREE.MeshBasicMaterial({ map: t, transparent: true, toneMapped: false, depthWrite: false }));
  m.renderOrder = 10;
  return m;
}
const COLORES = { verde: "#16A34A", rojo: "#DC2626", azul: "#3B5BFD", turquesa: "#0D9488" };
const SITIOS = [[-1.55, 2.55, 0.6], [1.85, 2.95, 0.2], [-1.85, 0.75, 1.5], [1.4, -0.15, 1.9]];
const tarjetas = [];

// ---------------------------------------------------------------- encuadre
let W = 1, H = 1;
function encuadrar() {
  W = innerWidth; H = innerHeight;
  renderer.setSize(W, H, false);
  camara.aspect = W / H;
  const horizontal = W / H > 1.3;
  const [fw, fh] = horizontal ? [0.5, 0.78] : (H / W > 1.6 ? [0.92, 0.42] : [0.84, 0.44]);
  const t = Math.tan(THREE.MathUtils.degToRad(camara.fov / 2));
  const d = Math.max(5.0 / (fw * 2 * t * camara.aspect), 3.9 / (fh * 2 * t));
  camara.position.set(0, d * 0.42, d);
  camara.lookAt(0, 1.05, 0);
  camara.setViewOffset(W, H, horizontal ? -W * 0.2 : 0, horizontal ? 0 : -H * (H / W > 1.6 ? 0.08 : 0.1), W, H);
  camara.updateProjectionMatrix();
}

// ---------------------------------------------------------------- animación (t en segundos)
function colocar(t) {
  const entrada = facil((t - 0.2) / 2.0);
  const vaiven = captura ? 0.28 * Math.sin(Math.max(t - 2.4, 0) * 0.5) : 0;
  modelo.rotation.y = -1.4 * (1 - entrada) + 0.32 + vaiven;
  modelo.scale.setScalar(0.75 + 0.25 * entrada);
  modelo.position.y = -0.6 * (1 - entrada);
  bisagra.rotation.x = 1.5 * (1 - facil((t - 0.6) / 1.6)) - 0.28;
  const m = facil((t - 1.5) / 1.1);
  movil.position.set(1.75 + 1.5 * (1 - m), 0.98 + 0.03 * Math.sin(t * 1.3) - 1.6 * (1 - m), 1.15);
  movil.rotation.set(-0.08, -0.42 - 1.2 * (1 - m), 0.06);
  particulas.rotation.y = t * 0.12; anillo.rotation.z = t * 0.05;
  tarjetas.forEach((c, i) => {
    const s = rebote((t - 2.5 - i * 0.35) / 0.6);
    const [x, y, z] = SITIOS[i];
    c.scale.setScalar(Math.max(s, 0.0001));
    c.position.set(x, y + 0.06 * Math.sin(t * 1.6 + i), z);
    c.quaternion.copy(camara.quaternion);
    dentro(c);
  });
}

// Empuja la tarjeta hacia dentro si se saldría por un lado de la pantalla.
const derecha = new THREE.Vector3(), centro = new THREE.Vector3(), borde = new THREE.Vector3();
function dentro(c) {
  derecha.set(1, 0, 0).applyQuaternion(camara.quaternion);
  const media = c.geometry.parameters.width / 2;
  centro.copy(c.position).project(camara);
  borde.copy(c.position).addScaledVector(derecha, media).project(camara);
  const dx = borde.x - centro.x;
  if (dx <= 0) return;
  const sobra = Math.max(centro.x + dx - 0.95, 0) - Math.max(-0.95 - (centro.x - dx), 0);
  if (sobra) c.position.addScaledVector(derecha, -sobra * media / dx);
}

let controles = null;
window.dibujar = (t) => { colocar(t); renderer.render(escena, camara); };

window.listo = (async () => {
  await document.fonts.load("700 54px Jakarta");
  const [a, b] = await Promise.all([textura(CFG.pantalla), textura(CFG.movil)]);
  a.repeat.set(1, CFG.recorteY || 1); a.offset.set(0, 1 - (CFG.recorteY || 1));
  pantalla.material.map = a; pantallaMovil.material.map = b;
  pantalla.material.needsUpdate = pantallaMovil.material.needsUpdate = true;
  CFG.tarjetas.forEach(([texto, color]) => { const c = tarjeta(texto, COLORES[color]); tarjetas.push(c); escena.add(c); });
  encuadrar();
  addEventListener("resize", encuadrar);
  if (!captura) {
    controles = new OrbitControls(camara, lienzo);
    controles.target.set(0, 1.05, 0);
    controles.enableZoom = false; controles.enablePan = false;
    controles.enableDamping = true; controles.autoRotate = true; controles.autoRotateSpeed = 0.8;
    controles.minPolarAngle = 0.6; controles.maxPolarAngle = 1.45;
    controles.addEventListener("start", () => { document.body.classList.add("tocado"); });
    const inicio = performance.now();
    const bucle = () => {
      const t = (performance.now() - inicio) / 1000;
      controles.autoRotate = t > 4;
      controles.update(); window.dibujar(t);
      requestAnimationFrame(bucle);
    };
    requestAnimationFrame(bucle);
  }
})();

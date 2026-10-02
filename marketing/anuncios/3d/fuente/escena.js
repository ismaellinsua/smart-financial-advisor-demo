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
renderer.toneMappingExposure = 1.05;

const escena = new THREE.Scene();
escena.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
const camara = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
const luz = new THREE.DirectionalLight(0xffffff, 1.4);
luz.position.set(3, 6, 5);
const contraluz = new THREE.DirectionalLight(0x8ea2ff, 1.2);
contraluz.position.set(-4, 3, -4);
escena.add(luz, contraluz, new THREE.AmbientLight(0xb8c4ff, 0.35));

const cargador = new THREE.TextureLoader();
const textura = (src) => new Promise((ok, mal) => cargador.load(src, (t) => {
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; ok(t);
}, undefined, mal));
const lienzo2d = (w, h, dibujar) => {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  dibujar(c.getContext("2d"), c);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
};
const facil = (x) => 1 - Math.pow(1 - Math.min(Math.max(x, 0), 1), 3);
const rebote = (x) => {
  x = Math.min(Math.max(x, 0), 1);
  return 1 + 2.70158 * Math.pow(x - 1, 3) + 1.70158 * Math.pow(x - 1, 2);
};
// Rectángulo de esquinas redondeadas con UV de 0 a 1 (para pantallas).
function rectRedondo(w, h, r) {
  const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  const g = new THREE.ShapeGeometry(s, 16), p = g.attributes.position, uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) uv.setXY(i, (p.getX(i) - x) / w, (p.getY(i) - y) / h);
  return g;
}

const modelo = new THREE.Group();
escena.add(modelo);
const aluminio = new THREE.MeshPhysicalMaterial({ color: 0x6b7489, metalness: 0.9, roughness: 0.3, clearcoat: 0.5, clearcoatRoughness: 0.3 });
const negro = new THREE.MeshStandardMaterial({ color: 0x04060b, roughness: 0.25, metalness: 0.2 });

// ---------------------------------------------------------------- portátil
const portatil = new THREE.Group();
const base = new THREE.Mesh(new RoundedBoxGeometry(3.2, 0.1, 2.12, 4, 0.05), aluminio);
base.position.y = 0.05;
const teclas = lienzo2d(1400, 500, (k) => {
  k.fillStyle = "#59627a"; k.fillRect(0, 0, 1400, 500);
  k.fillStyle = "#151a26";
  const filas = 6, cols = 14, gx = 8, gy = 10, kw = (1400 - gx * (cols + 1)) / cols, kh = (500 - gy * (filas + 1)) / filas;
  for (let f = 0; f < filas; f++) {
    for (let c = 0; c < cols; c++) {
      if (f === 5 && c >= 4 && c <= 9) continue;
      k.beginPath(); k.roundRect(gx + c * (kw + gx), gy + f * (kh + gy), kw, kh, 10); k.fill();
    }
  }
  k.beginPath(); k.roundRect(gx + 4 * (kw + gx), gy + 5 * (kh + gy), kw * 6 + gx * 5, kh, 10); k.fill();
});
const teclado = new THREE.Mesh(new THREE.PlaneGeometry(2.8, 1.0), new THREE.MeshStandardMaterial({ map: teclas, roughness: 0.65, metalness: 0.3 }));
teclado.rotation.x = -Math.PI / 2; teclado.position.set(0, 0.101, -0.38);
const raton = new THREE.Mesh(rectRedondo(1.1, 0.62, 0.05), new THREE.MeshPhysicalMaterial({ color: 0x7c8599, metalness: 0.7, roughness: 0.22, clearcoat: 1 }));
raton.rotation.x = -Math.PI / 2; raton.position.set(0, 0.101, 0.62);
const bisagra = new THREE.Group();
bisagra.position.set(0, 0.1, -1.04);
const tapa = new THREE.Mesh(new RoundedBoxGeometry(3.2, 2.06, 0.06, 4, 0.03), aluminio);
tapa.position.set(0, 1.03, 0);
const marco = new THREE.Mesh(rectRedondo(3.16, 2.02, 0.07), negro);
marco.position.set(0, 1.03, 0.031);
const pantalla = new THREE.Mesh(new THREE.PlaneGeometry(3.04, 1.9), new THREE.MeshBasicMaterial({ toneMapped: false }));
pantalla.position.set(0, 1.05, 0.032);
const brillo = new THREE.Mesh(new THREE.PlaneGeometry(3.04, 1.9), new THREE.MeshBasicMaterial({
  transparent: true, depthWrite: false, toneMapped: false,
  map: lienzo2d(512, 320, (k) => {
    const g = k.createLinearGradient(0, 0, 512, 320);
    g.addColorStop(0, "rgba(255,255,255,.16)"); g.addColorStop(.45, "rgba(255,255,255,.03)"); g.addColorStop(1, "rgba(255,255,255,0)");
    k.fillStyle = g; k.fillRect(0, 0, 512, 320);
  }),
}));
brillo.position.set(0, 1.05, 0.034);
bisagra.add(tapa, marco, pantalla, brillo);
portatil.add(base, teclado, raton, bisagra);
modelo.add(portatil);

// ---------------------------------------------------------------- móvil
const movil = new THREE.Group();
const titanio = new THREE.MeshPhysicalMaterial({ color: 0x1b2438, metalness: 0.9, roughness: 0.22, clearcoat: 1 });
const cuerpo = new THREE.Mesh(new RoundedBoxGeometry(0.92, 1.94, 0.085, 6, 0.04), titanio);
const frente = new THREE.Mesh(rectRedondo(0.9, 1.92, 0.14), negro);
frente.position.z = 0.0435;
const pantallaMovil = new THREE.Mesh(rectRedondo(0.85, 1.86, 0.12), new THREE.MeshBasicMaterial({ toneMapped: false }));
pantallaMovil.position.z = 0.0445;
const isla = new THREE.Mesh(rectRedondo(0.24, 0.065, 0.032), negro);
isla.position.set(0, 0.86, 0.0455);
const boton = (y, l) => { const b = new THREE.Mesh(new RoundedBoxGeometry(0.02, l, 0.035, 2, 0.008), titanio); b.position.set(0.465, y, 0); return b; };
movil.add(cuerpo, frente, pantallaMovil, isla, boton(0.45, 0.24), boton(0.1, 0.16));
modelo.add(movil);

// ---------------------------------------------------------------- suelo: sombra de contacto y reflejo de color
const degradado = (stops) => lienzo2d(256, 256, (k) => {
  const g = k.createRadialGradient(128, 128, 0, 128, 128, 128);
  stops.forEach(([p, c]) => g.addColorStop(p, c)); k.fillStyle = g; k.fillRect(0, 0, 256, 256);
});
const sombra = new THREE.Mesh(new THREE.PlaneGeometry(4.6, 2.9),
  new THREE.MeshBasicMaterial({ map: degradado([[0, "rgba(0,0,0,.6)"], [1, "rgba(0,0,0,0)"]]), transparent: true, depthWrite: false }));
sombra.rotation.x = -Math.PI / 2; sombra.position.y = -0.005;
const reflejo = new THREE.Mesh(new THREE.PlaneGeometry(8, 5),
  new THREE.MeshBasicMaterial({ map: degradado([[0, "rgba(59,91,253,.55)"], [.5, "rgba(20,184,166,.18)"], [1, "rgba(20,184,166,0)"]]),
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
reflejo.rotation.x = -Math.PI / 2; reflejo.position.y = -0.02;
modelo.add(reflejo, sombra);

// ---------------------------------------------------------------- halo y partículas detrás
const halo = new THREE.Mesh(new THREE.PlaneGeometry(10, 10), new THREE.MeshBasicMaterial({
  map: degradado([[0, "rgba(109,75,255,.45)"], [.4, "rgba(59,91,253,.15)"], [1, "rgba(59,91,253,0)"]]),
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
halo.position.set(0, 1.2, -2.6);
escena.add(halo);
const N = 1100, pos = new Float32Array(N * 3), col = new Float32Array(N * 3);
const oro = Math.PI * (3 - Math.sqrt(5));
for (let i = 0; i < N; i++) {
  const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), a = oro * i;
  pos.set([Math.cos(a) * r * 3.6, y * 3.6, Math.sin(a) * r * 3.6], i * 3);
  const c = new THREE.Color().lerpColors(new THREE.Color(0x8ea2ff), new THREE.Color(0x5eead4), (y + 1) / 2);
  col.set([c.r, c.g, c.b], i * 3);
}
const geoP = new THREE.BufferGeometry();
geoP.setAttribute("position", new THREE.BufferAttribute(pos, 3));
geoP.setAttribute("color", new THREE.BufferAttribute(col, 3));
const particulas = new THREE.Points(geoP, new THREE.PointsMaterial({ size: 0.03, vertexColors: true, transparent: true, opacity: 0.45, depthWrite: false }));
particulas.position.set(0, 1.1, -1.4);
escena.add(particulas);
const anillo = new THREE.Mesh(new THREE.TorusGeometry(4.5, 0.005, 8, 200), new THREE.MeshBasicMaterial({ color: 0x8ea2ff, transparent: true, opacity: 0.2 }));
anillo.rotation.set(1.05, 0.35, 0); anillo.position.copy(particulas.position);
escena.add(anillo);

// ---------------------------------------------------------------- avisos flotantes (estilo notificación)
const COLORES = { verde: "#16A34A", rojo: "#DC2626", azul: "#3B5BFD", turquesa: "#0D9488", naranja: "#EA580C" };
function aviso([titulo, detalle, color, icono]) {
  const medir = document.createElement("canvas").getContext("2d");
  medir.font = "700 50px Jakarta, sans-serif"; const a1 = medir.measureText(titulo).width;
  medir.font = "500 38px Jakarta, sans-serif"; const a2 = medir.measureText(detalle).width;
  const ancho = Math.ceil(Math.max(a1, a2) + 300), alto = 230, m = 30;
  const t = lienzo2d(ancho, alto, (k) => {
    k.shadowColor = "rgba(5,10,30,.45)"; k.shadowBlur = 26; k.shadowOffsetY = 8;
    k.fillStyle = "rgba(255,255,255,.97)"; k.beginPath(); k.roundRect(m, m - 6, ancho - m * 2, alto - m * 2, 44); k.fill();
    k.shadowColor = "transparent";
    const c = COLORES[color] || color;
    k.fillStyle = c; k.beginPath(); k.roundRect(m + 28, 52, 114, 114, 30); k.fill();
    k.fillStyle = "#fff"; k.font = "800 62px Jakarta, sans-serif"; k.textAlign = "center"; k.textBaseline = "middle";
    k.fillText(icono, m + 85, 112);
    k.textAlign = "left"; k.textBaseline = "alphabetic";
    k.fillStyle = "#0E1726"; k.font = "700 50px Jakarta, sans-serif"; k.fillText(titulo, m + 172, 100);
    k.fillStyle = "#5B6578"; k.font = "500 38px Jakarta, sans-serif"; k.fillText(detalle, m + 172, 152);
  });
  const h = 0.5, malla = new THREE.Mesh(new THREE.PlaneGeometry(h * ancho / alto, h),
    new THREE.MeshBasicMaterial({ map: t, transparent: true, toneMapped: false, depthWrite: false, depthTest: false }));
  malla.renderOrder = 10;
  return malla;
}
const SITIOS = [[-1.6, 2.6, 0.6], [1.8, 3.0, 0.2], [-1.9, 0.8, 1.5], [1.4, -0.15, 1.9]];
const avisos = [];

// ---------------------------------------------------------------- encuadre
let W = 1, H = 1;
function encuadrar() {
  W = innerWidth; H = innerHeight;
  renderer.setSize(W, H, false);
  camara.aspect = W / H;
  const horizontal = W / H > 1.3, alto = H / W > 1.6;
  const [fw, fh] = horizontal ? [0.5, 0.78] : (alto ? [0.92, 0.42] : [0.84, 0.44]);
  const t = Math.tan(THREE.MathUtils.degToRad(camara.fov / 2));
  const d = Math.max(5.0 / (fw * 2 * t * camara.aspect), 3.9 / (fh * 2 * t));
  camara.position.set(0, d * 0.42, d);
  camara.lookAt(0, 1.05, 0);
  camara.setViewOffset(W, H, horizontal ? -W * 0.2 : 0, horizontal ? 0 : -H * (alto ? 0.07 : 0.1), W, H);
  camara.updateProjectionMatrix();
}

// Empuja el aviso hacia dentro si se saldría por un lado de la pantalla.
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

// ---------------------------------------------------------------- animación (t en segundos)
function colocar(t) {
  const entrada = facil((t - 0.2) / 2.0);
  const vaiven = captura ? 0.26 * Math.sin(Math.max(t - 2.4, 0) * 0.5) : 0;
  modelo.rotation.y = -1.4 * (1 - entrada) + 0.32 + vaiven;
  modelo.scale.setScalar(0.75 + 0.25 * entrada);
  modelo.position.y = -0.6 * (1 - entrada);
  bisagra.rotation.x = 1.5 * (1 - facil((t - 0.6) / 1.6)) - 0.28;
  const m = facil((t - 1.5) / 1.1);
  movil.position.set(1.75 + 1.5 * (1 - m), 0.98 + 0.03 * Math.sin(t * 1.3) - 1.6 * (1 - m), 1.15);
  movil.rotation.set(-0.08, -0.42 - 1.2 * (1 - m), 0.06);
  particulas.rotation.y = t * 0.1; anillo.rotation.z = t * 0.04;
  halo.quaternion.copy(camara.quaternion);
  avisos.forEach((c, i) => {
    const s = rebote((t - 2.5 - i * 0.35) / 0.6);
    const [x, y, z] = SITIOS[i % SITIOS.length];
    c.scale.setScalar(Math.max(s, 0.0001));
    c.position.set(x, y + 0.05 * Math.sin(t * 1.4 + i), z);
    c.quaternion.copy(camara.quaternion);
    dentro(c);
  });
}

window.dibujar = (t) => { colocar(t); renderer.render(escena, camara); };

window.listo = (async () => {
  await Promise.all([document.fonts.load("700 50px Jakarta"), document.fonts.load("500 38px Jakarta"), document.fonts.load("800 62px Jakarta")]);
  const [a, b] = await Promise.all([textura(CFG.pantalla), textura(CFG.movil)]);
  pantalla.material.map = a; pantallaMovil.material.map = b;
  pantalla.material.needsUpdate = pantallaMovil.material.needsUpdate = true;
  CFG.tarjetas.forEach((d) => { const c = aviso(d); avisos.push(c); escena.add(c); });
  encuadrar();
  addEventListener("resize", encuadrar);
  if (!captura) {
    const controles = new OrbitControls(camara, lienzo);
    controles.target.set(0, 1.05, 0);
    controles.enableZoom = false; controles.enablePan = false;
    controles.enableDamping = true; controles.autoRotateSpeed = 0.7;
    controles.minPolarAngle = 0.6; controles.maxPolarAngle = 1.45;
    controles.addEventListener("start", () => document.body.classList.add("tocado"));
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

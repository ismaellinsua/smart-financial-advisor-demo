/* NirKanA · calculadoras gratuitas de la web (IVA, arqueo de caja y margen).
   Todo se calcula en el navegador: no se envía ni se guarda nada. Las funciones de cálculo (arqueo, margen, leerNumero…) son
   puras y se prueban en Node (tests/web-herramientas.test.mjs); lo demás solo las engancha con los campos de la página.
   Los importes se calculan en céntimos enteros para que 0,10 + 0,20 sea exactamente 0,30. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) { module.exports = api; return; }
  const start = () => api.init(document);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})(this, function () {
  "use strict";

  /* ---------------------------------------------------------------- lectura y formato de números */
  /** «12,5», «12.5», «1.234,56», «1,234.56», «1.234» (= 1234) o «12 €» → número; vacío → null; otra cosa → NaN.
      En España la coma separa los decimales y el punto, los miles: «1,234» es 1,234 y «1.234» es 1234. */
  function leerNumero(texto) {
    const s = String(texto ?? "").replace(/[€\s]/g, "");
    if (s === "") return null;
    let limpio = s, m;
    if ((m = s.match(/^(-?[1-9]\d{0,2}(?:\.\d{3})+),(\d*)$/))) limpio = `${m[1].replace(/\./g, "")}.${m[2]}`;        // 1.234,56
    else if ((m = s.match(/^(-?[1-9]\d{0,2}(?:,\d{3})+)\.(\d*)$/))) limpio = `${m[1].replace(/,/g, "")}.${m[2]}`;     // 1,234.56
    else if (/^-?[1-9]\d{0,2}(?:\.\d{3})+$/.test(s)) limpio = s.replace(/\./g, "");                                    // 1.234 · 12.345.678
    else if (/^-?[1-9]\d{0,2}(?:,\d{3}){2,}$/.test(s)) limpio = s.replace(/,/g, "");                                    // 1,234,567
    else limpio = s.replace(",", ".");
    return /^-?(\d+\.?\d*|\.\d+)$/.test(limpio) ? Number(limpio) : NaN;
  }

  /** Número de unidades: solo enteros desde 0; vacío → 0; otra cosa → NaN. */
  function leerEntero(texto) {
    const s = String(texto ?? "").replace(/\s/g, "");
    if (s === "") return 0;
    return /^\d{1,6}$/.test(s) ? Number(s) : NaN;
  }

  /** Importe en euros (≥ 0) → céntimos; vacío → 0; inválido o negativo → NaN. */
  function leerCentimos(texto) {
    const n = leerNumero(texto);
    if (n === null) return 0;
    return Number.isFinite(n) && n >= 0 && n < 1e9 ? Math.round(n * 100) : NaN;
  }

  const dinero = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
  const decimal = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const libre = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }); // «100» y no «100,0»
  const euros = (centimos) => dinero.format(centimos / 100);
  const eurosDeImporte = (importe) => dinero.format(Math.round(importe * 100) / 100);
  const porcentaje = (valor) => (Number.isFinite(valor) ? `${decimal.format(valor)} %` : "—");

  /* ---------------------------------------------------------------- arqueo de caja */
  /** filas: [[valor en céntimos, cantidad]…]; el resto, en céntimos. Devuelve lo contado, lo esperado y la diferencia. */
  function arqueo({ filas, fondo = 0, ventas = 0, entradas = 0, salidas = 0, dejar = null }) {
    const contado = filas.reduce((suma, [valor, cantidad]) => suma + valor * cantidad, 0);
    const esperado = fondo + ventas + entradas - salidas;
    const diferencia = contado - esperado;
    return {
      contado, esperado, diferencia,
      estado: diferencia === 0 ? "cuadra" : diferencia > 0 ? "sobra" : "falta",
      retirar: dejar === null ? null : contado - dejar,
    };
  }

  /* ---------------------------------------------------------------- margen y precio de venta */
  /**
   * modo «margen»: parte del coste y del margen que quieres; modo «precio»: parte del coste y del precio al que vendes.
   * coste y precio, en euros; el coste va siempre sin IVA. El descuento se aplica al precio con IVA (lo que ve el cliente).
   */
  function margen({ modo, coste, margenPct = 0, precio = 0, precioConIva = true, ivaPct = 21, descuentoPct = 0 }) {
    if (!(coste >= 0)) return { error: "coste" };
    let neto;
    if (modo === "margen") {
      if (!(margenPct >= 0 && margenPct < 100)) return { error: "margen" };
      neto = coste / (1 - margenPct / 100);
    } else {
      if (!(precio > 0)) return { error: "precio" };
      neto = precioConIva ? precio / (1 + ivaPct / 100) : precio;
    }
    const beneficio = neto - coste;
    const resultado = {
      neto, pvp: neto * (1 + ivaPct / 100), iva: neto * (ivaPct / 100), beneficio,
      margenPct: neto > 0 ? (beneficio / neto) * 100 : NaN,
      recargoPct: coste > 0 ? (beneficio / coste) * 100 : NaN,
    };
    if (descuentoPct > 0 && descuentoPct < 100) {
      const netoD = neto * (1 - descuentoPct / 100), beneficioD = netoD - coste;
      resultado.descuento = {
        pct: descuentoPct, neto: netoD, pvp: netoD * (1 + ivaPct / 100), beneficio: beneficioD,
        margenPct: netoD > 0 ? (beneficioD / netoD) * 100 : NaN,
        pierde: beneficioD <= 0,
        // cuántas unidades más hay que vender para ganar en total lo mismo que sin descuento
        masUnidadesPct: beneficioD > 0 && beneficio > 0 ? (beneficio / beneficioD - 1) * 100 : null,
      };
    }
    return resultado;
  }

  /* ---------------------------------------------------------------- IVA: añadir o quitar */
  /**
   * modo «anadir»: el importe es la base (sin IVA); modo «quitar»: el importe ya lleva el IVA.
   * Importe en céntimos enteros; ivaPct, el tipo (21, 10, 4…). Devuelve base, cuota y total en céntimos.
   * Quitar el IVA es dividir entre (1 + tipo), no restar el tipo: 121 € con un 21 % son 100 € de base, no 95,59 €.
   */
  function iva({ modo, importe, ivaPct = 21 }) {
    if (!(Number.isInteger(importe) && importe >= 0)) return { error: "importe" };
    if (!(Number.isFinite(ivaPct) && ivaPct >= 0 && ivaPct <= 100)) return { error: "tipo" };
    let base, cuota;
    if (modo === "anadir") {
      base = importe;
      cuota = Math.round((importe * ivaPct) / 100);
    } else {
      base = Math.round((importe * 100) / (100 + ivaPct));
      cuota = importe - base;
    }
    return { base, cuota, total: base + cuota, restarMal: modo === "quitar" ? importe - Math.round((importe * ivaPct) / 100) : null };
  }

  /* ---------------------------------------------------------------- página: arqueo de caja */
  const avisar = (slug, titulo) => document.dispatchEvent(new CustomEvent("nirkana:evento", { detail: { slug, titulo } }));
  const marcar = (campo, mal) => { campo.setAttribute("aria-invalid", mal ? "true" : "false"); campo.classList.toggle("mal", mal); return mal; };

  function iniciarArqueo(form) {
    const salida = (nombre) => form.querySelector(`[data-out="${nombre}"]`);
    const conteos = [...form.querySelectorAll("[data-valor]")];
    const dinero_ = (nombre) => form.querySelector(`[data-in="${nombre}"]`);
    let usada = false;
    const recalcular = () => {
      let hayErrores = false, hayDatos = false;
      const filas = conteos.map((campo) => {
        const n = leerEntero(campo.value);
        hayErrores = marcar(campo, Number.isNaN(n)) || hayErrores;
        hayDatos = hayDatos || (n > 0);
        const cantidad = Number.isNaN(n) ? 0 : n;
        form.querySelector(`[data-sub="${campo.dataset.valor}"]`).textContent = euros(Number(campo.dataset.valor) * cantidad);
        return [Number(campo.dataset.valor), cantidad];
      });
      const lee = (nombre) => {
        const campo = dinero_(nombre), c = leerCentimos(campo.value);
        hayErrores = marcar(campo, Number.isNaN(c)) || hayErrores;
        if (campo.value.trim() !== "" && !Number.isNaN(c)) hayDatos = true;
        return Number.isNaN(c) ? 0 : c;
      };
      const dejarCampo = dinero_("dejar");
      const dejar = dejarCampo.value.trim() === "" ? null : leerCentimos(dejarCampo.value);
      marcar(dejarCampo, Number.isNaN(dejar));
      const r = arqueo({ filas, fondo: lee("fondo"), ventas: lee("ventas"), entradas: lee("entradas"), salidas: lee("salidas"), dejar: Number.isNaN(dejar) ? null : dejar });
      salida("contado").textContent = euros(r.contado);
      salida("esperado").textContent = euros(r.esperado);
      const estado = salida("estado");
      estado.dataset.estado = hayErrores ? "error" : !hayDatos ? "vacio" : r.estado;
      salida("estado-titulo").textContent = hayErrores ? "Revisa los campos marcados: solo números."
        : !hayDatos ? "Escribe lo que has contado y lo que debería haber."
        : r.estado === "cuadra" ? "La caja cuadra."
        : r.estado === "sobra" ? `Sobran ${euros(r.diferencia)}.` : `Faltan ${euros(-r.diferencia)}.`;
      salida("estado-detalle").textContent = hayErrores || !hayDatos ? ""
        : `Contado ${euros(r.contado)} · esperado ${euros(r.esperado)} · diferencia ${r.diferencia > 0 ? "+" : r.diferencia < 0 ? "−" : ""}${euros(Math.abs(r.diferencia))}.`;
      const retirar = salida("retirar");
      retirar.hidden = r.retirar === null || hayErrores;
      if (r.retirar !== null) retirar.textContent = r.retirar >= 0 ? `Para dejar ese fondo, retira ${euros(r.retirar)} del cajón.` : `Te faltan ${euros(-r.retirar)} para llegar al fondo que quieres dejar.`;
    };
    form.addEventListener("input", () => { if (!usada) { usada = true; avisar("herramienta-arqueo", "Usa la calculadora de arqueo de caja"); } recalcular(); });
    form.addEventListener("reset", () => setTimeout(recalcular, 0));
    form.querySelector("[data-imprimir]")?.addEventListener("click", () => window.print());
    recalcular();
  }

  /* ---------------------------------------------------------------- página: margen */
  function iniciarMargen(form) {
    const campo = (nombre) => form.querySelector(`[data-in="${nombre}"]`);
    const salida = (nombre) => form.querySelector(`[data-out="${nombre}"]`);
    const modo = () => form.querySelector('input[name="modo"]:checked').value;
    let usada = false;
    const numero = (nombre, [min, max] = [0, 1e9]) => {
      const el = campo(nombre), n = leerNumero(el.value);
      const mal = n !== null && !(Number.isFinite(n) && n >= min && n <= max);
      marcar(el, mal);
      return mal ? NaN : n;
    };
    const recalcular = () => {
      const m = modo();
      form.dataset.modo = m;
      for (const el of form.querySelectorAll("[data-solo]")) el.hidden = el.dataset.solo !== m;
      const coste = numero("coste"), margenPct = numero("margen", [0, 99.99]), precio = numero("precio"), descuento = numero("descuento", [0, 99.99]);
      const resultados = salida("resultados"), aviso = salida("aviso");
      const faltan = coste === null || Number.isNaN(coste) || (m === "margen" ? margenPct === null || Number.isNaN(margenPct) : precio === null || Number.isNaN(precio) || precio === 0);
      resultados.hidden = faltan;
      aviso.hidden = !faltan;
      salida("resumen").textContent = "";
      if (faltan) return;
      const r = margen({
        modo: m, coste, margenPct: margenPct ?? 0, precio: precio ?? 0, precioConIva: campo("iva-incluido").value === "si",
        ivaPct: Number(campo("iva").value), descuentoPct: descuento ?? 0,
      });
      if (r.error) { resultados.hidden = true; aviso.hidden = false; return; }
      salida("resumen").textContent = `Precio al público, ${eurosDeImporte(r.pvp)}. Beneficio por unidad, ${eurosDeImporte(r.beneficio)}. Margen, ${porcentaje(r.margenPct)}.`;
      salida("neto").textContent = eurosDeImporte(r.neto);
      salida("iva").textContent = eurosDeImporte(r.iva);
      salida("pvp").textContent = eurosDeImporte(r.pvp);
      salida("beneficio").textContent = eurosDeImporte(r.beneficio);
      salida("margen").textContent = porcentaje(r.margenPct);
      salida("recargo").textContent = porcentaje(r.recargoPct);
      const bloque = salida("descuento");
      bloque.hidden = !r.descuento;
      if (r.descuento) {
        const d = r.descuento;
        salida("d-pvp").textContent = eurosDeImporte(d.pvp);
        salida("d-beneficio").textContent = eurosDeImporte(d.beneficio);
        salida("d-margen").textContent = porcentaje(d.margenPct);
        salida("d-texto").textContent = d.pierde ? "Con ese descuento ya no ganas nada por unidad: vendes por debajo del coste o igual."
          : `Para ganar en total lo mismo que sin descuento tendrías que vender un ${libre.format(d.masUnidadesPct)} % más de unidades.`;
      }
    };
    form.addEventListener("input", () => { if (!usada) { usada = true; avisar("herramienta-margen", "Usa la calculadora de margen"); } recalcular(); });
    form.addEventListener("change", recalcular);
    form.addEventListener("reset", () => setTimeout(recalcular, 0));
    recalcular();
  }

  /* ---------------------------------------------------------------- página: IVA */
  function iniciarIva(form) {
    const campo = (nombre) => form.querySelector(`[data-in="${nombre}"]`);
    const salida = (nombre) => form.querySelector(`[data-out="${nombre}"]`);
    const modo = () => form.querySelector('input[name="modo-iva"]:checked').value;
    let usada = false;
    const recalcular = () => {
      const m = modo();
      form.dataset.modo = m;
      for (const el of form.querySelectorAll("[data-solo]")) el.hidden = el.dataset.solo !== m;
      const el = campo("importe"), n = leerNumero(el.value);
      const mal = n !== null && !(Number.isFinite(n) && n >= 0 && n < 1e9);
      marcar(el, mal);
      const resultados = salida("resultados"), aviso = salida("aviso");
      const falta = n === null || mal;
      resultados.hidden = falta;
      aviso.hidden = !falta;
      salida("resumen").textContent = "";
      if (falta) return;
      const importe = Math.round(n * 100), tipo = Number(campo("iva").value);
      const r = iva({ modo: m, importe, ivaPct: tipo });
      if (r.error) { resultados.hidden = true; aviso.hidden = false; return; }
      salida("base").textContent = euros(r.base);
      salida("cuota").textContent = euros(r.cuota);
      salida("total").textContent = euros(r.total);
      salida("tipo").textContent = `${tipo} %`;
      salida("resumen").textContent = `Base sin IVA, ${euros(r.base)}. IVA del ${tipo} %, ${euros(r.cuota)}. Total con IVA, ${euros(r.total)}.`;
      const ojo = salida("ojo");
      ojo.hidden = !(m === "quitar" && tipo > 0 && r.restarMal !== r.base);
      if (!ojo.hidden) ojo.textContent = `Ojo: restar el ${tipo} % a ${euros(importe)} daría ${euros(r.restarMal)}, que no es la base. La base es ${euros(r.base)}.`;
      for (const fila of form.querySelectorAll("[data-otro]")) {
        const o = iva({ modo: m, importe, ivaPct: Number(fila.dataset.otro) });
        fila.querySelector('[data-o="base"]').textContent = euros(o.base);
        fila.querySelector('[data-o="cuota"]').textContent = euros(o.cuota);
        fila.querySelector('[data-o="total"]').textContent = euros(o.total);
      }
    };
    form.addEventListener("input", () => { if (!usada) { usada = true; avisar("herramienta-iva", "Usa la calculadora de IVA"); } recalcular(); });
    form.addEventListener("change", recalcular);
    form.addEventListener("reset", () => setTimeout(recalcular, 0));
    recalcular();
  }

  function init(doc) {
    const arqueoForm = doc.querySelector('[data-calc="arqueo"]');
    if (arqueoForm) iniciarArqueo(arqueoForm);
    const margenForm = doc.querySelector('[data-calc="margen"]');
    if (margenForm) iniciarMargen(margenForm);
    const ivaForm = doc.querySelector('[data-calc="iva"]');
    if (ivaForm) iniciarIva(ivaForm);
  }

  return { leerNumero, leerEntero, leerCentimos, arqueo, margen, iva, euros, eurosDeImporte, porcentaje, init };
});

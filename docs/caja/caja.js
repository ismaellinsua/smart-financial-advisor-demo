// NirKanA offline till: sells from a catalogue file, keeps the sales on this device and exports them for the app.
// Nothing is sent anywhere: the page works with no connection once installed, and the data never leaves the
// device except in the sales file the user saves or shares.
"use strict";

(() => {
  const KEY_PACKAGE = "nkc.package";
  const KEY_SALES = "nkc.sales";
  const KEY_EXPORTED = "nkc.exported"; // ids of the sales included in the last saved file
  const counterKey = (series) => `nkc.counter.${series}`;

  const $ = (id) => document.getElementById(id);
  const store = {
    get(key, fallback) {
      try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); }
      catch { return fallback; }
    },
    set(key, value) { localStorage.setItem(key, JSON.stringify(value)); },
  };

  let pkg = store.get(KEY_PACKAGE, null);
  let cart = []; // {id, name, price (cents), vat, qty}
  let method = "";
  let category = "";
  let lastSale = null;

  // ------------------------------------------------------------------ money
  const cents = (value) => Math.round(Number(value) * 100);
  const euros = (c) => (c / 100).toLocaleString("es-ES", { style: "currency", currency: (pkg && pkg.business.currency) || "EUR" });
  const pad = (n, width) => String(n).padStart(width, "0");
  const localIso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1, 2)}-${pad(d.getDate(), 2)}T${pad(d.getHours(), 2)}:${pad(d.getMinutes(), 2)}:${pad(d.getSeconds(), 2)}`;
  const shown = (iso) => { const [d, t] = iso.split("T"); const [y, m, dd] = d.split("-"); return `${dd}/${m}/${y} ${t.slice(0, 5)}`; };
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID()
    : ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, (c) => (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)));

  // VAT included in the price: per rate, base = total / (1 + rate), rounded once (as the app does).
  function breakdown(lines) {
    const byRate = new Map();
    for (const l of lines) byRate.set(l.vat, (byRate.get(l.vat) || 0) + l.price * l.qty);
    return [...byRate.entries()].sort((a, b) => b[0] - a[0]).map(([rate, gross]) => {
      const base = Math.round(gross / (1 + rate / 100));
      return { rate, base, tax: gross - base, gross };
    });
  }
  const cartTotal = () => cart.reduce((sum, l) => sum + l.price * l.qty, 0);

  // ------------------------------------------------------------------ elements
  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") node.className = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else if (k in node) node[k] = v;
      else node.setAttribute(k, v);
    }
    for (const c of children) node.append(c);
    return node;
  }

  // ------------------------------------------------------------------ catalogue
  function loadPackage(file, errorBox) {
    errorBox.hidden = true;
    const reader = new FileReader();
    reader.onload = () => {
      let data;
      try { data = JSON.parse(reader.result); } catch { data = null; }
      if (!data || data.kind !== "nirkana-caja" || data.version !== 1 || !Array.isArray(data.products) || !data.series) {
        return fail(errorBox, "Ese archivo no es un catálogo de la caja sin conexión. Descárgalo de la app en Caja → Caja sin conexión.");
      }
      const pending = store.get(KEY_SALES, []);
      if (pkg && pending.length && (pkg.key !== data.key || pkg.series !== data.series || (pkg.location_id || null) !== (data.location_id || null))) {
        return fail(errorBox, "Antes de cargar el catálogo de otro negocio u otra caja, envía a la app las ventas pendientes y bórralas de aquí.");
      }
      pkg = data;
      store.set(KEY_PACKAGE, pkg);
      const current = store.get(counterKey(pkg.series), 0);
      store.set(counterKey(pkg.series), Math.max(current, (Number(pkg.next_number) || 1) - 1));
      cart = []; method = ""; category = "";
      $("pending-dialog").open && $("pending-dialog").close();
      render();
    };
    reader.readAsText(file);
  }

  function fail(box, message) { box.textContent = message; box.hidden = false; }

  // ------------------------------------------------------------------ render
  function render() {
    const ready = Boolean(pkg);
    $("setup").hidden = ready;
    $("till").hidden = !ready;
    if (!ready) { renderPending(); return; }
    $("business").textContent = pkg.business.business_name || "Caja sin conexión";
    $("catalog-date").textContent = `${pkg.location ? pkg.location + " · " : ""}Caja ${pkg.device} · catálogo del ${shown(pkg.generated_at).slice(0, 10)}`;
    renderCategories();
    renderGrid();
    renderCart();
    renderPending();
  }

  function renderCategories() {
    const names = [...new Set(pkg.products.map((p) => p.category))];
    const box = $("categories");
    box.replaceChildren(...["", ...names].map((name) => el("button", {
      type: "button", class: "chip", textContent: name || "Todo", "aria-pressed": String(name === category),
      onclick: () => { category = name; renderCategories(); renderGrid(); },
    })));
  }

  function renderGrid() {
    const q = $("search").value.trim().toLowerCase();
    const items = pkg.products.filter((p) => (!category || p.category === category) && (!q || p.name.toLowerCase().includes(q)));
    $("grid").replaceChildren(...items.map((p) => el("button", {
      type: "button", class: "product", onclick: () => add(p), "aria-label": `Añadir ${p.name}`,
    }, el("span", { textContent: p.name }), el("span", { class: "price", textContent: euros(cents(p.price)) }))));
    if (!items.length) $("grid").append(el("p", { class: "muted", textContent: "No hay productos con ese nombre." }));
  }

  function add(p) {
    const line = cart.find((l) => l.id === p.id);
    if (line) line.qty += 1;
    else cart.push({ id: p.id, name: p.name, price: cents(p.price), vat: Number(p.vat), qty: 1 });
    renderCart();
  }

  function renderCart() {
    $("lines").replaceChildren(...cart.map((l) => el("li", {},
      el("span", { textContent: l.name }),
      el("strong", { textContent: euros(l.price * l.qty) }),
      el("span", { class: "qty" },
        el("button", { type: "button", textContent: "−", "aria-label": `Quitar uno de ${l.name}`, onclick: () => { l.qty -= 1; cart = cart.filter((x) => x.qty > 0); renderCart(); } }),
        el("span", { textContent: `${l.qty} × ${euros(l.price)}` }),
        el("button", { type: "button", textContent: "+", "aria-label": `Añadir otro ${l.name}`, onclick: () => { l.qty += 1; renderCart(); } })),
    )));
    $("empty").hidden = cart.length > 0;
    const total = cartTotal();
    $("total").textContent = euros(total);
    const methods = pkg.payment_methods && pkg.payment_methods.length ? pkg.payment_methods : ["Efectivo", "Tarjeta"];
    $("methods").replaceChildren(...methods.map((m) => el("button", {
      type: "button", class: "chip", role: "radio", textContent: m, "aria-checked": String(m === method),
      onclick: () => { method = m; renderCart(); },
    })));
    $("cash-row").hidden = method !== "Efectivo";
    const tendered = cents($("tendered").value || 0);
    $("change").textContent = method === "Efectivo" && tendered >= total && total > 0 ? `Cambio: ${euros(tendered - total)}` : "";
    $("charge").disabled = !cart.length || !method || (method === "Efectivo" && tendered > 0 && tendered < total);
    $("charge").textContent = method ? `Cobrar ${euros(total)}` : "Elige la forma de pago";
    const count = cart.reduce((n, l) => n + l.qty, 0);
    $("to-cart").hidden = !count;
    $("to-cart").textContent = `Ver ticket (${count}) · ${euros(total)}`;
  }

  // ------------------------------------------------------------------ sell
  function charge() {
    if (!cart.length || !method) return;
    const sales = store.get(KEY_SALES, []);
    const n = store.get(counterKey(pkg.series), 0) + 1;
    const sale = {
      id: uuid(), number: `${pkg.series}${pad(n, 6)}`, created_at: localIso(new Date()), payment_method: method,
      total: cartTotal() / 100, tendered: method === "Efectivo" ? cents($("tendered").value || 0) / 100 : 0,
      items: cart.map((l) => ({ product_id: l.id, name: l.name, quantity: l.qty, unit_price: l.price / 100, tax_rate: l.vat })),
    };
    // Saved before anything is shown, so a closed tab or a dead battery never loses a charged sale.
    sales.push(sale);
    store.set(KEY_SALES, sales);
    store.set(counterKey(pkg.series), n);
    lastSale = sale;
    cart = []; method = ""; $("tendered").value = "";
    renderCart();
    renderPending();
    $("ticket").replaceChildren(ticketNode(sale));
    $("ticket-dialog").showModal();
  }

  function ticketNode(sale) {
    const b = pkg.business;
    const lines = sale.items.map((i) => ({ price: cents(i.unit_price), qty: i.quantity, vat: i.tax_rate }));
    const rows = sale.items.map((i) => el("tr", {}, el("td", { textContent: `${i.quantity} × ${i.name}` }),
      el("td", { textContent: euros(cents(i.unit_price) * i.quantity) })));
    const taxes = breakdown(lines).map((t) => el("tr", {},
      el("td", { textContent: `IVA ${String(t.rate).replace(".", ",")} % s/ ${euros(t.base)}` }), el("td", { textContent: euros(t.tax) })));
    const total = cents(sale.total);
    const extra = sale.tendered ? [
      el("tr", {}, el("td", { textContent: "Entregado" }), el("td", { textContent: euros(cents(sale.tendered)) })),
      el("tr", {}, el("td", { textContent: "Cambio" }), el("td", { textContent: euros(cents(sale.tendered) - total) })),
    ] : [];
    return el("div", { class: "ticket" },
      el("div", { class: "center" }, el("strong", { textContent: b.business_name || "" })),
      ...[b.tax_id && `NIF ${b.tax_id}`, b.address, b.phone].filter(Boolean).map((t) => el("div", { class: "center", textContent: t })),
      el("div", { class: "center", textContent: "Factura simplificada" }),
      el("div", { textContent: `${sale.number} · ${shown(sale.created_at)}` }),
      el("table", {}, ...rows,
        el("tr", { class: "grand" }, el("td", { textContent: "TOTAL" }), el("td", { textContent: euros(total) })),
        ...taxes,
        el("tr", {}, el("td", { textContent: sale.payment_method }), el("td", { textContent: "" })),
        ...extra),
      b.receipt_footer ? el("div", { class: "center", textContent: b.receipt_footer }) : "",
    );
  }

  function printTicket() {
    if (!lastSale) return;
    $("print-area").replaceChildren(ticketNode(lastSale));
    window.print();
  }

  // ------------------------------------------------------------------ pending sales
  function renderPending() {
    const sales = store.get(KEY_SALES, []);
    $("open-pending").hidden = !sales.length;
    $("pending-count").textContent = String(sales.length);
    const total = sales.reduce((s, x) => s + cents(x.total), 0);
    $("pending-summary").textContent = sales.length
      ? `${sales.length} venta${sales.length === 1 ? "" : "s"} · ${euros(total)}. Se guardan en este dispositivo hasta que las borres.`
      : "No hay ventas pendientes.";
    $("pending-list").replaceChildren(...sales.slice().reverse().slice(0, 100).map((s) => el("li", {},
      el("span", { textContent: `${s.number} · ${shown(s.created_at)}` }), el("strong", { textContent: euros(cents(s.total)) }))));
    const exported = new Set(store.get(KEY_EXPORTED, []));
    $("clear").disabled = !sales.some((s) => exported.has(s.id));
    $("export").disabled = !sales.length;
    $("share").hidden = !(navigator.canShare && sales.length);
  }

  function salesFile() {
    const sales = store.get(KEY_SALES, []);
    const body = JSON.stringify({
      kind: "nirkana-ventas", version: 1, key: pkg.key, device: pkg.device, location_id: pkg.location_id || null,
      exported_at: localIso(new Date()), sales,
    }, null, 1);
    const name = `ventas-caja${pkg.device}-${localIso(new Date()).slice(0, 16).replace(/[-:T]/g, "")}.json`;
    store.set(KEY_EXPORTED, sales.map((s) => s.id));
    return new File([body], name, { type: "application/json" });
  }

  function saveFile() {
    const file = salesFile();
    const link = el("a", { href: URL.createObjectURL(file), download: file.name });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 10000);
    renderPending();
  }

  async function shareFile() {
    const file = salesFile();
    try {
      if (navigator.canShare({ files: [file] })) await navigator.share({ files: [file], title: file.name });
    } catch { /* cancelled by the user */ }
    renderPending();
  }

  function clearImported() {
    const exported = new Set(store.get(KEY_EXPORTED, []));
    const left = store.get(KEY_SALES, []).filter((s) => !exported.has(s.id));
    const gone = store.get(KEY_SALES, []).length - left.length;
    if (!confirm(`¿Borrar de este dispositivo las ${gone} ventas del último archivo guardado? Hazlo solo si la app ya confirmó que las importó.`)) return;
    store.set(KEY_SALES, left);
    store.set(KEY_EXPORTED, []);
    renderPending();
  }

  // ------------------------------------------------------------------ connection
  function renderNet() {
    const on = navigator.onLine;
    $("net").textContent = on ? "Con conexión" : "Sin conexión";
    $("net").className = `pill ${on ? "on" : "off"}`;
  }

  // ------------------------------------------------------------------ wire up
  document.addEventListener("DOMContentLoaded", () => {
    $("package-file").addEventListener("change", (e) => e.target.files[0] && loadPackage(e.target.files[0], $("setup-error")));
    $("package-file-2").addEventListener("change", (e) => e.target.files[0] && loadPackage(e.target.files[0], $("pending-error")));
    $("search").addEventListener("input", renderGrid);
    $("tendered").addEventListener("input", renderCart);
    $("charge").addEventListener("click", charge);
    $("print").addEventListener("click", printTicket);
    $("next-sale").addEventListener("click", () => $("ticket-dialog").close());
    $("open-pending").addEventListener("click", () => { renderPending(); $("pending-dialog").showModal(); });
    $("close-pending").addEventListener("click", () => $("pending-dialog").close());
    $("export").addEventListener("click", saveFile);
    $("share").addEventListener("click", shareFile);
    $("clear").addEventListener("click", clearImported);
    $("to-cart").addEventListener("click", () => document.querySelector(".cart").scrollIntoView({ behavior: "smooth" }));
    window.addEventListener("online", renderNet);
    window.addEventListener("offline", renderNet);
    renderNet();
    render();
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  });
})();

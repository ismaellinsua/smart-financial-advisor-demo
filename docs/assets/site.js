/* NirKanA — contact links, contact form and 3D effects. No third-party code. */

// ---------------------------------------------------------------- your contact details (edit here)
// Requests arrive through Formspree (if configured), WhatsApp (if there is a number) or, failing both, email.
const CONTACT = {
  // Contact email: shown as a button, used by the form when there is no Formspree id or WhatsApp number.
  email: "nirkana.oficial@gmail.com",
  // WhatsApp number with country code and digits only, e.g. "34600111222". Empty hides the button.
  whatsapp: "",
  // Formspree form id (the part after https://formspree.io/f/). Empty: the form sends the request by WhatsApp.
  formspreeId: "mbgdrbyg",
};
const MESSAGE = "Hola, quiero NirKanA para mi negocio. ¿Hablamos?";

// Address of the app for existing customers (e.g. "https://app.nirkana.es"). Empty: no «Entrar» link is shown.
const APP_URL = "";

// Address of the free 24-hour trial (e.g. "https://prueba.nirkana.es"). Empty: the «Probar NirKanA» buttons stay hidden
// and «Quiero NirKanA» takes their place, so the page never links to a trial that is not running yet.
const TRIAL_URL = "https://nirkana-prueba.onrender.com";

// Address of the offline demo, a page of this same site (the built NirKanA-demo.html lives at /demo/index.html). It is a
// business with example data that anyone can open without signing up. Empty: no «Ver la demo» link is shown.
const DEMO_URL = "/demo/";

// Visit counter (GoatCounter): your site code, e.g. "nirkana" for nirkana.goatcounter.com. Empty: nothing is counted.
// No cookies, nothing stored on the visitor's device, no third-party script; visitors who ask not to be tracked
// (Do Not Track or Global Privacy Control) are not counted.
const ANALYTICS = { goatcounter: "nirkana" };

(() => {
  "use strict";
  document.documentElement.classList.add("js");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(pointer: fine)").matches;

  // ------------------------------------------------------------ respectful visit counter
  const counting = /^[a-z0-9][a-z0-9-]{1,49}$/.test(ANALYTICS.goatcounter)
    && navigator.doNotTrack !== "1" && !navigator.globalPrivacyControl
    && /(^|\.)nirkana\.es$/.test(location.hostname); // only the published site, never local copies
  const countVisit = (path, title, event = false) => {
    if (!counting) return;
    let from = "";
    try { from = document.referrer ? new URL(document.referrer).hostname : ""; } catch { /* no referrer */ }
    const query = new URLSearchParams({ p: path, t: title, r: from === location.hostname ? "" : from,
                                        s: `${screen.width},${screen.height}`, rnd: Math.random().toString(36).slice(2) });
    if (event) query.set("e", "true");
    new Image().src = `https://${ANALYTICS.goatcounter}.goatcounter.com/count?${query}`;
  };
  countVisit(location.pathname, document.title);
  // Events that other scripts of the site (the free calculators) or any link marked with data-evento ask to count.
  document.addEventListener("nirkana:evento", (event) => {
    const { slug, titulo } = event.detail || {};
    if (/^[a-z0-9-]{3,40}$/.test(slug || "")) countVisit(slug, String(titulo || slug).slice(0, 80), true);
  });
  for (const marked of document.querySelectorAll("[data-evento]")) {
    if (!/^[a-z0-9-]{3,40}$/.test(marked.dataset.evento)) continue;
    marked.addEventListener("click", () => countVisit(marked.dataset.evento, String(marked.dataset.eventoTitulo || marked.dataset.evento).slice(0, 80), true));
  }

  // ------------------------------------------------------------ direct contact buttons
  const phone = String(CONTACT.whatsapp).replace(/\D/g, "");
  const email = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(CONTACT.email || "") ? CONTACT.email : "";
  const mailto = (subject, body) =>
    `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  const mailLink = document.getElementById("email-link");
  if (mailLink && email) {
    mailLink.href = mailto("Quiero NirKanA", MESSAGE);
    mailLink.hidden = false;
    mailLink.addEventListener("click", () => countVisit("contacto-email", "Clic en Contactar por email", true));
  }
  // The address itself, visible: many people read their mail in a web page and a mailto: link does nothing for them.
  if (email) {
    for (const link of document.querySelectorAll("a[data-email]")) {
      link.href = mailto(link.getAttribute("data-subject") || "Quiero NirKanA", MESSAGE);
      link.textContent = email;
      link.hidden = false;
      link.addEventListener("click", () => countVisit("contacto-email", "Clic en la dirección de email", true));
    }
    for (const wrap of document.querySelectorAll("[data-email-wrap]")) wrap.hidden = false;
  }
  const copyButton = document.getElementById("email-copy");
  const copiedNote = document.getElementById("email-copied");
  if (copyButton && copiedNote && email) {
    copyButton.addEventListener("click", async () => {
      countVisit("contacto-copiar", "Dirección de email copiada", true);
      let copied = false;
      try { await navigator.clipboard.writeText(email); copied = true; } catch { /* some browsers refuse: select it instead */ }
      if (!copied) {
        const range = document.createRange();
        range.selectNodeContents(document.getElementById("email-text"));
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      }
      copiedNote.textContent = copied ? "Copiada" : "Selecciónala y cópiala (Ctrl+C)";
    });
  }
  // How many visitors reach the price (an event, once per visit).
  const priceSection = document.getElementById("precio");
  if (priceSection && "IntersectionObserver" in window) {
    const watcher = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      countVisit("precio-visto", "Ha visto el precio", true);
      watcher.disconnect();
    }, { threshold: 0.5 });
    watcher.observe(priceSection);
  }
  // How many visitors reach the solutions by kind of business (an event, once per visit).
  const solutionsSection = document.getElementById("soluciones");
  if (solutionsSection && "IntersectionObserver" in window) {
    const watcher = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      countVisit("soluciones-vistas", "Ha visto las soluciones por sector", true);
      watcher.disconnect();
    }, { threshold: 0.3 });
    watcher.observe(solutionsSection);
  }
  if (phone.length >= 8) {
    for (const wa of document.querySelectorAll("#whatsapp-link, #whatsapp-float")) {
      wa.href = `https://wa.me/${phone}?text=${encodeURIComponent(MESSAGE)}`;
      wa.hidden = false;
    }
  }

  // ------------------------------------------------------------ «Entrar»: the app, for existing customers
  const appLink = document.getElementById("app-link");
  if (appLink && /^https:\/\/[a-z0-9.-]+(\/.*)?$/i.test(APP_URL)) {
    appLink.href = APP_URL;
    appLink.rel = "noopener noreferrer";
    appLink.hidden = false;
  }

  // ------------------------------------------------------------ «Probar NirKanA»: the free 24-hour trial
  // The pages already carry class="has-demo" / "has-trial" on <html> to match this configuration, so the buttons are
  // right on the first paint (a script cannot run before it: the CSP forbids inline scripts). The toggles below only
  // correct a page whose class was left out of step; tests/web-boundaries.test.mjs checks they agree.
  const trialOn = /^https:\/\/[a-z0-9.-]+(\/.*)?$/i.test(TRIAL_URL);
  const demoOn = /^\/[a-z0-9\/_-]*$/i.test(DEMO_URL) || /^https:\/\/[a-z0-9.-]+(\/.*)?$/i.test(DEMO_URL);
  document.documentElement.classList.toggle("has-trial", trialOn); // site.css swaps «Quiero NirKanA» for «Probar NirKanA»
  document.documentElement.classList.toggle("has-demo", demoOn);   // site.css shows the demo links
  if (trialOn) {
    for (const link of document.querySelectorAll("a[data-trial]")) {
      link.href = TRIAL_URL;
      link.rel = "noopener noreferrer";
      link.addEventListener("click", (event) => {
        countVisit("prueba-abierta", "Clic en Probar NirKanA", true);
        openTrial(event, link);
      });
    }
  }

  // The trial runs on a service that sleeps after 15 minutes without visits and then needs up to a minute (sometimes
  // more) to wake up. Rather than leave the visitor on the host's own waiting page, ask it to wake and show our own
  // waiting screen. Two kinds of request go out, because which one wakes the service is not something the host
  // documents: one small image of the app (it only loads once the app answers; the host's waiting page and its 502
  // are not images, so they count as «not yet») and, if that first try fails, one hidden page request, which is what
  // opening the trial does. The trial opens by itself the moment the image loads; if that has not happened after 50
  // seconds the visitor is simply taken there (the host's own waiting page then carries on): there is never a dead
  // end. Only a plain click is handled: new tab, new window and the like keep their normal behaviour.
  const TRIAL_GIVE_UP_MS = 50000;    // after this long, go to the trial anyway
  const TRIAL_REASSURE_MS = 25000;   // after this long, say that it is still starting
  const TRIAL_RETRY_MS = 2500;       // the host answers with something that is not an image while it wakes up: ask again
  const TRIAL_SHOW_AFTER_MS = 700;   // an app that is already awake opens at once, without any screen in between
  const openTrial = (event, link) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (typeof HTMLDialogElement !== "function") return; // very old browser: the plain link does its job
    event.preventDefault();
    const target = link.href;
    const started = Date.now();
    let finished = false;
    let attempt = 0;
    let probe = null;
    let waker = null;
    let retry = 0;
    let dialog = null;
    const timers = [];

    const stop = () => {
      finished = true;
      clearTimeout(retry);
      timers.forEach(clearTimeout);
      if (probe) probe.onload = probe.onerror = null;
      if (waker) waker.remove();
    };
    let leaving = false;
    const open = (event, title) => {
      leaving = true;
      stop();
      if (dialog && dialog.open) dialog.close();
      countVisit(event, title, true);
      setTimeout(() => window.location.assign(target), 150); // a moment for the count to leave before the page does
    };
    const wakeWithPage = () => {
      if (waker || finished) return;
      waker = document.createElement("iframe");
      waker.hidden = true;                // never shown, but it still loads
      waker.tabIndex = -1;
      waker.setAttribute("aria-hidden", "true");
      waker.setAttribute("sandbox", "");  // whatever page comes back can do nothing: it only has to be requested
      waker.src = target;
      document.body.append(waker);
    };
    const ask = () => {
      if (finished) return;
      probe = new Image();
      probe.onload = () => open("prueba-lista", "La prueba abre sola");
      probe.onerror = () => {
        if (finished) return;
        wakeWithPage();
        retry = setTimeout(ask, TRIAL_RETRY_MS);
      };
      probe.src = `${new URL(target).origin}/icons/simbolo.svg?despertar=${started}-${++attempt}`;
    };
    const showScreen = () => {
      if (finished) return;
      dialog = document.createElement("dialog");
      dialog.className = "trial-wait";
      dialog.setAttribute("aria-labelledby", "trial-wait-title");
      dialog.setAttribute("aria-describedby", "trial-wait-text");
      const spinner = document.createElement("div");
      spinner.className = "trial-wait-spin";
      spinner.setAttribute("aria-hidden", "true");
      const title = document.createElement("h2");
      title.id = "trial-wait-title";
      title.textContent = "Preparando tu prueba gratuita";
      const text = document.createElement("p");
      text.id = "trial-wait-text";
      text.setAttribute("role", "status");
      text.textContent = "La primera vez tarda hasta un minuto en arrancar. Se abrirá sola en cuanto esté lista.";
      const actions = document.createElement("div");
      actions.className = "trial-wait-actions";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "btn ghost small";
      cancel.textContent = "Cancelar";
      cancel.addEventListener("click", () => dialog.close());
      actions.append(cancel);
      dialog.append(spinner, title, text, actions);
      dialog.addEventListener("close", () => { // Escape and «Cancelar»: the visitor stays here
        if (!leaving) countVisit("prueba-cancelada", "El visitante cancela la espera", true);
        stop();
        dialog.remove();
      });
      document.body.append(dialog);
      dialog.showModal();
      cancel.focus();
      countVisit("prueba-espera", "Pantalla de espera de la prueba", true);
      timers.push(setTimeout(() => {
        text.textContent = "Sigue arrancando; falta poco. Se abrirá sola en cuanto esté lista.";
      }, TRIAL_REASSURE_MS - (Date.now() - started)));
    };

    timers.push(setTimeout(showScreen, TRIAL_SHOW_AFTER_MS));
    timers.push(setTimeout(() => open("prueba-lenta", "La prueba tarda: se lleva al visitante"), TRIAL_GIVE_UP_MS));
    ask();
  };

  // ------------------------------------------------------------ «Ver la demo»: the example business, no sign-up
  if (demoOn) {
    for (const link of document.querySelectorAll("a[data-demo]")) {
      const sector = link.getAttribute("data-demo"); // a sector opens straight on that kind of business
      link.href = sector ? `${DEMO_URL}?negocio=${encodeURIComponent(sector)}` : DEMO_URL;
      link.addEventListener("click", () => countVisit("demo-abierta", "Clic en Ver la demo", true));
    }
  }

  // ------------------------------------------------------------ menu on small screens
  const top = document.querySelector(".top");
  const menuBtn = document.querySelector(".menu-btn");
  if (top && menuBtn) {
    const setMenu = (open) => {
      top.classList.toggle("open", open);
      menuBtn.setAttribute("aria-expanded", String(open));
      menuBtn.setAttribute("aria-label", open ? "Cerrar el menú" : "Abrir el menú");
    };
    menuBtn.addEventListener("click", () => setMenu(!top.classList.contains("open")));
    document.querySelectorAll(".top nav a").forEach((a) => a.addEventListener("click", () => setMenu(false)));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && top.classList.contains("open")) { setMenu(false); menuBtn.focus(); }
    });
    document.addEventListener("click", (e) => { if (!top.contains(e.target)) setMenu(false); });
    window.matchMedia("(min-width: 1181px)").addEventListener("change", (e) => { if (e.matches) setMenu(false); });
  }

  // ------------------------------------------------------------ contact form
  const form = document.getElementById("contact-form");
  const status = document.getElementById("form-status");
  const say = (text, kind) => { status.textContent = text; status.className = `status ${kind || ""}`; };
  const slug = (text) => text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const clean = (v, max) => String(v || "").replace(/[\u0000-\u0008\u000B-\u001F\u007F]/g, "").trim().slice(0, max);

  const formType = form ? form.elements.namedItem("tipo") : null;
  let typeChosen = false;
  const suggestType = (label) => { if (formType && !typeChosen && label) formType.value = label; };
  if (formType) formType.addEventListener("change", () => { typeChosen = true; });
  const formRequest = form ? form.elements.namedItem("solicitud") : null;
  const setOption = (select, label) => {
    if (!select || !label) return false;
    const option = [...select.options].find((o) => (o.value || o.textContent) === label || o.textContent.trim() === label);
    if (option) select.value = option.value;
    return Boolean(option);
  };
  // «Consultar mi caso» (data-sector) and «Pedir presupuesto» (data-request) arrive at the form with it already filled in,
  // so the visitor is not asked twice. What the visitor chose by hand is never overwritten by a suggestion (see suggestType).
  const promoBox = form ? form.elements.namedItem("promocion") : null;
  document.querySelectorAll("[data-sector], [data-request], [data-promo]").forEach((link) => {
    link.addEventListener("click", () => {
      if (link.hasAttribute("data-promo") && promoBox) {
        promoBox.checked = true;
        countVisit("promo-clic", "Clic en la promoción del 20 %", true);
      }
      const sector = link.getAttribute("data-sector");
      if (sector && setOption(formType, sector)) {
        typeChosen = true;
        countVisit(`contacto-${slug(sector)}`, `Pide información desde el sector ${sector}`, true);
      }
      setOption(formRequest, link.getAttribute("data-request"));
    });
  });

  if (form) {
    let lastSent = 0;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      if (data.get("_gotcha")) return; // a robot filled the hidden field: silently ignore
      if (!form.checkValidity()) {
        form.reportValidity();
        say("Revisa los campos marcados.", "err");
        return;
      }
      if (Date.now() - lastSent < 30000) { say("Ya hemos recibido tu mensaje. Gracias.", "ok"); return; }

      const fields = {
        solicitud: clean(data.get("solicitud"), 60),
        nombre: clean(data.get("nombre"), 80),
        tipo: clean(data.get("tipo"), 40), email: clean(data.get("email"), 120),
        telefono: clean(data.get("telefono"), 20), mensaje: clean(data.get("mensaje"), 1500),
        promocion: data.get("promocion") ? clean(promoBox.value, 60) : "",
      };
      const button = form.querySelector("button[type=submit]");

      if (!CONTACT.formspreeId) { // no form service configured: send the request by WhatsApp or email instead
        const text = `${MESSAGE}\n\nSolicitud: ${fields.solicitud}\nNombre: ${fields.nombre}\nTipo de negocio: ${fields.tipo}\nPromoción: ${fields.promocion || "-"}\n` +
          `Email: ${fields.email}\nTeléfono: ${fields.telefono || "-"}\n\n${fields.mensaje}`;
        if (phone.length < 8 && email) {
          window.location.href = mailto(`${fields.solicitud} · NirKanA · ${fields.nombre}`, text);
          say(`Se ha abierto tu correo con el mensaje preparado. Si no se abre, escríbenos a ${email}.`, "ok");
          lastSent = Date.now();
          return;
        }
        if (phone.length < 8) {
          say("El formulario todavía no está disponible. Inténtalo de nuevo en unos días.", "err");
          return;
        }
        window.open(`https://wa.me/${phone}?text=${encodeURIComponent(text)}`, "_blank", "noopener,noreferrer");
        say("Se ha abierto WhatsApp con tu mensaje preparado. Solo tienes que enviarlo.", "ok");
        lastSent = Date.now();
        return;
      }

      button.disabled = true;
      say("Enviando…");
      try {
        const id = encodeURIComponent(CONTACT.formspreeId);
        const res = await fetch(`https://formspree.io/f/${id}`, {
          method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ ...fields, _subject: `${fields.solicitud} · NirKanA · ${fields.nombre}` }),
          credentials: "omit", referrerPolicy: "strict-origin-when-cross-origin",
        });
        if (!res.ok) throw new Error(String(res.status));
        form.reset();
        typeChosen = false;
        lastSent = Date.now();
        countVisit("contacto-enviado", "Formulario de contacto enviado", true); // how many visits become requests
        if (fields.promocion) countVisit("promo-solicitada", "Solicitud con la promoción del 20 %", true);
        say("¡Gracias! Te responderé en menos de 24 horas laborables.", "ok");
      } catch {
        say(email ? `No se pudo enviar. Inténtalo de nuevo o escríbenos a ${email}.` : "No se pudo enviar. Inténtalo de nuevo en unos minutos.", "err");
      } finally {
        button.disabled = false;
      }
    });
  }

  // ------------------------------------------------------------ counters (supports a suffix such as "25+")
  const counters = document.querySelectorAll("[data-count]");
  const count = (el) => {
    const text = el.dataset.count || "0";
    const match = text.match(/^(\d+)/);
    const target = match ? Number(match[1]) : 0;
    const suffix = text.replace(/^\d+/, "");
    if (reduceMotion) { el.textContent = String(target) + suffix; return; }
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / 1200, 1);
      el.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3)))) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => { if (entry.isIntersecting) { count(entry.target); io.unobserve(entry.target); } });
    }, { threshold: 0.6 });
    counters.forEach((el) => io.observe(el));
  }

  // ------------------------------------------------------------ folded boxes (calculator, promotion terms): a link to them opens them
  const openFolded = () => {
    const box = location.hash.length > 1 ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    if (box && box.matches("details")) box.open = true;
  };
  openFolded();
  window.addEventListener("hashchange", openFolded);
  document.querySelectorAll("[data-promo-link]").forEach((link) => link.addEventListener("click", () => {
    const box = document.getElementById((link.getAttribute("href") || "").split("#")[1] || "");
    if (box && box.matches("details")) box.open = true;
  }));

  // ------------------------------------------------------------ sector tabs (ARIA tabs with arrow keys)
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const TAB_TYPES = { "tab-hosteleria": "Hostelería", "tab-belleza": "Belleza y estética", "tab-comercio": "Comercio",
                      "tab-autonomo": "Autónomo", "tab-pyme": "Pyme", "tab-otros": "Otro" };
  const selectTab = (tab, focus) => {
    suggestType(TAB_TYPES[tab.id]);
    tabs.forEach((t) => {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(t.getAttribute("aria-controls"));
      panel.hidden = !on;
      if (on && !reduceMotion) { panel.classList.remove("enter"); void panel.offsetWidth; panel.classList.add("enter"); }
    });
    // Keep the selected sector visible without scrolling the document away from the visitor.
    const strip = tab.closest('[role="tablist"]');
    if (strip) {
      const selected = tab.getBoundingClientRect();
      const viewport = strip.getBoundingClientRect();
      const shift = selected.left < viewport.left ? selected.left - viewport.left
        : selected.right > viewport.right ? selected.right - viewport.right : 0;
      if (shift) strip.scrollBy({ left: shift, behavior: reduceMotion ? "instant" : "smooth" });
    }
    if (focus) tab.focus();
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => {
      selectTab(tab);
      countVisit(`sector-${tab.id.replace("tab-", "")}`, `Sector consultado: ${TAB_TYPES[tab.id]}`, true); // which businesses are asking
    });
    tab.addEventListener("keydown", (e) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      if (step) { e.preventDefault(); selectTab(tabs[(i + step + tabs.length) % tabs.length], true); }
      if (e.key === "Home" || e.key === "End") {
        e.preventDefault(); selectTab(e.key === "Home" ? tabs[0] : tabs[tabs.length - 1], true);
      }
    });
  });
  document.querySelectorAll("[data-tab]").forEach((link) => {
    link.addEventListener("click", () => { const t = document.getElementById(link.dataset.tab); if (t) selectTab(t); });
  });

  // Each sector shows three screens: the thumbnails swap the big one.
  document.querySelectorAll(".panel").forEach((panel) => {
    const big = panel.querySelector(".browser");
    if (!big) return; // «Otros negocios» has no screenshots
    const main = big.querySelector(".main");
    const label = big.querySelector(".chrome > span");
    panel.querySelectorAll(".thumbs button").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(btn.classList.contains("on")));
      btn.addEventListener("click", () => {
        panel.querySelectorAll(".thumbs button").forEach((b) => {
          b.classList.toggle("on", b === btn);
          b.setAttribute("aria-pressed", String(b === btn));
        });
        big.dataset.full = btn.dataset.full;
        main.classList.add("swap");
        setTimeout(() => {
          main.src = btn.dataset.src;
          main.alt = btn.dataset.alt;
          label.textContent = `nirkana · ${btn.textContent.trim().toLowerCase()}`;
          main.classList.remove("swap");
        }, reduceMotion ? 0 : 200);
      });
    });
  });

  // ------------------------------------------------------------ arriving from the end-of-trial page (or a shared link)
  // Only known values are accepted; anything else in the address is ignored.
  const params = new URLSearchParams(location.search);
  if (form && params.get("promo") === "20" && promoBox) promoBox.checked = true;
  if (form && params.get("solicitud") === "presupuesto") setOption(formRequest, "Pedir presupuesto");
  const wanted = params.get("sector");
  if (form && wanted && TAB_TYPES[`tab-${wanted}`]) { setOption(formType, TAB_TYPES[`tab-${wanted}`]); typeChosen = true; }
  // Links that carry the visitor's sector on to the home page (the end-of-trial page)
  if (/^[a-z]{3,12}$/.test(wanted || "")) {
    document.querySelectorAll("a[data-forward]").forEach((link) => {
      const url = new URL(link.getAttribute("href"), location.href);
      url.searchParams.set("sector", wanted);
      link.setAttribute("href", `${url.pathname}${url.search}${url.hash}`);
    });
  }

  // ------------------------------------------------------------ lightbox: any screenshot opens full size
  const lightbox = document.getElementById("lightbox");
  if (lightbox && typeof lightbox.showModal === "function") {
    const lbImg = lightbox.querySelector("img");
    const lbCap = lightbox.querySelector(".lb-cap");
    document.querySelectorAll(".zoomable").forEach((el) => {
      el.addEventListener("click", () => {
        const img = el.querySelector("img");
        lbImg.src = el.dataset.full;
        lbImg.alt = img ? img.alt : "";
        const cap = el.querySelector(".cap b");
        lbCap.textContent = cap ? cap.textContent : lbImg.alt;
        lightbox.showModal();
      });
    });
    lightbox.querySelector(".lb-close").addEventListener("click", () => lightbox.close());
    lightbox.addEventListener("click", (e) => { if (e.target === lightbox) lightbox.close(); });
  }

  // ------------------------------------------------------------ cost-of-time calculator
  // Every figure comes from the visitor's own inputs (hours, value of an hour, share they think they could save);
  // nothing here is a claim about what NirKanA saves.
  const euros = (v) => `${String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ".")} €`;
  const calc = document.getElementById("calc");
  if (calc) {
    const $ = (id) => document.getElementById(id);
    const ranges = calc.querySelectorAll('input[type="range"]');
    const update = () => {
      const hours = Number($("c-hours").value), rate = Number($("c-rate").value), share = Number($("c-share").value) / 100;
      ranges.forEach((r) => r.style.setProperty("--fill", `${((r.value - r.min) / (r.max - r.min)) * 100}%`));
      $("o-hours").textContent = `${hours} h`;
      $("o-rate").textContent = euros(rate);
      $("o-share").textContent = `${Math.round(share * 100)} %`;
      const month = hours * 4.33;
      $("r-hours").textContent = `${Math.round(month)} h`;
      $("r-time").textContent = euros(month * rate);
      $("r-saved").textContent = `${Math.round(month * share)} h`;
      $("r-year").textContent = euros(month * share * rate * 12);
    };
    calc.addEventListener("input", update);
    calc.addEventListener("submit", (e) => e.preventDefault());
    update();
  }

  // ------------------------------------------------------------ scroll reveal, staggered among siblings
  if ("IntersectionObserver" in window && !reduceMotion) {
    document.documentElement.classList.add("reveal");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add("in"); io.unobserve(entry.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    document.querySelectorAll("[data-reveal]").forEach((el) => {
      const siblings = [...el.parentElement.children].filter((c) => c.hasAttribute("data-reveal"));
      el.style.setProperty("--d", `${Math.min(siblings.indexOf(el) * 0.07, 0.42)}s`);
      io.observe(el);
    });
  }

  // ------------------------------------------------------------ header: highlight the section in view
  const navLinks = [...document.querySelectorAll(".top nav a")];
  if (navLinks.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) navLinks.forEach((a) => a.classList.toggle("here", a.hash === `#${entry.target.id}`));
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    // Every section, so that one with no menu entry (Contacto, Seguridad…) leaves none highlighted.
    document.querySelectorAll("main section[id]").forEach((section) => io.observe(section));
  }

  // ------------------------------------------------------------ 3D particle orb behind the headline
  const hero = document.querySelector(".hero");
  const canvas = document.querySelector(".orb");
  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  if (canvas && canvas.getContext) {
    let ctx = null; // created on the first fit: opening a 2D context is not cheap and can wait for the first frame
    const small = window.innerWidth < 760;
    const N = small ? 420 : 1300;
    const golden = Math.PI * (3 - Math.sqrt(5));
    const points = Array.from({ length: N }, (_, i) => {
      const y = 1 - (i / (N - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const t = golden * i;
      return { x: Math.cos(t) * r, y, z: Math.sin(t) * r, phase: Math.random() * Math.PI * 2 };
    });
    let w = 0, h = 0, dpr = 1, running = true, visible = true;
    // Where the small hero text sits on the canvas: particles there are drawn faint so the text stays easy to read.
    const quiet = [...document.querySelectorAll(".hero .pill, .hero .lead")];
    let calm = [];
    const measure = () => {
      const c = canvas.getBoundingClientRect();
      calm = quiet.map((el) => {
        const r = el.getBoundingClientRect();
        return { l: r.left - c.left - 12, t: r.top - c.top - 10, r: r.right - c.left + 12, b: r.bottom - c.top + 10 };
      });
    };
    const inCalm = (x, y) => calm.some((q) => x > q.l && x < q.r && y > q.t && y < q.b);
    const resize = () => {
      if (!ctx) ctx = canvas.getContext("2d");
      w = canvas.clientWidth; h = canvas.clientHeight;
      // The dots are soft and tiny, so a phone does not need 3x resolution: a canvas of ~0.9 million pixels at most keeps
      // every frame cheap to upload (a full-hero canvas at 2.6x was ~1.5 million on a 412 px phone).
      dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(900000 / Math.max(1, w * h))));
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      measure();
    };
    const mix = (a, b, t) => Math.round(a + (b - a) * t);
    // Drawing one path per particle made every frame a long task on a phone. Particles are instead grouped into a few
    // colour and brightness steps (not visible to the eye) and each group is filled once: ~40 fills instead of ~1300.
    const SHADES = 6, LEVELS = 7;
    const shade = Array.from({ length: SHADES }, (_, k) => {
      const t = k / (SHADES - 1);
      return `${mix(142, 94, t)}, ${mix(162, 234, t)}, ${mix(255, 212, t)}`;
    });
    for (const p of points) p.shade = Math.round(((p.y + 1) / 2) * (SHADES - 1));
    const groups = Array.from({ length: SHADES * LEVELS }, () => []);
    const draw = (time) => {
      if (!ctx || !w || !h) return; // not laid out yet
      ctx.clearRect(0, 0, w, h);
      pointer.x += (pointer.tx - pointer.x) * 0.05;
      pointer.y += (pointer.ty - pointer.y) * 0.05;
      const ay = time * 0.00012 + pointer.x * 0.9;
      const ax = -0.35 + pointer.y * 0.6;
      const cy = Math.cos(ay), sy = Math.sin(ay), cx = Math.cos(ax), sx = Math.sin(ax);
      const R = small ? Math.min(w * 0.46, 200) : Math.min(w * 0.24, 320);
      const ox = w / 2, oy = small ? Math.min(h * 0.22, 320) : Math.min(h * 0.2, 400);
      const f = 2.4;
      for (const g of groups) g.length = 0;
      for (const p of points) {
        const breathe = 1 + 0.035 * Math.sin(time * 0.0012 + p.phase);
        const x = p.x * breathe, y = p.y * breathe, z = p.z * breathe;
        const x1 = x * cy - z * sy; const z1 = x * sy + z * cy;
        const y2 = y * cx - z1 * sx; const z2 = y * sx + z1 * cx;
        const scale = f / (f + z2);
        const depth = (1 - z2) / 2; // 1 = front
        const px = ox + x1 * R * scale, py = oy + y2 * R * scale;
        const alpha = (0.12 + depth * 0.55) * (inCalm(px, py) ? 0.18 : 1);
        const level = Math.min(LEVELS - 1, Math.max(0, Math.round(alpha / 0.67 * (LEVELS - 1))));
        groups[p.shade * LEVELS + level].push(px, py, (0.6 + depth * 1.5) * scale);
      }
      for (let k = 0; k < groups.length; k++) {
        const g = groups[k];
        if (!g.length) continue;
        const level = k % LEVELS;
        ctx.fillStyle = `rgba(${shade[(k - level) / LEVELS]}, ${((level / (LEVELS - 1)) * 0.67).toFixed(3)})`;
        ctx.beginPath();
        for (let i = 0; i < g.length; i += 3) {
          ctx.moveTo(g[i] + g[i + 2], g[i + 1]);
          ctx.arc(g[i], g[i + 1], g[i + 2], 0, Math.PI * 2);
        }
        ctx.fill();
      }
      // a tilted orbit ring
      ctx.strokeStyle = "rgba(142, 162, 255, .18)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(ox, oy, R * 1.45, R * 0.32, -0.25 + pointer.x * 0.3, 0, Math.PI * 2);
      ctx.stroke();
    };
    let last = -1000;
    const loop = (time) => {
      if (!running || !visible) return;
      if (time - last >= 30) { last = time; draw(time); } // the slow turn needs ~30 frames a second, not 60
      requestAnimationFrame(loop);
    };
    // Sized when the browser has laid the page out anyway (ResizeObserver), not by reading sizes here, which would force
    // a full style and layout pass in the middle of this script.
    const fit = () => { resize(); if (reduceMotion) draw(0); };
    if ("ResizeObserver" in window) new ResizeObserver(fit).observe(canvas);
    else { fit(); window.addEventListener("resize", fit); }
    if (!reduceMotion) {
      new IntersectionObserver(([entry]) => {
        const was = visible; visible = entry.isIntersecting;
        if (visible && !was) requestAnimationFrame(loop);
      }).observe(canvas);
      document.addEventListener("visibilitychange", () => {
        running = !document.hidden;
        if (running) requestAnimationFrame(loop);
      });
      requestAnimationFrame(loop);
    }
  }

  // The header turns dark glass while it sits over the dark hero, and light glass over the rest.
  if (top) {
    const darkSections = [...document.querySelectorAll(".hero")];
    let queued = false;
    const onDark = () => {
      queued = false;
      const edge = top.offsetHeight + 1, mid = top.offsetHeight / 2; // a dark section right under the bar counts too (the hero at the top)
      top.classList.toggle("on-dark", darkSections.some((s) => { const r = s.getBoundingClientRect(); return r.top <= edge && r.bottom >= mid; }));
    };
    const queue = () => { if (!queued) { queued = true; requestAnimationFrame(onDark); } };
    window.addEventListener("scroll", queue, { passive: true });
    window.addEventListener("resize", queue);
    onDark();
  }

  if (reduceMotion) return;

  // ------------------------------------------------------------ hero: light, orb and app follow the pointer
  const stage = document.querySelector("[data-tilt] .stage");
  if (hero) {
    hero.addEventListener("pointermove", (e) => {
      const r = hero.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      hero.style.setProperty("--px", `${(x * 100).toFixed(1)}%`);
      hero.style.setProperty("--py", `${(y * 100).toFixed(1)}%`);
      pointer.tx = x - 0.5; pointer.ty = y - 0.5;
      if (stage && finePointer) {
        stage.style.setProperty("--rx", `${((x - 0.5) * 12).toFixed(2)}deg`);
        stage.style.setProperty("--ry", `${((0.5 - y) * 6).toFixed(2)}deg`);
      }
    });
    hero.addEventListener("pointerleave", () => {
      pointer.tx = 0; pointer.ty = 0;
      if (stage) { stage.style.setProperty("--rx", "0deg"); stage.style.setProperty("--ry", "0deg"); }
    });
  }
  // The app lies back in 3D and stands up as you scroll.
  if (stage) {
    let frame = 0;
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const r = stage.getBoundingClientRect();
        const p = Math.min(Math.max(1 - (r.top - window.innerHeight * 0.25) / (window.innerHeight * 0.7), 0), 1);
        stage.style.setProperty("--sx", `${(22 * (1 - p)).toFixed(2)}deg`);
        stage.style.setProperty("--ss", (0.94 + 0.06 * p).toFixed(3));
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  if (!finePointer) return;

  // ------------------------------------------------------------ cards tilt towards the pointer
  document.querySelectorAll(".tilt").forEach((card) => {
    card.addEventListener("pointermove", (e) => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      card.style.setProperty("--rx", `${((x - 0.5) * 12).toFixed(2)}deg`);
      card.style.setProperty("--ry", `${((0.5 - y) * 12).toFixed(2)}deg`);
      card.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`);
      card.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
    });
    card.addEventListener("pointerleave", () => {
      card.style.setProperty("--rx", "0deg");
      card.style.setProperty("--ry", "0deg");
    });
  });

  // ------------------------------------------------------------ magnetic buttons
  document.querySelectorAll(".magnet").forEach((btn) => {
    btn.addEventListener("pointermove", (e) => {
      const r = btn.getBoundingClientRect();
      btn.style.setProperty("--mx2", `${((e.clientX - r.left - r.width / 2) * 0.25).toFixed(1)}px`);
      btn.style.setProperty("--my2", `${((e.clientY - r.top - r.height / 2) * 0.35).toFixed(1)}px`);
      btn.classList.add("pull");
    });
    btn.addEventListener("pointerleave", () => btn.classList.remove("pull"));
  });
})();


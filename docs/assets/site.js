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
const MESSAGE = "Hola, me interesa NirKanA para mi negocio. ¿Podemos ver una demo?";

// Address of the app for existing customers (e.g. "https://app.nirkana.es"). Empty: no «Entrar» link is shown.
const APP_URL = "";

// Visit counter (GoatCounter): your site code, e.g. "nirkana" for nirkana.goatcounter.com. Empty: nothing is counted.
// No cookies, nothing stored on the visitor's device, no third-party script; visitors who ask not to be tracked
// (Do Not Track or Global Privacy Control) are not counted.
const ANALYTICS = { goatcounter: "" };

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

  // ------------------------------------------------------------ direct contact buttons
  const phone = String(CONTACT.whatsapp).replace(/\D/g, "");
  const email = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(CONTACT.email || "") ? CONTACT.email : "";
  const mailto = (subject, body) =>
    `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  const mailLink = document.getElementById("email-link");
  if (mailLink && email) {
    mailLink.href = mailto("Demo de NirKanA", MESSAGE);
    mailLink.hidden = false;
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
    appLink.hidden = false;
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
    window.matchMedia("(min-width: 921px)").addEventListener("change", (e) => { if (e.matches) setMenu(false); });
  }

  // ------------------------------------------------------------ contact form
  const form = document.getElementById("contact-form");
  const status = document.getElementById("form-status");
  const say = (text, kind) => { status.textContent = text; status.className = `status ${kind || ""}`; };
  const clean = (v, max) => String(v || "").replace(/[\u0000-\u0008\u000B-\u001F\u007F]/g, "").trim().slice(0, max);

  const formType = form ? form.elements.namedItem("tipo") : null;
  let typeChosen = false;
  const suggestType = (label) => { if (formType && !typeChosen && label) formType.value = label; };
  if (formType) formType.addEventListener("change", () => { typeChosen = true; });

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
        nombre: clean(data.get("nombre"), 80), negocio: clean(data.get("negocio"), 100),
        tipo: clean(data.get("tipo"), 40), email: clean(data.get("email"), 120),
        telefono: clean(data.get("telefono"), 20), mensaje: clean(data.get("mensaje"), 1500),
      };
      const button = form.querySelector("button[type=submit]");

      if (!CONTACT.formspreeId) { // no form service configured: send the request by WhatsApp or email instead
        const text = `${MESSAGE}\n\nNombre: ${fields.nombre}\nNegocio: ${fields.negocio} (${fields.tipo})\n` +
          `Email: ${fields.email}\nTeléfono: ${fields.telefono || "-"}\n\n${fields.mensaje}`;
        if (phone.length < 8 && email) {
          window.location.href = mailto(`Demo de NirKanA · ${fields.negocio}`, text);
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
          body: JSON.stringify({ ...fields, _subject: `Demo de NirKanA · ${fields.negocio}` }),
          credentials: "omit", referrerPolicy: "strict-origin-when-cross-origin",
        });
        if (!res.ok) throw new Error(String(res.status));
        form.reset();
        typeChosen = false;
        lastSent = Date.now();
        countVisit("contacto-enviado", "Formulario de contacto enviado", true); // how many visits become requests
        say("¡Gracias! Te responderé en menos de 24 horas laborables.", "ok");
      } catch {
        say(email ? `No se pudo enviar. Inténtalo de nuevo o escríbenos a ${email}.` : "No se pudo enviar. Inténtalo de nuevo en unos minutos.", "err");
      } finally {
        button.disabled = false;
      }
    });
  }

  // ------------------------------------------------------------ scroll story: device follows the text
  const steps = [...document.querySelectorAll(".step-card")];
  const shots = [...document.querySelectorAll(".screens img")];
  const dots = [...document.querySelectorAll(".dots i")];
  const device = document.querySelector(".device");
  const angles = [-12, 12, -8, 10];
  const show = (i) => {
    steps.forEach((el, k) => el.classList.toggle("active", k === i));
    shots.forEach((el, k) => el.classList.toggle("on", k === i));
    dots.forEach((el, k) => el.classList.toggle("on", k === i));
    if (device) device.style.setProperty("--dy", `${angles[i] || 0}deg`);
  };
  if (steps.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => { if (entry.isIntersecting) show(steps.indexOf(entry.target)); });
    }, { rootMargin: "-45% 0px -45% 0px" });
    steps.forEach((el) => io.observe(el));
    show(0);
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

  // ------------------------------------------------------------ sector tabs (ARIA tabs with arrow keys)
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const TAB_TYPES = { "tab-rest": "Restaurante / cafetería", "tab-shop": "Tienda / comercio",
                      "tab-pro": "Autónomo / servicios", "tab-web": "Tienda online" };
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
    if (focus) tab.focus();
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", (e) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      if (step) { e.preventDefault(); selectTab(tabs[(i + step + tabs.length) % tabs.length], true); }
    });
  });
  document.querySelectorAll("[data-tab]").forEach((link) => {
    link.addEventListener("click", () => { const t = document.getElementById(link.dataset.tab); if (t) selectTab(t); });
  });

  // Each sector shows three screens: the thumbnails swap the big one.
  document.querySelectorAll(".panel").forEach((panel) => {
    const big = panel.querySelector(".browser");
    const main = big.querySelector(".main");
    const label = big.querySelector(".chrome > span");
    panel.querySelectorAll(".thumbs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        panel.querySelectorAll(".thumbs button").forEach((b) => b.classList.toggle("on", b === btn));
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

  // ------------------------------------------------------------ value calculator (estimates, no prices)
  // Share of admin time automated and share of sales recovered from mistakes, by sector. Kept deliberately modest.
  const SECTORS = {
    restaurant: { save: 0.5, leak: 0.01 },
    retail: { save: 0.45, leak: 0.008 },
    services: { save: 0.35, leak: 0.004 },
    online: { save: 0.4, leak: 0.006 },
  };
  const euros = (v) => `${String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ".")} €`;
  const calc = document.getElementById("calc");
  if (calc) {
    const $ = (id) => document.getElementById(id);
    const ranges = calc.querySelectorAll('input[type="range"]');
    const update = () => {
      const s = SECTORS[$("c-type").value] || SECTORS.restaurant;
      const sales = Number($("c-sales").value), hours = Number($("c-hours").value), rate = Number($("c-rate").value);
      ranges.forEach((r) => r.style.setProperty("--fill", `${((r.value - r.min) / (r.max - r.min)) * 100}%`));
      $("o-sales").textContent = euros(sales);
      $("o-hours").textContent = `${hours} h`;
      $("o-rate").textContent = euros(rate);
      const saved = hours * 4.33 * s.save;
      const timeValue = saved * rate;
      const loss = sales * s.leak;
      $("r-hours").textContent = `${Math.round(saved)} h`;
      $("r-time").textContent = euros(timeValue);
      $("r-loss").textContent = euros(loss);
      $("r-year").textContent = euros((timeValue + loss) * 12);
    };
    calc.addEventListener("input", update);
    $("c-type").addEventListener("change", (e) => suggestType(e.target.selectedOptions[0]?.textContent.trim()));
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
    const ctx = canvas.getContext("2d");
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
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      measure();
    };
    const mix = (a, b, t) => Math.round(a + (b - a) * t);
    const draw = (time) => {
      ctx.clearRect(0, 0, w, h);
      pointer.x += (pointer.tx - pointer.x) * 0.05;
      pointer.y += (pointer.ty - pointer.y) * 0.05;
      const ay = time * 0.00012 + pointer.x * 0.9;
      const ax = -0.35 + pointer.y * 0.6;
      const cy = Math.cos(ay), sy = Math.sin(ay), cx = Math.cos(ax), sx = Math.sin(ax);
      const R = small ? Math.min(w * 0.46, 200) : Math.min(w * 0.24, 320);
      const ox = w / 2, oy = small ? Math.min(h * 0.22, 320) : Math.min(h * 0.2, 400);
      const f = 2.4;
      for (const p of points) {
        const breathe = 1 + 0.035 * Math.sin(time * 0.0012 + p.phase);
        let x = p.x * breathe, y = p.y * breathe, z = p.z * breathe;
        const x1 = x * cy - z * sy; const z1 = x * sy + z * cy;
        const y2 = y * cx - z1 * sx; const z2 = y * sx + z1 * cx;
        const scale = f / (f + z2);
        const depth = (1 - z2) / 2; // 1 = front
        const t = (p.y + 1) / 2;
        const px = ox + x1 * R * scale, py = oy + y2 * R * scale;
        const alpha = (0.12 + depth * 0.55) * (inCalm(px, py) ? 0.18 : 1);
        ctx.fillStyle = `rgba(${mix(142, 94, t)}, ${mix(162, 234, t)}, ${mix(255, 212, t)}, ${alpha.toFixed(3)})`;
        const size = (0.6 + depth * 1.5) * scale;
        ctx.beginPath();
        ctx.arc(px, py, size, 0, Math.PI * 2);
        ctx.fill();
      }
      // a tilted orbit ring
      ctx.strokeStyle = "rgba(142, 162, 255, .18)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(ox, oy, R * 1.45, R * 0.32, -0.25 + pointer.x * 0.3, 0, Math.PI * 2);
      ctx.stroke();
    };
    const loop = (time) => {
      if (!running || !visible) return;
      draw(time);
      requestAnimationFrame(loop);
    };
    resize();
    window.addEventListener("resize", resize);
    if (reduceMotion) {
      draw(0);
    } else {
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

  // Header turns dark glass while it sits over the dark hero.
  if (top && hero) {
    const onDark = () => top.classList.toggle("on-dark", window.scrollY < hero.offsetHeight - 64);
    window.addEventListener("scroll", onDark, { passive: true });
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

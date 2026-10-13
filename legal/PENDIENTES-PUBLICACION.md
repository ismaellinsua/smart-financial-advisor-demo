# Pendientes legales antes de publicar NirKanA

**No generar ni publicar datos fiscales inventados.** La web sigue sin aviso legal definitivo hasta completar la identidad del titular por un canal privado.

- Completar de forma privada `legal/datos.json` a partir de `legal/datos.example.json`: titular legal, NIF, domicilio válido y fecha.
- Ejecutar `python ops/legal.py --check` y después `python ops/legal.py` solamente con datos verificados y autorización del titular.
- Revisar `docs/aviso-legal.html`, el pie de las páginas y `docs/privacidad.html` antes de publicar; solicitar revisión profesional.
- Verificar en producción cookies, localStorage, sessionStorage, IndexedDB y peticiones de terceros de web y demo; si aparecen tecnologías no esenciales, implantar consentimiento previo real.
- Verificar destinatario, base jurídica, conservación y subencargados del formulario Formspree.
- Comprobar que los precios, prueba de 24 horas, facturación y VERI*FACTU reflejan funcionalidades realmente desplegadas.

Normativa de referencia: LSSI-CE art. 10 y 22.2; RGPD y LOPDGDD; guía de cookies de la AEPD.

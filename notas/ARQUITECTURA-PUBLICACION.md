# NirKanA: límites entre web, demostración y producto comercial

## Fuente de verdad
- `nirkana-app`: aplicación comercial FastAPI/PWA, código privado, modo `produccion` en `app.nirkana.es`.
- El mismo código de `nirkana-app`, desplegado en modo `prueba` y con **otra base de datos**, gestiona la prueba de 24 horas en `prueba.nirkana.es`.
- `docs/` de este repositorio: web comercial estática de `nirkana.es`.
- `docs/demo/`: demostración **sin registro** y con datos ficticios, no equivalente a la prueba temporal de 24 horas.
- `sales_manager/`: implementación histórica Streamlit; no debe convertirse en backend de clientes ni conectarse a datos de producción.

## Reglas antes de publicar
1. No publicar ni activar un enlace a un subdominio hasta verificar HTTPS, despliegue, salud de la base de datos y separación de credenciales.
2. No copiar secretos ni datos de clientes a GitHub Pages, a `docs/demo/` o a `sales_manager/`.
3. Conservar `TRIAL_URL` y `APP_URL` vacíos hasta comprobar sus servicios; `DEMO_URL=/demo/` es una vista local ficticia.
4. La demo sin registro no promete 24 horas de acceso; ese plazo corresponde únicamente al servicio `APP_MODE=prueba`.
5. Toda venta o contratación real se gestiona desde `nirkana.oficial@gmail.com` hasta validar el circuito de pagos.
6. Mantener la web pública separada del repositorio privado de producto; revisar qué archivos se publican al desplegar `docs/`.
7. No afirmar conformidad fiscal o VERI*FACTU sin pruebas oficiales y revisión legal.
8. Antes de fusionar cambios, ejecutar las pruebas, revisar los enlaces y comprobar en móvil y escritorio.

## Flujo comercial
Visita `nirkana.es` → demo ficticia inmediata (opcional) → prueba de 24 horas (cuando esté desplegada) → contacto comercial → alta manual de cliente en producción.

## Riesgo pendiente
Este repositorio privado contiene la web de GitHub Pages. La visibilidad del repositorio y la disponibilidad pública de Pages son cuestiones distintas; comprobar que el sitio es accesible sin iniciar sesión y que no publica ficheros fuera de `docs/`. Para una separación de repositorios estricta, migrar únicamente los archivos estáticos aprobados a un repositorio web público, tras revisar secretos y licencias.

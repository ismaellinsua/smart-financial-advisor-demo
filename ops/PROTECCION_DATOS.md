# Protección de datos: medidas técnicas, subencargados y brechas

Documento interno de NirKanA. Describe lo que el software hace hoy, con referencias al código, para el registro de
actividades (RGPD art. 30), las medidas de seguridad (art. 32) y como base del contrato de encargado (art. 28) que
debe redactar un abogado. **Revísalo cada vez que cambie el hosting o un proveedor.**

## Papeles

| Quién | Papel | Sobre qué datos |
|---|---|---|
| Cada negocio cliente | Responsable del tratamiento | Sus clientes, su equipo, sus ventas y facturas |
| NirKanA (su titular) | Encargado del tratamiento | Lo anterior, solo para prestar el servicio |
| NirKanA | Responsable | Datos de contacto y de facturación de los negocios (alta, Stripe, soporte) |

## Qué datos trata la app

- **Clientes del negocio:** nombre, email, teléfono, NIF y dirección (solo si se factura), notas, compras, puntos,
  consentimiento de marketing con su fecha.
- **Reservas online:** nombre, teléfono, email y número de personas. El teléfono y el email se borran solos
  90 días después de la cita (`core/store_bookings.py`, `CONTACT_DAYS`).
- **Equipo:** nombre, usuario, rol, contraseña o PIN guardados como hash PBKDF2-SHA256 (nunca en claro), segundo
  factor (TOTP) opcional, sesiones y registro de actividad.
- **Pagos del servicio:** los gestiona Stripe. NirKanA solo guarda el identificador del cliente y de la suscripción,
  su estado y la fecha de renovación; nunca la tarjeta.

## Plazos de conservación (borrado automático diario)

| Dato | Plazo | Dónde |
|---|---|---|
| Teléfono y email de reservas | 90 días tras la cita | `forget_booking_contacts` |
| Registro de actividad | 2 años | `apply_retention`, `RETENTION_DAYS` en `core/store_privacy.py` |
| Informes de errores | 180 días | ídem |
| Sesiones cerradas o abandonadas | 90 días | ídem |
| Ventas, facturas y registro VERI*FACTU | Se conservan (obligación legal: 4 años fiscal, 6 mercantil) | — |
| Cliente que pide la supresión | Se anonimiza al momento; sus facturas conservan los datos fiscales obligatorios | `forget_customer` |

## Derechos de las personas (los ejerce el negocio desde la app)

Acceso y portabilidad (descarga de todos los datos de un cliente en JSON), supresión (anonimización), oposición al
marketing (consentimiento revocable con fecha). Cada exportación o supresión queda en el registro de actividad.

## Medidas de seguridad (art. 32)

| Medida | Detalle |
|---|---|
| Aislamiento entre negocios | Un esquema de PostgreSQL por negocio; cada consulta usa solo el suyo (`core/tenants.py`) |
| Acceso | Cuentas individuales con roles; bloqueo tras intentos fallidos, contados por la IP real del visitante; cookie de sesión HttpOnly en el contenedor; claves de verificación en dos pasos cifradas (`DATA_KEY`) y códigos de un solo uso; 2FA para administradores y para el panel de operador; intentos fallidos contados en la base de datos; códigos de recuperación; re-confirmar la contraseña antes de borrar o restaurar datos |
| Cifrado en tránsito | HTTPS (HSTS en el contenedor); PostgreSQL remoto solo con TLS comprobando el certificado del servidor (`sslmode=verify-full`) |
| Cifrado de copias | Copias diarias cifradas con frase de paso (`ops/backup.py`), una por negocio |
| Cabeceras | Protección contra incrustar la app en otras webs, `nosniff`, `Referrer-Policy`, `Permissions-Policy` |
| Sin terceros en el navegador | Fuentes e iconos servidos por la propia app: el navegador del usuario no contacta con Google ni con nadie más |
| Integridad de facturas | Registro de facturación encadenado con hash y protegido contra cambios incluso por SQL directo |
| Trazabilidad | Registro de actividad: accesos, fallos, anulaciones, facturas, exportaciones, cambios de equipo |
| Errores | El usuario ve una referencia, nunca detalles internos; el detalle queda en el servidor |

## Subencargados

Rellena la columna «En uso» con lo que esté contratado de verdad antes de firmar ningún contrato.

| Proveedor | Para qué | Ubicación de los datos | En uso |
|---|---|---|---|
| Neon (Databricks) | Base de datos PostgreSQL | UE, Fráncfort (eu-central-1), si se elige al crear el proyecto | |
| Render | Servidor de la app (contenedor) | UE, Fráncfort, con `region: frankfurt` (`render.yaml`) | |
| Streamlit Community Cloud (Snowflake) | Servidor de la app (alternativa gratuita) | Probablemente EE. UU.: no usar para clientes de pago | |
| Stripe Payments Europe | Cobro de la suscripción | UE (Irlanda), con transferencias a EE. UU. bajo el marco UE-EE. UU. | |
| Proveedor de email (SMTP) | Avisos, recordatorios, recuperación de contraseña | Según el proveedor elegido | |
| GitHub (Microsoft) | Código; copias cifradas como artefactos de Actions | EE. UU.; las copias van cifradas antes de salir | |
| Almacenamiento S3/R2/B2 (opcional) | Copia externa cifrada | Según el proveedor elegido | |

## Si hay una brecha de seguridad

1. **Contener:** suspender el negocio afectado en `?operador`, rotar las claves expuestas (Neon, Stripe, SMTP,
   `operator_password`, `operator_totp_secret`) y cerrar las sesiones.
2. **Evaluar** con el registro de actividad y el de errores: qué datos, de cuántas personas, desde cuándo.
3. **Avisar al negocio sin demora** (es el responsable): qué pasó, qué datos, qué se ha hecho. Él notifica a la AEPD
   en **72 horas** si hay riesgo para las personas, y a las personas si el riesgo es alto.
4. **Documentar** el incidente (fecha, alcance, medidas) aunque no haga falta notificarlo.

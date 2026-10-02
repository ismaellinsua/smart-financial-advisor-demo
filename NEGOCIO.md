# NirKanA · El negocio en una página

Gestor de ventas para restaurantes, tiendas, autónomos y tiendas online en España. Se usa desde el navegador del móvil,
la tablet o el ordenador, sin instalar nada.

> Las cifras de este documento son **estimaciones orientativas**, no promesas. Los importes van **sin IVA**. Lo fiscal y
> legal conviene confirmarlo con una gestoría antes de cobrar al primer cliente.

---

## 1. Qué tienes ya hecho

| Pieza | Dónde está | Estado |
|---|---|---|
| **App de ventas** | `sales_manager/` · publicada en Streamlit Community Cloud | ✅ Funciona |
| **Web de presentación** | `docs/` · para GitHub Pages | ✅ Hecha · falta activar Pages y poner tu contacto |
| **Anuncios** | `marketing/anuncios/` · abre `galeria.html` | ✅ 33 imágenes, 8 vídeos, 12 imágenes 3D, 8 vídeos 3D, 4 anuncios 3D interactivos |
| **Textos para redes** | `marketing/anuncios/TEXTOS.md` | ✅ Instagram, Facebook, LinkedIn, TikTok, WhatsApp y Google |

**Qué hace la app**

- **Operación:** cobro rápido (efectivo, tarjeta, Bizum, pago mixto, cuenta dividida), mesas y comandas, pantalla de
  cocina, agenda de citas, devoluciones, cierre de caja, tickets y facturas en PDF.
- **Gestión:** productos y stock, proveedores y pedidos, gastos y beneficio neto, promociones automáticas y puntos.
- **Inteligencia:** alertas (stock que se agota, caja que no cuadra, ventas que bajan), análisis ABC, precios
  recomendados e informe semanal en PDF.
- **Equipo y seguridad:** cuentas con PIN y roles (administrador, encargado, empleado), registro de actividad,
  contraseñas cifradas, bloqueo ante intentos y copias de seguridad.

---

## 2. Precios

### Instalación personalizada (pago único)

| Negocio | Precio | Incluye |
|---|---|---|
| Autónomo / servicios | **250 – 400 €** | Configuración, catálogo, agenda, datos fiscales y 1 h de formación |
| Tienda / comercio | **400 – 700 €** | Lo anterior + productos y stock, proveedores y equipo |
| Restaurante / cafetería | **700 – 1.200 €** | Lo anterior + carta, mesas, cocina, promociones y formación al personal |

### Mensualidad

| Plan | Precio/mes | Para quién |
|---|---|---|
| **Básico** | **29 – 39 €** | Autónomos y tiendas pequeñas, 1–2 usuarios |
| **Profesional** | **59 – 79 €** | Tiendas y restaurantes, hasta 6–8 usuarios, alertas e informe semanal |
| **Premium** | **99 – 129 €** | Varios puestos o mucho volumen, soporte prioritario |

- **Pago anual:** 10 meses en lugar de 12.
- **Lanzamiento (primeros 3–5 clientes):** unos **300 € de instalación + 49 €/mes**, a cambio de una reseña y de poder
  enseñarlos como ejemplo. Después, precios de la tabla.

---

## 3. Cuántos clientes puedes conseguir

Para una persona sola que dedica parte de su tiempo a vender:

| Actividad cada semana | Resultado esperable al mes |
|---|---|
| Visitar o llamar a unos 20 negocios de tu zona, enseñando el anuncio 3D en el móvil | 6 – 10 demos |
| Publicar 3 anuncios en redes y enviar el mensaje de WhatsApp a conocidos | Algunas solicitudes más |
| **Total** | **2 – 4 clientes nuevos al mes** (más al principio si tiras de contactos) |

Dónde buscarlos primero: bares y cafeterías del barrio, peluquerías y estética, tiendas de ropa y alimentación,
asesorías que puedan recomendarte y negocios que ya conozcas.

### Ingresos estimados en 6 meses

| Escenario | Clientes nuevos | Facturado en 6 meses | Mensualidades que cobras en el mes 6 |
|---|---|---|---|
| **Prudente** | 2 al mes (12 en total) | **≈ 7.200 €** | **≈ 660 €/mes** |
| **Medio** | 4 al mes (24 en total) | **≈ 15.700 €** | **≈ 1.370 €/mes** |

Supuestos: los 5 primeros con precio de lanzamiento (300 € + 49 €/mes); el resto, 500 € de instalación y 59 €/mes.
Lo importante es la **mensualidad**: se suma mes a mes mientras los clientes sigan contigo.

---

## 4. Tus gastos

| Gasto | Aproximado | Notas |
|---|---|---|
| Cuota de autónomos | **≈ 80 €/mes** el primer año (cuota reducida) | Después depende de tus ingresos reales |
| Gestoría | 40 – 80 €/mes | Te hace los impuestos trimestrales y te asesora |
| Alojamiento de la app | 5 – 25 € por cliente y mes | La versión gratuita de Streamlit no sirve para clientes de pago |
| Base de datos (Neon) | 0 – 20 €/mes | Gratis al principio |
| Dominio (p. ej. nirkana.es) | ≈ 10 – 15 €/año | |
| Formulario (Formspree) | 0 € | Gratis hasta 50 mensajes al mes |
| Publicidad en redes | 0 – 300 €/mes | Opcional; empieza con poco y mide |
| Registro de la marca NirKanA | ≈ 150 € una vez | En la OEPM; protege el nombre |
| Seguro de responsabilidad civil | ≈ 150 – 300 €/año | Recomendable si gestionas datos de clientes |

**Ejemplo en el escenario medio, mes 6:** unos 80 € de autónomos, 60 € de gestoría y 240 € de alojamiento para 24
clientes. En total, unos **380 €/mes** de gastos frente a unos **3.370 €** facturados ese mes (instalaciones más
mensualidades), antes de impuestos.

---

## 5. Hacerlo todo legal

**Antes del primer cobro**

1. **Alta de autónomo:** en Hacienda (modelo 036/037, con el epígrafe de servicios informáticos) y en la Seguridad Social
   (RETA). Una gestoría lo hace en un día.
2. **Facturas correctas:** numeradas, con tu NIF y el del cliente, IVA del 21 %. Pregunta a la gestoría si tus facturas
   llevan retención de IRPF.
3. **Contrato con cada cliente:** qué incluye el servicio, precio, permanencia y cómo darse de baja, más un **contrato
   de encargado del tratamiento** (RGPD). Es obligatorio porque guardas datos de sus clientes en tu sistema.
4. **Aviso legal en la web:** la ley (LSSI) obliga a mostrar tu nombre, NIF, domicilio y un email de contacto. La web
   ya tiene el aviso de privacidad, pero **falta el aviso legal**. Lo añadimos cuando me pases esos datos.

**Impuestos cada trimestre** (los presenta la gestoría): IVA (modelo 303) e IRPF (modelo 130).

**Facturación electrónica (Veri\*Factu):** los programas que emiten tickets y facturas tendrán que cumplir unos
requisitos técnicos y de registro. Las fechas se aplazaron y ahora están previstas para 2027. **La app todavía no lo
cumple.** Es la mejora más importante antes de vender a muchos clientes; confirma la fecha con tu gestoría.

**Publicidad:** no prometas resultados que no puedas demostrar. Las cifras de las capturas son de ejemplo. Escribe a
negocios que no te conocen de uno en uno y de forma personal: nada de envíos masivos sin permiso.

---

## 6. Lo que falta para arrancar

| Paso | Quién | Tiempo |
|---|---|---|
| Activar GitHub Pages (`main` → `/docs`) para publicar la web | Tú, en Settings → Pages | 1 minuto |
| Pasarme tu WhatsApp o tu código de Formspree para el formulario | Tú → yo lo configuro | 5 minutos |
| Alta de autónomo y gestoría | Tú | 1–3 días |
| Datos para el aviso legal de la web | Tú → yo lo añado | 10 minutos |
| Alojamiento de pago para clientes reales | Juntos | 1 hora |
| Adaptar la app a Veri\*Factu | Juntos | Próxima gran mejora |

**Ojo si pones el repositorio en privado:** con una cuenta gratuita de GitHub, Pages deja de publicar la web. Tendrías
que usar GitHub Pro o subir la carpeta `docs/` a Netlify o Cloudflare Pages, que son gratuitos.

---

## 7. Próximas mejoras

1. Veri\*Factu en la app.
2. Planes y precios en la web.
3. Aviso legal y dominio propio.
4. Alojamiento profesional para clientes.
5. Presentación en PDF para las visitas a negocios.

"""Textos de las guías de la web (docs/guias/). Los convierte en páginas `ops/guias.py`.

Reglas (las comprueban `tests/web-claims.test.mjs` y `tests/web-guias.test.mjs`):
  - Explican cómo hacer algo bien, con ejemplos inventados y sin cifras de estudios ni de clientes.
  - Sobre NirKanA solo dicen lo que ya dicen las páginas de sector y la portada (caja contada a ciegas, stock que se mueve con
    cada venta, agenda sin solapes, botón de WhatsApp con el aviso escrito, paquete del trimestre…) y lo que NirKanA no hace hoy.
  - Nada de VERI*FACTU, ni «cumple/conforme», ni precios (el precio vive solo en la portada).
  - Las respuestas de las preguntas frecuentes son texto sin enlaces: son las mismas que van en los datos estructurados.
"""

# slug → datos de la guía. El orden de este diccionario es el orden del índice.
GUIDES = {}


def guide(**data):
    GUIDES[data["slug"]] = data


SECTOR = {
    "restaurantes": ("/tpv-restaurantes/", "TPV para restaurantes y bares"),
    "peluquerias": ("/programa-peluquerias-estetica/", "Programa para peluquerías y estética"),
    "tiendas": ("/tpv-tiendas/", "TPV para tiendas y comercios"),
    "autonomos": ("/programa-facturacion-autonomos/", "Programa de facturación para autónomos"),
    "online": ("/tpv-tienda-online/", "Gestión de tiendas online"),
}

# ---------------------------------------------------------------------------------------------------------------- 1
guide(
    slug="que-es-un-tpv",
    title="Qué es un TPV y cómo elegir el de tu negocio · NirKanA",
    description="Qué es un TPV, en qué se diferencia de un datáfono y ocho preguntas para elegir el de tu bar, tienda o negocio con citas, con los errores que conviene evitar.",
    h1="Qué es un TPV y cómo elegir el de tu negocio",
    lead="Un TPV (terminal punto de venta) es lo que usas para cobrar y apuntar cada venta. Aquí tienes qué hace, qué tipos hay y qué preguntar antes de elegir uno, sin tecnicismos.",
    group="Cobrar y cuadrar la caja",
    summary="Qué hace un TPV, en qué se diferencia de un datáfono y ocho preguntas para elegir bien.",
    icon="i-device",
    demo="tienda",
    sectors=["restaurantes", "tiendas"],
    related=["arqueo-y-cierre-de-caja", "control-de-stock-en-una-tienda"],
    subject="Consulta desde la guía sobre qué es un TPV",
    sections=[
        ("que-es", "Qué es un TPV", """
<p>TPV son las siglas de <strong>terminal punto de venta</strong> (en inglés, POS). Es el conjunto de programa y aparatos con el que registras cada venta, la cobras y guardas el ticket: lo que ves en el mostrador de una tienda o en la barra de un bar.</p>
<p>Un buen TPV hace, como mínimo, cuatro cosas:</p>
<ul>
<li><strong>Apunta la venta:</strong> qué se ha vendido, a qué precio y con qué IVA.</li>
<li><strong>Registra el cobro:</strong> en efectivo, con tarjeta o mezclando las dos formas.</li>
<li><strong>Emite el ticket</strong> y, cuando el cliente la pide, la factura.</li>
<li><strong>Lleva la caja:</strong> lo que ha entrado y salido cada día, y si al cerrar coincide con lo que hay en el cajón.</li>
</ul>
<p>Según el programa, también controla el stock, guarda fichas de clientes, gestiona mesas y comandas o lleva una agenda de citas. Esa es la diferencia que más pesa al elegir: qué hace <em>además</em> de cobrar.</p>
<h3>TPV y datáfono no son lo mismo</h3>
<p>El <strong>datáfono</strong> es el aparato que cobra con tarjeta y habla con el banco. El <strong>TPV</strong> es el sistema que organiza la venta. Algunos TPV llevan el cobro con tarjeta integrado; otros se usan junto al datáfono de siempre: cobras en el datáfono y marcas «tarjeta» en el TPV. Pregunta siempre cuál de las dos cosas estás contratando.</p>
"""),
        ("tipos", "Tipos de TPV: con equipo propio, en la nube y en el móvil", """
<div class="tablewrap" role="region" aria-label="Comparación de tipos de TPV" tabindex="0">
<table>
<thead><tr><th scope="col">Tipo</th><th scope="col">Cómo funciona</th><th scope="col">Suele encajar</th><th scope="col">Ten en cuenta</th></tr></thead>
<tbody>
<tr><th scope="row">TPV clásico</th><td>Ordenador o pantalla táctil con el programa instalado, más impresora y cajón.</td><td>Puestos fijos con mucho volumen de cobros.</td><td>El equipo es tuyo y cuesta más al principio; si falla, el puesto se para.</td></tr>
<tr><th scope="row">TPV en la nube</th><td>Se abre en el navegador; los datos se guardan en los servidores del proveedor.</td><td>Casi cualquier negocio con conexión a internet.</td><td>Pregunta qué pasa si se cae internet y quién guarda tus datos.</td></tr>
<tr><th scope="row">TPV en el móvil o la tableta</th><td>El mismo programa, en la pantalla que ya tienes.</td><td>Cobrar en la mesa, en la tienda o en movimiento.</td><td>En una pantalla pequeña cuesta más manejar catálogos muy grandes.</td></tr>
</tbody>
</table>
</div>
"""),
        ("ocho-preguntas", "Ocho preguntas antes de elegir", """
<ol>
<li><strong>¿Qué necesita mi tipo de negocio?</strong> Un bar necesita mesas, comandas y cocina; una tienda, stock y códigos de barras; un negocio con citas, agenda y cobro del servicio. Un TPV genérico se queda corto en cuanto tu negocio tiene su propia forma de trabajar.</li>
<li><strong>¿Qué equipos tengo ya?</strong> Móviles, tabletas, un ordenador, impresora de tickets, lector de códigos o cajón. Pregunta si el programa funciona con lo que ya tienes antes de comprar nada.</li>
<li><strong>¿Qué pasa si se cae internet?</strong> Pide que te lo expliquen con un caso concreto: ¿puedo seguir cobrando?, ¿cuándo se envían las ventas?, ¿qué no funcionará mientras tanto?</li>
<li><strong>¿Quién lo va a usar y qué debe poder hacer cada persona?</strong> Quien cobra no debería poder cambiar precios ni anular ventas sin que quede registrado. Busca usuarios, PIN y permisos por rol.</li>
<li><strong>¿Cómo se cierra la caja?</strong> Lo ideal es contar el efectivo y ver el descuadre al momento, con constancia de quién cierra. En la <a href="/guias/arqueo-y-cierre-de-caja/">guía de arqueo y cierre de caja</a> tienes qué comprobar.</li>
<li><strong>¿Puedo sacar mis datos cuando quiera?</strong> Ventas, facturas, productos y clientes deberían poder descargarse, por ejemplo en Excel. Si algún día cambias de programa, no quieres empezar de cero.</li>
<li><strong>¿Cuánto cuesta en total?</strong> Suma la cuota mensual, el alta o la instalación, el equipo, las comisiones por cobrar con tarjeta y los extras. Y pregunta si el precio lleva el IVA aparte.</li>
<li><strong>¿Puedo probarlo antes de decidir?</strong> Lo normal es poder abrirlo y usarlo unas horas con datos de ejemplo, sin dar datos de tarjeta. Si solo te lo enseñan en una presentación, pide una prueba.</li>
</ol>
"""),
        ("errores", "Errores frecuentes al elegir un TPV", """
<ul>
<li>Comprar el equipo antes de probar el programa.</li>
<li>Comparar solo la cuota mensual y olvidar el alta, el equipo y las comisiones.</li>
<li>No tener un plan B para cuando falle internet o un dispositivo.</li>
<li>Dar a todo el mundo acceso a todo.</li>
<li>No comprobar cómo se exportan los datos hasta el día que quieres irte.</li>
<li>Elegir por la lista de funciones y no por lo que tu equipo va a usar cada día.</li>
</ul>
"""),
    ],
    nirkana="""
<p>NirKanA es un TPV y programa de gestión para restaurantes, tiendas, negocios con citas, autónomos y tiendas online. Respecto a las ocho preguntas:</p>
<ul>
<li><strong>Equipos:</strong> funciona en el navegador de cualquier móvil, tablet u ordenador, sin terminal especial, y se puede instalar en la pantalla de inicio como una app.</li>
<li><strong>Personas y permisos:</strong> administrador, encargado y empleado; cada uno entra con su PIN y ve solo lo suyo, y lo que hace queda firmado.</li>
<li><strong>Caja:</strong> el efectivo se cuenta sin ver lo esperado, al cerrar ves el descuadre al momento y queda registrado quién cerró.</li>
<li><strong>Datos:</strong> puedes descargar una copia completa cuando quieras, y ventas, facturas, gastos, compras, productos, clientes y cierres de caja se exportan a Excel.</li>
<li><strong>Prueba:</strong> 24 horas gratis, sin tarjeta, con un negocio de ejemplo.</li>
<li><strong>Precio:</strong> está a la vista en la <a href="/#precio">sección de precio</a>.</li>
</ul>
""",
    shot=("vender-c", "Pantalla de venta de NirKanA con los productos a la izquierda y el ticket a la derecha", "La pantalla de venta: productos, ticket y cobro"),
    faq=[
        ("¿Un TPV es lo mismo que un datáfono?",
         "No. El datáfono es el aparato que cobra con tarjeta y se comunica con el banco; el TPV es el sistema que registra la venta, el ticket y la caja. Algunos TPV integran el cobro con tarjeta y otros se usan junto a tu datáfono."),
        ("¿Puedo usar el móvil como TPV?",
         "Sí, si el programa funciona en el navegador o tiene su propia app. NirKanA se abre en el navegador de cualquier móvil, tablet u ordenador, sin comprar un terminal especial."),
        ("¿Cuánto cuesta un TPV?",
         "Depende del tipo: uno con equipo propio exige comprar el equipo, y uno en la nube suele cobrar una cuota mensual. Para comparar, suma cuota, alta o instalación, equipo, comisiones por cobrar con tarjeta y extras, y comprueba si el precio lleva el IVA aparte."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 2
guide(
    slug="arqueo-y-cierre-de-caja",
    title="Arqueo y cierre de caja: cómo hacerlo paso a paso · NirKanA",
    description="Qué es el arqueo de caja, cuándo hacerlo y cómo cuadrar la caja al cerrar el día, con un ejemplo de cálculo y qué hacer si hay descuadre.",
    h1="Arqueo y cierre de caja: cómo hacerlo paso a paso",
    lead="Cuadrar la caja es comprobar que el dinero del cajón coincide con lo que dicen las ventas. Con un método fijo se hace en pocos minutos y deja de ser un quebradero de cabeza.",
    group="Cobrar y cuadrar la caja",
    summary="Los siete pasos para cuadrar la caja, un ejemplo con números y qué hacer si no cuadra.",
    icon="i-receipt",
    demo="hosteleria",
    sectors=["restaurantes", "tiendas"],
    related=["que-es-un-tpv", "documentos-del-trimestre-para-la-gestoria"],
    subject="Consulta desde la guía de arqueo y cierre de caja",
    sections=[
        ("diferencia", "Arqueo y cierre: qué es cada cosa", """
<p>El <strong>arqueo</strong> es contar el dinero real (billetes y monedas) y compararlo con lo que debería haber según las ventas registradas. El <strong>cierre</strong> es dar por terminado el día o el turno: fijas el total, anotas el descuadre si lo hay, retiras el efectivo y guardas el registro.</p>
<p>Conviene hacerlo al cerrar el día y, si cobra más de una persona, en cada cambio de turno. Así, cuando algo no cuadra, sabes quién tenía la caja y a qué hora.</p>
"""),
        ("pasos", "Los siete pasos para cuadrar la caja", """
<ol>
<li><strong>Al abrir, anota el fondo de caja.</strong> Es el dinero con el que empiezas (monedas y billetes pequeños para dar cambio). Cuéntalo y deja constancia.</li>
<li><strong>Durante el día, registra todas las ventas</strong> con su forma de pago, y también las entradas y salidas de efectivo que no son ventas: pagar a un proveedor con dinero del cajón, retirar efectivo, devolver un importe.</li>
<li><strong>Al cerrar, saca el total esperado</strong> de cada forma de pago: efectivo, tarjeta y otras.</li>
<li><strong>Cuenta el efectivo por denominaciones</strong> (billetes de 50, 20, 10 y 5; monedas de 2 € y 1 €; y las de céntimos) y suma. Cuenta antes de mirar cuánto debería haber, para no ajustar el recuento sin querer.</li>
<li><strong>Calcula el efectivo esperado:</strong> fondo inicial + ventas en efectivo + entradas − salidas.</li>
<li><strong>Compara y anota la diferencia,</strong> tanto si sobra dinero como si falta, y quién cierra.</li>
<li><strong>Retira el efectivo que vas a ingresar</strong> y deja el fondo para el día siguiente. Guarda el registro del cierre.</li>
</ol>
<p>Las ventas con tarjeta no están en el cajón: se comprueban comparando el total de tarjeta que registra tu TPV con el cierre del datáfono.</p>
"""),
        ("ejemplo", "Un ejemplo con números", """
<div class="tablewrap compact" role="region" aria-label="Ejemplo de cuadre de caja" tabindex="0">
<table>
<caption>Ejemplo inventado: la caja de un día</caption>
<thead><tr><th scope="col">Concepto</th><th scope="col">Importe</th></tr></thead>
<tbody>
<tr><th scope="row">Fondo inicial</th><td>150,00 €</td></tr>
<tr><th scope="row">Ventas cobradas en efectivo</th><td>612,40 €</td></tr>
<tr><th scope="row">Pago a un proveedor con dinero del cajón</th><td>−25,00 €</td></tr>
<tr><th scope="row"><strong>Efectivo esperado</strong></th><td><strong>737,40 €</strong></td></tr>
<tr><th scope="row">Efectivo contado</th><td>735,90 €</td></tr>
<tr><th scope="row"><strong>Descuadre</strong></th><td><strong>−1,50 €</strong></td></tr>
</tbody>
</table>
</div>
<p>Faltan 1,50 €. Puede ser un cambio mal dado o una venta sin registrar. Se anota la diferencia tal cual: no se «arregla» metiendo dinero en el cajón sin dejar constancia.</p>
"""),
        ("descuadres", "Por qué no cuadra: causas frecuentes", """
<ul>
<li>Cambio mal dado o billetes confundidos.</li>
<li>Ventas cobradas pero sin registrar, o registradas con otra forma de pago.</li>
<li>Devoluciones o anulaciones sin anotar.</li>
<li>Gastos pagados con el dinero del cajón y no apuntados.</li>
<li>Propinas mezcladas con la recaudación.</li>
<li>Un error al contar: si hay diferencia, cuenta de nuevo.</li>
</ul>
<div class="callout"><p><strong>Regla de oro:</strong> un descuadre pequeño anotado es información; un descuadre «arreglado» sin anotar esconde el problema. Si se repite siempre en el mismo turno o con la misma persona, revisa cómo se cobra y qué ventas se anulan, y habla con tu equipo.</p></div>
"""),
        ("buenas", "Buenas prácticas que lo facilitan", """
<ul>
<li><strong>Contar «a ciegas»:</strong> sin ver el total esperado hasta terminar de contar.</li>
<li><strong>Dejar constancia</strong> de quién cierra y a qué hora.</li>
<li><strong>Un fondo de caja fijo:</strong> la misma cantidad cada día.</li>
<li><strong>Ingresar el efectivo en el banco</strong> con regularidad y guardar el justificante.</li>
<li><strong>Guardar los cierres:</strong> tu gestoría los agradecerá (mira la <a href="/guias/documentos-del-trimestre-para-la-gestoria/">guía de documentos del trimestre</a>).</li>
</ul>
"""),
    ],
    nirkana="""
<p>En NirKanA el cierre de caja sigue ese mismo método:</p>
<ul>
<li>Abres la caja con su fondo inicial y la ves abierta mientras cobras.</li>
<li>Al cerrar, cuentas el efectivo (con ayuda para contar billetes y monedas) sin ver lo esperado.</li>
<li>El descuadre aparece al momento y queda registrado quién cerró.</li>
<li>Los cierres de caja entran en el ZIP del trimestre que puedes darle a tu gestoría.</li>
</ul>
""",
    shot=("caja-c", "Pantalla Caja de NirKanA con la caja abierta, el efectivo esperado y el apartado para cerrar contando billetes y monedas", "La pantalla de Caja: resumen del día y cierre contando el efectivo"),
    faq=[
        ("¿Cada cuánto debo hacer el arqueo de caja?",
         "Como mínimo al cerrar el día. Si varias personas cobran, hazlo también en cada cambio de turno: así sabes quién tenía la caja cuando apareció una diferencia."),
        ("¿Qué hago si la caja no cuadra?",
         "Cuenta de nuevo, repasa las anulaciones, devoluciones y gastos pagados en efectivo, y anota la diferencia tal cual. No metas ni saques dinero para que cuadre sin dejar constancia; si se repite, revisa el turno y la forma de cobrar."),
        ("¿Qué diferencia hay entre arqueo y cierre de caja?",
         "El arqueo es contar el dinero y compararlo con lo que dicen las ventas. El cierre es dar por terminado el turno o el día: fijas el total, anotas el descuadre, retiras el efectivo y guardas el registro."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 3
guide(
    slug="control-de-stock-en-una-tienda",
    title="Control de stock en una tienda: método sencillo en 5 pasos · NirKanA",
    description="Cómo controlar el stock de una tienda pequeña: ordenar el catálogo, fijar el stock mínimo, registrar movimientos, contar y reponer, con un ejemplo de cálculo.",
    h1="Control de stock en una tienda: método sencillo en cinco pasos",
    lead="Quedarte sin lo que más vendes cuesta ventas; comprar de más deja dinero parado en la estantería. Este método sirve para una tienda pequeña, con una hoja de cálculo o con un programa.",
    group="Stock, precios y tienda online",
    summary="Cinco pasos para no quedarte sin lo que más vendes, con el cálculo del stock mínimo.",
    icon="i-box",
    demo="tienda",
    sectors=["tiendas", "online"],
    related=["calcular-el-margen-de-un-producto", "que-es-un-tpv"],
    subject="Consulta desde la guía de control de stock",
    sections=[
        ("pasos", "Cinco pasos para llevar el stock", """
<ol>
<li><strong>Ordena el catálogo.</strong> Un código por producto (una referencia propia o el código de barras), un nombre claro y ningún duplicado. Si el mismo producto está dos veces con nombres distintos, el stock nunca cuadra.</li>
<li><strong>Fija un stock mínimo por producto:</strong> la cantidad a la que toca pedir. Para calcularlo: <em>ventas diarias × días que tarda en llegar el pedido + un margen de seguridad</em>.</li>
<li><strong>Registra cada movimiento:</strong> ventas, compras, devoluciones de clientes, devoluciones al proveedor y mermas (roturas, caducados, pérdidas). Lo que no se anota hace que el stock «mienta».</li>
<li><strong>Cuenta de vez en cuando.</strong> En lugar de cerrar un día para contarlo todo, cuenta una categoría cada semana, compara con lo que dice el sistema y ajusta anotando el motivo.</li>
<li><strong>Repón con datos.</strong> Mira lo vendido en el último mes y pide según el ritmo real de ventas, no por intuición. Vigila más los productos que más rotan y no repongas los que no se mueven.</li>
</ol>
"""),
        ("ejemplo", "Ejemplo: cuánto stock mínimo necesito", """
<p>Un producto del que vendes 60 unidades al mes se vende a un ritmo de 2 al día. Tu proveedor tarda 5 días en entregar y quieres un margen de seguridad de 4 unidades para semanas buenas o retrasos:</p>
<div class="tablewrap" role="region" aria-label="Ejemplo de cálculo del stock mínimo" tabindex="0">
<table>
<caption>Ejemplo inventado con dos productos</caption>
<thead><tr><th scope="col">Producto</th><th scope="col">Ventas al día</th><th scope="col">Días de entrega</th><th scope="col">Margen de seguridad</th><th scope="col">Stock mínimo</th></tr></thead>
<tbody>
<tr><th scope="row">Producto A (60 al mes)</th><td>2</td><td>5</td><td>4</td><td><strong>14 unidades</strong> (2 × 5 + 4)</td></tr>
<tr><th scope="row">Producto B (15 al mes)</th><td>0,5</td><td>10</td><td>3</td><td><strong>8 unidades</strong> (0,5 × 10 + 3)</td></tr>
</tbody>
</table>
</div>
<p>Cuando el stock de A baja de 14 unidades, toca pedir. El producto B se vende poco, pero tarda más en llegar, así que su mínimo también es alto en proporción.</p>
"""),
        ("errores", "Errores típicos", """
<ul>
<li><strong>Stock negativo:</strong> vender productos que el sistema no sabe que tienes porque no registraste la compra.</li>
<li><strong>No anotar devoluciones ni mermas:</strong> la diferencia aparece en el recuento y nadie sabe de dónde viene.</li>
<li><strong>Contar una sola vez al año:</strong> los errores se acumulan y luego cuesta encontrarlos.</li>
<li><strong>Una sola ficha para todas las tallas o colores:</strong> sabes que quedan «camisetas», pero no cuáles.</li>
<li><strong>Pedir por intuición:</strong> sobra de lo que no se mueve y falta de lo que sí.</li>
</ul>
"""),
        ("excel", "¿Basta con una hoja de cálculo?", """
<p>Para pocos productos y una sola persona vendiendo, sí. Cuando hay muchas ventas al día, varias personas cobrando o cientos de referencias, actualizar a mano falla: se olvida una venta, se escribe una cifra mal, dos personas editan a la vez. Ahí compensa que <strong>cada venta descuente el stock sola</strong> y que el programa te avise cuando algo está bajo.</p>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Venta rápida:</strong> buscas por nombre o escaneas el código (con el lector o con la cámara del móvil) y el producto va al ticket.</li>
<li><strong>Stock que se mueve solo:</strong> cada venta, compra o devolución actualiza las unidades, y las ves en el propio TPV. Los productos avisan cuando quedan pocos.</li>
<li><strong>Reposición:</strong> calcula qué pedir según lo que has vendido en el último mes y crea el pedido al proveedor con un clic.</li>
<li><strong>Compras y proveedores:</strong> registras los pedidos y la mercancía recibida, y el coste de cada producto se actualiza solo.</li>
<li><strong>Catálogo desde Excel:</strong> importas tu lista de productos desde un Excel o CSV y ves qué se creará o se actualizará antes de guardar nada.</li>
</ul>
""",
    shot=("productos-c", "Lista de productos de NirKanA con categoría, precio, coste y existencias de cada uno", "Productos con su precio, su coste y las unidades que quedan"),
    faq=[
        ("¿Cómo calculo el stock mínimo de un producto?",
         "Multiplica lo que vendes al día por los días que tarda en llegar el pedido y suma un margen de seguridad. Si vendes 2 al día, el proveedor tarda 5 días y quieres 4 de margen, el mínimo es 2 × 5 + 4 = 14 unidades."),
        ("¿Cada cuánto hay que hacer inventario?",
         "En una tienda pequeña funciona bien un recuento rotativo: cada semana o cada mes, una categoría distinta, comparando con lo que dice el sistema. Además, conviene un recuento completo al menos una vez al año."),
        ("¿Qué es una merma y cómo se anota?",
         "Es lo que pierdes sin venderlo: roturas, caducados, pérdidas o muestras. Se anota como una salida de stock con su motivo, para que las cuentas cuadren y veas cuánto te cuesta."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 4
guide(
    slug="agenda-de-citas-para-peluquerias",
    title="Agenda de citas para peluquerías: sin solapes ni plantones · NirKanA",
    description="Cómo organizar las citas de una peluquería o centro de estética: duración real de cada servicio, sin solapes, con confirmaciones y un mensaje de WhatsApp modelo.",
    h1="Cómo organizar las citas de una peluquería: sin solapes y con menos plantones",
    lead="Citas repartidas entre WhatsApp, llamadas y una libreta acaban en solapes y huecos vacíos. Con una sola agenda y unas reglas sencillas, el día se ordena y los clientes vuelven.",
    group="Citas y clientes",
    summary="Cinco principios para una agenda sin solapes y un mensaje de WhatsApp para confirmar citas.",
    icon="i-calendar",
    demo="servicios",
    sectors=["peluquerias", "autonomos"],
    related=["que-es-un-tpv", "arqueo-y-cierre-de-caja"],
    subject="Consulta desde la guía de agenda de citas para peluquerías",
    sections=[
        ("problemas", "Los tres problemas de siempre", """
<ul>
<li><strong>Citas por todas partes:</strong> algunas llegan por WhatsApp, otras por teléfono y otras en persona, y cada una se apunta en un sitio distinto.</li>
<li><strong>Solapes:</strong> dos clientes a la misma hora con la misma persona, porque nadie vio la otra cita.</li>
<li><strong>Plantones y huecos:</strong> el cliente no viene y el hueco se pierde, o queda libre sin que nadie lo sepa a tiempo.</li>
</ul>
"""),
        ("principios", "Cinco principios de una agenda que funciona", """
<ol>
<li><strong>Una sola agenda.</strong> Si la cita no está ahí, no existe. Da igual por dónde llegó: se apunta en el mismo sitio.</li>
<li><strong>Cada cita completa:</strong> cliente, servicio, duración, persona que lo atiende y un teléfono de contacto.</li>
<li><strong>Duración real de cada servicio,</strong> con los tiempos de pose o espera incluidos (color, mechas, tratamientos). Mídela durante una semana y ajusta.</li>
<li><strong>Una persona no puede tener dos citas a la misma hora.</strong> Si se pisan, alguien espera o alguien se va: mejor detectarlo al apuntar la cita que cuando el cliente ya está en la puerta.</li>
<li><strong>Un pequeño margen entre citas</strong> para recoger, cobrar y absorber retrasos.</li>
</ol>
"""),
        ("plantones", "Cómo reducir los plantones", """
<ul>
<li><strong>Confirma cada cita</strong> uno o dos días antes con un mensaje corto.</li>
<li><strong>Ten una política de cancelación sencilla</strong> y dila al reservar: avisar con tiempo permite ofrecer el hueco a otra persona.</li>
<li><strong>Lleva una lista de espera</strong> de clientes que aceptarían un hueco libre a última hora.</li>
<li><strong>Fíjate en quién falla más:</strong> si algún cliente se repite, habla con él, confirma su cita el mismo día o no le des citas con tanta antelación.</li>
</ul>
<p>Un mensaje que puedes copiar y adaptar:</p>
<div class="callout"><p>«Hola, {nombre}. Te recordamos tu cita de {servicio} el {día} a las {hora} en {negocio}. ¿Nos confirmas con un “sí”? Si no puedes venir, avísanos y ofrecemos el hueco a otra persona. ¡Gracias!»</p></div>
"""),
        ("clientes", "Que los clientes vuelvan", """
<ul>
<li><strong>Ficha de cada cliente</strong> con lo que se le hizo, lo que gasta y sus próximas citas: en la siguiente visita sabes por dónde seguir.</li>
<li><strong>Un mensaje a quien lleva un mes sin venir:</strong> amable, sin presionar, con una propuesta de fecha.</li>
<li><strong>Promociones en los días flojos:</strong> si los martes hay huecos, un descuento ese día puede llenarlos.</li>
</ul>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Agenda por persona:</strong> el día se ve en lista o con una columna por profesional. Cada cita lleva cliente, servicio, duración y la persona que atiende.</li>
<li><strong>Sin solapes:</strong> si una cita se pisa con otra de esa misma persona, NirKanA no la guarda y te dice con quién coincide.</li>
<li><strong>Aviso por WhatsApp:</strong> cada cita tiene un botón que abre WhatsApp con el aviso ya escrito; lo envías tú. Hoy NirKanA no envía recordatorios automáticos.</li>
<li><strong>Cobro desde la agenda:</strong> al terminar, «Cobrar» lleva el servicio y el cliente al ticket.</li>
<li><strong>Clientes que vuelven:</strong> la ficha guarda lo que gasta, lo que más compra, sus próximas citas y sus puntos, y un filtro te enseña quién lleva un mes sin venir.</li>
</ul>
<p>Una limitación a tener en cuenta: tus clientes todavía no reservan solos; la agenda es para ti y tu equipo.</p>
""",
    shot=("agenda-persona-c", "Agenda por persona de NirKanA con una columna por profesional y las citas del día de una peluquería", "Agenda por persona: una columna por profesional"),
    faq=[
        ("¿Cuánto margen dejo entre citas?",
         "Depende del servicio, pero conviene dejar unos minutos para recoger, cobrar y absorber retrasos. Empieza con un margen pequeño, mide durante una semana cuánto se retrasan las citas y ajusta."),
        ("¿Cómo evito que me dejen plantada?",
         "Confirma cada cita uno o dos días antes, ten una política de cancelación sencilla y pide que avisen si no pueden venir. Una lista de espera te permite ocupar los huecos que se liberan."),
        ("¿Puedo avisar a mis clientes por WhatsApp desde la agenda?",
         "Con NirKanA, cada cita tiene un botón que abre WhatsApp con el aviso ya escrito y lo envías tú. Hoy no envía recordatorios automáticos."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 5
guide(
    slug="que-debe-llevar-una-factura",
    title="Qué debe llevar una factura: lista de comprobación · NirKanA",
    description="Los datos que debe incluir una factura en España, en qué se diferencia del ticket, qué es una rectificativa y los errores habituales, con una lista de comprobación.",
    h1="Qué debe llevar una factura: lista de comprobación para autónomos y pequeños negocios",
    lead="Una factura bien hecha evita devoluciones, retrasos de cobro y problemas con tu gestoría. Esta lista resume los datos que debe llevar y los errores más habituales.",
    group="Facturas y gestoría",
    summary="Los datos de una factura completa, cuándo basta un ticket y los errores que más se repiten.",
    icon="i-briefcase",
    demo="servicios",
    sectors=["autonomos", "tiendas"],
    related=["documentos-del-trimestre-para-la-gestoria", "calcular-el-margen-de-un-producto"],
    subject="Consulta desde la guía de qué debe llevar una factura",
    disclaimer="Esta guía es informativa y no sustituye el consejo de un profesional. Las normas y los casos particulares (exenciones, operaciones con el extranjero, facturas electrónicas…) te los confirma tu gestoría.",
    sections=[
        ("datos", "Los datos de una factura completa", """
<ul>
<li><strong>Número</strong> y, si usas varias, <strong>serie.</strong> La numeración es correlativa: sin saltos ni repeticiones dentro de cada serie.</li>
<li><strong>Fecha de expedición,</strong> y la fecha de la operación si es distinta.</li>
<li><strong>Datos de quien factura:</strong> nombre y apellidos o razón social, NIF y domicilio.</li>
<li><strong>Datos del cliente:</strong> nombre o razón social, NIF y domicilio. Son imprescindibles cuando el cliente es una empresa o un profesional.</li>
<li><strong>Descripción de lo que facturas:</strong> qué es, cuántas unidades y el precio unitario sin IVA, con los descuentos si los hay.</li>
<li><strong>Base imponible,</strong> tipo de IVA aplicado y <strong>cuota</strong> resultante, cada cosa por separado.</li>
<li><strong>Total</strong> a pagar.</li>
<li>Si la operación no lleva IVA o está exenta, <strong>la mención</strong> que corresponda; y la <strong>retención de IRPF</strong> cuando proceda.</li>
</ul>
<p>Tu gestoría te dirá si en tu actividad hay algo más que añadir.</p>
"""),
        ("ticket", "Ticket o factura: cuándo basta un ticket", """
<p>El ticket que das en el mostrador puede valer como factura «simplificada» si lleva los datos que exige la norma: lleva menos datos y no necesita los del cliente. Se admite en muchos cobros del comercio y de los servicios a particulares, con límites de importe que tu gestoría puede confirmarte.</p>
<p>Si tu cliente es una empresa o un profesional y necesita el documento para deducirse el IVA o el gasto, <strong>pide siempre la factura completa</strong> con sus datos.</p>
"""),
        ("rectificativas", "Cuando te equivocas: facturas rectificativas", """
<p>Una factura emitida no se borra ni se cambia. Si hay un error o una devolución, se emite una <strong>factura rectificativa</strong> que corrige la original y hace referencia a ella. Así la numeración sigue sin saltos y queda constancia de lo que pasó.</p>
"""),
        ("errores", "Errores habituales", """
<ul>
<li>Saltos o repeticiones en la numeración.</li>
<li>Faltan el NIF o el domicilio del cliente cuando es una empresa.</li>
<li>El IVA se calcula sobre el total en lugar de sobre la base.</li>
<li>Descripciones vagas, como «servicios varios».</li>
<li>Una fecha que no corresponde o ninguna.</li>
<li>Mezclar importes con IVA y sin IVA en el mismo documento.</li>
<li>No guardar copia, o guardarla en un sitio que solo conoce una persona.</li>
</ul>
"""),
        ("hacerlas", "Cómo hacerlas sin complicarte", """
<p>Usa siempre la misma plantilla, deja que la numeración la lleve el programa, guarda cada factura en PDF y archívalas por trimestre. Cuanto menos tengas que escribir a mano, menos errores habrá. En la <a href="/guias/documentos-del-trimestre-para-la-gestoria/">guía de documentos del trimestre</a> tienes cómo entregárselas a tu gestoría.</p>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Facturas con tus datos y los del cliente:</strong> con tu NIF y el del cliente, IVA por tipo y numeración propia por serie y año; las imprimes o las guardas en PDF.</li>
<li><strong>Devoluciones y rectificativas:</strong> se hacen desde la misma pantalla que los tickets y las facturas.</li>
<li><strong>Para tu gestoría:</strong> ventas, facturas, gastos y compras en Excel por periodo, el resumen de IVA del trimestre y un ZIP del trimestre con todo junto.</li>
</ul>
<p>Una limitación a tener en cuenta: hoy la factura lleva IVA por tipo, pero no calcula retenciones de IRPF.</p>
""",
    shot=("factura-c", "Factura de ejemplo de NirKanA con los datos de quien factura y del cliente, el IVA por tipo y el total", "Una factura de ejemplo con los datos del emisor, el cliente, el IVA y el total"),
    faq=[
        ("¿Se puede borrar una factura emitida?",
         "No. Una factura emitida se corrige con una factura rectificativa, y la original se conserva. Así la numeración no tiene saltos y queda constancia del cambio."),
        ("¿Puedo dar solo un ticket a un cliente?",
         "Si el cliente es un particular y el importe lo permite, un ticket puede bastar. Si es una empresa o un profesional, o si te pide factura, emítela completa con sus datos. Tu gestoría te confirma los límites."),
        ("¿Cada cuánto se reinicia la numeración de las facturas?",
         "La numeración debe ser correlativa dentro de cada serie. Mucha gente reinicia la serie cada año, por ejemplo F-2026-0001. Elige un criterio y mantenlo siempre."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 6
guide(
    slug="documentos-del-trimestre-para-la-gestoria",
    title="Documentos del trimestre para tu gestoría: lista y rutina · NirKanA",
    description="Qué documentos preparar cada trimestre para tu gestoría (ventas, facturas, gastos y cierres de caja) y una rutina de quince minutos a la semana para no llegar con prisas.",
    h1="Qué documentos preparar cada trimestre para tu gestoría",
    lead="Llegar al final del trimestre con las ventas, las facturas y los gastos ordenados ahorra prisas y errores. Esta lista y una rutina de quince minutos a la semana lo dejan casi hecho.",
    group="Facturas y gestoría",
    summary="La lista de documentos del trimestre y una rutina semanal de quince minutos.",
    icon="i-download",
    demo="servicios",
    sectors=["autonomos"],
    related=["que-debe-llevar-una-factura", "arqueo-y-cierre-de-caja"],
    subject="Consulta desde la guía de documentos del trimestre",
    disclaimer="Esta guía es informativa. Qué documentos necesitas, en qué formato y para cuándo te lo indica tu gestoría.",
    sections=[
        ("lista", "La lista del trimestre", """
<ul>
<li><strong>Ventas e ingresos:</strong> el listado de ventas del periodo y las facturas emitidas, con las rectificativas.</li>
<li><strong>Gastos y compras:</strong> las facturas de proveedores y suministros (alquiler, luz, internet, mercancía…). Pide siempre factura con tus datos, no solo el ticket.</li>
<li><strong>Cierres de caja</strong> del periodo, si cobras en efectivo.</li>
<li><strong>Movimientos del banco</strong> del negocio, si tu gestoría los pide.</li>
<li><strong>Cuotas y nóminas,</strong> si las hay.</li>
<li><strong>Cambios del periodo:</strong> un local nuevo, un trabajador, la compra de un equipo importante.</li>
</ul>
<p>Pregunta a tu gestoría cuál es su lista y su fecha límite para recibirla: suele ser anterior a la oficial.</p>
"""),
        ("rutina", "Una rutina de quince minutos a la semana", """
<ol>
<li><strong>Elige un día fijo</strong> y ponlo en el calendario.</li>
<li><strong>Revisa que todas las ventas de la semana estén registradas</strong> y que los cierres de caja estén hechos.</li>
<li><strong>Guarda las facturas de gastos</strong> en una carpeta del trimestre, en PDF o con foto legible, con un nombre que ordene solo (por ejemplo, fecha, proveedor e importe).</li>
<li><strong>Apunta lo pendiente de cobrar</strong> y a quién hay que reclamárselo.</li>
</ol>
"""),
        ("errores", "Errores que retrasan el trimestre", """
<ul>
<li>Facturas de gastos sueltas en el coche, en un cajón o en una conversación de WhatsApp.</li>
<li>Gastos personales mezclados con los del negocio.</li>
<li>Una caja que no se cuadra a diario y llega descuadrada a fin de trimestre.</li>
<li>Facturas emitidas con la numeración saltada.</li>
<li>Dejarlo todo para la última semana.</li>
</ul>
"""),
        ("entregar", "Cómo entregarlo", """
<p>Pregunta a tu gestoría qué formato prefiere: Excel, PDF o acceso a un programa. Ordena por fecha, envía una sola carpeta o un solo archivo comprimido, evita duplicados y señala lo que no tengas claro, para que no tenga que adivinarlo.</p>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Todo en Excel:</strong> descargas las ventas, las facturas emitidas y rectificativas, los gastos y las compras del periodo que elijas.</li>
<li><strong>IVA del trimestre:</strong> Resultados te da el resumen de IVA del trimestre.</li>
<li><strong>Un ZIP del trimestre:</strong> con «Para tu gestoría» bajas el trimestre entero en un ZIP (IVA, ventas, facturas, gastos y cierres de caja).</li>
<li><strong>Acceso de asesor:</strong> tu gestoría puede entrar con un usuario de solo lectura y descargar lo que necesite; no puede vender ni cambiar nada.</li>
<li><strong>Excel sin fórmulas ocultas:</strong> las exportaciones se generan sin fórmulas que puedan ejecutarse al abrirlas.</li>
</ul>
""",
    shot=("resultados-c", "Pantalla de Resultados de NirKanA con las ventas, el coste de lo vendido, el margen, los gastos y el IVA del trimestre", "Resultados: ventas, costes, margen, gastos y el IVA del trimestre"),
    faq=[
        ("¿Con qué frecuencia debo pasar los documentos a mi gestoría?",
         "Depende de tu gestoría y de tu actividad. Lo más común es cada trimestre, y muchas prefieren recibirlos cada mes. Pregúntale su calendario y entrega algo antes de su fecha límite."),
        ("¿Qué hago con los gastos que solo tengo en ticket?",
         "Pide siempre factura con tus datos. Si solo tienes el ticket, consúltalo con tu gestoría antes de contarlo como gasto: te dirá si te sirve en tu caso."),
        ("¿Mi gestoría puede ver mis datos en NirKanA?",
         "Sí, si le das acceso. El acceso de asesor es de solo lectura: ve y descarga el IVA, las ventas, las facturas, los gastos y los cierres del trimestre, y no puede vender ni cambiar nada."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 7
guide(
    slug="calcular-el-margen-de-un-producto",
    title="Cómo calcular el margen de un producto y fijar el precio · NirKanA",
    description="Diferencia entre margen y recargo, fórmula para calcular el margen sin IVA y cómo fijar el precio de venta, con ejemplos y el efecto de un descuento.",
    h1="Cómo calcular el margen de un producto y fijar el precio de venta",
    lead="Vender mucho no sirve si cada venta deja poco. Con dos fórmulas sabes cuánto ganas por producto y qué precio necesitas para llegar al margen que buscas.",
    group="Stock, precios y tienda online",
    summary="Margen frente a recargo, la fórmula del precio de venta y lo que cuesta un descuento.",
    icon="i-chart",
    demo="online",
    sectors=["online", "tiendas"],
    related=["control-de-stock-en-una-tienda", "que-debe-llevar-una-factura"],
    subject="Consulta desde la guía de cálculo del margen",
    sections=[
        ("conceptos", "Margen y recargo no son lo mismo", """
<p>Antes de calcular, dos ideas. El <strong>coste</strong> es lo que te cuesta cada unidad (la compra, el transporte, el embalaje…). Y todos los cálculos se hacen con el <strong>precio sin IVA</strong>: el IVA no es tuyo.</p>
<ul>
<li><strong>Margen (%)</strong> = (precio sin IVA − coste) ÷ precio sin IVA × 100. Es la parte del precio que te queda.</li>
<li><strong>Recargo (%)</strong> = (precio sin IVA − coste) ÷ coste × 100. Es lo que añades sobre el coste.</li>
</ul>
<p>Ejemplo: un producto te cuesta 12 € y lo vendes a 20 € sin IVA. Ganas 8 € por unidad: un <strong>margen del 40 %</strong> y un <strong>recargo del 66,7 %</strong>. Con el IVA general del 21 %, el cliente paga 24,20 €.</p>
"""),
        ("precio", "Cómo fijar el precio de venta", """
<p>Si ya sabes qué margen quieres, el precio sin IVA sale de dividir el coste entre uno menos el margen: <strong>precio = coste ÷ (1 − margen)</strong>.</p>
<div class="tablewrap compact" role="region" aria-label="Precio de venta según el margen" tabindex="0">
<table>
<caption>Ejemplo inventado: un producto que cuesta 12 €</caption>
<thead><tr><th scope="col">Margen que buscas</th><th scope="col">Precio sin IVA</th><th scope="col">Precio con IVA (21 %)</th></tr></thead>
<tbody>
<tr><th scope="row">30 %</th><td>17,14 €</td><td>20,74 €</td></tr>
<tr><th scope="row">40 %</th><td>20,00 €</td><td>24,20 €</td></tr>
<tr><th scope="row">50 %</th><td>24,00 €</td><td>29,04 €</td></tr>
</tbody>
</table>
</div>
"""),
        ("costes", "No olvides los costes que no se ven", """
<ul>
<li>El envío y el embalaje, sobre todo si ofreces envío gratis.</li>
<li>Las comisiones de plataformas o por cobrar con tarjeta.</li>
<li>Las devoluciones y las mermas.</li>
<li>El tiempo que dedicas a preparar y gestionar cada pedido.</li>
</ul>
<p>Súmalos al coste del producto: si no, el margen que calculas es mayor que el que realmente te queda.</p>
"""),
        ("descuentos", "Lo que cuesta un descuento", """
<p>Un descuento parece pequeño, pero se come el margen. Un producto cuesta 60 € y se vende a 100 € sin IVA: ganas 40 € por unidad. Si lo rebajas un 20 %, se vende a 80 € y ganas 20 €: <strong>la mitad.</strong> Para ganar lo mismo que antes tendrías que vender el doble.</p>
<div class="callout"><p>Antes de hacer una promoción, calcula cuánto beneficio queda por unidad y cuántas más tienes que vender para compensarlo.</p></div>
"""),
        ("revisar", "Revisa tus márgenes cada cierto tiempo", """
<p>Si tu proveedor sube el precio y tú no cambias el tuyo, el margen baja sin que te des cuenta. Revisa de vez en cuando los productos que más vendes y compara el coste actual con el precio. Ordenar los productos por lo que aportan, no solo por lo que venden, te enseña dónde conviene poner el esfuerzo.</p>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Cada producto muestra su margen,</strong> y el coste se actualiza solo al recibir pedidos.</li>
<li><strong>Catálogo completo:</strong> código, código de barras, precio (o PVP con IVA), IVA, coste y stock en un solo sitio, que puedes importar desde Excel o CSV.</li>
<li><strong>Resultados:</strong> ventas, coste de lo vendido, margen y gastos de cualquier periodo.</li>
</ul>
<p>Para que el margen salga exacto, cada producto tiene que tener su coste: se lo pones tú o se actualiza al recibir pedidos de proveedores.</p>
""",
    shot=("productos-c", "Lista de productos de NirKanA con categoría, precio, coste y existencias de cada uno", "Productos con precio y coste: la base para calcular el margen"),
    faq=[
        ("¿Cuál es la diferencia entre margen y recargo?",
         "El margen es la parte del precio de venta que te queda como ganancia; el recargo es lo que añades sobre el coste. Con un coste de 12 € y un precio de 20 € sin IVA, el margen es del 40 % y el recargo del 66,7 %."),
        ("¿El margen se calcula con o sin IVA?",
         "Sin IVA. El IVA lo repercutes al cliente para ingresarlo después, así que no forma parte de tu ganancia. Calcula siempre con el precio y el coste sin IVA."),
        ("¿Qué margen es bueno?",
         "No hay un número válido para todos: depende del sector, de tus gastos fijos y de lo que vendes. Una forma práctica es sumar tus gastos del mes y comprobar qué margen necesitas para cubrirlos con las ventas que haces."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- índice
HUB = dict(
    title="Guías para llevar tu negocio: caja, stock, citas y facturas · NirKanA",
    description="Guías prácticas para autónomos y pequeños negocios: cómo elegir un TPV, cuadrar la caja, controlar el stock, organizar citas, facturar y preparar el trimestre.",
    h1="Guías para llevar mejor tu negocio",
    lead="Explicaciones claras, con ejemplos y listas de comprobación, sobre lo que más tiempo quita a un negocio pequeño: cobrar, cuadrar la caja, controlar el stock, organizar citas y tener las facturas en orden.",
    demo="tienda",
    faq=[
        ("¿Quién escribe estas guías?",
         "El equipo de NirKanA. Son guías generales sobre cómo llevar un negocio pequeño; no son asesoramiento fiscal ni legal, y para dudas concretas conviene hablar con tu gestoría."),
        ("¿Hace falta usar NirKanA para aplicar estas guías?",
         "No. Los métodos sirven con una hoja de cálculo o con cualquier otro programa. En cada guía explicamos además cómo lo hace NirKanA, por si quieres probarlo."),
        ("¿Puedo probar NirKanA antes de decidir?",
         "Sí: puedes abrirlo 24 horas gratis, sin tarjeta, con un negocio de ejemplo. Y si prefieres contarnos tu caso, escríbenos y te respondemos."),
    ],
)

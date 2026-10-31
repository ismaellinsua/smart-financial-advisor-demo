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
    "peluquerias": ("/programa-peluquerias-estetica/", "Programa para peluquerías y barberías"),
    "tiendas": ("/tpv-tiendas/", "TPV para tiendas y comercios"),
    "autonomos": ("/programa-facturacion-autonomos/", "Programa de facturación para autónomos"),
    "online": ("/tpv-tienda-online/", "Gestión de tiendas online"),
    "pymes": ("/programa-gestion-pequenas-empresas/", "Programa de gestión para pequeñas empresas"),
    "entrenadores": ("/programa-entrenadores-personales/", "App para entrenadores personales"),
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
    tools=["calculadora-de-arqueo-de-caja"],
    updated="2026-10-22",
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
<p>Para el paso de contar y comparar tienes una <a href="/herramientas/calculadora-de-arqueo-de-caja/">calculadora de arqueo de caja</a> gratis, con los billetes y las monedas del euro y una plantilla de Excel para imprimir.</p>
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

# ---------------------------------------------------------------------------------------------------------------- 2b
guide(
    slug="comandas-y-pantalla-de-cocina-en-un-bar",
    title="Comandas y pantalla de cocina en un bar o restaurante · NirKanA",
    description="Qué debe llevar una comanda, cuándo conviene pasar del papel a una pantalla de cocina y cómo coordinar sala y cocina en un bar o restaurante, con los errores más comunes.",
    h1="Comandas y pantalla de cocina en un bar o restaurante",
    lead="La comanda es el mensaje que va de la sala a la cocina. Si llega tarde, incompleta o ilegible, se nota en el plato y en la mesa. Aquí tienes cómo ordenarla, con papel o con pantalla.",
    group="Bares y restaurantes",
    summary="Qué lleva una comanda bien hecha, papel frente a pantalla de cocina y cinco errores que frenan el servicio.",
    icon="i-utensils",
    demo="hosteleria",
    sectors=["restaurantes"],
    related=["arqueo-y-cierre-de-caja", "que-es-un-tpv"],
    published="2026-10-22",
    subject="Consulta desde la guía de comandas y pantalla de cocina",
    sections=[
        ("que-es", "Qué es una comanda y por qué importa", """
<p>La <strong>comanda</strong> es el pedido de una mesa tal y como llega a la cocina y a la barra: qué se ha pedido, cuántas unidades, con qué cambios y en qué orden debe salir. Parece un papel más, pero de ella dependen tres cosas:</p>
<ul>
<li><strong>Que el plato sea el que pidió el cliente,</strong> con su «sin cebolla» o su «poco hecho».</li>
<li><strong>Que salga en el orden y en el momento adecuados:</strong> los entrantes antes que los principales, y todo lo de una mesa junto.</li>
<li><strong>Que la cuenta sea correcta:</strong> lo que se cocina es lo que se cobra. Una comanda perdida es un plato que no se cobra o un cliente que espera sin que nadie lo sepa.</li>
</ul>
"""),
        ("que-lleva", "Qué debe llevar una comanda", """
<p>Sea en papel o en pantalla, una comanda completa lleva siempre lo mismo:</p>
<ol>
<li><strong>Mesa o número de pedido,</strong> y cuántos comensales son.</li>
<li><strong>Hora a la que se toma,</strong> para saber cuánto lleva esperando.</li>
<li><strong>Quién la toma:</strong> si hay una duda, se sabe a quién preguntar.</li>
<li><strong>Cada plato con su cantidad,</strong> uno por línea y con el nombre que usa la cocina.</li>
<li><strong>Cambios y notas junto al plato al que afectan:</strong> «sin cebolla», «para compartir», «poco hecho».</li>
<li><strong>Alergias e intolerancias bien visibles,</strong> no escondidas entre las notas. Es lo único que no admite letra pequeña ni interpretaciones.</li>
<li><strong>Orden de salida:</strong> qué sale primero y qué «marcha» después.</li>
<li><strong>Destino:</strong> si va a la cocina, a la plancha o a la barra.</li>
</ol>
<div class="tablewrap compact" role="region" aria-label="Ejemplo de comanda" tabindex="0">
<table>
<caption>Ejemplo inventado de una comanda</caption>
<thead><tr><th scope="col">Mesa 7 · 4 comensales · 21:05</th><th scope="col">Notas</th><th scope="col">Salida</th></tr></thead>
<tbody>
<tr><th scope="row">2 × Ensalada de la casa</th><td>Una sin cebolla</td><td>Primero</td></tr>
<tr><th scope="row">1 × Croquetas caseras (6 uds.)</th><td>Para compartir</td><td>Primero</td></tr>
<tr><th scope="row">2 × Solomillo</th><td>Uno poco hecho y otro al punto</td><td>Segundo</td></tr>
<tr><th scope="row">1 × Pasta sin gluten</th><td><strong>Celiaquía</strong></td><td>Segundo</td></tr>
</tbody>
</table>
</div>
"""),
        ("papel-o-pantalla", "Papel, impresora de cocina o pantalla de cocina", """
<p>No hay una opción mejor para todos los locales. Esto es lo que cambia de una a otra:</p>
<div class="tablewrap" role="region" aria-label="Comparación de formas de pasar las comandas" tabindex="0">
<table>
<thead><tr><th scope="col">Forma</th><th scope="col">Cómo funciona</th><th scope="col">Lo bueno</th><th scope="col">Lo que hay que vigilar</th></tr></thead>
<tbody>
<tr><th scope="row">Libreta y papel</th><td>El camarero apunta, arranca la hoja y la lleva a la cocina.</td><td>No necesita nada y es inmediata.</td><td>Letra ilegible, hojas que se pierden y viajes de ida y vuelta.</td></tr>
<tr><th scope="row">Impresora en la cocina</th><td>El pedido se imprime en un ticket en cuanto se envía.</td><td>La cocina recibe un papel claro, sin viajes.</td><td>Papel y mantenimiento: si se atasca o se queda sin papel, el pedido no llega.</td></tr>
<tr><th scope="row">Pantalla de cocina</th><td>El pedido aparece en una pantalla y la cocina lo marca según avanza.</td><td>Sin papel, y con la hora y el estado de cada plato registrados.</td><td>Hace falta una pantalla y buena conexión en la cocina, y acostumbrar al equipo.</td></tr>
</tbody>
</table>
</div>
<p>Cuanto mayor es el local, más se nota la diferencia: con pocas mesas y una sola persona sirviendo, el papel funciona; con varias personas pidiendo a la vez y platos que salen por tandas, cada viaje y cada hoja perdida cuestan tiempo.</p>
"""),
        ("recorrido", "Un servicio sin gritos: el recorrido de una mesa", """
<ol>
<li><strong>Se abre la mesa</strong> con el número de comensales. Así sabes qué mesas están libres, cuáles ocupadas y cuánto llevan.</li>
<li><strong>Se toma la comanda en la mesa,</strong> no de memoria en la barra: lo apuntas delante del cliente y repites el pedido para confirmarlo.</li>
<li><strong>Se envía por tandas:</strong> los entrantes ya, y los principales cuando los entrantes estén sobre la mesa. Así los platos no se enfrían esperando.</li>
<li><strong>La cocina marca el avance:</strong> pendiente, en preparación, listo. La sala sabe qué recoger y cuándo.</li>
<li><strong>Si el cliente añade algo,</strong> va a la misma mesa y a la misma cuenta, con su hora, para que no se mezcle con lo anterior.</li>
<li><strong>Se cobra:</strong> la mesa entera o dividida entre varias personas, en efectivo, con tarjeta o mezclando ambas.</li>
<li><strong>Se libera la mesa</strong> para el siguiente servicio.</li>
</ol>
<p>Al terminar el servicio, la caja se cuadra con el método de la <a href="/guias/arqueo-y-cierre-de-caja/">guía de arqueo y cierre de caja</a>.</p>
"""),
        ("errores", "Cinco errores que frenan el servicio", """
<ul>
<li><strong>Comandas sin orden de salida.</strong> La cocina prepara todo a la vez y el principal llega antes de que se hayan terminado los entrantes.</li>
<li><strong>Alergias apuntadas «de palabra».</strong> Si no están escritas de forma visible en la comanda, dependen de que alguien se acuerde. Escríbelas siempre, en su propia línea.</li>
<li><strong>Dos camareros, una mesa y ninguna coordinación.</strong> Cada uno pide lo que oye y se duplican o se olvidan platos. Decide quién abre la mesa y haz que todo lo que se añada vaya a la misma cuenta.</li>
<li><strong>Cambios de última hora de viva voz.</strong> Si el cliente cambia de idea, el cambio tiene que quedar en la comanda; si no, se cocina lo antiguo y se cobra lo nuevo, o al revés.</li>
<li><strong>No mirar cuánto lleva esperando cada plato.</strong> La mesa que espera mucho más que las demás es la que acaba llamando al camarero. Ten a la vista el tiempo de cada pedido.</li>
</ul>
<div class="callout"><p><strong>Una regla simple:</strong> fija el tiempo máximo que quieres que espere un pedido y revisa cada día qué mesas lo han superado. Si se repite a la misma hora o con el mismo plato, hay un cuello de botella que se puede resolver.</p></div>
"""),
        ("coordinar", "Cómo coordinar sala y cocina", """
<ul>
<li><strong>Un solo nombre para cada plato.</strong> Que la carta, la comanda y la cocina usen el mismo; evita abreviaturas que solo entiende una persona.</li>
<li><strong>Un responsable por turno</strong> que reparta las mesas y vigile los tiempos.</li>
<li><strong>Los platos agotados se avisan a la sala</strong> antes de que alguien los pida.</li>
<li><strong>Una revisión corta al cerrar:</strong> qué platos han tardado más, qué comandas hubo que corregir y qué mesas se cobraron con descuento.</li>
</ul>
"""),
    ],
    nirkana="""
<p>Esto es lo que ya hace NirKanA en un restaurante, un bar o una cafetería:</p>
<ul>
<li><strong>Plano de mesas:</strong> ves de un vistazo qué mesas están libres, cuántos comensales hay y lo que queda por cobrar.</li>
<li><strong>Comandas desde el móvil:</strong> cada camarero pide desde su móvil con su PIN, y varios pueden pedir en la misma mesa a la vez.</li>
<li><strong>Pantalla de cocina:</strong> la cocina ve los platos en su pantalla, que se actualiza sola, los marca en preparación o listos y ve qué lleva más esperando.</li>
<li><strong>Cuenta dividida y pago mixto:</strong> cobras la mesa entera o por partes, mezclas efectivo y tarjeta, y el cambio se calcula solo.</li>
<li><strong>Cierre de caja:</strong> el efectivo se cuenta sin ver lo esperado y, al cerrar, ves el descuadre al momento.</li>
</ul>
<p>Hoy las reservas las apunta tu equipo (cliente, hora, comensales y notas): no hay una página pública para que tus clientes reserven solos.</p>
""",
    shot=("cocina-c", "Pantalla de cocina de NirKanA con los platos de cada mesa y el tiempo que llevan esperando", "La pantalla de cocina: los platos de cada mesa y lo que llevan esperando"),
    faq=[
        ("¿Qué es una pantalla de cocina?",
         "Es una pantalla en la cocina que muestra los pedidos que llegan de la sala, en lugar de papeles o tickets. Quien cocina marca cada plato como en preparación o listo, y el pedido queda registrado con su hora."),
        ("¿Hace falta una impresora en la cocina?",
         "No necesariamente. Con una pantalla de cocina no hace falta imprimir cada comanda. Si tu cocina trabaja mejor con papel, puedes mantener una impresora aparte; antes de comprarla, comprueba que funciona con tu programa y tu dispositivo."),
        ("¿Pueden pedir varios camareros en la misma mesa?",
         "Depende del programa. En NirKanA cada camarero pide desde su móvil con su PIN y varios pueden pedir en la misma mesa a la vez."),
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
    updated="2026-10-30",
    title="Agenda de citas para peluquerías: organización y reservas · NirKanA",
    description="Organiza las citas de tu peluquería: tiempos por servicio, reservas online y confirmaciones por WhatsApp. Con un mensaje modelo y consejos para reducir ausencias.",
    h1="Cómo organizar las citas de una peluquería: sin solapes y con menos plantones",
    lead="Reúne las citas de WhatsApp, teléfono y reservas online en una agenda. Aprende a asignar tiempos por servicio, comprobar huecos y confirmar citas para reducir solapes y ausencias.",
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
<p><strong>Reserva online:</strong> tus clientes pueden elegir servicio, profesional y hora disponible desde tu enlace. Puedes confirmar cada solicitud o permitir la confirmación automática. Consulta cómo funciona en el <a href="/programa-peluquerias-estetica/#reserva-online">programa para peluquerías y barberías con reserva online</a>.</p>
<p>La prueba gratuita de 24 horas permite ver la agenda, la caja y las facturas. La reserva online se enseña en una demostración. No se cobra señal al reservar y los mensajes de WhatsApp los envías tú.</p>
""",
    shot=("agenda-persona-c", "Agenda por persona de NirKanA con una columna por profesional y las citas del día de una peluquería", "Agenda por persona: una columna por profesional"),
    faq=[
        ("¿Mis clientes pueden reservar online con NirKanA?",
         "Sí. Pueden elegir servicio, profesional y una hora disponible desde tu enlace de reservas. Tú decides si confirmas cada solicitud o si se confirma automáticamente. La reserva online se enseña en una demostración; la prueba de 24 horas muestra la agenda, la caja y las facturas."),
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
    tools=["calculadora-de-iva"],
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
    description="Calcula el margen de un producto con fórmulas y ejemplos. Distingue margen y recargo, incluye envío y comisiones por SKU y prueba la calculadora gratuita.",
    h1="Cómo calcular el margen de un producto y fijar el precio de venta",
    lead="Vender mucho no sirve si cada venta deja poco. Con dos fórmulas sabes cuánto ganas por producto y qué precio necesitas para llegar al margen que buscas.",
    group="Stock, precios y tienda online",
    summary="Margen frente a recargo, la fórmula del precio de venta y lo que cuesta un descuento.",
    icon="i-chart",
    demo="online",
    sectors=["online", "tiendas"],
    related=["control-de-stock-en-una-tienda", "que-debe-llevar-una-factura"],
    tools=["calculadora-de-margen"],
    updated="2026-10-30",
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
<p>Si prefieres no hacer la cuenta a mano, la <a href="/herramientas/calculadora-de-margen/">calculadora de margen y precio de venta</a> parte del coste y del margen (o del precio) y añade el IVA y el efecto de un descuento.</p>
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
        ("margen-ecommerce-sku", "Cómo calcular el margen por SKU en una tienda online", """
<p>Un SKU es la referencia que identifica un producto o variante. Para comparar referencias, calcula cuánto deja cada venta después de los costes variables que le corresponden. Ese resultado es el <strong>margen de contribución</strong>: todavía debe cubrir gastos fijos como alquileres, sueldos o suscripciones.</p>
<div class="tablewrap compact" role="region" aria-label="Ejemplo de margen por SKU" tabindex="0">
<table>
<caption>Ejemplo inventado: una unidad vendida por 100 € sin IVA</caption>
<thead><tr><th scope="col">Concepto</th><th scope="col">Importe por unidad</th></tr></thead>
<tbody>
<tr><th scope="row">Venta neta, después de descuentos</th><td>100,00 €</td></tr>
<tr><th scope="row">Compra del producto</th><td>50,00 €</td></tr>
<tr><th scope="row">Embalaje</th><td>2,00 €</td></tr>
<tr><th scope="row">Envío asumido por la tienda</th><td>5,00 €</td></tr>
<tr><th scope="row">Comisiones atribuibles a esa venta</th><td>3,00 €</td></tr>
<tr><th scope="row">Coste variable total</th><td>60,00 €</td></tr>
<tr><th scope="row">Contribución antes de gastos fijos</th><td>40,00 € (40 %)</td></tr>
</tbody>
</table>
</div>
<p>Si solo restas la compra, obtienes un 50 %; al incluir embalaje, envío y comisiones, queda un 40 %. No lo llames beneficio neto: aún faltan los gastos fijos y los impuestos que correspondan.</p>
<p>Si un pedido contiene varias unidades, reparte los costes del pedido con un criterio consistente y no cargues todo el envío a cada producto. Usa los importes reales de tus liquidaciones para las comisiones. Revisa también el coste de las devoluciones.</p>
<p>Para comprobar el ejemplo, introduce 60 € de coste total y 100 € de precio sin IVA en la <a href="/herramientas/calculadora-de-margen/">calculadora gratuita de margen</a>. La herramienta calcula con los datos que introduces; no obtiene automáticamente los costes de una tienda online.</p>
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

# ---------------------------------------------------------------------------------------------------------------- 8
guide(
    slug="stock-de-tienda-online-y-tienda-fisica",
    title="Stock de tienda online y física: un solo inventario · NirKanA",
    description="Cómo llevar un solo inventario si vendes en una tienda online y en una tienda física: cinco reglas, cuándo descontar el stock de un pedido y un ejemplo con números.",
    h1="Stock de una tienda online y una tienda física: cómo llevar un solo inventario",
    lead="Vender por internet y en el local los mismos productos funciona hasta que uno se agota: entonces alguien compra lo que ya no queda. Un solo inventario y unas reglas claras lo evitan.",
    group="Stock, precios y tienda online",
    summary="Cinco reglas para llevar un solo inventario si vendes en la web y en el local, y cuándo descontar un pedido online.",
    icon="i-cloud",
    demo="online",
    sectors=["online", "tiendas"],
    related=["control-de-stock-en-una-tienda", "calcular-el-margen-de-un-producto"],
    published="2026-10-22",
    subject="Consulta desde la guía de stock de tienda online y física",
    sections=[
        ("por-que", "Por qué el stock se desajusta cuando vendes en dos sitios", """
<p>Con un solo canal, cada venta descuenta una unidad y las cuentas son fáciles. Al añadir el segundo aparecen los desajustes, y los motivos suelen ser casi siempre los mismos:</p>
<ul>
<li><strong>Dos inventarios separados:</strong> una hoja para la web y otra para la tienda, que alguien tiene que mantener a mano.</li>
<li><strong>Retrasos:</strong> el pedido de la web se anota al día siguiente y, mientras tanto, la última unidad se vende en el mostrador.</li>
<li><strong>Productos con nombres o códigos distintos</strong> en cada canal, que no se pueden cruzar.</li>
<li><strong>Cancelaciones y devoluciones</strong> que se anotan en un sitio y no en el otro.</li>
<li><strong>Mercancía reservada</strong> para un pedido que se cobra o se envía días después.</li>
</ul>
<p>El resultado es el que nadie quiere: vender algo que no tienes, pedir disculpas y cancelar el pedido.</p>
"""),
        ("reglas", "Cinco reglas para llevar un solo inventario", """
<ol>
<li><strong>Un código por producto, el mismo en los dos canales.</strong> Una referencia propia o el código de barras, escrito igual en tu tienda online y en tu programa. Sin esa clave común no hay forma fiable de cruzar las ventas.</li>
<li><strong>Una sola fuente de verdad.</strong> Elige dónde vive el stock «oficial» y haz que todo pase por ahí: ventas del local, pedidos de la web, compras a proveedores y devoluciones.</li>
<li><strong>Anota los pedidos online el mismo día,</strong> mejor al recibirlos que al final de la semana. El retraso es una de las causas más habituales de los desajustes.</li>
<li><strong>Protege las últimas unidades.</strong> En los productos con poco stock, publica en la web una unidad menos de las que tienes, o reserva la última para el local. Es mejor perder una venta que vender dos veces lo mismo.</li>
<li><strong>Cuenta y compara con regularidad.</strong> Un recuento rotativo semanal de una categoría te enseña dónde se desajusta el sistema antes de que se acumule. Tienes el método en la <a href="/guias/control-de-stock-en-una-tienda/">guía de control de stock en una tienda</a>.</li>
</ol>
"""),
        ("cuando-descontar", "¿Cuándo se descuenta el stock de un pedido online?", """
<p>No hay una única respuesta correcta; lo importante es elegir una regla y aplicarla siempre igual.</p>
<div class="tablewrap" role="region" aria-label="Cuándo descontar el stock de un pedido online" tabindex="0">
<table>
<thead><tr><th scope="col">Momento</th><th scope="col">Ventaja</th><th scope="col">Riesgo</th></tr></thead>
<tbody>
<tr><th scope="row">Al recibir el pedido</th><td>Evitas vender dos veces la misma unidad.</td><td>Si el cliente no paga o cancela, hay que devolver la unidad al stock.</td></tr>
<tr><th scope="row">Al cobrarlo</th><td>Solo reservas mercancía de pedidos pagados.</td><td>Entre el pedido y el cobro, la unidad sigue «disponible» para otra venta.</td></tr>
<tr><th scope="row">Al enviarlo</th><td>El stock refleja lo que de verdad ha salido del almacén.</td><td>Mientras se prepara, esa unidad todavía puede venderse en la tienda.</td></tr>
</tbody>
</table>
</div>
<p>Para un negocio pequeño, lo más seguro suele ser descontar al recibir el pedido y devolver la unidad al stock si se cancela antes de enviarlo.</p>
"""),
        ("ejemplo", "Un ejemplo con números", """
<p>Una camiseta con 6 unidades en stock, vendida en el local y en la web. Esto es lo que ve un inventario único a lo largo de un día:</p>
<div class="tablewrap compact" role="region" aria-label="Ejemplo de movimientos de stock de un producto" tabindex="0">
<table>
<caption>Ejemplo inventado: una camiseta en dos canales</caption>
<thead><tr><th scope="col">Movimiento</th><th scope="col">Unidades</th><th scope="col">Stock</th></tr></thead>
<tbody>
<tr><th scope="row">Stock al abrir</th><td>—</td><td>6</td></tr>
<tr><th scope="row">Venta en el local</th><td>−2</td><td>4</td></tr>
<tr><th scope="row">Pedido en la web</th><td>−1</td><td>3</td></tr>
<tr><th scope="row">Otro pedido en la web, cancelado antes de enviarlo</th><td>−1 y +1</td><td>3</td></tr>
<tr><th scope="row">Devolución de un pedido ya enviado (llega en buen estado)</th><td>+1</td><td>4</td></tr>
</tbody>
</table>
</div>
<p>Si el stock mínimo de esa camiseta es 3, cuando baje de ahí toca pedir. Fíjate en que cada movimiento tiene su motivo: así, al contar, sabes de dónde viene cualquier diferencia.</p>
"""),
        ("sin-conexion", "¿Y si tu tienda online y tu programa no están conectados?", """
<p>Muchas tiendas pequeñas trabajan así: la plataforma de la tienda online por un lado y el programa de la tienda por otro, sin conexión automática. Se puede llevar bien con una rutina corta:</p>
<ol>
<li><strong>Cada pedido online se registra como una venta</strong> en tu programa el mismo día, con el mismo código de producto.</li>
<li><strong>El catálogo se mantiene en un único archivo</strong> (Excel o CSV) con código, nombre, precio, coste y stock, y se importa cada vez que cambia.</li>
<li><strong>Una vez por semana,</strong> compara el stock que muestra la web con el de tu programa y corrige lo que no coincida, anotando el motivo.</li>
</ol>
<p>Son unos minutos al día, y cuando las ventas crecen compensa buscar una integración que lo haga sola. Mientras tanto, lo que no conviene es llevar dos inventarios y fiarse de los dos.</p>
"""),
        ("errores", "Errores frecuentes", """
<ul>
<li>Llevar una hoja de stock para la web y otra para el local.</li>
<li>Cambiar el nombre de un producto en un canal y no en el otro, de modo que dejan de cruzarse.</li>
<li>No anotar las devoluciones de la web.</li>
<li>Subir al stock una devolución sin comprobar que el producto está en condiciones de venderse: si no lo está, es una merma.</li>
<li>No avisar al equipo de la tienda de que la última unidad está reservada para un pedido.</li>
</ul>
"""),
    ],
    nirkana="""
<p>NirKanA no se conecta hoy de forma automática con plataformas como Shopify o WooCommerce, pero te da un solo sitio para el catálogo y el stock del local y de la web:</p>
<ul>
<li><strong>Catálogo con stock:</strong> productos con código, código de barras, precio, coste y stock en un solo sitio.</li>
<li><strong>Un stock para los dos canales:</strong> el TPV y tu catálogo comparten productos y stock, y cada pedido de la web se registra como una venta.</li>
<li><strong>Importa desde Excel o CSV:</strong> subes tu lista de productos y ves qué se creará o se actualizará antes de guardar nada.</li>
<li><strong>Reposición:</strong> ves qué se agota y cuánto pedir, y creas el pedido al proveedor con un clic.</li>
<li><strong>Envíos y servicios:</strong> los cobras como un producto más, sin stock.</li>
</ul>
<p>Si necesitas una integración concreta con tu plataforma, cuéntanos cuál y la estudiamos.</p>
""",
    shot=("reposicion-c", "Resumen de NirKanA con lo más vendido y el aviso de reposición: cinco productos se agotan en menos de una semana", "Reposición: qué se agota y cuánto pedir (con datos de ejemplo)"),
    faq=[
        ("¿Cómo evito vender online algo que ya he vendido en la tienda?",
         "Haz que los dos canales descuenten del mismo inventario, registra los pedidos online el mismo día y protege las últimas unidades de los productos con poco stock publicando en la web una menos de las que tienes. Si llevas dos hojas separadas, el desajuste es cuestión de tiempo."),
        ("¿Cuándo debo descontar el stock de un pedido online?",
         "Elige un momento y úsalo siempre igual: al recibir el pedido evitas vender dos veces la misma unidad, al cobrarlo reservas solo lo pagado y al enviarlo reflejas lo que ya ha salido. Para un negocio pequeño suele ser lo más seguro descontar al recibir el pedido y devolver la unidad si se cancela antes del envío."),
        ("¿Se conecta NirKanA con Shopify o WooCommerce?",
         "No. Hoy no hay conexión automática: importas tu lista de productos desde un Excel o CSV y registras los pedidos como ventas. Si necesitas una integración concreta, cuéntanos cuál y la estudiamos."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 9
guide(
    slug="devoluciones-y-cambios-en-una-tienda",
    title="Devoluciones y cambios en una tienda: cómo organizarlos · NirKanA",
    description="Cómo organizar las devoluciones y los cambios en una tienda: política escrita, pasos para registrarlos y qué cambia en la caja, el stock y la factura, con los errores más comunes.",
    h1="Devoluciones y cambios en una tienda: cómo organizarlos",
    lead="Una devolución bien gestionada deja tranquilo al cliente y las cuentas en orden; una mal gestionada descuadra la caja, el stock y a veces la factura. Este es un método sencillo para organizarlas.",
    group="Cobrar y cuadrar la caja",
    summary="Política escrita, los pasos de una devolución y qué cambia en la caja, el stock y la factura.",
    icon="i-bag",
    demo="tienda",
    sectors=["tiendas", "online"],
    related=["arqueo-y-cierre-de-caja", "control-de-stock-en-una-tienda", "que-debe-llevar-una-factura"],
    published="2026-10-22",
    subject="Consulta desde la guía de devoluciones y cambios",
    disclaimer="Esta guía explica cómo organizar las devoluciones y los cambios; no es asesoramiento jurídico. Las obligaciones concretas (garantía, venta a distancia, facturas rectificativas) dependen de cada caso: confírmalas con tu gestoría o en la información oficial de consumo.",
    sections=[
        ("politica", "Empieza por una política de cambios y devoluciones escrita", """
<p>La mayoría de los problemas con las devoluciones vienen de no haber decidido nada antes. Una política corta, escrita y a la vista (en el mostrador, en el ticket o en la web) evita discusiones y hace que todo el equipo responda lo mismo. Decide, como mínimo:</p>
<ul>
<li><strong>Plazo:</strong> cuántos días tiene el cliente para cambiar o devolver.</li>
<li><strong>Estado del producto:</strong> con etiquetas, sin usar, en su envase.</li>
<li><strong>Qué hay que presentar:</strong> el ticket, la factura o cualquier otro comprobante de la compra.</li>
<li><strong>Qué se ofrece:</strong> cambio por otro producto, vale o devolución del dinero.</li>
<li><strong>Cómo se devuelve el dinero:</strong> lo habitual es hacerlo por la misma vía por la que se pagó.</li>
<li><strong>Qué se excluye,</strong> si hay algo que no admite devolución (productos personalizados o de higiene, por ejemplo).</li>
<li><strong>Quién puede aprobarla</strong> cuando el caso se sale de la norma.</li>
</ul>
"""),
        ("situaciones", "Tres situaciones que conviene distinguir", """
<p>No todas las devoluciones son iguales, y no todas dependen solo de tu política:</p>
<ul>
<li><strong>Producto defectuoso o que no es lo que se vendió:</strong> el cliente tiene derechos legales (la garantía legal), con independencia de tu política de cambios.</li>
<li><strong>Cambio de talla, color o modelo sin defecto:</strong> en una tienda física, aceptarlo es decisión tuya. Si lo ofreces, ponlo por escrito.</li>
<li><strong>Compra a distancia (por ejemplo, en una tienda online):</strong> suele haber un derecho de desistimiento, con sus propios plazos y condiciones.</li>
</ul>
<p>Los plazos y las condiciones concretas dependen de cada caso y de la normativa vigente: confírmalos con tu gestoría o en la información oficial de consumo antes de fijar tu política.</p>
"""),
        ("pasos", "Los pasos de una devolución", """
<ol>
<li><strong>Localiza la venta original:</strong> con el ticket o buscándola por fecha, importe o cliente.</li>
<li><strong>Revisa el producto</strong> y comprueba que encaja en tu política: estado, plazo y comprobante.</li>
<li><strong>Decide con el cliente:</strong> cambio, vale o devolución del dinero.</li>
<li><strong>Registra la devolución en tu programa,</strong> con los productos que vuelven y el importe. No saques dinero del cajón sin anotarlo: es una de las causas más habituales de los descuadres.</li>
<li><strong>Devuelve el dinero por la misma vía del pago:</strong> efectivo desde el cajón, o tarjeta con la devolución del datáfono.</li>
<li><strong>Repón el producto al stock</strong> si está en condiciones de volver a venderse; si no, anótalo como merma.</li>
<li><strong>Si había factura, emite la rectificativa</strong> que la corrige, en lugar de borrarla.</li>
<li><strong>Entrega un comprobante</strong> de la devolución y guarda el tuyo.</li>
</ol>
"""),
        ("que-cambia", "Qué cambia en la caja, el stock y la factura", """
<div class="tablewrap" role="region" aria-label="Qué cambia con una devolución" tabindex="0">
<table>
<thead><tr><th scope="col">Dónde</th><th scope="col">Qué cambia</th><th scope="col">Qué hay que anotar</th></tr></thead>
<tbody>
<tr><th scope="row">Caja</th><td>Sale dinero del cajón si se devuelve en efectivo.</td><td>La devolución, con su importe y la forma de pago original.</td></tr>
<tr><th scope="row">Tarjeta</th><td>Se devuelve por el datáfono al mismo medio de pago.</td><td>La devolución, para que el total de tarjeta de tu programa coincida con el del datáfono.</td></tr>
<tr><th scope="row">Stock</th><td>Las unidades vuelven al stock si se pueden volver a vender.</td><td>El motivo; si están dañadas, una merma en lugar de una entrada.</td></tr>
<tr><th scope="row">Factura e IVA</th><td>Una factura emitida no se borra: se corrige con una rectificativa.</td><td>La rectificativa, vinculada a la factura original.</td></tr>
</tbody>
</table>
</div>
"""),
        ("cambios", "Cambios: una devolución y una venta a la vez", """
<p>Un cambio es, a efectos de cuentas, devolver un producto y vender otro. Si los dos valen lo mismo no se mueve dinero, pero sí el stock: una unidad entra y otra sale. Si el nuevo cuesta más, cobras la diferencia; si cuesta menos, devuelves la diferencia o entregas un vale. Anotarlo como una devolución y una venta, en lugar de «cambiar sin más», mantiene la caja y el stock en orden.</p>
"""),
        ("errores", "Errores frecuentes con las devoluciones", """
<ul>
<li><strong>Devolver dinero sin registrar nada:</strong> la caja no cuadra y nadie sabe por qué.</li>
<li><strong>Devolver en efectivo una compra pagada con tarjeta:</strong> la devolución debería ir al mismo medio de pago, también para evitar fraudes.</li>
<li><strong>Dejar que cualquiera apruebe cualquier devolución:</strong> decide quién puede hacerlo y revisa de vez en cuando las ventas anuladas y devueltas.</li>
<li><strong>Olvidar el stock:</strong> el producto vuelve a la estantería pero el sistema no se entera, o al revés.</li>
<li><strong>Borrar una factura en lugar de rectificarla,</strong> con el desorden que luego supone para tu gestoría.</li>
</ul>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Devoluciones parciales:</strong> devuelves solo los productos que el cliente trae, no la venta entera.</li>
<li><strong>Stock que se mueve solo:</strong> cada venta, compra o devolución actualiza las unidades.</li>
<li><strong>Facturas rectificativas</strong> para corregir una factura ya emitida, que puedes imprimir o guardar en PDF.</li>
<li><strong>Cada venta queda firmada por quien la hizo,</strong> y el registro de actividad guarda los accesos, las anulaciones, las facturas, los cierres de caja y los cambios de configuración.</li>
<li><strong>Cierre de caja contado a ciegas,</strong> con el descuadre a la vista.</li>
</ul>
""",
    shot=("ventas-c", "Pantalla Ventas de NirKanA con los tickets del día, su forma de pago y su estado", "Ventas: todos los tickets, con su forma de pago y su estado"),
    faq=[
        ("¿Estoy obligado a aceptar devoluciones en mi tienda?",
         "Si el producto tiene un defecto o no es lo que se vendió, el cliente tiene derechos legales con independencia de tu política. En una tienda física, aceptar cambios o devoluciones de un producto sin defecto es decisión tuya, y conviene fijarlo y escribirlo. En las compras a distancia suele haber un derecho de desistimiento: confirma las condiciones con tu gestoría o en la información oficial de consumo."),
        ("¿Cómo se devuelve el dinero de una compra pagada con tarjeta?",
         "Lo habitual es devolverlo al mismo medio de pago, con la devolución en el datáfono, y registrar la devolución en tu programa con la forma de pago original. Así el total de tarjeta de tu programa coincide con el del datáfono."),
        ("¿Qué pasa con la factura si el cliente devuelve el producto?",
         "Una factura emitida no se borra: se corrige con una factura rectificativa que anula o reduce su importe. Tu gestoría puede confirmarte cómo aplicarlo en tu caso. NirKanA permite devoluciones parciales y emitir facturas rectificativas."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 10
guide(
    slug="como-elegir-una-impresora-de-tickets",
    title="Cómo elegir una impresora de tickets para tu negocio · NirKanA",
    description="Qué mirar al elegir una impresora de tickets: tipo, ancho de papel, conexión y compatibilidad con tu programa, y cómo probarla antes de comprar para no equivocarte.",
    h1="Cómo elegir una impresora de tickets para tu negocio",
    lead="Una impresora de tickets que no encaja con tu programa o con tu mostrador da más problemas que ventajas. Estas son las cosas que conviene mirar antes de comprarla y cómo probarla.",
    group="Cobrar y cuadrar la caja",
    summary="Tipo, ancho de papel, conexión y compatibilidad: qué comprobar antes de comprar una impresora de tickets.",
    icon="i-receipt",
    demo="tienda",
    sectors=["tiendas", "restaurantes"],
    related=["que-es-un-tpv", "devoluciones-y-cambios-en-una-tienda"],
    published="2026-10-22",
    subject="Consulta desde la guía de impresoras de tickets",
    sections=[
        ("que-imprimir", "Antes de elegir: qué vas a imprimir", """
<p>Piensa primero en lo que necesitas sacar en papel:</p>
<ul>
<li><strong>El ticket de venta,</strong> estrecho y rápido, que se entrega al cobrar.</li>
<li><strong>La comanda de cocina,</strong> en bares y restaurantes que no usan pantalla.</li>
<li><strong>La factura,</strong> que suele imprimirse en un folio A4 o guardarse en PDF, y para la que no hace falta una impresora de tickets.</li>
<li><strong>Las etiquetas de precio,</strong> que necesitan otro tipo de impresora distinto.</li>
</ul>
<p>Esta guía trata de las dos primeras: las impresoras de tickets, también llamadas de recibos.</p>
"""),
        ("tipos", "Tipos de impresora de tickets", """
<div class="tablewrap" role="region" aria-label="Tipos de impresora de tickets" tabindex="0">
<table>
<thead><tr><th scope="col">Tipo</th><th scope="col">Cómo imprime</th><th scope="col">Suele encajar</th><th scope="col">Ten en cuenta</th></tr></thead>
<tbody>
<tr><th scope="row">Térmica de sobremesa</th><td>Calienta un papel especial: no usa tinta ni cinta.</td><td>Mostradores y barras. Es la más habitual.</td><td>El papel térmico se desvanece con el calor, la luz y el tiempo.</td></tr>
<tr><th scope="row">De impacto (matricial)</th><td>Golpea una cinta contra el papel, que puede ser papel normal.</td><td>Cocinas, por aguantar mejor el calor, la humedad y la grasa.</td><td>Es más ruidosa y más lenta.</td></tr>
<tr><th scope="row">Térmica portátil</th><td>Pequeña y con batería, a menudo de 58 mm.</td><td>Cobrar en la mesa, en un puesto o en la calle.</td><td>Hay que cargarla, y la conexión sin cables varía según el modelo.</td></tr>
</tbody>
</table>
</div>
"""),
        ("ancho", "Ancho del papel: 58 mm o 80 mm", """
<p>Los rollos de ticket se venden sobre todo en dos anchos:</p>
<ul>
<li><strong>58 mm:</strong> impresoras pequeñas, buenas para mostradores con poco espacio, tickets cortos o para llevar encima. Entra menos texto en cada línea.</li>
<li><strong>80 mm:</strong> más espacio para nombres de producto largos, el desglose del IVA, códigos QR y más información. Es muy habitual en bares y comercios.</li>
</ul>
<p>Si tus productos tienen nombres largos o imprimes mucha información en el ticket, el de 80 mm te dará menos problemas; si cobras en movimiento, el de 58 mm es más cómodo.</p>
"""),
        ("conexion", "Cómo se conecta: USB, red o Bluetooth", """
<div class="tablewrap" role="region" aria-label="Formas de conectar una impresora de tickets" tabindex="0">
<table>
<thead><tr><th scope="col">Conexión</th><th scope="col">Suele ir bien para</th><th scope="col">Ten en cuenta</th></tr></thead>
<tbody>
<tr><th scope="row">USB</th><td>Un puesto fijo con un ordenador al lado.</td><td>Sirve para un equipo a la vez, y que funcione desde el navegador depende del sistema y del modelo.</td></tr>
<tr><th scope="row">Red (cable o wifi)</th><td>Varios dispositivos que imprimen en la misma impresora, como en una barra o una cocina.</td><td>Hay que configurar la red, y depende de cómo imprima tu programa.</td></tr>
<tr><th scope="row">Bluetooth</th><td>Cobrar con el móvil o la tableta, sin cables.</td><td>La compatibilidad varía mucho según el modelo, el sistema del móvil y el navegador.</td></tr>
</tbody>
</table>
</div>
<p>Lo importante: <strong>que una impresora funcione con un ordenador no significa que funcione igual desde el navegador de un móvil.</strong> Pregunta al fabricante y a tu proveedor del programa, y pruébala antes de comprar.</p>
"""),
        ("compatibilidad", "Compatibilidad: que hable el mismo idioma que tu programa", """
<p>La mayoría de las impresoras térmicas de tickets entienden un conjunto de órdenes llamado <strong>ESC/POS</strong>, que funciona como un estándar de hecho. Si tu programa imprime con esas órdenes, muchos modelos servirán; si imprime de otra manera, por ejemplo a través del diálogo de impresión del sistema, hace falta que la impresora tenga un controlador para tu dispositivo.</p>
<p>La pregunta correcta no es «¿es buena esta impresora?», sino <strong>«¿funciona con mi programa, con mi dispositivo y con mi navegador?»</strong>.</p>
"""),
        ("lista", "Lista de comprobación antes de comprar", """
<ol>
<li>¿Funciona con mi móvil, mi tablet o mi ordenador, y con mi navegador?</li>
<li>¿Lo confirma el proveedor de mi programa, o puedo probarla antes de decidir?</li>
<li>¿Qué ancho de papel necesito, 58 u 80 mm?</li>
<li>¿Tiene corte automático? Si cobras mucho, ahorra tiempo.</li>
<li>¿Necesito abrir un cajón portamonedas? Muchos modelos tienen una salida para que el cajón se abra al imprimir; comprueba que es la que usa tu cajón.</li>
<li>¿Dónde compro los rollos de repuesto y cuánto cuestan? Es un gasto que se repite.</li>
<li>¿Qué garantía tiene y quién la repara si falla?</li>
<li>¿Cabe en mi mostrador y hace ruido?</li>
</ol>
"""),
        ("papel", "Cuidar el papel y guardar copias", """
<p>El papel térmico se desvanece con el calor, la luz directa y el paso del tiempo: un ticket guardado al sol puede quedar en blanco al cabo de unos meses. Si necesitas conservar un comprobante, guarda también una copia digital, y almacena los rollos en un sitio fresco y seco. Para las facturas, lo más práctico es guardarlas en PDF.</p>
<p>Y si no quieres imprimirlo todo, es una decisión de tu negocio y de lo que esperan tus clientes: antes de dejar de dar el ticket en papel, confirma con tu gestoría qué comprobantes tienes que entregar y conservar.</p>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Imprime tickets desde el navegador.</strong></li>
<li><strong>Facturas</strong> con los datos fiscales del cliente, que puedes imprimir o guardar en PDF.</li>
<li><strong>Impresoras térmicas y lectores de códigos:</strong> la conexión directa depende del modelo y del navegador, y la probamos contigo antes de que te decidas.</li>
<li><strong>Lector de códigos de barras:</strong> el buscador del TPV acepta el código que escribe el lector y añade el producto al ticket; también puedes escanear con la cámara del móvil.</li>
</ul>
<p>Si ya tienes una impresora o estás a punto de comprarla, escríbenos el modelo y lo vemos antes de que gastes dinero.</p>
""",
    shot=("vender-c", "Pantalla de venta de NirKanA con los productos a la izquierda y el ticket a la derecha", "La pantalla de venta con el ticket abierto"),
    faq=[
        ("¿Qué ancho de papel necesito, 58 u 80 mm?",
         "El de 58 mm es más compacto y vale para tickets cortos o para cobrar en movimiento; el de 80 mm da más espacio para nombres largos, el desglose del IVA y el código QR. Si tienes sitio en el mostrador y dudas, el de 80 mm te da más margen."),
        ("¿Vale cualquier impresora o tiene que ser de tickets?",
         "Para tickets conviene una impresora térmica de tickets, no una de oficina: es más rápida, no usa tinta y está pensada para rollos estrechos. Antes de comprarla, comprueba que funciona con tu programa, tu dispositivo y tu navegador. Con NirKanA lo probamos contigo antes de que te decidas."),
        ("¿Puedo usar una impresora Bluetooth con el móvil?",
         "A veces. Depende del modelo de la impresora, del sistema del móvil y del navegador: hay combinaciones que funcionan y otras que no. Por eso conviene probarla antes de comprarla, o comprarla con posibilidad de devolución."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- entrada de TikTok
# /tiktok/: la página a la que lleva el enlace de la biografía. No se indexa ni sale en el mapa del sitio, y nada de la web enlaza a
# ella; GoatCounter cuenta sus visitas por la ruta y sus botones por los eventos tiktok-prueba, tiktok-demo y tiktok-correo.
TIKTOK = dict(
    title="Bienvenido desde TikTok · NirKanA",
    description="Prueba NirKanA 24 horas gratis, sin tarjeta, o escríbenos por correo. Con calculadoras gratis y guías para llevar tu negocio.",
    eyebrow="Si vienes de TikTok",
    h1="Lleva tu negocio desde el móvil, sin papeles ni Excel",
    lead="NirKanA es el programa para cobrar, cuadrar la caja, controlar el stock y organizar las citas de tu negocio. Ábrelo 24 horas gratis, sin tarjeta y con un negocio de ejemplo, y míralo como lo vería tu equipo.",
    demo="tienda",
    subject="Vengo de TikTok",
    shot=("vender-c", "Pantalla de venta de NirKanA con el ticket abierto", "vender"),
    free_title="También gratis: calculadoras y guías",
    free_lead="Sin registro y sin dar ningún dato. Las calculadoras hacen las cuentas en tu propio navegador.",
    guides=("Guías para llevar mejor tu negocio", "Cobrar, cuadrar la caja, pasar comandas, controlar el stock, gestionar devoluciones, organizar citas y tener las facturas en orden.", "i-list"),
    sectors_title="Cómo se usa en tu tipo de negocio",
    sectors=[
        ("peluquerias", "i-calendar", "Reserva online desde tu enlace, agenda por persona y cobro con un toque."),
        ("restaurantes", "i-utensils", "Mesas, comandas desde el móvil, pantalla de cocina y cierre de caja."),
        ("tiendas", "i-bag", "Venta rápida, stock que se mueve solo y reposición."),
        ("autonomos", "i-briefcase", "Citas, facturas y el paquete del trimestre para tu gestoría."),
        ("online", "i-cloud", "Catálogo, stock y márgenes de la web y del local en un solo sitio."),
        ("pymes", "i-users", "Todo el equipo con los mismos datos, cada persona con su acceso."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- índice
# ---------------------------------------------------------------------------------------------------------------- 12
guide(
    slug="organizar-clientes-entrenador-personal",
    title="Cómo organizar a tus clientes como entrenador personal · NirKanA",
    description="Cómo llevar a tus clientes como entrenador personal: la ficha de cada uno, planes que puedas reutilizar, el seguimiento, las cuotas y los bonos, y una rutina semanal.",
    h1="Cómo organizar a tus clientes como entrenador personal: ficha, planes, seguimiento y cobros",
    lead="Con cinco clientes basta con una libreta y el WhatsApp. Con veinte, se te olvida quién tiene el bono a punto de acabar, qué carga movía cada uno o a quién le toca revisar el plan. Esta guía te propone una forma de organizarlo que se sostiene semana a semana.",
    group="Citas y clientes",
    summary="La ficha de cada cliente, planes reutilizables, el seguimiento, cuotas y bonos, y una rutina semanal para no perder el hilo.",
    icon="i-users",
    demo="servicios",
    sectors=["entrenadores", "autonomos"],
    related=["agenda-de-citas-para-peluquerias", "documentos-del-trimestre-para-la-gestoria"],
    published="2026-10-30",
    subject="Consulta desde la guía para entrenadores personales",
    disclaimer="Esta guía es informativa. Lo que afecta a datos de salud, contratos o impuestos te lo confirma tu asesor o tu gestoría, y las dietas personalizadas son cosa de un dietista-nutricionista.",
    sections=[
        ("ficha", "1. Una ficha por cliente, con lo que de verdad usas", """
<p>Antes del primer entrenamiento, apunta en un solo sitio lo que vas a necesitar después. No hace falta más:</p>
<ul>
<li><strong>Contacto:</strong> nombre, teléfono y correo.</li>
<li><strong>Objetivo,</strong> en sus palabras: «correr 10 km en primavera», «quitarme el dolor de espalda», «ganar fuerza».</li>
<li><strong>Nivel</strong> (principiante, intermedio, avanzado) y desde cuándo entrena contigo.</li>
<li><strong>Lesiones y limitaciones:</strong> lo que no debe hacer o lo que hay que vigilar.</li>
<li><strong>Cómo te paga:</strong> cuota mensual, bono o sesión suelta.</li>
</ul>
<p>El peso, las medidas, las fotos de progreso o lo que come son <strong>datos de salud</strong>. Pide permiso a tu cliente antes de guardarlos, explícale para qué los usas y apúntate que te lo ha dado. Si un día lo retira, bórralos.</p>
"""),
        ("planes", "2. Planes que puedas reutilizar", """
<p>Escribir cada plan desde cero te come las tardes. Mejor ten unas pocas <strong>plantillas</strong> y ajústalas a cada cliente:</p>
<ul>
<li>Una por objetivo y nivel: por ejemplo, «Fuerza, principiante, 3 días» o «Cuerpo completo, 2 días».</li>
<li>Cada día con sus ejercicios y, en cada uno, <strong>series, repeticiones, carga y descanso,</strong> y una nota corta si hace falta («rodillas hacia fuera», «sin dolor»).</li>
<li>Una biblioteca de ejercicios con <strong>cómo se hace</strong> cada uno, y un vídeo si lo tienes: la explicación la escribes una vez y sirve para todos.</li>
</ul>
<p>Al copiar una plantilla a un cliente, cambia lo que no le va: un ejercicio por su lesión, otra carga, un día menos. Guarda los planes anteriores en lugar de borrarlos: te sirven para ver cómo ha avanzado.</p>
"""),
        ("seguimiento", "3. Seguimiento sin agobiar", """
<p>Medir sirve para ajustar el plan y para que tu cliente vea que avanza, pero si le pides demasiado lo deja. Unas reglas sencillas:</p>
<ul>
<li><strong>Peso:</strong> siempre en las mismas condiciones, por ejemplo al levantarse y antes de desayunar, y mira la tendencia de varias semanas, no el número de un día.</li>
<li><strong>Medidas</strong> (cintura, cadera, brazo…): cada pocas semanas, con la misma cinta y en el mismo punto.</li>
<li><strong>Fotos de progreso:</strong> misma luz, misma postura y mismo sitio.</li>
<li><strong>Cada sesión:</strong> qué hizo, con qué carga, cuántas repeticiones y cómo de dura le pareció, del 1 al 10. Con eso sabes cuándo subir la carga y cuándo no.</li>
</ul>
<p>Si tu cliente entrena también por su cuenta, que lo apunte él: así no dependes de que te lo cuente.</p>
"""),
        ("cobros", "4. Cuotas, bonos y sesiones sueltas, cada cosa clara", """
<div class="tablewrap compact" role="region" aria-label="Formas de cobrar a un cliente de entrenamiento" tabindex="0">
<table>
<thead><tr><th scope="col">Forma</th><th scope="col">Cómo funciona</th><th scope="col">Qué vigilar</th></tr></thead>
<tbody>
<tr><th scope="row">Cuota mensual</th><td>Un importe fijo cada mes, con un día de cobro.</td><td>Quién no ha pagado pasado ese día.</td></tr>
<tr><th scope="row">Bono de sesiones</th><td>Paga por adelantado, por ejemplo 10 sesiones.</td><td>Cuántas le quedan y avisar antes de que se acabe.</td></tr>
<tr><th scope="row">Sesión suelta</th><td>Paga cada sesión.</td><td>Que no se quede ninguna sin cobrar.</td></tr>
</tbody>
</table>
</div>
<p>Apunta cada cobro el mismo día, con la forma de pago (efectivo, Bizum, transferencia…). Para recordar un pago pendiente, un mensaje corto y amable funciona mejor que una conversación: «Hola, Ana: te recuerdo la cuota de octubre, 90 €. Cuando te venga bien. ¡Gracias!».</p>
"""),
        ("rutina", "5. Una rutina semanal que se sostiene", """
<ul>
<li><strong>Cada día:</strong> mira las sesiones de hoy y, al terminar, marca quién vino y apunta lo que hizo.</li>
<li><strong>Una vez por semana:</strong> repasa los cobros pendientes, los bonos que se acaban y quién no ha entrenado; manda los recordatorios en un solo rato.</li>
<li><strong>Cada pocas semanas,</strong> por cliente: revisa sus medidas y su plan, y cámbialo si se ha estancado o ha cambiado su objetivo.</li>
<li><strong>Cada trimestre:</strong> junta tus cobros y tus gastos (material, sala, formación, seguro) para tu gestoría; en la <a href="/guias/documentos-del-trimestre-para-la-gestoria/">guía de documentos del trimestre</a> tienes la lista.</li>
</ul>
<p>Lo importante no es la herramienta, sino que todo esté en el mismo sitio y que lo mires siempre en el mismo momento.</p>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Ficha de cada cliente</strong> con su plan, su seguimiento (peso con gráfica, medidas y fotos), su alimentación y sus cobros.</li>
<li><strong>Planes por días</strong> a partir de tus plantillas, con una biblioteca de ejercicios que puedes empezar con 40 básicos y 3 plantillas.</li>
<li><strong>Cuotas, bonos y sesiones sueltas:</strong> lo pendiente sale solo, con el recordatorio por WhatsApp ya escrito.</li>
<li><strong>La app de tu cliente:</strong> ve su plan en el móvil y apunta cada sesión, su peso y sus medidas.</li>
</ul>
<p>Los datos de salud solo se guardan con el permiso del cliente, y la app no hace dietas. Tienes todo lo que incluye en la <a href="/programa-entrenadores-personales/">página para entrenadores personales</a>.</p>
""",
    shot=("entreno-plan-c", "Plan de entrenamiento por días en NirKanA: cada ejercicio con series, repeticiones y descanso", "El plan de un cliente, día a día (datos de ejemplo)"),
    faq=[
        ("¿Cada cuánto conviene medir a un cliente?",
         "El peso, si quiere, cada semana y siempre en las mismas condiciones. Las medidas y las fotos, cada pocas semanas. Lo que cuenta es la tendencia, no el dato de un día."),
        ("¿Qué es mejor, cuota mensual o bono de sesiones?",
         "Depende de tus clientes. La cuota da ingresos estables y encaja con quien entrena todas las semanas; el bono encaja con quien viene de forma irregular. Muchos entrenadores ofrecen las dos y la sesión suelta."),
        ("¿Puedo pasarle una dieta a mi cliente?",
         "Las dietas personalizadas son cosa de un dietista-nutricionista. Como entrenador, lo prudente es dar pautas generales o trabajar con uno y pasarle a tu cliente el plan que haga ese profesional."),
        ("¿Necesito permiso para guardar el peso y las fotos de mis clientes?",
         "Son datos de salud: pide el permiso de tu cliente antes de guardarlos, explícale para qué los usas y bórralos si lo retira. Tu asesor te confirma el texto que conviene usar."),
    ],
)

HUB = dict(
    title="Guías para llevar tu negocio: caja, stock, citas y facturas · NirKanA",
    description="Guías prácticas para autónomos y pequeños negocios: TPV, caja, comandas, stock, devoluciones, impresoras de tickets, citas, facturas y el trimestre con tu gestoría.",
    h1="Guías para llevar mejor tu negocio",
    lead="Explicaciones claras, con ejemplos y listas de comprobación, sobre lo que más tiempo quita a un negocio pequeño: cobrar, cuadrar la caja, pasar comandas, controlar el stock, gestionar devoluciones, organizar citas y tener las facturas en orden.",
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

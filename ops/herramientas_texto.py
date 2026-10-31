"""Textos de las herramientas gratuitas de la web (docs/herramientas/). Los convierte en páginas `ops/guias.py`; las cuentas las hace
docs/assets/herramientas.js en el navegador de quien la usa (no se envía ni se guarda nada).

Mismas reglas que las guías (las comprueban `tests/web-claims.test.mjs` y `tests/web-herramientas.test.mjs`): explican cómo hacer
algo bien con ejemplos inventados, sobre NirKanA solo dicen lo que ya dicen la portada y los sectores, y las respuestas de las
preguntas frecuentes son texto sin enlaces (son también los datos estructurados).
"""

TOOLS = {}


def tool(**data):
    TOOLS[data["slug"]] = data


HUB = dict(
    title="Herramientas gratis para tu negocio: IVA, caja y margen · NirKanA",
    description="Herramientas gratuitas para negocios: calculadora de IVA para añadirlo o quitarlo, arqueo de caja en euros con plantilla de Excel, y margen y precio de venta.",
    h1="Herramientas gratis para tu negocio",
    lead="Calculadoras sencillas para las cuentas que haces a menudo: el IVA de un precio, cuadrar la caja y fijar precios. Gratis, sin registro y sin que tus datos salgan del navegador.",
    demo="tienda",
    faq=[
        ("¿Las herramientas son gratis de verdad?",
         "Sí. No piden registro, ni correo, ni tarjeta, y no tienen versión de pago. Están para que hagas tus cuentas y, si te gusta cómo trabajamos, pruebes NirKanA."),
        ("¿Guardáis lo que escribo en las calculadoras?",
         "No. Las cuentas se hacen en tu navegador: no se envía ni se guarda nada. Si cierras la página, se borra lo que habías escrito."),
        ("¿Funcionan en el móvil?",
         "Sí. Se adaptan a la pantalla del móvil y de la tableta, y los campos abren el teclado numérico."),
        ("¿Sustituyen a un programa de gestión?",
         "No: te ayudan a hacer una cuenta concreta. Un programa como NirKanA, además, guarda las ventas, el stock y los cierres de caja, y hace estas cuentas por ti."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 0
tool(
    slug="calculadora-de-iva",
    title="Calculadora de IVA: añadir o quitar el IVA de un precio · NirKanA",
    description="Calcula gratis el IVA de un precio: añade el 21 %, el 10 % o el 4 % a la base, o quítalo de un precio con IVA incluido sin el error de restar el porcentaje.",
    h1="Calculadora de IVA: añadir o quitar el IVA",
    lead="Pon un precio sin IVA y te damos el IVA y el total. O al revés: pon un precio con el IVA incluido y te damos la base y el IVA que lleva dentro, con el 21 %, el 10 % o el 4 %.",
    summary="Añade el IVA a un precio sin IVA o quítalo de un precio con IVA incluido, con el 21 %, el 10 % o el 4 %.",
    icon="i-receipt",
    demo="servicios",
    widget="iva",
    sectors=["autonomos", "tiendas"],
    related=["que-debe-llevar-una-factura", "calcular-el-margen-de-un-producto"],
    subject="Consulta desde la calculadora de IVA",
    app_name="Calculadora de IVA",
    sections=[
        ("formulas", "Las fórmulas, por si quieres hacerlo a mano", """
<ul>
<li><strong>Añadir el IVA: total = base × (1 + tipo).</strong> Con una base de 100 € y un 21 %: 100 × 1,21 = 121 €.</li>
<li><strong>IVA de una base: IVA = base × tipo.</strong> 100 × 0,21 = 21 €.</li>
<li><strong>Quitar el IVA: base = total ÷ (1 + tipo).</strong> Con 121 € y un 21 %: 121 ÷ 1,21 = 100 €.</li>
<li><strong>IVA que lleva dentro un precio: IVA = total − base.</strong> 121 − 100 = 21 €.</li>
</ul>
<p>Con el 10 %, el número es 1,10; con el 4 %, 1,04. Los importes se redondean al céntimo.</p>
"""),
        ("error", "El error más común: restar el porcentaje", """
<p>Para quitar el IVA no se resta el 21 % del precio: se divide entre 1,21. Si a 121 € le restas el 21 % te salen 95,59 €, y la base real es 100 €. La diferencia parece pequeña, pero en una factura o en el resumen de un trimestre se nota. La calculadora te avisa cuando las dos cuentas no coinciden.</p>
<div class="tablewrap compact" role="region" aria-label="Restar el porcentaje frente a dividir" tabindex="0">
<table>
<caption>Quitar el IVA del 21 % de un precio con IVA incluido</caption>
<thead><tr><th scope="col">Precio con IVA</th><th scope="col">Restando el 21 % (mal)</th><th scope="col">Dividiendo entre 1,21 (bien)</th></tr></thead>
<tbody>
<tr><td>12,10 €</td><td>9,56 €</td><td>10,00 €</td></tr>
<tr><td>121,00 €</td><td>95,59 €</td><td>100,00 €</td></tr>
<tr><td>1.210,00 €</td><td>955,90 €</td><td>1.000,00 €</td></tr>
</tbody>
</table>
</div>
"""),
        ("tipos", "Qué tipo de IVA usar", """
<p>En la Península y Baleares los tipos más habituales son el <strong>21 % general,</strong> el <strong>10 % reducido</strong> y el <strong>4 % superreducido</strong>. Cuál corresponde depende de lo que vendas o del servicio que prestes, y hay operaciones exentas o que no llevan IVA. Si dudas, tu gestoría te confirma el tipo de tu actividad. En Canarias, Ceuta y Melilla no se aplica el IVA, sino otros impuestos (IGIC e IPSI).</p>
"""),
        ("factura", "En una factura, cada cosa en su sitio", """
<p>En una factura completa la base, el tipo y la cuota de IVA van por separado, y si hay varios tipos, desglosados por tipo. Calcula el IVA sobre la base de cada línea o de cada tipo, no sobre el total. Tienes la lista completa de lo que debe llevar en la <a href="/guias/que-debe-llevar-una-factura/">guía de qué debe llevar una factura</a>, y si lo que quieres es fijar el precio de un producto a partir de su coste, usa la <a href="/herramientas/calculadora-de-margen/">calculadora de margen</a>.</p>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Facturas con tus datos y los del cliente:</strong> con tu NIF y el del cliente, IVA por tipo y numeración propia por serie y año.</li>
<li><strong>Para tu gestoría:</strong> ventas, facturas, gastos y compras en Excel por periodo, el resumen de IVA del trimestre y un ZIP del trimestre con todo junto.</li>
</ul>
<p>Así no tienes que hacer estas cuentas a mano en cada venta.</p>
""",
    shot=("factura-c", "Factura de ejemplo de NirKanA con la base, el IVA por tipo y el total", "Una factura de ejemplo con la base, el IVA y el total"),
    faq=[
        ("¿Cómo se quita el IVA de un precio?",
         "Dividiendo el precio entre 1 más el tipo de IVA. Con un 21 %, divide entre 1,21: 121 euros son 100 euros de base y 21 euros de IVA. Con un 10 %, divide entre 1,10, y con un 4 %, entre 1,04."),
        ("¿Cómo se calcula el IVA del 21 %?",
         "Multiplica la base, el precio sin IVA, por 0,21 para saber el IVA, o por 1,21 para saber el total. Con una base de 100 euros, el IVA es de 21 euros y el total, de 121 euros."),
        ("¿Por qué no vale restar el 21 % para quitar el IVA?",
         "Porque el 21 % se calculó sobre la base, no sobre el total. Si a 121 euros le restas el 21 %, te salen 95,59 euros, pero la base es 100 euros. Para quitar el IVA hay que dividir entre 1,21."),
        ("¿Qué tipos de IVA hay en España?",
         "Los más habituales son el 21 % general, el 10 % reducido y el 4 % superreducido, y algunas operaciones están exentas. El tipo depende de lo que vendas; tu gestoría te confirma el de tu actividad. En Canarias, Ceuta y Melilla se aplican otros impuestos."),
        ("¿El IVA se calcula sobre el total o sobre la base?",
         "Sobre la base: el precio sin IVA, después de los descuentos. En una factura con varios tipos, el IVA se calcula y se muestra por separado para cada tipo."),
        ("¿Se guarda lo que escribo?",
         "No. Los cálculos se hacen en tu navegador: no se envía ni se guarda nada."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 1
tool(
    slug="calculadora-de-arqueo-de-caja",
    updated="2026-10-30",
    title="Contar caja online gratis: billetes y monedas · NirKanA",
    description="Cuenta tu caja online gratis y sin registro. Suma billetes y monedas en euros, comprueba el descuadre y guarda el resultado en PDF. Incluye plantilla de Excel.",
    h1="Contar caja online: calculadora de arqueo gratis",
    lead="Para contar tu caja online, introduce cuántos billetes y monedas tienes de cada tipo. La calculadora suma el efectivo y lo compara con el fondo, las ventas y las salidas que indiques. Gratis y sin registro.",
    summary="Cuenta billetes y monedas en euros, compáralo con lo esperado y ve el descuadre al momento. Con plantilla de Excel.",
    icon="i-receipt",
    demo="hosteleria",
    widget="arqueo",
    sectors=["restaurantes", "tiendas"],
    related=["arqueo-y-cierre-de-caja", "que-es-un-tpv"],
    subject="Consulta desde la calculadora de arqueo de caja",
    app_name="Calculadora de arqueo de caja",
    sections=[
        ("como-se-usa", "Cómo contar la caja online paso a paso", """
<ol>
<li><strong>Cuenta el efectivo antes de mirar cuánto debería haber.</strong> Escribe cuántos billetes y monedas hay de cada tipo; lo que dejes en blanco cuenta como cero.</li>
<li><strong>Apunta lo que debería haber:</strong> el fondo con el que empezaste, las ventas cobradas en efectivo, otras entradas (por ejemplo, un cambio que te traen) y las salidas (pagos a proveedores, retiradas, devoluciones en efectivo).</li>
<li><strong>Mira el resultado.</strong> La calculadora resta lo esperado de lo contado: si es cero, la caja cuadra; si es positivo, sobra dinero; si es negativo, falta.</li>
<li><strong>Si quieres, indica el fondo que dejas para mañana</strong> y te dice cuánto tienes que retirar del cajón.</li>
</ol>
<p>La cuenta es sencilla: <em>efectivo esperado = fondo inicial + ventas en efectivo + otras entradas − salidas</em>, y <em>diferencia = contado − esperado</em>.</p>
"""),
        ("ejemplo-recuento", "Ejemplo de recuento de billetes y monedas", """
<p>Ejemplo inventado: cuentas 4 billetes de 20 €, 2 de 10 €, 3 de 5 €, 6 monedas de 2 € y 8 de 1 €. El efectivo contado suma <strong>135 €</strong>.</p>
<p>Si empezaste con 50 €, cobraste 100 € en efectivo y retiraste 10 €, deberían quedar <strong>140 €</strong>. La diferencia es 135 − 140 = <strong>−5 €</strong>: faltan 5 €. El ejemplo sirve para comprobar las cuentas; no identifica la causa del descuadre.</p>
<p>Introduce las cantidades en la calculadora de arriba para reproducirlo. Para conservar el resultado, usa «Imprimir o guardar en PDF» y elige guardar como PDF en el diálogo del navegador.</p>
"""),
        ("no-cuadra", "Qué hacer si no cuadra", """
<ul>
<li><strong>Vuelve a contar,</strong> empezando por los billetes de más valor: es el fallo más habitual.</li>
<li><strong>Comprueba las salidas:</strong> pagos a proveedores, retiradas de dinero, propinas repartidas o cambios que diste.</li>
<li><strong>Mira si la diferencia es igual a un billete o a una moneda:</strong> suele indicar un cambio mal dado.</li>
<li><strong>Repasa las devoluciones y las anulaciones</strong> del día.</li>
<li><strong>Apunta la diferencia y quién cerró,</strong> aunque no encuentres la causa. En la <a href="/guias/arqueo-y-cierre-de-caja/">guía de arqueo y cierre de caja</a> tienes el método completo.</li>
</ul>
"""),
        ("tarjeta", "¿Y las ventas con tarjeta y Bizum?", """
<p>No están en el cajón, así que no entran en esta cuenta. Se comprueban aparte: el total de tarjeta que registra tu programa de ventas contra el cierre del datáfono, y el de Bizum contra los movimientos de tu cuenta.</p>
"""),
        ("plantilla", "Plantilla de Excel del arqueo de caja", """
<p>Si prefieres una hoja de cálculo, descarga la plantilla: tiene las mismas cuentas que esta calculadora (efectivo contado por denominaciones, efectivo esperado, diferencia y efectivo a retirar), casillas para la fecha y para quien cuenta, y cabe en una página A4 para imprimirla y firmarla. Es un archivo de Excel normal, sin macros, y también se abre con LibreOffice o con Google Sheets.</p>
<p><a class="btn ghost" href="/descargas/plantilla-arqueo-de-caja.xlsx" download data-evento="plantilla-arqueo" data-evento-titulo="Descarga la plantilla de arqueo de caja"><svg class="ic"><use href="#i-download"/></svg> Descargar la plantilla (Excel)</a></p>
"""),
    ],
    nirkana="""
<p>En NirKanA el arqueo viene hecho en la propia pantalla de caja:</p>
<ul>
<li>Abres la caja con su fondo inicial y la ves abierta mientras cobras.</li>
<li>Al cerrar, cuentas el efectivo (con ayuda para contar billetes y monedas) sin ver lo esperado.</li>
<li>El descuadre aparece al momento y queda registrado quién cerró.</li>
<li>Los cierres de caja entran en el ZIP del trimestre que puedes darle a tu gestoría.</li>
</ul>
""",
    shot=("caja-c", "Pantalla Caja de NirKanA con la caja abierta, el efectivo esperado y el apartado para cerrar contando billetes y monedas", "La pantalla de Caja: resumen del día y cierre contando el efectivo"),
    faq=[
        ("¿Qué es el arqueo de caja?",
         "Es contar el dinero real que hay en la caja (billetes y monedas) y compararlo con el que debería haber según las ventas y los movimientos apuntados."),
        ("¿Cada cuánto hay que hacer el arqueo?",
         "Como mínimo al cerrar el día. Si varias personas cobran, hazlo también en cada cambio de turno: así sabes quién tenía la caja cuando apareció una diferencia."),
        ("¿Se guarda lo que escribo en la calculadora?",
         "No. Las cuentas se hacen en tu navegador: no se envía ni se guarda nada, y si cierras la página se borra. Para conservar el resultado, imprímelo o guárdalo en PDF con el botón de imprimir."),
        ("¿Qué hago con el dinero de la tarjeta y de Bizum?",
         "No está en el cajón, así que no se cuenta aquí. Compara el total de tarjeta de tu programa con el cierre del datáfono y el de Bizum con los movimientos de tu cuenta."),
        ("¿Cuánto fondo de caja conviene dejar?",
         "Lo suficiente para dar cambio durante el día sin tener que salir a cambiar. Mucha gente deja la misma cantidad cada día, porque así el arqueo es más fácil de comparar."),
        ("¿Sirve para cualquier negocio?",
         "Sí: bares, tiendas, peluquerías o cualquier negocio que cobre en efectivo. La calculadora usa los billetes y las monedas del euro."),
    ],
)

# ---------------------------------------------------------------------------------------------------------------- 2
tool(
    slug="calculadora-de-margen",
    title="Calculadora de margen, recargo y precio de venta con IVA · NirKanA",
    description="Calcula el precio de venta con IVA a partir del coste y del margen que quieres, o el margen de un precio que ya tienes. Con el recargo y lo que cuesta un descuento.",
    h1="Calculadora de margen y precio de venta",
    lead="Pon lo que te cuesta un producto y el margen que quieres ganar, y te da el precio con IVA. O al revés: pon el precio al que vendes y mira el margen que te deja, con el recargo y el efecto de un descuento.",
    summary="Del coste y el margen al precio con IVA, o del precio al margen, con el recargo y lo que cuesta un descuento.",
    icon="i-chart",
    demo="tienda",
    widget="margen",
    sectors=["tiendas", "online"],
    related=["calcular-el-margen-de-un-producto", "control-de-stock-en-una-tienda"],
    subject="Consulta desde la calculadora de margen",
    app_name="Calculadora de margen y precio de venta",
    sections=[
        ("formulas", "Las fórmulas, por si quieres hacerlo a mano", """
<ul>
<li><strong>Precio sin IVA = coste ÷ (1 − margen).</strong> Con un coste de 10 € y un margen del 40 %: 10 ÷ 0,60 = 16,67 €.</li>
<li><strong>Precio con IVA = precio sin IVA × (1 + IVA).</strong> Con un 21 %: 16,67 × 1,21 = 20,17 €.</li>
<li><strong>Margen = (precio sin IVA − coste) ÷ precio sin IVA.</strong> Es la parte del precio que te queda.</li>
<li><strong>Recargo = (precio sin IVA − coste) ÷ coste.</strong> Es lo que añades sobre el coste.</li>
</ul>
"""),
        ("margen-recargo", "Margen y recargo no son lo mismo", """
<div class="tablewrap compact" role="region" aria-label="Margen frente a recargo" tabindex="0">
<table>
<caption>El mismo producto, con un coste de 10 € sin IVA</caption>
<thead><tr><th scope="col">Precio sin IVA</th><th scope="col">Beneficio</th><th scope="col">Margen</th><th scope="col">Recargo</th></tr></thead>
<tbody>
<tr><td>12,00 €</td><td>2,00 €</td><td>16,7 %</td><td>20 %</td></tr>
<tr><td>14,00 €</td><td>4,00 €</td><td>28,6 %</td><td>40 %</td></tr>
<tr><td>16,67 €</td><td>6,67 €</td><td>40,0 %</td><td>66,7 %</td></tr>
<tr><td>20,00 €</td><td>10,00 €</td><td>50,0 %</td><td>100 %</td></tr>
</tbody>
</table>
</div>
<p>El recargo siempre sale mayor que el margen. Si sumas un 40 % al coste, tu margen real es del 28,6 %, no del 40 %. Por eso conviene decidir con el margen, que es lo que te queda de cada venta.</p>
"""),
        ("iva", "El IVA no es ganancia", """
<p>El IVA que cobras al cliente lo ingresas después: no forma parte de tu margen. Por eso el margen se calcula con el precio sin IVA, y si tu precio de venta ya lleva IVA hay que quitárselo antes de calcular. Los tipos más habituales son el 21 % general, el 10 % reducido y el 4 % superreducido; usa el que corresponde a tu producto y consúltalo con tu gestoría si dudas (en Canarias, Ceuta y Melilla los impuestos son otros).</p>
"""),
        ("descuento", "Lo que cuesta un descuento", """
<p>Un descuento se aplica sobre el precio, pero te quita beneficio. Con un coste de 10 € y un precio de 16,67 € sin IVA (margen del 40 %), un 20 % de descuento deja el precio en 13,33 €, el beneficio en 3,33 € y el margen en el 25 %: ganas la mitad por unidad, así que tendrías que vender el doble para ganar lo mismo. La calculadora lo hace con el descuento que escribas.</p>
"""),
    ],
    nirkana="""
<ul>
<li><strong>Cada producto muestra su margen,</strong> y el coste se actualiza solo al recibir pedidos.</li>
<li><strong>Resultados:</strong> ventas, coste de lo vendido, margen y gastos de cualquier periodo, con el beneficio neto.</li>
</ul>
<p>Para que el margen salga exacto, cada producto tiene que tener su coste: se lo pones tú o se actualiza al recibir pedidos de proveedores. Tienes el método completo en la <a href="/guias/calcular-el-margen-de-un-producto/">guía para calcular el margen de un producto</a>.</p>
""",
    shot=("resultados-c", "Pantalla Resultados de NirKanA con las ventas, el coste de lo vendido, el margen bruto, los gastos y el beneficio neto", "Resultados: ventas, coste de lo vendido, margen y gastos (datos de ejemplo)"),
    faq=[
        ("¿Cuál es la diferencia entre margen y recargo?",
         "El margen es la parte del precio sin IVA que te queda como beneficio; el recargo es lo que añades sobre el coste. Con un coste de 10 € y un precio de 14 €, el recargo es del 40 % y el margen del 28,6 %."),
        ("¿Cómo calculo el precio de venta a partir del coste?",
         "Divide el coste entre 1 menos el margen que quieres (en forma decimal) y suma el IVA. Con un coste de 10 € y un margen del 40 %: 10 ÷ 0,6 = 16,67 € sin IVA, y 20,17 € con un 21 % de IVA."),
        ("¿El margen se calcula con o sin IVA?",
         "Sin IVA: el IVA que cobras no es tuyo, lo ingresas después. Si tu precio de venta ya lleva IVA, quítaselo antes de calcular el margen; la calculadora lo hace si eliges «con IVA incluido»."),
        ("¿Qué margen debería tener mi producto?",
         "Depende de tu sector, de tus gastos fijos y de lo que valora tu cliente: no hay una cifra válida para todos. Lo útil es comprobar que el margen de cada producto, sumado, cubre tus gastos (alquiler, sueldos, suministros) y deja beneficio."),
        ("¿Cuánto me cuesta un descuento?",
         "Más de lo que parece: con un margen del 40 %, un descuento del 20 % deja el margen en el 25 % y obliga a vender el doble de unidades para ganar lo mismo. Pon el descuento en la calculadora para ver tu caso."),
        ("¿Se guarda lo que escribo?",
         "No. Los cálculos se hacen en tu navegador: no se envía ni se guarda nada."),
    ],
)

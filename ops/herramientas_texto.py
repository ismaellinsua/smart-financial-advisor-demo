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
    title="Herramientas gratis para tu negocio: caja y margen · NirKanA",
    description="Herramientas gratuitas para negocios: calculadora de arqueo de caja en euros, con plantilla de Excel, y calculadora de margen y precio de venta con IVA.",
    h1="Herramientas gratis para tu negocio",
    lead="Calculadoras sencillas para las cuentas que haces a menudo: cuadrar la caja y fijar precios. Gratis, sin registro y sin que tus datos salgan del navegador.",
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

# ---------------------------------------------------------------------------------------------------------------- 1
tool(
    slug="calculadora-de-arqueo-de-caja",
    title="Calculadora de arqueo de caja: cuenta billetes y monedas · NirKanA",
    description="Calculadora gratis de arqueo de caja en euros: cuenta billetes y monedas, compara con lo que debería haber y ve al momento si cuadra. Con plantilla de Excel.",
    h1="Calculadora de arqueo de caja",
    lead="Cuenta los billetes y las monedas del cajón, apunta lo que debería haber y comprueba al instante si la caja cuadra. Gratis, sin registro y sin que nada salga de tu navegador.",
    summary="Cuenta billetes y monedas en euros, compáralo con lo esperado y ve el descuadre al momento. Con plantilla de Excel.",
    icon="i-receipt",
    demo="hosteleria",
    widget="arqueo",
    sectors=["restaurantes", "tiendas"],
    related=["arqueo-y-cierre-de-caja", "que-es-un-tpv"],
    subject="Consulta desde la calculadora de arqueo de caja",
    app_name="Calculadora de arqueo de caja",
    sections=[
        ("como-se-usa", "Cómo se usa", """
<ol>
<li><strong>Cuenta el efectivo antes de mirar cuánto debería haber.</strong> Escribe cuántos billetes y monedas hay de cada tipo; lo que dejes en blanco cuenta como cero.</li>
<li><strong>Apunta lo que debería haber:</strong> el fondo con el que empezaste, las ventas cobradas en efectivo, otras entradas (por ejemplo, un cambio que te traen) y las salidas (pagos a proveedores, retiradas, devoluciones en efectivo).</li>
<li><strong>Mira el resultado.</strong> La calculadora resta lo esperado de lo contado: si es cero, la caja cuadra; si es positivo, sobra dinero; si es negativo, falta.</li>
<li><strong>Si quieres, indica el fondo que dejas para mañana</strong> y te dice cuánto tienes que retirar del cajón.</li>
</ol>
<p>La cuenta es sencilla: <em>efectivo esperado = fondo inicial + ventas en efectivo + otras entradas − salidas</em>, y <em>diferencia = contado − esperado</em>.</p>
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

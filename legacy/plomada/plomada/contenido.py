"""Textos editoriales largos. Separados del generador para que se puedan
corregir sin tocar codigo. Nada aqui afirma que alguien cometio un delito.

El texto que ve el lector va con su ortografia completa (tildes y enes).
Lo que NO lleva tildes es lo que viene del pipeline en MAYUSCULAS (nombres
de entidad, municipio, departamento) y los identificadores de columna
(<code>valor_plausible</code>, <code>f_cuenta_compartida</code>): esos son
datos y nombres de campo, no prosa, y se citan tal como salen de la fuente.
"""

AVISO = ("Un indicio no es una acusación. Todo lo que aparece aquí es un <strong>indicio</strong> "
         "calculado sobre datos públicos del SECOP II para priorizar revisión. "
         "No afirma que persona o entidad alguna haya obrado de forma irregular.")

AVISO_CORTO = "Indicio para revisión, no acusación."

FALSOS_POSITIVOS = [
    ("Juntas de Acción Comunal con cuenta compartida",
     "Las JAC de un mismo municipio comparten cuenta bancaria porque la alcaldía "
     "canaliza los pagos por una sola tesorería. La bandera de cuenta compartida se "
     "encendía sin que hubiera nada que revisar.",
     "Se clasifica con <code>ev_tipo_red_cuenta</code>, y cada caso enciende (o no) "
     "una bandera distinta: <code>empresas_independientes</code> enciende "
     "<code>f_cuenta_compartida</code> (indicio fuerte); <code>consorcios</code> "
     "enciende una bandera aparte y más débil, <code>f_cuenta_consorcios</code>; y "
     "<code>comunitaria</code> no enciende ninguna bandera — es ruido administrativo "
     "conocido, no un indicio ni siquiera atenuado."),
    ("Convenios interadministrativos leídos como obra directa",
     "Cuando el Estado le contrata al Estado, la contratación directa está autorizada "
     "por el artículo 2 de la ley 1150 de 2007. Estos convenios eran el 26% de los "
     "falsos positivos de la bandera de obra por contratación directa.",
     "Se excluyen del conteo los procesos en los que contratante y contratista son "
     "ambos entidades públicas. El contrato sigue siendo consultable, pero la bandera "
     "no se enciende."),
    ("Consorcios y uniones temporales con cuenta del líder",
     "En un consorcio la cuenta de pago suele estar a nombre de la empresa líder. "
     "Eso hace que varios NIT compartan cuenta sin que exista simulación de competencia.",
     "Enciende <code>f_cuenta_consorcios</code>, una bandera propia y de peso bajo "
     "(no una versión atenuada de <code>f_cuenta_compartida</code>), presentada "
     "siempre con la razón a la vista."),
    ("Valores de publicación imposibles",
     "24 contratos están publicados con cifras aritméticamente imposibles, hasta "
     "6 x 10<sup>18</sup> pesos, más que el PIB mundial. Concentraban el 98,6% del "
     "total agregado y distorsionaban cualquier ranking por dinero.",
     "No se borran: se muestran como falla de publicación de la entidad. Todo el "
     "dinero de este sitio se suma con <code>valor_plausible</code>, la versión "
     "saneada, nunca con <code>valor</code>."),
    ("Municipios pequeños encabezando el ranking por azar",
     "Un municipio con 4 contratos y 2 marcados da 50% de tasa cruda y encabezaría "
     "cualquier lista ordenada por porcentaje, sin que eso signifique nada.",
     "Todos los rankings se ordenan por <code>tasa_ajustada</code>, que aplica "
     "contracción bayesiana hacia la tasa nacional. La tasa cruda se muestra al lado "
     "para que la corrección sea visible y auditable."),
]

LIMITACIONES = [
    ("Cobertura desigual de identificadores",
     "El análisis de red solo puede calcularse sobre los contratos que traen el "
     "identificador. Es un piso, no un censo: si una relación no aparece, puede ser "
     "porque no existe o porque el dato no fue publicado."),
    ("Municipio sin definir",
     "Una parte de los contratos trae <code>NO DEFINIDO</code> en el campo de ciudad. "
     "Se tratan como dato ausente y no se pintan en el mapa ni se atribuyen a ningún "
     "municipio."),
    ("El universo es obra pública, no toda la contratación",
     "De 5.975.627 contratos del SECOP II se analizan 77.864 de obra, interventoría, "
     "consultoría, APP y concesión. Los 5.123.891 de prestación de servicios quedan "
     "fuera del alcance de este trabajo."),
    ("Las banderas describen patrones, no intenciones",
     "Cada bandera responde a una pregunta verificable sobre el expediente publicado. "
     "Ninguna responde por qué ocurrió lo que ocurrió. Esa respuesta requiere reportería."),
    ("Los datos son una foto del SECOP II en la fecha de corte",
     "Un contrato puede haberse modificado, liquidado o caído después del corte. "
     "El enlace a la fuente oficial está en cada ficha justamente para eso."),
]

PUNTAJE = """
<p>El puntaje no es una probabilidad de irregularidad ni el resultado de un modelo
entrenado. Es una suma explicable, y esa es una decisión deliberada: un puntaje de
caja negra no se puede defender ante un editor ni ante un juez.</p>
<ol>
  <li>Cada una de las banderas responde a una pregunta objetiva sobre el expediente
      publicado, del tipo <em>cuántas ofertas recibió este proceso</em>. La respuesta
      sale del dato, no de un criterio.</li>
  <li>Cada bandera encendida aporta su <strong>peso</strong>. Los pesos están en
      <code>banderas_glosario.csv</code> y se pueden auditar uno por uno.</li>
  <li>La suma es <code>puntos_crudos</code>. El <code>score</code> es esa suma
      normalizada a 0&ndash;1 para poder comparar contratos entre sí.</li>
  <li>Un contrato entra al conjunto de <strong>atípicos</strong> cuando acumula
      señales fuertes, no por un puntaje alto compuesto de muchas señales débiles.
      Diez indicios menores no equivalen a uno grave.</li>
</ol>
<p>El umbral está donde está por una razón práctica: más abajo, el volumen de
contratos marcados deja de ser revisable por un equipo humano y la herramienta
pierde su utilidad; más arriba, se pierden casos que sí ameritan revisión. Es un
punto de corte operativo, no una frontera entre lo lícito y lo ilícito.</p>
"""

INTRO_METODOLOGIA = """
<p>Esta página existe para que cualquiera pueda desarmar lo que hicimos. Es la parte
del proyecto que dice lo que <strong>no</strong> podemos afirmar.</p>
<p>Plomada lee la contratación de obra pública del Estado colombiano publicada en el
SECOP II, la plataforma oficial. Todos los datos son públicos y no hay en este sitio
ninguna información filtrada, reservada ni obtenida por fuera de los canales
oficiales. Lo que aportamos no es información nueva: es una forma de mirarla.</p>
<p>La diferencia con un buscador de contratos es el sujeto. Un buscador organiza la
información por empresa, y la empresa es lo más fácil de cambiar: se disuelve y al
día siguiente aparece otra con otro NIT. Plomada organiza la información por las
personas que firman &mdash; ordenador del gasto, supervisor, representante legal,
ordenador de pago &mdash; porque una cédula no se disuelve.</p>
"""

PRIVACIDAD = """
<p>Este sitio conecta por identificadores personales pero <strong>no los publica</strong>.
Nunca salen del pipeline hacia una página, una descarga o una respuesta:</p>
<ul>
  <li>Números de cuenta bancaria, en cualquier forma.</li>
  <li>La cédula del representante legal y la del supervisor, que son particulares.</li>
  <li>El documento del contratista cuando es persona natural.</li>
  <li>La cédula del ordenador del gasto. Es un funcionario público en ejercicio y su
      <em>nombre</em> sí es información pública, pero el número no aporta nada al
      lector y sí aporta riesgo.</li>
</ul>
<p>Lo que sí se publica es el <em>hecho</em> de la relación. &laquo;Tres proveedores
comparten cuenta bancaria&raquo; es publicable y es exactamente el indicio; el número
de la cuenta no lo es, y no lo será. Esto no es una política escrita: es un
serializador en la capa de datos y una prueba automática que tumba la publicación del
sitio si una columna prohibida alcanza a llegar a un archivo.</p>
"""

FUENTES = """
<ul>
  <li><a href="https://www.colombiacompra.gov.co/transparencia/conjuntos-de-datos-abiertos"
      rel="noopener">SECOP II &mdash; datos abiertos de Colombia Compra Eficiente</a>,
      fuente primaria de todos los contratos.</li>
  <li><a href="https://www.dane.gov.co/index.php/servicios-al-ciudadano/servicios-informacion/codigos-estadisticos"
      rel="noopener">DIVIPOLA y Marco Geoestadístico Nacional del DANE</a>,
      fronteras y códigos de departamento y municipio.</li>
  <li><a href="/datos/">Datos derivados de este sitio</a>, en CSV, ya saneados de
      identificadores personales.</li>
</ul>
"""


# ─────────────────────────────────────────────────────────────── vista /api/
# Todo lo de aqui abajo esta verificado contra produccion (openapi.json en
# vivo y curl real, 2026-08-23). Ni un endpoint ni un campo inventado.
#
# La base del API NO se escribe aqui: build.py la interpola desde API_URL
# (configurable con PLOMADA_API_URL), porque render.yaml ya declara un host
# futuro distinto del que esta vivo hoy. Por eso los ejemplos de esta seccion
# llevan {base} y los formatea pagina_api().

API_INTRO = """
<p>Los mismos datos que mueven este sitio están disponibles como API pública.
Es de <strong>solo lectura</strong>, no pide autenticación y no tiene cupo: todo lo
que sirve son datos públicos del SECOP II, y no hay razón para ponerles una puerta.</p>
<p>Lo que devuelve son <em>indicios</em>. Una bandera encendida quiere decir que un
contrato merece que alguien lo mire, no que alguien haya obrado mal. Cada respuesta
lleva esa salvedad en <code>meta.aviso</code>, y en los CSV viaja en la cabecera
<code>X-Plomada-Aviso</code>. Si va a citar una cifra, lea antes
<code>/v1/meta</code>: trae la cobertura real de cada campo y las limitaciones que
hay que decir en voz alta.</p>
"""

API_CONVENCIONES = """
<p>Toda respuesta viene en el mismo sobre: <code>datos</code> con el contenido y
<code>meta</code> con la versión, la fuente, el aviso y la paginación.</p>
<ul>
  <li><b>Errores.</b> Un cuerpo <code>{"error": {"codigo", "mensaje", "detalle"}}</code>.
      El <code>codigo</code> es estable y es por el que conviene ramificar;
      el <code>mensaje</code> es para leer.</li>
  <li><b>Paginación.</b> <code>limite</code> (tope <b>200</b>) y
      <code>desplazamiento</code>. El total real viene en
      <code>meta.paginacion.total</code>, que casi siempre es mayor que lo que
      devolvió: sin mirarlo es fácil publicar «200 contratos» cuando eran miles.</li>
  <li><b>CSV.</b> Los listados aceptan <code>?formato=csv</code>. Respeta el mismo
      tope de 200, así que una descarga completa se arma paginando.</li>
</ul>
"""

# (ruta, que responde). Los textos son los `summary` del openapi.json en vivo,
# ajustados a la ortografia del sitio. Verificado: 20 rutas bajo /v1.
API_ENDPOINTS = [
    ("/v1", "Índice de la API: el catálogo de todo lo que sigue."),
    ("/v1/meta", "Cobertura real de cada campo y las limitaciones. Léalo primero."),
    ("/v1/titulares", "Las cifras de encabezado del proyecto."),
    ("/v1/indicios", "Cuánta plata hay por categoría de indicio."),
    ("/v1/banderas", "Glosario de las banderas, con su peso y su glosa."),
    ("/v1/contratos", "Buscador de contratos, con filtros y orden."),
    ("/v1/contratos/{id_contrato}", "Ficha completa de un contrato, bandera por bandera."),
    ("/v1/entidades", "Buscador de entidades contratantes."),
    ("/v1/entidades/{nit_entidad}", "Perfil de una entidad."),
    ("/v1/proveedores", "Buscador de proveedores."),
    ("/v1/proveedores/{doc}", "Perfil de un proveedor y su red."),
    ("/v1/municipios", "Ranking municipal por tasa ajustada."),
    ("/v1/departamentos", "Plata y tasas por departamento."),
    ("/v1/tipos-obra", "Plata por tipo de obra."),
    ("/v1/fuentes", "Plata por fuente de recursos."),
    ("/v1/autosupervision", "Entidades donde autosupervisar es la norma."),
    ("/v1/red/clusters", "Grupos económicos detectados."),
    ("/v1/red/clusters/{cluster_id}", "El subgrafo de un grupo económico."),
    ("/v1/alertas", "Licitaciones abiertas que ya presentan banderas."),
    ("/v1/alertas/resumen", "Conteo por universo del snapshot de alertas."),
]

API_COLD_START = """
<p>El API vive en un plan gratuito que <strong>duerme el servicio cuando nadie lo
usa</strong>. La primera llamada después de un rato puede tardar entre 30 y 60
segundos; las siguientes responden normal. No está caído: está despertando. Si
escribe un cliente, déle a la primera petición un tiempo de espera generoso —
este sitio usa 60 segundos para la primera y 15 para el resto.</p>
"""

# ──────────────────────────────────────────────────────── seccion MCP en /api/
# Verificado con tools/list contra produccion (2026-08-23) y contra
# api/app/mcp/server.py: son estas siete, con estos nombres.
MCP_INTRO = """
<p>Los mismos datos están publicados como <strong>servidor MCP</strong>, el protocolo
con el que un asistente conversacional consulta herramientas externas. Sirve para
preguntarle a los datos en lenguaje natural desde un cliente que ya use — Claude
Desktop, Claude Code o cualquiera con soporte de MCP remoto — sin escribir código.</p>
<p>Es el mismo trato que el API: solo lectura, sin autenticación, sobre datos
públicos. Y la misma salvedad, que el servidor declara en sus propias instrucciones:
lo que devuelve son indicios para priorizar una revisión, no prueba de nada.</p>
"""

MCP_TOOLS = [
    ("resumen_indicios", "Las cifras titulares y las limitaciones que las acompañan."),
    ("buscar_contratos_atipicos", "Contratos marcados, con filtros."),
    ("detalle_contrato", "La ficha completa de un contrato, con cada bandera encendida."),
    ("perfil_entidad", "El resumen de una entidad contratante."),
    ("buscar_proveedor", "El perfil de un proveedor y su red."),
    ("alertas_preadjudicacion", "Licitaciones que todavía aceptan ofertas."),
    ("glosario_banderas", "Las 26 banderas con su peso."),
]


# ───────────────────────────────────────────────────── vista /asistente/ (F4)
# El asistente habla con el servidor MCP a traves del proxy /chat del API. La
# key es del lector (BYOK): Plomada no tiene una, no la quiere y no la ve.

ASISTENTE_INTRO = """
<p>Pregúntele a los datos en español. Detrás hay un modelo de lenguaje conectado a
las mismas herramientas que expone el servidor MCP: puede buscar contratos marcados,
abrir la ficha de uno, perfilar una entidad o un proveedor, listar las licitaciones
que todavía aceptan ofertas y explicar cualquiera de las 26 banderas.</p>
<p>Lo que responda sale de los datos, no de su memoria: cada cifra que cite viene de
una consulta al API en ese momento. Aun así, es un modelo de lenguaje y se puede
equivocar al resumir. Todo lo que diga es verificable: pídale el enlace a la ficha
del contrato y compruébelo.</p>
"""

ASISTENTE_KEY_AYUDA = """
<p>El asistente funciona con <strong>su propia API key de Anthropic</strong>. Plomada
no tiene una llave compartida, no cobra nada y no intermedia el pago: el consumo va
directo a su cuenta y lo ve en su consola de Anthropic.</p>
<p>La llave se guarda <strong>solo en este navegador</strong> y viaja únicamente a
Plomada para reenviarla a Anthropic en cada pregunta. No se guarda en ningún
servidor, no entra en la dirección de la página y no queda en ningún registro.
Puede borrarla cuando quiera con el botón de abajo.</p>
"""

ASISTENTE_SIN_JS = """
<p>El asistente necesita JavaScript para funcionar, y este navegador lo tiene
desactivado. Los mismos datos siguen a su alcance sin él:</p>
<ul>
  <li><a href="/buscar/">El buscador de contratos</a>, con filtros y descarga en CSV.</li>
  <li><a href="/api/">El API</a>, si prefiere consultarlo desde su propio programa.</li>
  <li><a href="/api/#mcp">El servidor MCP</a>, para conectar el asistente que ya use.</li>
</ul>
"""

# Escritas contra las tools que EXISTEN: cada una la puede responder alguna de
# las siete (buscar_contratos_atipicos, glosario_banderas,
# alertas_preadjudicacion, perfil_entidad). No sugerir nada que ninguna cubra.
ASISTENTE_SUGERENCIAS = [
    "¿Qué contratos atípicos hay en Santander?",
    "¿Qué significa la bandera de cuenta compartida?",
    "¿Qué licitaciones de obra siguen abiertas y ya tienen banderas?",
    "Muéstrame el perfil de una entidad con mucha autosupervisión",
]

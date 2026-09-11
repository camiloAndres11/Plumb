"""Prueba que tumba la publicacion. Sin framework: `python3 test_privacy.py`.

Lo que verifica, en orden de gravedad:
  1. Ninguna columna ni ningun VALOR prohibido llego a un artefacto de site/.
  2. Ningun texto de la interfaz usa el vocabulario prohibido.
  3. Toda ficha de contrato permite verificar en la fuente oficial.
  4. Los rankings ordenan por tasa ajustada y no por la cruda.
  5. Las banderas y sus textos vienen del CSV, no del codigo.
  6. Los helpers de presentacion (plata, titulo, url) hacen lo que dicen.
  7. El mapa satelital de la ficha nunca pinta el fallback de Colombia y nunca
     inyecta HTML crudo en el popup.
  8. El grafo de red del tablero (datos/red.json) no publica ningun documento
     de proveedor crudo, ni como columna ni con forma de NIT/cedula donde
     deberia haber un id secuencial.
  9. Blindaje T0 de docs/PLAN_VUE.md, antes de que exista una sola linea de
     Vue: el vocabulario prohibido tambien se barre en los JSON publicados y
     en las fuentes de frontend/src/; ningun .vue trae 'v-html'; el bundle de
     static/vendor/islas/ no trae una URL externa (salvo arcgisonline.com,
     ya documentada); y el bundle corresponde al hash de sus fuentes.
"""
import csv, hashlib, html, json, re, sys
from pathlib import Path

import build
import data as D

RAIZ = Path(__file__).parent
SITE = RAIZ / "site"
FRONTEND = RAIZ.parent / "frontend"
BUNDLE = RAIZ / "static" / "vendor" / "islas"
fallos = []


def check(ok, mensaje):
    if not ok:
        fallos.append(mensaje)


def artefactos():
    return [p for p in SITE.rglob("*") if p.is_file()
            and p.suffix in (".html", ".json", ".csv", ".xml", ".txt", ".geojson")]


def texto_visible(html_str):
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html_str)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return html.unescape(s)


# ---------------------------------------------------------- 1. identificadores
def test_columnas_prohibidas():
    prohibidas = D.PROHIBIDAS | D.PROHIBIDAS_CONDICIONALES
    for p in artefactos():
        t = p.read_text(encoding="utf-8", errors="replace")
        for col in prohibidas:
            # el nombre de la columna solo puede aparecer citado en la metodologia
            if re.search(r"\b" + re.escape(col) + r"\b", t) and "metodologia" not in str(p):
                fallos.append(f"FUGA: la columna '{col}' aparece en {p.relative_to(SITE)}")
        if p.suffix in (".json", ".csv"):
            cabezas = (t[:4000] if p.suffix == ".csv" else t[:4000])
            for col in prohibidas:
                check(col not in cabezas,
                      f"FUGA: '{col}' es una columna publicada en {p.relative_to(SITE)}")


def test_valores_prohibidos():
    """El de verdad: los VALORES concretos no pueden estar en ningun archivo."""
    fuente = list(D.leer_csv("contratos_atipicos.csv"))
    if not fuente:
        fallos.append("No hay out/contratos_atipicos.csv contra el cual comparar")
        return
    cols_txt = ["cuenta_key"]
    cols_num = ["doc_replegal", "doc_supervisor", "doc_ordenador"]
    valores_txt = {r[c] for r in fuente for c in cols_txt if r.get(c)}
    valores_num = {r[c] for r in fuente for c in cols_num if r.get(c)}
    # doc_proveedor solo esta prohibido cuando el proveedor es persona natural
    valores_num |= {r["doc_proveedor"] for r in fuente
                    if r.get("doc_proveedor") and not D.es_persona_juridica(r.get("proveedor"))}
    # Con datos reales, doc_ordenador/doc_supervisor/doc_replegal a veces vienen
    # vacios de identidad personal y la fuente (SECOP II) rellena esas columnas
    # con el NIT de la propia entidad -- no es una cedula que se este colando,
    # es el mismo numero que nit_entidad ya publica legitimamente en esa misma
    # ficha (D.publicar() si expone nit_entidad). Excluirlos evita cientos de
    # falsos positivos sin dejar de proteger ninguna cedula real: si un valor
    # nunca aparece como nit_entidad de nadie, sigue prohibido.
    nits_entidad = {r["nit_entidad"] for r in fuente if r.get("nit_entidad")}
    valores_num -= nits_entidad
    # Placeholders de "sin dato" en la fuente (todo el mismo digito repetido:
    # '000000', '111111111', ...) no identifican a nadie; tambien se excluyen.
    valores_num = {v for v in valores_num if len(set(v)) > 1}

    for p in artefactos():
        t = p.read_text(encoding="utf-8", errors="replace")
        for v in valores_txt:
            check(v not in t, f"FUGA: la cuenta bancaria '{v}' aparece en {p.relative_to(SITE)}")
        # los numericos, como token aislado, para no chocar con cifras de dinero
        encontrados = set(re.findall(r"(?<![\d.,-])\d{6,12}(?![\d.,])", t)) & valores_num
        for v in sorted(encontrados):
            duenos = [r["id_contrato"] for r in fuente
                      if v in (r.get(c) for c in cols_num + ["doc_proveedor"])]
            fallos.append(f"FUGA: el documento '{v}' ({duenos[:2]}) aparece en {p.relative_to(SITE)}")


def test_serializador():
    fila = next(D.contratos())
    pub = D.publicar(fila)
    for col in D.PROHIBIDAS | D.PROHIBIDAS_CONDICIONALES:
        check(col not in pub, f"publicar() dejo pasar '{col}'")
    check(D.es_persona_juridica("MYG LINARES S.A.S."), "S.A.S. deberia ser persona juridica")
    check(D.es_persona_juridica("CONSORCIO VIAS DEL SUR"), "consorcio deberia ser persona juridica")
    check(not D.es_persona_juridica("JAIRO ANTONIO MENDOZA PALACIOS"),
          "una persona natural no deberia clasificarse como juridica")


def test_red_sin_documentos():
    """El tablero (pipeline/export_web.py, Tanda A) escribe out_web/red.json,
    que build.py copia a site/datos/red.json -- de ahi que caiga bajo el
    mismo barrido que el resto de site/. Antes de A3 esta publicaba 'doc' en
    cada nodo y 'doc_a'/'doc_b' en cada arista, sin filtro.

    No hay una lista de valores conocidos contra la cual comparar (a
    diferencia de test_valores_prohibidos): los datos del tablero salen del
    warehouse, no de contratos_atipicos.csv. Por eso la comprobacion aqui es
    ESTRUCTURAL: ni la clave cruda ('doc', 'doc_a', 'doc_b'), ni un id con
    forma de NIT/cedula (6 a 12 digitos sueltos) donde deberia haber un id
    secuencial ('n0', 'n1', ...) asignado por sanear_red().
    """
    ruta = SITE / "datos" / "red.json"
    if not ruta.exists():
        return  # pipeline/export_web.py no corrio en este build (sin warehouse): nada que barrer
    try:
        red = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fallos.append(f"datos/red.json no es JSON valido: {e}")
        return
    check(isinstance(red, list), "datos/red.json deberia ser una lista de clusters")
    numero_crudo = re.compile(r"^\d{6,12}$")
    for cluster in red if isinstance(red, list) else []:
        cid = cluster.get("id", "?")
        for n in cluster.get("nodos", []):
            check("doc" not in n, f"FUGA: datos/red.json trae la columna 'doc' en un nodo (cluster {cid})")
            idv = n.get("id")
            check(idv is not None,
                  f"FUGA: un nodo del cluster {cid} en datos/red.json no tiene 'id' (¿sanear_red() no corrio?)")
            if idv is not None:
                check(not numero_crudo.match(str(idv)),
                      f"FUGA: el id de nodo '{idv}' (cluster {cid}) tiene forma de documento, no de id secuencial")
        for a in cluster.get("aristas", []):
            check("doc_a" not in a and "doc_b" not in a,
                  f"FUGA: datos/red.json trae doc_a/doc_b crudos en una arista (cluster {cid})")
            for k in ("a", "b"):
                v = a.get(k)
                check(v is not None, f"FUGA: una arista del cluster {cid} no trae '{k}'")
                if v is not None:
                    check(not numero_crudo.match(str(v)),
                          f"FUGA: el extremo '{k}'='{v}' de una arista (cluster {cid}) tiene forma de documento")


# ------------------------------------------------------------- 2. vocabulario
PROHIBIDO = re.compile(r"\b(corrupt\w*|fraude\w*|fraudulent\w*|delito\w*|delictiv\w*|"
                       r"robo|robos|rob[oó]|saque\w*|culpable\w*|criminal\w*|"
                       r"soborn\w*|pill[oa]s?)\b", re.I)

# 'criminal' tambien es parte legitima del nombre de unidades de policia o CTI
# citadas TAL CUAL como vienen en `entidad`/`descripcion` de la fuente (SECOP
# II) -- p.ej. "Seccion de Analisis Criminal", "Seccional Investigacion
# Criminal". Ahi no es que Plomada este acusando a nadie: es el nombre oficial
# de la entidad o del objeto del contrato. Solo se descarta esa frase puntual;
# 'criminal' usado de cualquier otra forma sigue prohibido.
_CRIMINAL_INSTITUCIONAL = re.compile(r"(?:investigaci[oó]n|an[aá]lisis)\s+criminal", re.I)

# El API real (GET /v1/meta -> limitaciones) trae el mismo tipo de aviso que
# ya usa contenido.py: "Riesgo no es fraude: son indicios para priorizar
# investigacion." Esa frase EXISTE justamente para negar la acusacion, no
# para hacerla -- es el mismo patron que el AVISO fijo del sitio ("No afirma
# que persona o entidad alguna haya obrado de forma irregular"). Bloquearla
# por contener la palabra seria censurar la propia salvedad que el sitio
# necesita mostrar. Solo se descarta la negacion puntual ("no es/implica/
# significa <palabra>"); la palabra sola, sin negar, sigue prohibida.
_NEGACION = re.compile(
    r"no\s+(?:es|son|implica\w*|significa\w*)\s+(?:corrupt\w*|fraude\w*|fraudulent\w*|"
    r"delito\w*|delictiv\w*|robo\w*|rob[oó]|saque\w*|culpable\w*|criminal\w*|"
    r"soborn\w*|pill[oa]s?)", re.I)


def _vocabulario_prohibido(texto):
    limpio = _NEGACION.sub(" ", _CRIMINAL_INSTITUCIONAL.sub(" ", texto))
    return set(PROHIBIDO.findall(limpio))


def test_vocabulario():
    for p in SITE.rglob("*.html"):
        for m in _vocabulario_prohibido(texto_visible(p.read_text(encoding="utf-8"))):
            fallos.append(f"LENGUAJE: '{m}' en {p.relative_to(SITE)}")


# ------------------------------------------------------------ 3. verificable
def test_ficha_shell_verificable():
    """La ficha ya no se pre-renderiza: hay UN shell que static/ficha.js
    hidrata desde el API. Lo que se comprueba cambia de sitio, no de fondo.

    El aviso "Indicio, no acusacion" tiene que estar en el HTML ESTATICO, no
    pintarse por JS: es la salvedad que no puede depender de que una llamada
    de red funcione. Si el API esta caido, el visitante igual la ve.
    """
    p = SITE / "contrato" / "index.html"
    check(p.exists(), "no se genero el shell de ficha (contrato/index.html)")
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    check("Indicio, no acusación" in t, "el shell de ficha no trae el aviso en el HTML estatico")
    check("/static/ficha.js" in t, "el shell de ficha no carga ficha.js")

    # El "verificar en la fuente" ahora lo pinta ficha.js: se comprueba ahi.
    js = (RAIZ / "static" / "ficha.js").read_text(encoding="utf-8")
    check("urlproceso" in js and "Verificar en SECOP II" in js,
          "ficha.js no ofrece el enlace de verificacion en la fuente oficial")
    check("no publicó enlace al proceso" in js or "no publico enlace al proceso" in js,
          "ficha.js no avisa cuando la fuente no publico enlace al proceso")


def test_urls_compartibles():
    for ruta in ("index.html", "plomada/index.html", "mapa/index.html", "buscar/index.html",
                 "metodologia/index.html", "datos/index.html", "sitemap.xml",
                 "contrato/index.html", "municipio/index.html"):
        check((SITE / ruta).exists(), f"falta {ruta}")

    # Las fichas se hidratan en el navegador pero SIGUEN teniendo URL propia:
    # sin esto dejan de ser compartibles y rastreables, que es el producto.
    mapa = (SITE / "sitemap.xml").read_text(encoding="utf-8")
    check(mapa.count("/contrato/") > 1000,
          "el sitemap perdio las fichas de contrato: dejan de ser rastreables")
    check(mapa.count("/municipio/") > 100, "el sitemap perdio los municipios")

    # Sin la regla de reescritura, /contrato/<slug>/ devuelve 404 en un host
    # estatico y ninguna URL compartida funciona.
    red = SITE / "_redirects"
    check(red.exists(), "falta _redirects: /contrato/<slug>/ daria 404 en el host")
    if red.exists():
        t = red.read_text(encoding="utf-8")
        check("/contrato/*" in t and "/municipio/*" in t,
              "_redirects no cubre las dos rutas dinamicas")


# ---------------------------------------------------------------- 4. rankings
def test_tasa_ajustada():
    muns = D.municipios()
    pequeno = [m for m in muns if m["n_contratos"] <= 6 and m["tasa_cruda"] >= .5]
    check(pequeno, "los datos de prueba deberian traer un municipio chico con tasa cruda alta")
    lider_ajustada = max(muns, key=lambda m: m["tasa_ajustada"])
    for m in pequeno:
        check(m["tasa_ajustada"] < m["tasa_cruda"],
              f"{m['ciudad']}: la tasa ajustada no contrajo la cruda")
        check(m is not lider_ajustada,
              f"{m['ciudad']} encabeza el ranking con solo {m['n_contratos']} contratos")
    # El orden se comprueba contra la PROPIA pagina, no contra D.municipios().
    # La portada se arma con los municipios del API y D.municipios() lee
    # out/ (o las fixtures, en un build limpio como el de Render): son dos
    # fuentes distintas y compararlas hacia fallar el build por un desacuerdo
    # entre datasets, no por un ranking mal ordenado. Lo que importa es que lo
    # PUBLICADO este ordenado por tasa ajustada, y eso se lee del HTML.
    # La portada de Plomada vive en /plomada/: la raiz (/) es la landing
    # comercial de Adjudica y no publica ranking alguno.
    portada = (SITE / "plomada" / "index.html").read_text(encoding="utf-8")
    tasas = [float(x.replace(".", "").replace(",", "."))
             for x in re.findall(r'class="num destacado">([\d.,]+)%<', portada)]
    check(tasas, "la portada no publica ninguna tasa ajustada")
    check(tasas == sorted(tasas, reverse=True),
          f"la portada no ordena los municipios por tasa ajustada: {tasas[:12]}")
    for pag in (SITE / "plomada" / "index.html", SITE / "mapa" / "index.html"):
        t = pag.read_text(encoding="utf-8")
        check("Tasa cruda" in t and "Tasa ajustada" in t,
              f"{pag.relative_to(SITE)} no muestra las dos tasas juntas")


# ----------------------------------------------------------------- 5. banderas
def test_banderas_del_csv():
    glos = D.glosario()
    check(glos, "banderas_glosario.csv vacio")
    met = texto_visible((SITE / "metodologia" / "index.html").read_text(encoding="utf-8"))
    for b in glos.values():
        check(b["glosa"][:60] in met,
              f"la glosa de {b['bandera']} no salio del CSV a la metodologia")
    # una bandera nueva del pipeline se absorbe sola
    fila = dict(next(D.contratos()))
    fila["f_bandera_inventada_manana"] = 1
    items, _ = D.banderas_encendidas(fila, glos)
    nueva = [i for i in items if i["bandera"] == "f_bandera_inventada_manana"]
    check(nueva, "la UI no absorbe una bandera nueva del pipeline")

    # cuenta compartida: solo empresas_independientes es indicio fuerte
    base = {k: 0 for k in glos}
    base.update(f_cuenta_compartida=1, ev_proveedores_por_cuenta=3)
    for tipo, esperado in (("empresas_independientes", False), ("consorcios", True),
                           ("comunitaria", True)):
        it, _ = D.banderas_encendidas({**base, "ev_tipo_red_cuenta": tipo}, glos)
        check(it[0]["atenuada"] is esperado,
              f"red de cuenta '{tipo}': atenuada deberia ser {esperado}")


# ------------------------------------------------------------- 6. presentacion
def test_presentacion():
    check(D.plata(209_043_881_234_567) == "$209 billones", D.plata(209_043_881_234_567))
    check(D.plata(500_000_000_000) == "$500 mil millones", D.plata(500_000_000_000))
    check(D.plata(63_500_000_000) == "$63,5 mil millones", D.plata(63_500_000_000))
    check(D.plata(1_000_000_000_000) == "$1 billon", D.plata(1_000_000_000_000))
    check(D.plata(None) == "sin dato", "plata(None)")
    check(len(D.plata(6e18)) < 30, "una cifra imposible deberia seguir siendo legible")

    check(D.titulo("GOBERNACION DEL CHOCO") == "Gobernacion del Choco", D.titulo("GOBERNACION DEL CHOCO"))
    check(D.titulo("E.S.E. HOSPITAL SAN RAFAEL") == "E.S.E. Hospital San Rafael",
          D.titulo("E.S.E. HOSPITAL SAN RAFAEL"))
    check("ICCU" in D.titulo("CONCESIONES DE CUNDINAMARCA - ICCU"), "ICCU se destrozo")
    check("SENA" in D.titulo("SERVICIO NACIONAL DE APRENDIZAJE - SENA"), "SENA se destrozo")
    check("S.A.S." in D.titulo("MYG LINARES S.A.S."), "S.A.S. se destrozo")
    check(D.titulo("EL CARMEN DE VIBORAL") == "El Carmen de Viboral", D.titulo("EL CARMEN DE VIBORAL"))

    u = D.url_secop("{'url': 'https://community.secop.gov.co/Public/Tendering/"
                    "OpportunityDetail/Index?noticeUID=CO1.NTC.5056481&isFromPublicArea=True'}")
    check(u and u.startswith("https://community.secop.gov.co/") and "NTC.5056481" in u, f"url_secop: {u}")
    check(D.url_secop("") is None and D.url_secop("basura") is None, "url_secop deberia tolerar basura")

    check(D.ciudad_visible("NO DEFINIDO") is None, "'NO DEFINIDO' no es un municipio")
    check(D.ciudad_visible("EL BAGRE") == "El Bagre", "ciudad_visible")


def test_valor_plausible():
    """El dinero se suma con valor_plausible, nunca con valor.

    Ya no hay 12.678 fichas pre-renderizadas que barrer: la explicacion del
    valor imposible la pinta static/ficha.js. Se comprueba que la plantilla
    siga trayendola, y que la regla se cumpla en los datos.
    """
    cs = list(D.contratos())
    raros = [c for c in cs if c.get("valor") and c["valor"] != c.get("valor_plausible")]
    check(raros, "los datos de prueba deberian traer un valor imposible")

    js = (RAIZ / "static" / "ficha.js").read_text(encoding="utf-8")
    check("falla de publicación" in js or "falla de publicacion" in js,
          "ficha.js no explica que el valor publicado por la entidad es imposible")
    check("valor_plausible" in js, "ficha.js no usa valor_plausible como valor del contrato")

    total_pub = sum(c["valor_plausible"] or 0 for c in cs)
    total_bruto = sum(c["valor"] or 0 for c in cs)
    check(total_pub < total_bruto / 1000,
          "el saneado deberia ser ordenes de magnitud menor que el bruto en estos datos")


# --------------------------------------------------------------------- 7. mapa
DEFECTO = {"lat": 4.570868, "lon": -74.297333, "precision": "defecto"}


def test_mapa_no_pinta_el_defecto():
    fila = {"dir_ejecucion": "KM 1 VIA X", "ciudad": "EL BAGRE", "departamento": "ANTIOQUIA"}
    cache_sin_datos = {"exacta": {}, "municipio": {}}
    cache_con_defecto = {"exacta": {}, "municipio": {"Antioquia|El Bagre": DEFECTO}}
    cache_real = {"exacta": {}, "municipio": {"Antioquia|El Bagre":
                 {"lat": 7.6, "lon": -74.8, "precision": "cabecera_municipal"}}}

    check(D.coords_contrato(fila, cache_sin_datos) is None, "sin cache no deberia haber coords")
    check(D.coords_contrato(fila, cache_con_defecto) is None,
          "el fallback 'defecto' (centro de Colombia) no debe tratarse como ubicacion valida")
    check(D.coords_contrato(fila, cache_real) is not None, "una cabecera real si debe devolver coords")

    html_sin, hay = build.bloque_mapa(fila, cache_con_defecto)
    check(not hay and "mapa-satelital" not in html_sin,
          "con solo el defecto en cache no deberia renderizarse el contenedor del mapa")
    html_ok, hay = build.bloque_mapa(fila, cache_real)
    check(hay and 'id="mapa-satelital"' in html_ok, "con una cabecera real si debe renderizarse el mapa")

    # ciudad ausente ('NO DEFINIDO'): no hay donde centrar el mapa, ni con cache llena
    fila_sin_mun = {**fila, "ciudad": "NO DEFINIDO"}
    check(D.coords_contrato(fila_sin_mun, cache_real) is None,
          "sin municipio confiable no deberia haber coords aunque el cache tenga datos")


def test_mapa_sin_html_crudo_en_popup():
    """El popup se arma con textContent/DOM, no interpolando HTML en un string."""
    js = (RAIZ / "static" / "mapa-satelital.js").read_text(encoding="utf-8")
    check("createElement" in js and "textContent" in js,
          "el popup deberia construirse con DOM/textContent, no con un template de HTML")
    check("innerHTML" not in js and "bindPopup(`" not in js,
          "el popup no deberia interpolar la direccion dentro de un string de HTML")

    fila = {"dir_ejecucion": 'KM 1 <script>alert(1)</script>', "ciudad": "EL BAGRE", "departamento": "ANTIOQUIA"}
    cache = {"exacta": {}, "municipio": {"Antioquia|El Bagre":
             {"lat": 7.6, "lon": -74.8, "precision": "cabecera_municipal"}}}
    html_mapa, _ = build.bloque_mapa(fila, cache)
    check("<script>" not in html_mapa, "una direccion con markup deberia salir escapada, no cruda")


def test_geocache_no_bloquea_sin_red():
    """build.py debe poder correr sin geo/geocache.json: fichas sin mapa, sin fallar."""
    fila = dict(next(D.contratos()))
    html_mapa, hay = build.bloque_mapa(fila, {"exacta": {}, "municipio": {}})
    check(not hay, "sin cache, ninguna ficha deberia intentar pintar un mapa")
    check("no geocodificada" in html_mapa, "deberia avisar que falta geocodificar, no fallar silenciosamente")


# -------------------------------------------- 9. blindaje T0 para Vue
# docs/PLAN_VUE.md §2.1: "no se escribe una linea de Vue hasta que la puerta
# de vocabulario cubra .json y los fuentes JS/Vue". frontend/ todavia no
# existe (llega en T1 del plan) -- estas pruebas degradan en silencio hasta
# entonces, y entran solas el dia que frontend/src/ aparezca.
URL_EXTERNA = re.compile(r"https?://[^\s'\"),>]+")
# arcgisonline.com: tiles satelitales, click-to-load (VENDOR.md §5) -- la
# unica peticion de red real que este proyecto le hace a un tercero, y solo
# tras el clic del lector. w3.org: el runtime de Vue trae "http://www.w3.org
# /2000/svg" y hermanos como identificadores de namespace XML para
# createElementNS -- son strings inertes, nunca se piden por red. vuejs.org:
# el runtime de produccion de Vue 3 deja un enlace a su pagina de referencia
# de errores dentro del mensaje que arma si un componente revienta en
# tiempo de ejecucion (asi ahorra el texto completo del warning en el
# bundle) -- tampoco es una peticion, es texto que solo se leeria en la
# consola si algo ya se rompio.
DOMINIOS_PERMITIDOS = ("arcgisonline.com", "w3.org", "vuejs.org")


def _fuentes_frontend():
    src = FRONTEND / "src"
    if not src.exists():
        return []
    return sorted(p for p in src.rglob("*") if p.is_file() and p.suffix in (".vue", ".js"))


def _hash_fuentes_frontend():
    h = hashlib.sha256()
    for p in _fuentes_frontend():
        h.update(str(p.relative_to(FRONTEND)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def test_vocabulario_json():
    """El hueco #1 de PLAN_VUE.md §2.1: test_vocabulario solo mira *.html. Un
    texto editorial que se mueva a un JSON que el cliente pinta quedaria
    invisible al escaner sin este test."""
    for p in SITE.rglob("*.json"):
        for m in _vocabulario_prohibido(p.read_text(encoding="utf-8", errors="replace")):
            fallos.append(f"LENGUAJE: '{m}' en {p.relative_to(SITE)}")


def test_vocabulario_fuentes():
    """El hueco #2 de PLAN_VUE.md §2.1: texto_visible() borra los <script>
    enteros y artefactos() ni siquiera mira .js/.vue. Mira los FUENTES
    (frontend/src/**), no el bundle: el bundle compilado y minificado no es
    donde se escribe texto editorial nuevo, es donde se depuraria un bug."""
    for p in _fuentes_frontend():
        rel = p.relative_to(FRONTEND)
        for m in set(PROHIBIDO.findall(p.read_text(encoding="utf-8", errors="replace"))):
            fallos.append(f"LENGUAJE: '{m}' en frontend/{rel}")


def test_sin_v_html():
    """v-html es el innerHTML de Vue (PLAN_VUE.md §2.2): mismo riesgo que
    test_mapa_sin_html_crudo_en_popup ya cierra en JS plano. Sobre FUENTES,
    nunca sobre el bundle -- el runtime de Vue usa innerHTML por dentro y la
    puerta fallaria siempre si mirara el artefacto compilado."""
    for p in _fuentes_frontend():
        if p.suffix != ".vue":
            continue
        if "v-html" in p.read_text(encoding="utf-8", errors="replace"):
            fallos.append(f"FUGA: 'v-html' en frontend/{p.relative_to(FRONTEND)}")


def test_bundle_sin_url_externa():
    """Espejo de la puerta de design/construir.py (falla si el CSS compuesto
    trae una URL externa), aplicada al bundle de Vue. Unica excepcion
    documentada: arcgisonline.com, los tiles satelitales click-to-load que
    MapaSatelital.vue pide solo tras el clic del lector (VENDOR.md §5)."""
    if not BUNDLE.exists():
        return
    for p in BUNDLE.rglob("*"):
        if not p.is_file() or p.suffix not in (".js", ".css", ".txt", ".html"):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        for url in URL_EXTERNA.findall(t):
            check(any(d in url for d in DOMINIOS_PERMITIDOS),
                  f"FUGA: URL externa '{url}' en {p.relative_to(BUNDLE)}")


def test_bundle_corresponde_a_fuentes():
    """MANIFIESTO.txt guarda el hash de frontend/src/** al compilar. Si
    alguien edita un .vue y no recompila, esto lo atrapa antes de que un
    bundle desfasado llegue a produccion (el bug ya arreglado en el fuente
    seguiria vivo en lo que de verdad se sirve)."""
    manifiesto = BUNDLE / "MANIFIESTO.txt"
    if not manifiesto.exists():
        return
    m = re.search(r"hash-fuentes:\s*([0-9a-f]{64})", manifiesto.read_text(encoding="utf-8"))
    check(m is not None, "MANIFIESTO.txt no trae la linea 'hash-fuentes: <sha256>'")
    if m is not None:
        check(m.group(1) == _hash_fuentes_frontend(),
              "el bundle de static/vendor/islas/ no corresponde a frontend/src/ -- "
              "corra 'npm --prefix frontend run build' para regenerar el bundle y el manifiesto")


def main():
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            fn()
    if fallos:
        print(f"\n  {len(fallos)} FALLO(S) — no se publica:\n")
        vistos, resto = set(), 0
        for f in fallos:
            clase = f.split(" en ")[0]          # un ejemplo por tipo de fallo, no 245 lineas
            if clase in vistos:
                resto += 1
                continue
            vistos.add(clase)
            print("   ✗", f)
        if resto:
            print(f"   … y {resto} mas del mismo tipo en otros archivos.")
        print()
        sys.exit(1)
    print("  todo en orden: sin fugas de identificadores, sin lenguaje acusatorio, "
          "fichas verificables, rankings por tasa ajustada.")


if __name__ == "__main__":
    if not SITE.exists():
        sys.exit("No hay site/. Corra: python3 build.py")
    main()

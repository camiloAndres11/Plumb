"""Capa de datos de Plomada. UNICO punto que toca los CSV.

Todo lo que sale de aqui ya esta: saneado de identificadores prohibidos,
con la URL de SECOP extraida, y con helpers de presentacion. Ningun
componente vuelve a parsear un CSV ni a formatear un peso a mano.
Cuando esto sea una API, se cambia solo este archivo.
"""
import ast, csv, json, os, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).parent
REPO_RAIZ = RAIZ.parent
FIXTURES = RAIZ / "fixtures"
GEOCACHE = RAIZ / "geo" / "geocache.json"


def _resolver_out():
    """Directorio de datos, en orden de confianza decreciente:

    1. $PLOMADA_OUT, si esta definida: control explicito, para pruebas o CI.
    2. <raiz-del-repo>/out/, si existe y trae contratos_atipicos.csv: es el
       contrato real que exporta pipeline/report.py (mismos 5 CSV, mismo
       esquema).
    3. fixtures/ sinteticas, como ultimo recurso.

    Se anuncia por stderr cual se eligio: si alguien publica una demo con
    fixtures creyendo que son datos reales, es un problema serio, no un
    detalle de log.
    """
    env = os.environ.get("PLOMADA_OUT")
    if env:
        print(f"[plomada/data.py] PLOMADA_OUT={env} -> usando ese directorio", file=sys.stderr)
        return Path(env)
    real = REPO_RAIZ / "out"
    if (real / "contratos_atipicos.csv").exists():
        print(f"[plomada/data.py] usando datos REALES de {real}", file=sys.stderr)
        return real
    print(f"[plomada/data.py] AVISO: no hay {real} ni $PLOMADA_OUT — "
          f"usando fixtures SINTETICAS de {FIXTURES}. Esto NO son datos reales.",
          file=sys.stderr)
    return FIXTURES


OUT = _resolver_out()

# ---------------------------------------------------------------- privacidad
# FRONT.md seccion 5. No se publican jamas, en ninguna respuesta ni artefacto.
PROHIBIDAS = frozenset({"cuenta_key", "doc_replegal", "doc_supervisor",
                        "numero_cuenta", "cuenta_bancaria"})
# doc_proveedor solo se publica si el proveedor es persona juridica (NIT).
# Zona gris: doc_ordenador es funcionario publico, pero igual mostramos el
# nombre, no el numero -> tambien se elimina del payload.
PROHIBIDAS_CONDICIONALES = frozenset({"doc_proveedor", "doc_ordenador"})

SUFIJOS_JURIDICOS = ("S.A.S", "SAS", "S.A", "LTDA", "E.S.P", "ESP", "E.S.E", "ESE",
                     "CONSORCIO", "UNION TEMPORAL", "U.T", "FUNDACION", "CORPORACION",
                     "COOPERATIVA", "ASOCIACION", "JUNTA", "S.C.A", "EMPRESA", "INSTITUTO")


def es_persona_juridica(nombre):
    n = " " + re.sub(r"[^A-Z. ]", "", (nombre or "").upper()) + " "
    return any(s in n for s in SUFIJOS_JURIDICOS)


def publicar(fila):
    """Serializador publico. Toda fila que salga hacia un artefacto pasa por aqui."""
    limpia = {k: v for k, v in fila.items() if k not in PROHIBIDAS}
    for k in PROHIBIDAS_CONDICIONALES:
        limpia.pop(k, None)
    return limpia


# ------------------------------------------------------- presentacion: texto
# El pipeline entrega MAYUSCULAS SIN TILDES. Estas siglas no se title-casean.
SIGLAS = frozenset("""ICCU ANI SENA ANH ANLA DANE DNP IDU IDU SGP SGR ESE EPS IPS ARL
UT AIU APP PGN CGR SIC UAE UNGRD INVIAS ICBF UPME UNAL UPTC UIS UDEA IE ONG SA SAS
LTDA ESP DC AA BID BM ONU OEA CAR CVC CRC CDA NIT RUT SECOP CO COP EU USA""".split())
MINUSCULAS = frozenset("de del la las el los y e en al a con por para o u da do".split())
_ROMANO = re.compile(r"^[IVXLC]+$")


def titulo(texto):
    """Title-case que no destroza siglas ni abreviaturas con punto."""
    if not texto:
        return ""
    palabras, salida = str(texto).split(), []
    for i, p in enumerate(palabras):
        nucleo = p.strip(".,;:()[]\"'")
        limpio = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜ]", "", nucleo)
        sigla = (nucleo.upper() in SIGLAS
                 or ("." in nucleo and len(limpio) <= 5)      # E.S.E., S.A.S., D.C.
                 or (limpio.isupper() and len(limpio) >= 2 and not set(limpio) & set("AEIOU"))
                 or (_ROMANO.match(nucleo) and len(nucleo) > 1))
        if sigla:
            salida.append(p.upper())
        elif i and p.lower() in MINUSCULAS:
            salida.append(p.lower())
        else:
            salida.append(p.capitalize())
    return " ".join(salida)


def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or ""))
                   if unicodedata.category(c) != "Mn").upper().strip()


NO_DEFINIDO = "NO DEFINIDO"


def ciudad_visible(ciudad):
    """'NO DEFINIDO' es dato ausente, no un municipio."""
    return None if sin_tildes(ciudad) in ("", NO_DEFINIDO, "NO APLICA") else titulo(ciudad)


# ---------------------------------------------------- presentacion: dinero
# En Colombia billon = 10^12.
_ESCALAS = ((10 ** 12, "billones", "billon"), (10 ** 9, "mil millones", "mil millones"),
            (10 ** 6, "millones", "millon"))


def _num(x, dec):
    s = f"{x:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",").replace(" ", ".")


def plata(valor, exacto=False):
    """$209 billones / $500 mil millones / $63,5 mil millones."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "sin dato"
    if exacto or abs(v) < 10 ** 6:
        return "$" + _num(v, 0)
    for corte, plural, singular in _ESCALAS:
        if abs(v) >= corte:
            n = v / corte
            dec = 0 if abs(n) >= 100 or abs(n - round(n)) < 0.05 else 1
            unidad = singular if round(abs(n), dec) == 1 else plural
            return f"${_num(n, dec)} {unidad}"
    return "$" + _num(v, 0)


def pct(x, dec=1):
    try:
        return _num(float(x) * 100, dec) + "%"
    except (TypeError, ValueError):
        return "sin dato"


def entero(x):
    try:
        return _num(float(x), 0)
    except (TypeError, ValueError):
        return "sin dato"


# ------------------------------------------------------------- urlproceso
_URL = re.compile(r"https?://[^\s'\"}\\]+")


def url_secop(bruto):
    """urlproceso llega como struct serializado: {'url': 'https://...'}."""
    if not bruto:
        return None
    try:
        v = ast.literal_eval(bruto)
        if isinstance(v, dict):
            u = v.get("url") or v.get("URL")
            if u:
                return str(u)
    except (ValueError, SyntaxError):
        pass
    m = _URL.search(str(bruto))
    return m.group(0) if m else None


# ------------------------------------------------------------------ lectura
def _n(v):
    """Numero tolerante: '' -> None, '3' -> 3, '0.42' -> 0.42."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except ValueError:
        return None
    return int(f) if f.is_integer() and abs(f) < 2 ** 53 else f


def leer_csv(nombre):
    ruta = OUT / nombre
    if not ruta.exists():
        return []
    with open(ruta, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


NUMERICAS = re.compile(r"^(valor|precio|n_|dias_|ev_|puntos|score|tasa|share|alpha|beta|"
                       r"anio|rec_|f_|es_atipico)")


def _tipar(fila):
    return {k: (_n(v) if NUMERICAS.match(k) and k != "ev_tipo_red_cuenta" else v)
            for k, v in fila.items()}


# ------------------------------------------------------------------ banderas
def glosario():
    """UNICA fuente de verdad de nombres y textos de banderas."""
    g = {}
    for r in leer_csv("banderas_glosario.csv"):
        g[r["bandera"]] = {"bandera": r["bandera"], "peso": float(r["peso"] or 0),
                           "grupo": r["grupo"] or "Otras", "glosa": r["glosa"]}
    return g


# Redes de cuenta: solo empresas_independientes es indicio fuerte.
# 'comunitaria' esta a proposito sin bandera: en el pipeline real
# (sql/02_flags.sql) ni f_cuenta_compartida ni f_cuenta_consorcios se
# encienden para ese tipo — el municipio canalizando pagos de varias JAC por
# la misma cuenta es ruido administrativo conocido, no un indicio, ni fuerte
# ni atenuado. Se deja aqui solo para que RED_CUENTA.get(tipo) no explote si
# alguna vez se llama con ese valor.
RED_CUENTA = {
    "empresas_independientes": (False, "empresas sin relacion societaria declarada"),
    "consorcios": (True, "consorcio: la cuenta suele estar a nombre del lider, es esperable"),
    "comunitaria": (True, "cuenta comunitaria: el municipio canaliza pagos, es ruido administrativo"),
}

# f_datos_faltantes (sql/02_flags.sql, E1): que campo obligatorio falta, en
# espanol llano. NUNCA el nombre de columna (doc_supervisor, etc.) ni su
# valor: test_privacy.py barre los artefactos buscando esos literales. Solo
# se comprueba presencia (r.get(campo) vacio o None), jamas se emite el dato.
CAMPOS_OBLIGATORIOS = (
    ("doc_ordenador", "la cedula del ordenador"),
    ("doc_supervisor", "la cedula del supervisor"),
    ("doc_proveedor", "el documento del proveedor"),
    ("valor", "el valor del contrato"),
    ("fecha_firma", "la fecha de firma"),
)

_DIC_FIRMA_CIERRE = re.compile(r"^\d{4}-12-(1[6-9]|2\d|3[01])$")


def _ev(r):
    """flag -> frase con el numero que la disparo. Devuelve (texto, atenuada).

    Las 22 claves de aqui abajo son, una a una, las 22 banderas de la tabla
    `pesos` de sql/03_ranking.sql — esa tabla es la fuente de verdad de
    cuales banderas existen; esta funcion solo decide COMO explicarlas.
    'sin evidencia no se publica': una bandera sin entrada aqui se sigue
    mostrando (banderas_encendidas() la absorbe con su glosa), pero sin la
    frase con el numero que la disparo.
    """
    def num(k):
        return r.get(k)
    t = {}
    if num("n_oferentes_unicos") is not None:
        n = num("n_oferentes_unicos")
        t["f_proponente_unico"] = (f"este proceso recibio {entero(n)} oferta" + ("" if n == 1 else "s"), False)
    if num("n_invitados") is not None and num("n_oferentes_unicos") is not None:
        n_of = num("n_oferentes_unicos")
        t["f_invitacion_vacia"] = (f"se invito a {entero(num('n_invitados'))} proponentes y solo "
                                   f"{entero(n_of)} presento oferta" + ("" if n_of == 1 else "s"), False)
    if num("dias_ventana") is not None and num("ev_ventana_mediana_modalidad"):
        t["f_ventana_corta"] = (f"{entero(num('dias_ventana'))} dias de ventana frente a "
                                f"{entero(num('ev_ventana_mediana_modalidad'))} de mediana en su modalidad", False)
    if num("ev_contratos_supervisor"):
        t["f_supervisor_sobrecargado"] = (f"esta persona figura en {entero(num('ev_contratos_supervisor'))} contratos a cargo", False)
    if num("ev_share_top1_ordenador") is not None:
        s = f"{pct(num('ev_share_top1_ordenador'))} del valor que autorizo fue a un solo proveedor"
        if num("ev_hhi_ordenador") is not None:
            s += f" (indice de concentracion {_num(num('ev_hhi_ordenador'), 2)})"
        t["f_ordenador_concentrado"] = (s, False)
    if num("ev_entidades_ordenador"):
        t["f_ordenador_itinerante"] = (f"ha firmado en {entero(num('ev_entidades_ordenador'))} entidades distintas", False)
    # el mismo funcionario ordena el gasto y supervisa la ejecucion. La frase
    # tiene que decir por que ESTE caso se marca y no los de una entidad
    # donde es costumbre (README, decision 11): la tasa de la entidad es la
    # que hace la diferencia entre indicio y ruido de publicacion.
    if (num("ev_tasa_autosupervision_entidad") is not None
            and r.get("doc_ordenador") and r.get("doc_ordenador") == r.get("doc_supervisor")):
        t["f_ordenador_es_supervisor"] = (
            "el mismo funcionario autoriza el gasto y supervisa la ejecucion; en esta entidad eso ocurre "
            f"en el {pct(num('ev_tasa_autosupervision_entidad'))} de los contratos — es la excepcion, no "
            "la costumbre de publicacion de la entidad", False)
    if num("ev_proveedores_por_cuenta"):
        tipo = r.get("ev_tipo_red_cuenta") or ""
        aten, nota = RED_CUENTA.get(tipo, (False, tipo.replace("_", " ")))
        t["f_cuenta_compartida"] = (f"{entero(num('ev_proveedores_por_cuenta'))} proveedores comparten "
                                    f"la misma cuenta bancaria — {nota}", aten)
        # f_cuenta_consorcios es OTRA bandera (peso 1), no una variante atenuada
        # de f_cuenta_compartida: en sql/02_flags.sql cada una es su propia
        # columna, y solo se enciende una u otra segun el tipo de red.
        if tipo == "consorcios":
            _, nota_cons = RED_CUENTA["consorcios"]
            t["f_cuenta_consorcios"] = (f"{entero(num('ev_proveedores_por_cuenta'))} proveedores del "
                                        f"consorcio comparten cuenta bancaria — {nota_cons}", True)
    if num("ev_empresas_por_replegal"):
        t["f_replegal_multiempresa"] = (f"el mismo representante legal figura en "
                                        f"{entero(num('ev_empresas_por_replegal'))} empresas proveedoras", False)
    if num("ev_hermanos_30d"):
        t["f_fraccionamiento"] = (f"{entero(num('ev_hermanos_30d'))} contratos hermanos al mismo "
                                  f"proveedor en 30 dias", False)
    if num("ev_tope_minima_entidad") and num("valor_plausible"):
        t["f_al_tope_minima"] = (f"{plata(num('valor_plausible'))} frente a un tope de minima cuantia de "
                                 f"{plata(num('ev_tope_minima_entidad'))} en esta entidad", False)
    if num("valor_plausible") and num("precio_base") and num("n_oferentes_unicos") == 1:
        ratio = num("valor_plausible") / num("precio_base")
        t["f_ratio_calcado"] = (f"adjudicado en {plata(num('valor_plausible'))} sobre un presupuesto "
                                f"oficial de {plata(num('precio_base'))} ({pct(ratio)} del presupuesto), "
                                "con un solo oferente", False)
    # f_sobrepago real (sql/02_flags.sql, C2): se PAGO mas de lo que vale el
    # contrato (valor_pagado > valor_plausible), no "se adjudico por encima
    # del precio base" — eso es f_ratio_calcado / el estudio de mercado, otra
    # bandera. Repetir la frase vieja aqui describiria una condicion que no
    # es la que en realidad prende f_sobrepago.
    if num("valor_pagado") and num("valor_plausible") and num("valor_pagado") > num("valor_plausible"):
        t["f_sobrepago"] = (f"se pagaron {plata(num('valor_pagado'))}, por encima de los "
                            f"{plata(num('valor_plausible'))} que vale el contrato segun el valor saneado", False)
    if num("valor_anticipo") and num("valor_plausible"):
        p = num("valor_anticipo") / num("valor_plausible")
        t["f_anticipo_no_declarado"] = (f"anticipo de {plata(num('valor_anticipo'))} ({pct(p)} del valor) "
                                        "girado sin que el contrato declare tener anticipo", False)
        # f_anticipo_al_tope real: agota el 50% legal, no "es alto". La frase
        # tiene que decir eso (README, decision metodologica 5): nadie puede
        # pasarse del 50% en SECOP II, lo que informa es quien lo agota.
        t["f_anticipo_al_tope"] = (f"el anticipo de {plata(num('valor_anticipo'))} agota exactamente "
                                   "el tope legal del 50% del valor del contrato", False)
    if num("dias_adicionados") and num("dias_originales"):
        p_adicion = num("dias_adicionados") / num("dias_originales")
        t["f_prorroga_mayor"] = (f"{entero(num('dias_adicionados'))} dias adicionados sobre "
                                 f"{entero(num('dias_originales'))} pactados, un {pct(p_adicion)} de adicion", False)
    if r.get("fecha_firma") and _DIC_FIRMA_CIERRE.match(r["fecha_firma"]):
        t["f_cierre_de_periodo"] = (f"firmado el {r['fecha_firma']}, en la segunda quincena de diciembre "
                                    "del ultimo anio del periodo de gobierno: contratacion de ultima hora "
                                    "antes de entregar la administracion", False)
    if not r.get("precio_base") and not r.get("urlproceso"):
        t["f_sin_proceso"] = ("no hay proceso de seleccion publicado en SECOP II al cual enlazar; "
                              "sin ficha de proceso, esto no se puede verificar en el origen", False)
    faltan = [nombre for campo, nombre in CAMPOS_OBLIGATORIOS if not r.get(campo)]
    if faltan:
        t["f_datos_faltantes"] = (f"faltan campos de publicacion obligatoria: {', '.join(faltan)}", False)
    if num("valor") and num("valor_plausible") and num("valor") != num("valor_plausible"):
        t["f_valor_implausible"] = (f"la entidad publico {plata(num('valor'))}; se usa "
                                    f"{plata(num('valor_plausible'))} como valor saneado", False)
    if r.get("modalidad"):
        t["f_obra_directa"] = (f'{titulo(r.get("tipo_contrato"))} adjudicada por '
                               f'{titulo(r["modalidad"])}, sin proceso competitivo', False)
    return t


ORDEN_GRUPOS = ["Competencia", "Red", "Dinero", "Umbrales", "Ejecucion", "Opacidad"]


def banderas_encendidas(fila, glos):
    """Banderas prendidas, agrupadas por grupo y ordenadas por peso desc.

    Una bandera que el pipeline agregue manana y no este mapeada aqui se
    muestra igual con su glosa: la UI la absorbe sola, solo sin frase numerica.
    """
    ev = _ev(fila)
    items = []
    for col, v in fila.items():
        if not col.startswith("f_") or not v:
            continue
        g = glos.get(col) or {"bandera": col, "peso": 0.0, "grupo": "Otras",
                              "glosa": "Bandera nueva del pipeline sin glosa registrada."}
        texto, atenuada = ev.get(col, (None, False))
        items.append({**g, "evidencia": texto, "atenuada": atenuada})
    items.sort(key=lambda x: (ORDEN_GRUPOS.index(x["grupo"]) if x["grupo"] in ORDEN_GRUPOS else 99,
                              -x["peso"], x["bandera"]))
    grupos = []
    for it in items:
        if not grupos or grupos[-1][0] != it["grupo"]:
            grupos.append((it["grupo"], []))
        grupos[-1][1].append(it)
    return items, grupos


# ------------------------------------------------------------------ fachada
def contratos():
    for r in leer_csv("contratos_atipicos.csv"):
        r = _tipar(r)
        r["_url"] = url_secop(r.get("urlproceso"))
        r["_ciudad"] = ciudad_visible(r.get("ciudad"))
        r["_juridica"] = es_persona_juridica(r.get("proveedor"))
        yield r


def municipios():
    return [_tipar(r) for r in leer_csv("ranking_municipios.csv")]


def departamentos():
    return [_tipar(r) for r in leer_csv("ranking_departamentos.csv")]


def administraciones():
    return [_tipar(r) for r in leer_csv("ranking_administraciones.csv")]


def slug(*partes):
    s = sin_tildes("-".join(str(p) for p in partes if p)).lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


# --------------------------------------------------------------- geocodificacion
# geocode.py (offline, con geopy) escribe geo/geocache.json; build.py solo lo lee.
# Nunca golpea la red durante el build: por eso viven en dos scripts separados.
def claves_geocodificacion(direccion, ciudad, departamento):
    """Claves de cache para un contrato: (query_exacta, clave_municipio).

    Devuelve (None, None) si no hay municipio confiable donde centrar el mapa
    (p.ej. ciudad == 'NO DEFINIDO'): sin evidencia de ubicacion no se publica mapa.
    """
    ciu = ciudad_visible(ciudad)
    if not ciu or not departamento:
        return None, None
    dep_t = titulo(departamento)
    direccion = (direccion or "").strip()
    exacta = f"{titulo(direccion)}, {ciu}, {dep_t}, Colombia" if direccion else None
    return exacta, f"{dep_t}|{ciu}"


def cargar_geocache():
    if GEOCACHE.exists():
        return json.loads(GEOCACHE.read_text(encoding="utf-8"))
    return {"exacta": {}, "municipio": {}}


def guardar_geocache(cache):
    GEOCACHE.parent.mkdir(exist_ok=True)
    GEOCACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True),
                        encoding="utf-8")


def coords_contrato(fila, geocache):
    """Coordenadas cacheadas para un contrato, o None si no se ha geocodificado.

    Nunca devuelve el fallback 'defecto' (centro de Colombia): mostrar un mapa
    generico centrado en Bogota para un contrato de otro departamento es peor
    que no mostrar mapa.
    """
    exacta, clave_mun = claves_geocodificacion(fila.get("dir_ejecucion"),
                                               fila.get("ciudad"), fila.get("departamento"))
    coords = (geocache.get("exacta", {}).get(exacta) if exacta else None) or \
             (geocache.get("municipio", {}).get(clave_mun) if clave_mun else None)
    if coords and coords.get("precision") != "defecto":
        return coords
    return None

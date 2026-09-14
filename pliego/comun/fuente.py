"""De donde salen las filas de los enfoques: fixtures (parquet) o Croma.

Los datos.py de filtro, radar y simulador no leen SECOP: leen parquet que
sus semilla.py generan con SQL sobre dos tablas del warehouse, `base`
(contratos de construccion) y `alertas` (procesos abiertos con banderas).
Este modulo arma esas dos tablas en un DuckDB en memoria a partir de Croma
y corre LAS MISMAS SQL de las semillas, asi que la fila que recibe cada
enfoque es la de siempre y ni logica.py ni app.py se enteran del cambio.

    PLIEGO_FUENTE=croma CROMA_API_KEY=croma_live_... uvicorn demo.app:app

o las mismas dos variables en el `.env` de la raiz (ver .env.example; las
lee pliego/comun/config.py). Sin ellas se leen los parquet commiteados.

Tres modos (activa()):
  fixtures   los parquet de pliego/*/fixtures/ (la demo, las pruebas)
  croma      Croma -> DuckDB EN MEMORIA para UN perfil (la demo con datos de hoy)
  warehouse  el DuckDB EN DISCO que llena la plataforma por departamento
             (pliego/comun/warehouse.py); cada empresa ve los departamentos
             de su contexto (pliego/comun/contexto.py)

Lo que se trae de Croma (todo a dataset, 1 credito por pagina de 100):
  - contratos SECOP II de los tipos de construccion, por departamento de
    interes del perfil, desde CROMA_DESDE_ANIO         -> `base`
  - procesos adjudicados con los mismos filtros: de ahi salen precio base,
    oferentes y ventana de cada contrato (el contrato no los trae) y el p10
    de dias de ventana por modalidad                   -> `procesos`
  - procesos sin adjudicar publicados en los ultimos 120 dias
                                                       -> `alertas`
Con el perfil de la demo (3 departamentos x 3 tipos x 4 anios) son del
orden de 100-300 creditos en frio; el plan Free trae 5.000 al mes. Cada
busqueda se cachea en $PLATAFORMA_DATOS/cache/croma/ por CROMA_CACHE_HORAS
(24): el segundo arranque del dia no gasta creditos ni espera.

Banderas de `alertas` que NO se pueden calcular con Croma y quedan en NULL
(la logica del filtro ya trata NULL como "no se sabe"): f_al_tope_minima
(pide el p99 de minima cuantia por entidad y anio, que no esta en lo
traido) y f_cierre_movido (pide el snapshot de ayer). Ver
docs/enfoques/croma.md.
"""
from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import duckdb
import pyarrow as pa

from pliego.comun import config as CFG
from pliego.comun import mapeo_croma as M

RAIZ = Path(__file__).resolve().parents[1]
# Los fixtures se calcularon contra esta fecha; con fixtures es "hoy".
FECHA_SNAPSHOT = date(2026, 8, 22)
TIPOS_CONSTRUCCION = ("Obra", "Interventoría", "Consultoría")
DIAS_ABIERTOS = 120   # cuan atras buscar procesos sin adjudicar
# Cada busqueda (todas sus paginas) se guarda en disco (config.cache_croma)
# y se reutiliza mientras sea del mismo dia: SECOP en Croma se refresca a
# diario y una pagina tarda hasta 30 s, asi que sin cache cada arranque son
# minutos.

# Croma filtra `department` "como SECOP lo escribe"; el perfil lo guarda
# normalizado (MAYUSCULAS sin tildes). Los que no esten aqui se pasan en
# Tipo Oracion, que acierta para la mayoria de departamentos.
DEPARTAMENTOS_SECOP = {
    "BOGOTA D.C.": "Bogotá D.C.", "BOGOTA": "Bogotá D.C.", "DISTRITO CAPITAL DE BOGOTA": "Bogotá D.C.",
    "NORTE DE SANTANDER": "Norte de Santander", "VALLE DEL CAUCA": "Valle del Cauca",
    "BOYACA": "Boyacá", "ATLANTICO": "Atlántico", "BOLIVAR": "Bolívar", "CORDOBA": "Córdoba",
    "CAQUETA": "Caquetá", "CHOCO": "Chocó", "GUAINIA": "Guainía", "VAUPES": "Vaupés",
    "QUINDIO": "Quindío", "NARINO": "Nariño",
    "SAN ANDRES, PROVIDENCIA Y SANTA CATALINA": "San Andrés, Providencia y Santa Catalina",
}


# ------------------------------------------------------------------ conmutador
def activa() -> str:
    """'croma' si se pidio y hay llave; 'warehouse' si se pidio y hay una
    empresa en contexto (sin contexto, p. ej. en pruebas, caen los fixtures);
    'fixtures' en cualquier otro caso."""
    modo = CFG.actual().pliego_fuente
    if modo == "croma":
        from pliego.comun import croma
        if croma.disponible():
            return "croma"
    if modo == "warehouse":
        from pliego.comun import contexto
        if contexto.get() is not None:
            return "warehouse"
    return "fixtures"


def hoy() -> date:
    return FECHA_SNAPSHOT if activa() == "fixtures" else date.today()


def etiqueta_fecha() -> str:
    """Para las cabeceras de los enfoques: de cuando son los datos."""
    if activa() == "fixtures":
        return f"snapshot {FECHA_SNAPSHOT.isoformat()} (se toma como hoy)"
    as_of = str(estado().get("as_of") or "")[:10]
    return f"datos al {as_of}" if as_of else "datos de hoy"


def filas(enfoque: str, nombre: str) -> list[dict]:
    """Las filas que `pliego/<enfoque>/fixtures/<nombre>.parquet` tendria:
    del parquet, o de Croma / del warehouse a traves de la misma SQL de la
    semilla."""
    modo = activa()
    if modo == "croma":
        return _consultar(_SEMILLAS[(enfoque, nombre)]())
    if modo == "warehouse":
        from pliego.comun import contexto, warehouse
        return warehouse.consultar(_SEMILLAS[(enfoque, nombre)](), contexto.ambito())
    return _parquet(RAIZ / enfoque / "fixtures" / f"{nombre}.parquet")


def estado() -> dict:
    """Para mostrar en la demo o en logs: que fuente, de cuando, cuanto."""
    modo = activa()
    if modo == "warehouse":
        from pliego.comun import contexto, warehouse
        return {"fuente": "warehouse", **warehouse.estado(contexto.ambito())}
    if modo != "croma":
        return {"fuente": "fixtures", "as_of": FECHA_SNAPSHOT.isoformat()}
    con, meta = _db()
    cur = con.cursor()
    n_base = cur.execute("SELECT count(*) FROM base").fetchone()[0]
    n_abiertos = cur.execute("SELECT count(*) FROM alertas WHERE universo = 'accionable'").fetchone()[0]
    return {"fuente": "croma", **meta, "n_base": n_base, "n_abiertos": n_abiertos}


# ---------------------------------------------------------------- las SQL
def _sql(modulo: str, constante: str):
    def carga():
        import importlib
        return getattr(importlib.import_module(f"pliego.{modulo}.semilla"), constante)
    return carga


_SEMILLAS = {
    ("filtro", "procesos_abiertos"): _sql("filtro", "PROCESOS"),
    ("filtro", "entidades_historial"): _sql("filtro", "ENTIDADES"),
    ("filtro", "entidad_familia"): _sql("filtro", "ENTIDAD_FAMILIA"),
    ("filtro", "unspsc_frecuencia"): _sql("filtro", "UNSPSC"),
    ("radar", "contratos"): _sql("radar", "CONTRATOS"),
    ("radar", "abiertos"): _sql("radar", "ABIERTOS"),
    ("simulador", "historico"): _sql("simulador", "HISTORICO"),
    ("simulador", "abiertos"): _sql("simulador", "ABIERTOS"),
}


def _parquet(ruta: Path) -> list[dict]:
    cur = duckdb.connect().execute(f"SELECT * FROM '{ruta}'")
    return _dicts(cur)


def _consultar(sql: str) -> list[dict]:
    con, _ = _db()
    # Un cursor por consulta: una conexion DuckDB no se comparte entre hilos
    # (el simulador precalienta en uno mientras la web responde en otro) y
    # compartirla devuelve resultados vacios al azar.
    return _dicts(con.cursor().execute(sql))


def _dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    out = []
    for t in cur.fetchall():
        f = dict(zip(cols, t))
        for k, v in f.items():
            if isinstance(v, date):
                f[k] = v.isoformat()
        out.append(f)
    return out


# ------------------------------------------------------------ Croma -> DuckDB
ESQUEMA_BASE = pa.schema([
    ("id_contrato", pa.string()), ("notice_uid", pa.string()), ("nit_entidad", pa.string()),
    ("entidad", pa.string()), ("departamento", pa.string()), ("ciudad", pa.string()),
    ("orden", pa.string()), ("modalidad", pa.string()), ("tipo_contrato", pa.string()),
    ("unspsc", pa.string()), ("descripcion", pa.string()), ("precio_base", pa.float64()),
    ("valor_adjudicado", pa.float64()), ("valor_plausible", pa.float64()),
    ("n_oferentes_unicos", pa.int64()), ("n_respuestas", pa.int64()),
    ("fecha_firma", pa.string()), ("fecha_inicio", pa.string()), ("fecha_fin", pa.string()),
    ("fecha_cierre_ofertas", pa.string()), ("estado", pa.string()), ("anio", pa.int64()),
    ("doc_proveedor", pa.string()), ("proveedor", pa.string()), ("es_grupo", pa.string()),
    ("valor_pagado", pa.float64()), ("valor_pend_ejecucion", pa.float64()),
])

ESQUEMA_PROCESO = pa.schema([
    ("id_del_proceso", pa.string()), ("notice_uid", pa.string()), ("urlproceso", pa.string()),
    ("nit_entidad", pa.string()), ("entidad", pa.string()), ("departamento", pa.string()),
    ("ciudad", pa.string()), ("tipo_contrato", pa.string()), ("modalidad", pa.string()),
    ("unspsc", pa.string()), ("descripcion", pa.string()), ("precio_base", pa.float64()),
    ("valor_adjudicado", pa.float64()), ("adjudicado", pa.bool_()),
    ("n_invitados", pa.int64()), ("n_manifestaron", pa.int64()), ("n_respuestas", pa.int64()),
    ("n_oferentes_unicos", pa.int64()), ("fecha_publicacion", pa.string()),
    ("fecha_cierre", pa.string()), ("fecha_adjudicacion", pa.string()),
    ("dias_ventana", pa.int64()), ("dias_restantes", pa.int64()),
])

# Las banderas del filtro, con la misma definicion que
# legacy/plomada/sql/30_procesos_abiertos.sql pero sobre lo que Croma deja
# calcular. Las mismas expresiones sirven al DuckDB en memoria (modo croma:
# tablas `procesos`, `base`, `abiertos` con dias ya calculados) y a la vista
# del warehouse en disco (tablas `*_todo` y dias contra current_date), asi
# que se generan desde un solo sitio y no pueden divergir.
def sql_agregados(procesos: str = "procesos", base: str = "base") -> str:
    """base_ventana (p10 de dias de ventana por modalidad) e hist_unico (tasa
    de proponente unico por entidad), a partir de las tablas dadas."""
    return f"""
CREATE OR REPLACE TABLE base_ventana AS
SELECT modalidad, quantile_cont(dias_ventana, 0.10) AS p10, count(*) AS n
FROM {procesos} WHERE dias_ventana IS NOT NULL AND dias_ventana >= 0
GROUP BY 1 HAVING count(*) >= 5;

CREATE OR REPLACE TABLE hist_unico AS
SELECT nit_entidad,
       avg(CASE WHEN n_oferentes_unicos <= 1 THEN 1 ELSE 0 END) AS tasa,
       count(*) AS n_historico
FROM {base}
WHERE n_oferentes_unicos IS NOT NULL AND modalidad NOT LIKE 'CONTRATACION DIRECTA%'
GROUP BY 1 HAVING count(*) >= 5;
"""


def sql_banderas(dias_ventana: str = "a.dias_ventana", dias_restantes: str = "a.dias_restantes") -> str:
    """Las columnas de banderas sobre un alias `a` (procesos abiertos) con
    `v` (base_ventana) y `h` (hist_unico) ya unidos; `dias_ventana` y
    `dias_restantes` son expresiones SQL. f_al_tope_minima y f_cierre_movido
    quedan NULL con Croma (ver el docstring del modulo)."""
    corta = f"({dias_ventana} IS NOT NULL AND v.p10 IS NOT NULL AND {dias_ventana} <= v.p10)"
    sin_interes = f"(coalesce(a.n_invitados, 0) >= 5 AND coalesce(a.n_manifestaron, 0) = 0 AND {dias_restantes} BETWEEN 0 AND 7)"
    return f"""
       CASE WHEN a.fecha_cierre IS NULL THEN 'sin_fecha_cierre'
            WHEN {dias_restantes} < 0 THEN 'cierre_vencido'
            ELSE 'accionable' END                                            AS universo,
       {corta}                                                               AS f_ventana_corta,
       CAST(NULL AS BOOLEAN)                                                 AS f_al_tope_minima,
       (h.tasa >= 0.80)                                                      AS f_historial_proponente_unico,
       h.tasa                                                                AS ev_tasa_historica_entidad,
       h.n_historico                                                         AS ev_n_historico_entidad,
       {sin_interes}                                                         AS f_sin_interes_a_tiempo,
       CAST(NULL AS BOOLEAN)                                                 AS f_cierre_movido,
       ( coalesce({corta}::INT, 0) + coalesce((h.tasa >= 0.80)::INT, 0) + coalesce({sin_interes}::INT, 0) ) AS n_banderas"""


SQL_ALERTAS = sql_agregados() + f"""
CREATE OR REPLACE TABLE alertas AS
SELECT a.*, {sql_banderas()}
FROM abiertos a
LEFT JOIN base_ventana v ON v.modalidad = a.modalidad
LEFT JOIN hist_unico h ON h.nit_entidad = a.nit_entidad;
"""


_CANDADO = threading.Lock()


def _db():
    """El DuckDB en memoria con `base`, `procesos`, `abiertos` y `alertas`
    armadas desde Croma. Se construye una vez por proceso: el candado es
    porque el simulador precalienta en un hilo al importar y, sin el, dos
    hilos descargarian todo a la vez (el doble de creditos)."""
    with _CANDADO:
        return _db_cacheada()


@lru_cache(maxsize=1)
def _db_cacheada():
    from pliego.comun import croma
    api = croma.CromaCliente()
    perfil = _perfil()
    contratos, adjudicados, abiertos, errores = _traer(api, perfil)
    return _armar(contratos, adjudicados, abiertos, hoy(), meta={
        "as_of": max((p.get("_as_of") or "" for p in adjudicados + abiertos), default=None),
        "creditos_restantes": api.creditos_restantes, "llamadas": api.llamadas,
        "errores": errores,
    })


def registros_a_filas(contratos: list[dict], adjudicados: list[dict], abiertos: list[dict], hoy: date):
    """Puro (sin red): registros Croma -> (base, procesos, abiertos) como
    filas del warehouse. Cada contrato se enlaza con su proceso adjudicado
    por notice_uid (o process_id) para heredar precio base y oferentes."""
    procesos = [M.proceso_a_fila(r, hoy) for r in adjudicados]
    por_uid = {p["notice_uid"]: p for p in procesos if p.get("notice_uid")}
    por_id = {p["id_del_proceso"]: p for p in procesos if p.get("id_del_proceso")}
    base = []
    for r in contratos:
        uid = M.notice_uid(*(r.get(n) for n in M.ALIAS["proceso_id"]))
        pid = M.id_proceso({"process_id": r.get("process_id")}) if r.get("process_id") else None
        base.append(M.contrato_a_fila(r, por_uid.get(uid) or por_id.get(pid)))
    return base, procesos, [M.proceso_a_fila(r, hoy) for r in abiertos]


def _armar(contratos: list[dict], adjudicados: list[dict], abiertos: list[dict], hoy: date, meta=None):
    """Registros Croma -> tablas en un DuckDB en memoria (modo croma).
    Separado de _db para que las pruebas lo alimenten con dicts."""
    base, procesos, abiertos_f = registros_a_filas(contratos, adjudicados, abiertos, hoy)
    con = duckdb.connect()
    con.register("_base", pa.Table.from_pylist(base, schema=ESQUEMA_BASE))
    con.register("_procesos", pa.Table.from_pylist(procesos, schema=ESQUEMA_PROCESO))
    con.register("_abiertos", pa.Table.from_pylist(abiertos_f, schema=ESQUEMA_PROCESO))
    con.execute("""
        CREATE TABLE base AS SELECT * REPLACE (
            try_cast(fecha_firma AS DATE) AS fecha_firma, try_cast(fecha_inicio AS DATE) AS fecha_inicio,
            try_cast(fecha_fin AS DATE) AS fecha_fin,
            try_cast(fecha_cierre_ofertas AS DATE) AS fecha_cierre_ofertas) FROM _base;
        CREATE TABLE procesos AS SELECT * REPLACE (
            try_cast(fecha_publicacion AS DATE) AS fecha_publicacion,
            try_cast(fecha_cierre AS DATE) AS fecha_cierre,
            try_cast(fecha_adjudicacion AS DATE) AS fecha_adjudicacion) FROM _procesos;
        CREATE TABLE abiertos AS SELECT * REPLACE (
            try_cast(fecha_publicacion AS DATE) AS fecha_publicacion,
            try_cast(fecha_cierre AS DATE) AS fecha_cierre,
            try_cast(fecha_adjudicacion AS DATE) AS fecha_adjudicacion) FROM _abiertos;
    """)
    con.execute(SQL_ALERTAS)
    return con, (meta or {})


def consultas_para(departamentos, desde: str | None = None, desde_abiertos: str | None = None) -> list[tuple]:
    """Las tres busquedas (contratos, adjudicados, abiertos) por departamento
    y tipo de contrato: lista de (destino, ruta, cuerpo). `desde` es la
    fecha desde la que traer historico (por defecto CROMA_DESDE_ANIO o hace
    4 anios); `desde_abiertos`, la de los procesos sin adjudicar (120 dias).
    Con departamentos vacio consulta todo el pais (caro: no lo hace nadie
    por defecto)."""
    if desde is None:
        desde = f"{CFG.actual().croma_desde_anio or hoy().year - 4}-01-01"
    if desde_abiertos is None:
        desde_abiertos = (hoy() - timedelta(days=DIAS_ABIERTOS)).isoformat()
    deptos = [_depto_secop(d) for d in departamentos] or [None]
    consultas = []
    for depto in deptos:
        comun = {"platform": "secop_ii"}
        if depto:
            comun["department"] = depto
        for tipo in TIPOS_CONSTRUCCION:
            consultas += [
                ("contratos", "/co/secop/contracts-search/v1",
                 {**comun, "contract_type": tipo, "from_date": desde}),
                ("adjudicados", "/co/secop/processes-search/v1",
                 {**comun, "contract_type": tipo, "from_date": desde, "awarded": "yes"}),
                ("abiertos", "/co/secop/processes-search/v1",
                 {**comun, "contract_type": tipo, "from_date": desde_abiertos, "awarded": "no",
                  "sort": "recent"}),
            ]
    return consultas


def traer(api, consultas: list[tuple]):
    """Ejecuta las consultas en paralelo y con cache en disco. Devuelve
    (contratos, adjudicados, abiertos, errores). Cada registro lleva
    `_as_of` de su pagina para saber de cuando es lo que se muestra."""
    salida = {"contratos": [], "adjudicados": [], "abiertos": []}
    errores = []

    def una(c):
        # Una busqueda que falla (timeout persistente, 402) no tumba el
        # arranque: se anota y se sigue con lo demas. estado() lo muestra.
        try:
            return _paginas(api, c[1], c[2])
        except Exception as e:   # CromaError o lo que sea que rompa una pagina
            errores.append({"consulta": c[2], "error": str(e)[:200]})
            return []

    with ThreadPoolExecutor(max_workers=max(1, CFG.actual().croma_hilos)) as pool:
        for (destino, _, _), filas in zip(consultas, pool.map(una, consultas)):
            salida[destino] += filas
    return salida["contratos"], salida["adjudicados"], salida["abiertos"], errores


def _traer(api, perfil: dict):
    """Modo croma: las consultas del perfil (de la demo o del contexto)."""
    return traer(api, consultas_para(perfil.get("departamentos_interes") or []))


def _paginas(api, ruta, cuerpo) -> list[dict]:
    """Todas las paginas de una busqueda, del cache del dia si existe."""
    llave = _llave_cache(ruta, cuerpo)
    en_cache = _leer_cache(llave)
    if en_cache is not None:
        return en_cache
    filas = list(api.paginar(ruta, cuerpo))
    _escribir_cache(llave, filas)
    return filas


def _llave_cache(ruta, cuerpo) -> Path:
    firma = hashlib.sha1((ruta + json.dumps(cuerpo, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()[:16]
    return CFG.actual().cache_croma / f"{ruta.strip('/').replace('/', '_')}-{firma}.json"


def _leer_cache(llave: Path):
    horas = float(CFG.actual().croma_cache_horas)
    if horas <= 0 or not llave.exists():
        return None
    edad = datetime.now() - datetime.fromtimestamp(llave.stat().st_mtime)
    if edad > timedelta(hours=horas):
        return None
    try:
        return json.loads(llave.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _escribir_cache(llave: Path, filas: list[dict]):
    try:
        llave.parent.mkdir(parents=True, exist_ok=True)
        llave.write_text(json.dumps(filas, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass   # sin cache se sigue igual, solo mas lento la proxima vez


def _depto_secop(d: str) -> str:
    n = M.norm_txt(d) or ""
    return DEPARTAMENTOS_SECOP.get(n) or " ".join(
        w if w in ("de", "del", "y") else w.capitalize() for w in n.lower().split())


def _perfil() -> dict:
    """El perfil de la constructora manda que departamentos traer. Hoy es el
    del filtro (los cinco enfoques comparten el mismo ficticio)."""
    return json.loads((RAIZ / "filtro" / "fixtures" / "perfil_constructora.json").read_text(encoding="utf-8"))

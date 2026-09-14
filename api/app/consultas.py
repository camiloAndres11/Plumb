"""Capa de consulta. Es la UNICA que escribe SQL en todo el servicio.

La usan los dos frentes de serving:
  - los routers del API REST (app/routers/*), y
  - las tools del servidor MCP (app/mcp/server.py).

Antes cada uno tenia su propio SQL: el umbral de "atipico" estaba escrito
a mano en el MCP y habria vuelto a escribirse en cada endpoint nuevo.
Ahora el umbral vive en sql/90_serving.sql (columna `es_atipico`) y las
consultas viven aqui.

SEGURIDAD DE LAS CONSULTAS
--------------------------
Ningun valor que venga del cliente se interpola en el SQL: todos van como
parametros (%s). Lo unico que se concatena son fragmentos elegidos de
listas blancas definidas en este archivo -- nombres de columna para
ordenar y nombres de bandera para filtrar. Si el valor no esta en la
lista, la funcion levanta ValueError y el router responde 400 sin haber
tocado la base.
"""
from __future__ import annotations

import functools

from app.config import config
from app.db import consultar, consultar_uno, contar, existe_tabla

# Columnas de la ficha resumida. Enumeradas, no SELECT *: lo que sale por
# HTTP se decide aqui y no cambia porque alguien agregue una columna
# aguas arriba.
_RESUMEN = """
  id_contrato, entidad, nit_entidad, departamento, ciudad, tipo_contrato,
  modalidad, tipo_obra, anio, fecha_firma, proveedor, doc_proveedor,
  valor, valor_plausible, es_atipico, puntos_crudos, n_banderas_fuertes,
  puntos_red, n_banderas_red_fuertes, score, urlproceso
"""

# Orden -> fragmento ORDER BY. El cliente manda la llave, nunca la columna.
# Todos terminan en id_contrato para que la paginacion sea estable: sin un
# desempate deterministico, dos paginas pueden repetir u omitir filas.
ORDENES_CONTRATO = {
    "-riesgo": "n_banderas_fuertes DESC, puntos_crudos DESC, valor_plausible DESC NULLS LAST",
    "riesgo": "n_banderas_fuertes ASC, puntos_crudos ASC",
    "-valor": "valor_plausible DESC NULLS LAST",
    "valor": "valor_plausible ASC NULLS LAST",
    "-fecha": "fecha_firma DESC NULLS LAST",
    "fecha": "fecha_firma ASC NULLS LAST",
    "-score": "score DESC NULLS LAST",
}

ORDENES_ENTIDAD = {
    "-valor": "valor_total DESC NULLS LAST",
    "-contratos": "n_contratos DESC",
    "-atipicos": "n_atipicos DESC",
    "-tasa": "tasa_atipicos DESC NULLS LAST",
}

ORDENES_PROVEEDOR = {
    "-valor": "valor_total DESC NULLS LAST",
    "-contratos": "n_contratos DESC",
    "-entidades": "n_entidades DESC NULLS LAST",
}

ORDENES_MUNICIPIO = {
    "-tasa_ajustada": "tasa_ajustada DESC NULLS LAST",
    "-tasa_cruda": "tasa_cruda DESC NULLS LAST",
    "-valor_atipico": "valor_atipico DESC NULLS LAST",
    "-contratos": "n_contratos DESC",
}

UNIVERSOS_ALERTA = ("accionable", "zombie_vencido", "sin_fecha_cierre")


def _orden(clave, permitidos, defecto, desempate):
    if clave is None:
        clave = defecto
    if clave not in permitidos:
        raise ValueError(
            "orden '%s' no permitido; usa uno de: %s"
            % (clave, ", ".join(sorted(permitidos)))
        )
    return permitidos[clave] + ", " + desempate


def _pagina(limite, desplazamiento):
    limite = max(1, min(int(limite or config.limite_default), config.limite_max))
    return limite, max(0, int(desplazamiento or 0))


# ---------------------------------------------------------------------
# Glosario de banderas. Se cachea: son 26 filas que solo cambian cuando
# se recarga la base, y se consultan en cada ficha de contrato.
# ---------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def glosario():
    return consultar(
        "SELECT bandera, peso, grupo, glosa, capa, evidencia FROM api_banderas "
        "ORDER BY peso DESC, capa, bandera"
    )


@functools.lru_cache(maxsize=1)
def _glosario_por_nombre():
    return {b["bandera"]: b for b in glosario()}


def nombres_banderas():
    return set(_glosario_por_nombre())


def _validar_banderas(banderas):
    validas = nombres_banderas()
    for b in banderas or []:
        if b not in validas:
            raise ValueError(
                "bandera '%s' no existe; consulta el glosario en GET /v1/banderas" % b
            )
    return list(banderas or [])


def banderas_encendidas(fila):
    """Nombres de las banderas activas en una fila de api_contratos."""
    return [b for b in _glosario_por_nombre() if fila.get(b)]


def _partes(f: dict) -> dict:
    """Las cedulas de ordenador, supervisor y representante legal se quedan
    en la base: solo sale su presencia y si ordenador y supervisor coinciden
    (lo que f_datos_faltantes y f_ordenador_es_supervisor necesitan)."""
    def hay(k):
        v = f.get(k)
        return v is not None and str(v).strip() != ""
    return {
        "proveedor": f.get("proveedor"), "doc_proveedor": f.get("doc_proveedor"),
        "ordenador": f.get("ordenador"), "supervisor": f.get("supervisor"),
        "tiene_doc_ordenador": hay("doc_ordenador"),
        "tiene_doc_supervisor": hay("doc_supervisor"),
        "tiene_doc_replegal": hay("doc_replegal"),
        "mismo_ordenador_supervisor": hay("doc_ordenador") and str(f.get("doc_ordenador")).strip() == str(f.get("doc_supervisor") or "").strip(),
    }


def _detalle_banderas(fila):
    """Banderas encendidas + los numeros ev_* que las sustentan.

    El mapeo bandera -> columnas de evidencia sale de la tabla
    api_banderas, no de un diccionario en Python: agregar una bandera en
    sql/03_ranking.sql y su evidencia en el paso 90 basta para que
    aparezca aqui.
    """
    salida = []
    for nombre, g in _glosario_por_nombre().items():
        if not fila.get(nombre):
            continue
        evidencia = {}
        for col in (g["evidencia"] or "").split(","):
            col = col.strip()
            if col and fila.get(col) is not None:
                evidencia[col] = fila[col]
        salida.append({
            "bandera": nombre,
            "peso": g["peso"],
            "grupo": g["grupo"],
            "capa": g["capa"],
            "glosa": g["glosa"],
            "evidencia": evidencia,
        })
    salida.sort(key=lambda b: (-b["peso"], b["bandera"]))
    return salida


# ---------------------------------------------------------------------
# Metadatos
# ---------------------------------------------------------------------
def meta():
    m = consultar_uno("SELECT * FROM api_meta WHERE id = 1") or {}
    return {
        "contratos": m.get("contratos", 0),
        "valor_total": m.get("valor_total"),
        "contratos_atipicos": m.get("contratos_atipicos", 0),
        "n_clusters": m.get("n_clusters", 0),
        "n_proveedores": m.get("n_proveedores", 0),
        "n_entidades": m.get("n_entidades", 0),
        "primer_anio": m.get("primer_anio"),
        "ultimo_anio": m.get("ultimo_anio"),
        "cobertura": {
            "cedula_ordenador": m.get("cobertura_cedula_ordenador"),
            "cedula_supervisor": m.get("cobertura_cedula_supervisor"),
            "cuenta_bancaria": m.get("cobertura_cuenta_bancaria"),
            "unido_a_proceso": m.get("cobertura_unido_a_proceso"),
            "tipo_obra": m.get("cobertura_tipo_obra"),
        },
        "limitaciones": [
            r["texto"] for r in
            consultar("SELECT texto FROM api_limitaciones ORDER BY orden")
        ],
        "construido": m.get("construido"),
    }


# ---------------------------------------------------------------------
# Agregados. Son tablas chicas (6 a 1.100 filas) y se devuelven enteras
# salvo municipios, que si pagina.
# ---------------------------------------------------------------------
def titulares():
    return consultar("SELECT concepto, n_contratos, valor FROM api_titulares")


def indicios():
    return consultar("SELECT indicio, grupo, n_contratos, valor FROM api_indicios ORDER BY valor DESC")


def departamentos():
    return consultar("SELECT * FROM api_departamentos ORDER BY total DESC NULLS LAST")


def tipos_obra():
    return consultar("SELECT * FROM api_tipos_obra ORDER BY total DESC NULLS LAST")


def fuentes():
    return consultar("SELECT * FROM api_fuentes ORDER BY total DESC NULLS LAST")


def autosupervision():
    return consultar("SELECT * FROM api_autosupervision ORDER BY valor_auto DESC NULLS LAST")


def municipios(departamento=None, min_contratos=20, orden=None, limite=None, desplazamiento=0):
    """El tablero recorta a los 60 primeros con n>=20; aqui el minimo es
    un parametro, porque un municipio chico puede ser justo el que le
    interesa a quien consulta. El defecto sigue siendo 20 para no
    encabezar la lista con ruido estadistico."""
    limite, desplazamiento = _pagina(limite, desplazamiento)
    orden_sql = _orden(orden, ORDENES_MUNICIPIO, "-tasa_ajustada", "ciudad")
    cond, params = ["n_contratos >= %s"], [int(min_contratos or 0)]
    if departamento:
        cond.append("departamento ILIKE %s")
        params.append("%%%s%%" % departamento)
    where = " AND ".join(cond)
    total = contar("api_municipios", where, params)
    filas = consultar(
        "SELECT * FROM api_municipios WHERE %s ORDER BY %s LIMIT %%s OFFSET %%s"
        % (where, orden_sql),
        params + [limite, desplazamiento],
    )
    return filas, total


# ---------------------------------------------------------------------
# Contratos
# ---------------------------------------------------------------------
def _filtros_contrato(
    entidad=None, nit_entidad=None, departamento=None, ciudad=None,
    tipo_contrato=None, modalidad=None, tipo_obra=None, anio=None,
    anio_desde=None, anio_hasta=None, proveedor=None, doc_proveedor=None,
    valor_min=None, valor_max=None, banderas=None, solo_atipicos=False,
    cluster_id=None, texto=None,
):
    cond, params = [], []

    def like(col, valor):
        cond.append("%s ILIKE %%s" % col)
        params.append("%%%s%%" % valor)

    def igual(col, valor):
        cond.append("%s = %%s" % col)
        params.append(valor)

    if entidad:
        like("entidad", entidad)
    if nit_entidad:
        igual("nit_entidad", nit_entidad)
    if departamento:
        like("departamento", departamento)
    if ciudad:
        like("ciudad", ciudad)
    if tipo_contrato:
        igual("tipo_contrato", tipo_contrato.upper())
    if modalidad:
        like("modalidad", modalidad)
    if tipo_obra:
        igual("tipo_obra", tipo_obra.upper())
    if anio is not None:
        igual("anio", int(anio))
    if anio_desde is not None:
        cond.append("anio >= %s")
        params.append(int(anio_desde))
    if anio_hasta is not None:
        cond.append("anio <= %s")
        params.append(int(anio_hasta))
    if proveedor:
        like("proveedor", proveedor)
    if doc_proveedor:
        igual("doc_proveedor", doc_proveedor)
    if cluster_id is not None:
        igual("cluster_id", int(cluster_id))
    if valor_min is not None:
        cond.append("valor_plausible >= %s")
        params.append(float(valor_min))
    if valor_max is not None:
        cond.append("valor_plausible <= %s")
        params.append(float(valor_max))
    if texto:
        like("descripcion", texto)
    if solo_atipicos:
        cond.append("es_atipico")
    # El nombre de la bandera se concatena, pero solo despues de pasar por
    # la lista blanca del glosario: no puede llegar SQL por aqui.
    for b in _validar_banderas(banderas):
        cond.append("%s IS TRUE" % b)

    return (" AND ".join(cond) if cond else ""), params


def buscar_contratos(orden=None, limite=None, desplazamiento=0, **filtros):
    limite, desplazamiento = _pagina(limite, desplazamiento)
    orden_sql = _orden(orden, ORDENES_CONTRATO, "-riesgo", "id_contrato")
    where, params = _filtros_contrato(**filtros)
    total = contar("api_contratos", where, params)
    columnas = _RESUMEN + ", " + ", ".join(sorted(nombres_banderas()))
    sql = "SELECT %s FROM api_contratos" % columnas
    if where:
        sql += " WHERE " + where
    sql += " ORDER BY %s LIMIT %%s OFFSET %%s" % orden_sql
    filas = consultar(sql, params + [limite, desplazamiento])
    salida = []
    for f in filas:
        encendidas = banderas_encendidas(f)
        fila = {k: f[k] for k in f if not k.startswith(("f_", "g_"))}
        fila["banderas"] = encendidas
        salida.append(fila)
    return salida, total


def contrato(id_contrato):
    """Ficha completa, con la evidencia numerica de cada bandera. Este es
    el endpoint donde 'sin evidencia no se publica' deja de ser una frase
    del README y pasa a ser el contrato de la API."""
    f = consultar_uno("SELECT * FROM api_contratos WHERE id_contrato = %s", [id_contrato])
    if not f:
        return None
    campo = lambda *ks: {k: f.get(k) for k in ks}  # noqa: E731
    return {
        "id_contrato": f["id_contrato"],
        "urlproceso": f.get("urlproceso"),
        **campo("entidad", "nit_entidad", "departamento", "ciudad", "orden",
                "tipo_contrato", "modalidad", "estado", "unspsc", "tipo_obra",
                "descripcion", "dir_ejecucion", "fecha_firma", "anio",
                "periodo_gobierno"),
        "dinero": campo("valor", "valor_plausible", "valor_pagado",
                        "valor_pend_ejecucion", "valor_anticipo", "precio_base",
                        "rec_regalias", "rec_sgp", "rec_propios_terr"),
        "competencia": campo("n_oferentes_unicos", "n_invitados", "dias_ventana",
                             "dias_originales", "dias_adicionados"),
        "partes": _partes(f),
        "riesgo": campo("es_atipico", "puntos_crudos", "score", "n_banderas_fuertes",
                        "puntos_red", "n_banderas_red_fuertes", "cluster_id",
                        "tamano_cluster"),
        "banderas": _detalle_banderas(f),
    }


# ---------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------
def buscar_entidades(texto=None, departamento=None, min_contratos=None,
                     orden=None, limite=None, desplazamiento=0):
    limite, desplazamiento = _pagina(limite, desplazamiento)
    orden_sql = _orden(orden, ORDENES_ENTIDAD, "-valor", "nit_entidad")
    cond, params = [], []
    if texto:
        # nombre parcial o NIT exacto: quien consulta rara vez sabe cual tiene
        cond.append("(entidad ILIKE %s OR nit_entidad = %s)")
        params += ["%%%s%%" % texto, texto]
    if departamento:
        cond.append("departamento ILIKE %s")
        params.append("%%%s%%" % departamento)
    if min_contratos:
        cond.append("n_contratos >= %s")
        params.append(int(min_contratos))
    where = " AND ".join(cond)
    total = contar("api_entidades", where, params)
    sql = "SELECT * FROM api_entidades"
    if where:
        sql += " WHERE " + where
    sql += " ORDER BY %s LIMIT %%s OFFSET %%s" % orden_sql
    return consultar(sql, params + [limite, desplazamiento]), total


def entidad(nit_entidad):
    e = consultar_uno("SELECT * FROM api_entidades WHERE nit_entidad = %s", [nit_entidad])
    if not e:
        return None
    conteos = consultar(
        "SELECT " + ", ".join(
            "count(*) FILTER (WHERE %s) AS %s" % (b, b) for b in sorted(nombres_banderas())
        ) + " FROM api_contratos WHERE nit_entidad = %s",
        [nit_entidad],
    )[0]
    g = _glosario_por_nombre()
    frecuentes = sorted(
        ({"bandera": b, "glosa": g[b]["glosa"], "peso": g[b]["peso"], "n_contratos": n}
         for b, n in conteos.items() if n),
        key=lambda x: (-x["n_contratos"], -x["peso"]),
    )[:10]
    top = consultar(
        """SELECT doc_proveedor, max(proveedor) AS proveedor, count(*) AS n_contratos,
                  sum(valor_plausible) AS valor_total,
                  count(*) FILTER (WHERE es_atipico) AS n_atipicos
           FROM api_contratos WHERE nit_entidad = %s AND doc_proveedor IS NOT NULL
           GROUP BY doc_proveedor
           ORDER BY sum(valor_plausible) DESC NULLS LAST LIMIT 10""",
        [nit_entidad],
    )
    return {**e, "banderas_frecuentes": frecuentes, "top_proveedores": top}


# ---------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------
def buscar_proveedores(texto=None, hace_ambos=None, cluster_id=None,
                       min_contratos=None, orden=None, limite=None, desplazamiento=0):
    limite, desplazamiento = _pagina(limite, desplazamiento)
    orden_sql = _orden(orden, ORDENES_PROVEEDOR, "-valor", "doc")
    cond, params = [], []
    if texto:
        cond.append("(nombre ILIKE %s OR doc = %s)")
        params += ["%%%s%%" % texto, texto]
    if hace_ambos:
        cond.append("hace_ambos")
    if cluster_id is not None:
        cond.append("cluster_id = %s")
        params.append(int(cluster_id))
    if min_contratos:
        cond.append("n_contratos >= %s")
        params.append(int(min_contratos))
    where = " AND ".join(cond)
    total = contar("api_proveedores", where, params)
    sql = "SELECT * FROM api_proveedores"
    if where:
        sql += " WHERE " + where
    sql += " ORDER BY %s LIMIT %%s OFFSET %%s" % orden_sql
    return consultar(sql, params + [limite, desplazamiento]), total


def proveedor(doc):
    p = consultar_uno("SELECT * FROM api_proveedores WHERE doc = %s", [doc])
    if not p:
        return None
    # Las aristas se guardan una sola vez por par (doc_a < doc_b), asi que
    # hay que mirar los dos extremos para encontrar a las contrapartes.
    contrapartes = consultar(
        """SELECT CASE WHEN a.doc_a = %s THEN a.doc_b ELSE a.doc_a END AS doc,
                  a.peso, a.n_tipos, a.tipos
           FROM api_cluster_aristas a
           WHERE a.doc_a = %s OR a.doc_b = %s
           ORDER BY a.n_tipos DESC, a.peso DESC LIMIT %s""",
        [doc, doc, doc, config.limite_max],
    )
    nombres = {}
    if contrapartes:
        docs = [c["doc"] for c in contrapartes]
        nombres = {
            r["doc"]: r["nombre"]
            for r in consultar("SELECT doc, nombre FROM api_proveedores WHERE doc = ANY(%s)", [docs])
        }
    for c in contrapartes:
        c["nombre"] = nombres.get(c["doc"])
        c["tipos"] = [t for t in (c["tipos"] or "").split(",") if t]
    entidades = [
        r["entidad"] for r in consultar(
            "SELECT DISTINCT entidad FROM api_contratos WHERE doc_proveedor = %s "
            "AND entidad IS NOT NULL ORDER BY entidad LIMIT %s",
            [doc, config.limite_max],
        )
    ]
    return {**p, "contrapartes": contrapartes, "entidades": entidades}


# ---------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------
def buscar_clusters(vigila_y_construye=None, min_proveedores=None,
                    limite=None, desplazamiento=0):
    limite, desplazamiento = _pagina(limite, desplazamiento)
    cond, params = [], []
    if vigila_y_construye:
        cond.append("vigila_y_construye")
    if min_proveedores:
        cond.append("n_proveedores >= %s")
        params.append(int(min_proveedores))
    where = " AND ".join(cond)
    total = contar("api_clusters", where, params)
    sql = "SELECT * FROM api_clusters"
    if where:
        sql += " WHERE " + where
    sql += (" ORDER BY vigila_y_construye DESC NULLS LAST, valor_total DESC NULLS LAST, "
            "cluster_id LIMIT %s OFFSET %s")
    return consultar(sql, params + [limite, desplazamiento]), total


def cluster(cluster_id):
    c = consultar_uno("SELECT * FROM api_clusters WHERE cluster_id = %s", [cluster_id])
    if not c:
        return None
    nodos = consultar(
        "SELECT doc, nombre, n_obra, n_interventoria, n_contratos, valor_total, "
        "n_entidades, es_entidad_publica FROM api_cluster_nodos WHERE cluster_id = %s "
        "ORDER BY valor_total DESC NULLS LAST",
        [cluster_id],
    )
    aristas = consultar(
        "SELECT doc_a, doc_b, peso, n_tipos, tipos FROM api_cluster_aristas "
        "WHERE cluster_id = %s ORDER BY n_tipos DESC, peso DESC",
        [cluster_id],
    )
    for a in aristas:
        a["tipos"] = [t for t in (a["tipos"] or "").split(",") if t]
    return {**c, "nodos": nodos, "aristas": aristas}


# ---------------------------------------------------------------------
# Alertas pre-adjudicacion. Opcionales: dependen de que alguien haya
# corrido pipeline/alertas.py contra un snapshot del dia.
# ---------------------------------------------------------------------
def hay_alertas():
    return existe_tabla("api_alertas")


def buscar_alertas(universo="accionable", departamento=None, entidad=None,
                   min_banderas=None, limite=None, desplazamiento=0):
    limite, desplazamiento = _pagina(limite, desplazamiento)
    cond, params = [], []
    if universo:
        if universo not in UNIVERSOS_ALERTA:
            raise ValueError(
                "universo '%s' no existe; usa uno de: %s"
                % (universo, ", ".join(UNIVERSOS_ALERTA))
            )
        cond.append("universo = %s")
        params.append(universo)
    if departamento:
        cond.append("departamento ILIKE %s")
        params.append("%%%s%%" % departamento)
    if entidad:
        cond.append("entidad ILIKE %s")
        params.append("%%%s%%" % entidad)
    if min_banderas is not None:
        cond.append("n_banderas >= %s")
        params.append(int(min_banderas))
    where = " AND ".join(cond)
    total = contar("api_alertas", where, params)
    sql = "SELECT * FROM api_alertas"
    if where:
        sql += " WHERE " + where
    # Mas banderas primero y, a igualdad, lo que cierra antes: el orden en
    # que sirve actuar.
    sql += (" ORDER BY n_banderas DESC, dias_restantes ASC NULLS LAST, "
            "id_del_proceso LIMIT %s OFFSET %s")
    return consultar(sql, params + [limite, desplazamiento]), total


def resumen_alertas():
    filas = consultar(
        "SELECT universo, n_procesos, n_con_alerta, precio_base_total, construido "
        "FROM api_alertas_resumen ORDER BY n_procesos DESC"
    )
    return {
        "construido": filas[0]["construido"] if filas else None,
        "por_universo": filas,
        "nota": (
            "Solo el universo 'accionable' admite una observacion con efecto hoy. "
            "'zombie_vencido' y 'sin_fecha_cierre' son opacidad de publicacion, no "
            "riesgo de fraude, y se reportan aparte a proposito."
        ),
    }

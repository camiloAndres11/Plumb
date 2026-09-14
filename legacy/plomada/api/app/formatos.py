"""Serializacion de las respuestas: el sobre {datos, meta} en JSON, o CSV.

El CSV no es un extra decorativo. El publico de este proyecto son
periodistas y veedores; que el resultado de un filtro se abra en Excel
sin escribir una linea de codigo es la diferencia entre que la API se use
y que no.
"""
from __future__ import annotations

import csv
import datetime
import decimal
import io

from fastapi.responses import JSONResponse, StreamingResponse

from app.config import AVISO, FUENTE, VERSION_API

FORMATOS = ("json", "csv")

# La cuenta bancaria es llave de union interna y no se publica en ninguna
# forma. En JSON esa garantia la da el `response_model` de cada endpoint
# (una columna que no este en el modelo no sale). El CSV no pasa por el
# modelo, asi que necesita su propia red: misma lista que revisa la
# puerta de calidad test_el_snapshot_publico_no_lleva_cuentas.
NUNCA_PUBLICAR = {"cuenta_key", "n_mero_de_cuenta", "numero_de_cuenta", "banco"}

# Una celda de TEXTO que empiece por uno de estos caracteres la ejecuta
# Excel como formula al abrir el archivo (=WEBSERVICE(...), DDE con + - @).
# No es teorico aqui: los valores vienen del SECOP II -- texto escrito por
# terceros (entidades, proveedores) -- y el publico objetivo de este CSV
# abre todo en Excel. Se neutraliza con el apostrofe que Excel entiende
# como "esto es texto". Solo aplica a str: los numeros negativos llegan
# como int/float/Decimal y no pasan por aqui, asi que siguen siendo numeros.
_INICIA_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _texto_seguro(texto):
    return "'" + texto if texto.startswith(_INICIA_FORMULA) else texto


def _plano(valor):
    """Aplana un valor para una celda de CSV. Mismo criterio que
    pipeline/export_web.py con las fechas: ISO, no repr de Python."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return valor.isoformat()
    if isinstance(valor, decimal.Decimal):
        return str(valor)
    if isinstance(valor, (list, tuple)):
        return _texto_seguro("|".join(str(v) for v in valor))
    if isinstance(valor, dict):
        return _texto_seguro(";".join("%s=%s" % (k, v) for k, v in valor.items()))
    if isinstance(valor, str):
        return _texto_seguro(valor)
    return valor


def _json_default(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, decimal.Decimal):
        return float(o)
    raise TypeError("no serializable: %r" % (o,))


def meta_respuesta(paginacion=None):
    meta = {"version": VERSION_API, "fuente": FUENTE, "aviso": AVISO}
    if paginacion:
        meta["paginacion"] = paginacion
    return meta


def paginacion(limite, desplazamiento, total, devueltas):
    return {
        "limite": limite,
        "desplazamiento": desplazamiento,
        "total": total,
        "devueltas": devueltas,
    }


def columnas_de(modelo):
    """Nombres de campo de un modelo de respuesta, en orden de declaracion.

    Sirve para que el CSV publique EXACTAMENTE las mismas columnas que el
    JSON. Sin esto las dos salidas divergen en silencio: el JSON lo filtra
    el `response_model` y el CSV saca lo que la consulta haya traido, que
    es como termina uno documentando un contrato y sirviendo otro.
    """
    return list(modelo.model_fields) if modelo is not None else None


def a_csv(filas, nombre, columnas=None):
    """CSV con BOM: sin el, Excel en Windows abre 'BOGOTA' con la tilde
    rota, y el 90% de los nombres de entidad del SECOP llevan tildes."""
    if not filas:
        contenido = ""
    else:
        if columnas is None:
            columnas = list(filas[0].keys())
        columnas = [c for c in columnas if c not in NUNCA_PUBLICAR]
        buffer = io.StringIO()
        escritor = csv.DictWriter(buffer, fieldnames=columnas, extrasaction="ignore")
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({c: _plano(fila.get(c)) for c in columnas})
        contenido = buffer.getvalue()
    return StreamingResponse(
        iter([("﻿" + contenido).encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plomada_%s.csv"' % nombre},
    )


class RespuestaJSON(JSONResponse):
    """JSONResponse que sabe serializar fechas y Decimals de Postgres."""

    def render(self, contenido) -> bytes:
        import json

        return json.dumps(
            contenido, ensure_ascii=False, allow_nan=False,
            separators=(",", ":"), default=_json_default,
        ).encode("utf-8")


def responder(datos, meta=None, formato="json", nombre="datos", modelo=None):
    """Punto unico de salida de los routers.

    En JSON devuelve un dict PLANO, no una Response ya construida. Es
    deliberado: FastAPI solo aplica el `response_model` cuando el endpoint
    devuelve datos crudos, y ese filtrado es lo que garantiza que una
    columna que no este en el modelo (p.ej. `cuenta_key`) no pueda salir
    por HTTP aunque una consulta la traiga por error. Devolver una
    JSONResponse aqui saltaria el modelo y convertiria esa garantia en
    una decoracion de la documentacion.

    En CSV se devuelven las filas planas y se pierde el sobre: un CSV con
    metadatos arriba no lo abre bien ninguna hoja de calculo. El aviso de
    riesgo!=fraude viaja entonces en la cabecera HTTP `X-Plomada-Aviso`,
    para que no se pierda del todo.
    """
    if formato == "csv":
        filas = datos if isinstance(datos, list) else [datos]
        respuesta = a_csv(filas, nombre, columnas_de(modelo))
        respuesta.headers["X-Plomada-Aviso"] = AVISO
        return respuesta
    return {"datos": datos, "meta": meta or meta_respuesta()}


def error(codigo, mensaje, estado, detalle=None):
    return RespuestaJSON(
        {"error": {"codigo": codigo, "mensaje": mensaje, "detalle": detalle}},
        status_code=estado,
    )

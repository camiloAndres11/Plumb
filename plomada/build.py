"""Genera el sitio estatico en site/.

Estatico a proposito: cada contrato, municipio y busqueda tiene una URL real
y compartible, el HTML sale ya renderizado (indexable) y no hay servidor que
mantener. Los 78.000 contratos caben en un portatil.
"""
import csv, html, json, os, shutil, sys
from collections import defaultdict
from pathlib import Path

import contenido as C
import data as D

RAIZ = Path(__file__).parent
SITE = RAIZ / "site"
# El tablero se alimenta del API REAL de Plomada (pipeline/api_tablero.py ->
# pipeline/api_cliente.py), nunca de out_web/ ni de fixtures locales -- ver
# escribir_datos_tablero(). build.py sigue siendo lo UNICO que escribe
# site/, para que test_privacy.py controle todo el artefacto publicado de
# una sola pasada.
PIPELINE = RAIZ.parent / "pipeline"
# El navegador consulta este API en cada vista. Se inyecta en el <head> de
# todas las paginas para que static/api.js lo lea (window.PLOMADA_API_URL) y
# ninguna vista tenga que hardcodearlo.
API_URL = os.environ.get("PLOMADA_API_URL", "https://plumb-duy6.onrender.com")
# Para enlazar API.md y MCP.md desde la vista /api/.
REPO_URL = "https://github.com/camiloAndres11/Plumb"
SITIO_NOMBRE = "Plomada"
LEMA = "Indicios de irregularidad en la contratación de obra pública en Colombia"

# Leaflet vendorizado (Tanda B, B6): plomada/static/vendor/leaflet/, version
# 1.9.4, licencia BSD-2 (ver design/VENDOR.md). Nada de unpkg en produccion.
LEAFLET_CSS = '<link rel="stylesheet" href="/static/vendor/leaflet/leaflet.css">'
LEAFLET_JS = '<script src="/static/vendor/leaflet/leaflet.js"></script>'


def h(x):
    return html.escape(str(x if x is not None else ""), quote=True)


# ---------------------------------------------------------------- tema (F1)
# Script anti-parpadeo: fija data-tema ANTES del primer pintado. Inline y
# sincrono a proposito -- un <script src> diferido dejaria un flash blanco
# en cada recarga en modo oscuro. Va en pagina(), o sea en TODAS las vistas
# a la vez, porque el shell es uno solo.
#
# Sin eleccion guardada manda prefers-color-scheme; con eleccion guardada
# manda la eleccion, siempre. El try/catch no es decorativo: en modo privado
# de algunos navegadores localStorage lanza al leer, y si lanza el sitio
# queda claro y funciona igual. Sin JS no hay atributo y el sitio queda
# claro: degradacion deliberada, no un olvido (por eso NO hay un
# @media (prefers-color-scheme: dark) suelto que duplicaria los tokens).
TEMA_INLINE = (
    '<script>(function(){try{'
    "var t=localStorage.getItem('plomada:tema');"
    "if(t!=='claro'&&t!=='oscuro'){"
    "t=window.matchMedia('(prefers-color-scheme: dark)').matches?'oscuro':'claro';}"
    "document.documentElement.setAttribute('data-tema',t);"
    '}catch(e){}})();</script>'
)
TEMA_JS = '<script type="module" src="/static/tema.js"></script>'

# El texto y aria-pressed que emite el servidor son los del tono claro: el
# servidor no sabe que tono lee el visitante. static/tema.js los corrige al
# montar, antes de cualquier interaccion.
BOTON_TEMA = (
    '<button type="button" class="nav-tema" id="conmutar-tema" '
    'aria-pressed="false" title="Cambiar entre tono claro y oscuro">'
    '<span class="nav-tema-icono" aria-hidden="true"></span>'
    '<span class="nav-tema-texto">Tono oscuro</span>'
    '</button>'
)


# ------------------------------------------------------------- nav (B1)
# Las ocho vistas (portada, tablero, mapa, buscador, metodologia, datos,
# ficha de contrato, ficha de municipio) pasan TODAS por pagina(): un solo
# shell, un solo <nav>. Adopta .nav + .nav-brand de Modernist (readme.md,
# componente "navigation"): el brand va primero y con margin-right:auto
# empuja los enlaces a la derecha, todos hijos directos de .nav para que el
# gap de Modernist quede parejo entre ellos -- envolverlos en un <nav>
# interior (como antes) les habria dejado sin espaciado, porque el gap de
# Modernist solo aplica entre hijos DIRECTOS.
# «API» va DESPUES de «Datos»: «Datos» son descargas para un lector, «API» es
# acceso programatico. El orden va de mas general a mas tecnico.
NAV_ENLACES = (
    ("/tablero/", "Tablero"), ("/mapa/", "Mapa"), ("/buscar/", "Buscador"),
    ("/metodologia/", "Metodología"), ("/datos/", "Datos"), ("/api/", "API"),
)


def nav(ruta_actual):
    enlaces = "".join(
        f'<a href="{h(u)}"{" aria-current=\"page\"" if ruta_actual.rstrip("/") == u.rstrip("/") else ""}>{h(t)}</a>'
        for u, t in NAV_ENLACES)
    actual = ' aria-current="page"' if ruta_actual.rstrip("/") == "/asistente" else ""
    cta = f'<a class="btn btn-primary nav-cta" href="/asistente/"{actual}>Asistente</a>'
    return (f'<header class="nav"><a class="nav-brand" href="/">Plomada</a>'
            f'{enlaces}{cta}{BOTON_TEMA}</header>')


# --------------------------------------------------------- islas de Vue (T1)
# docs/PLAN_VUE.md §4.3. build.py no aprende nada de Vue: solo emite un
# <div data-isla="..."> con un fallback pre-renderizado adentro (nunca
# vacio) y, una vez por pagina, el script del bundle. El bundle vive en
# plomada/static/vendor/islas/ (COMMITEADO, ver design/VENDOR.md) para que
# entre a site/ por el copytree de main() y siga habiendo un unico escritor.
ISLAS_JS = '<script type="module" src="/static/vendor/islas/islas.js"></script>'


def isla(nombre, fallback="", **props):
    """Contenedor de una isla de Vue. `fallback` es lo que ve un lector sin
    JS y lo que lee plomada/test_privacy.py: nunca se deja vacio. La isla lo
    *reemplaza* al montar, nunca lo *crea* de la nada."""
    attrs = "".join(f' data-{k.replace("_", "-")}="{h(v)}"' for k, v in props.items())
    return f'<div data-isla="{h(nombre)}"{attrs}>{fallback}</div>'


def aviso_fijo(texto, enlace=("Qué significa esto", "/metodologia/")):
    """El aviso permanente ('Indicio, no acusacion') como bloque reutilizable
    (B1): antes vivia copiado a mano solo en la ficha de contrato. Se usa en
    toda vista que muestre una cifra agregada o una ficha individual, para
    que la salvedad este siempre donde hay un numero que se pueda malleer."""
    texto_enlace, url_enlace = enlace
    return (f'<div class="aviso-fijo" role="note"><strong>Indicio, no acusación.</strong> '
            f'{texto} <a href="{h(url_enlace)}">{h(texto_enlace)}</a></div>')


# ----------------------------------------------------------------- plantilla
def pagina(titulo, descripcion, cuerpo, ruta, head="", js="", clase="", cabecera="",
           pie_aviso=True):
    canon = "/" + ruta if not ruta.startswith("/") else ruta
    # `pie_aviso=False` solo lo usa la portada, y solo porque ahi la salvedad
    # ya la dice la banda .cierre, palabra por palabra y en cuerpo mayor,
    # justo encima del pie: repetirla apila dos declaraciones identicas en
    # dos franjas pegadas. La salvedad NO desaparece de la portada -- cambia
    # de sitio. En las demas vistas el pie la sigue llevando.
    aviso_del_pie = f'<p class="aviso">{C.AVISO}</p>\n    ' if pie_aviso else ""
    return f"""<!doctype html>
<html lang="es">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{h(titulo)} — {SITIO_NOMBRE}</title>
<meta name="description" content="{h(descripcion)}">
<link rel="canonical" href="{h(canon)}">
<meta property="og:title" content="{h(titulo)} — {SITIO_NOMBRE}">
<meta property="og:description" content="{h(descripcion)}">
<meta property="og:type" content="article">
<link rel="icon" type="image/png" href="/static/favicon-32.png" sizes="32x32">
<link rel="icon" type="image/png" href="/static/favicon.png" sizes="any">
<link rel="apple-touch-icon" href="/static/favicon.png">
<link rel="stylesheet" href="/static/estilo.css">
{TEMA_INLINE}
<script>window.PLOMADA_API_URL={json.dumps(API_URL)};</script>
{head}
<body class="{clase}">
<a class="saltar" href="#principal">Saltar al contenido</a>
<div class="banda-oscura banda-cab">
{nav(canon)}
{cabecera}
</div>
<main id="principal">
{cuerpo}
</main>
<footer class="banda-oscura banda-pie">
  <div class="pie">
    {aviso_del_pie}<p>Datos públicos del SECOP II. <a href="/metodologia/">Cómo se calcula</a> ·
       <a href="/datos/">Descargar los datos</a></p>
  </div>
</footer>
{TEMA_JS}
{js}
"""


def escribir(ruta, contenido_html):
    destino = SITE / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido_html, encoding="utf-8")


def migas(*pares):
    partes = []
    for texto, url in pares:
        partes.append(f'<a href="{h(url)}">{h(texto)}</a>' if url else f"<span>{h(texto)}</span>")
    return '<nav class="migas" aria-label="Ruta">' + " / ".join(partes) + "</nav>"


def dato(etiqueta, valor, extra=""):
    return (f'<div class="dato"><dt>{h(etiqueta)}</dt>'
            f'<dd>{valor}{extra}</dd></div>')


def _cifra(x, dec):
    """D._num() con decimales, tolerando None.

    D.plata/pct/entero ya devuelven "sin dato" ante None, pero D._num() es el
    formateador crudo y revienta. Ahora que las cifras vienen del API, None es
    un valor normal (el API no respondio, o no publica ese agregado): la
    pagina tiene que decir "sin dato", no tumbar el build."""
    return "sin dato" if x is None else D._num(x, dec)


# ------------------------------------------------------------------- 7.1 ficha
def url_contrato(c):
    return f"/contrato/{D.slug(c['id_contrato'])}/"


def url_municipio(dep, ciu):
    return f"/municipio/{D.slug(dep, ciu)}/"


def barra_score(c):
    s = c.get("score") or 0
    fuertes = c.get("n_banderas_fuertes") or 0
    return f"""<div class="score">
  <div class="score-num"><b>{fuertes}</b> <span>señal{'' if fuertes == 1 else 'es'} fuerte{'' if fuertes == 1 else 's'}</span></div>
  <div class="score-bar" role="img" aria-label="Puntaje {D._num(s, 2)} de 1">
    <i style="width:{min(100, s * 100):.0f}%"></i></div>
  <div class="score-pie">Puntaje {D._num(s, 2)} / 1 &middot; suma de pesos, no una probabilidad.
    <a href="/metodologia/#puntaje">Cómo se calcula</a></div>
</div>"""


def bloque_banderas(grupos, total):
    if not total:
        return '<p class="vacio">Este contrato no tiene señales encendidas.</p>'
    out = []
    for grupo, items in grupos:
        out.append(f'<section class="grupo"><h3>{h(grupo)}</h3>')
        for b in items:
            aten = " atenuada" if b["atenuada"] else ""
            etq = ('<span class="etq-aten" title="Patrón esperable en este contexto: '
                   'no cuenta como indicio fuerte">señal atenuada</span>') if b["atenuada"] else ""
            ev = (f'<p class="evidencia"><span>Evidencia</span> {h(b["evidencia"])}</p>'
                  if b["evidencia"] else
                  '<p class="evidencia sin"><span>Evidencia</span> sin dato numérico '
                  'para esta bandera en este contrato</p>')
            out.append(f"""<article class="bandera{aten}">
  <h4>{h(D.titulo(b["bandera"].removeprefix("f_").replace("_", " ")))}
      <span class="peso" title="Peso de la bandera">peso {D._num(b["peso"], 1)}</span>{etq}</h4>
  <p class="glosa">{h(b["glosa"])}</p>
  {ev}
</article>""")
        out.append("</section>")
    return "".join(out)


NOTA_PRECISION = {
    "cabecera_municipal": "Ubicación aproximada: cabecera municipal. No se pudo geocodificar "
                          "la dirección exacta, común en zona rural.",
}


def bloque_mapa(c, geocache):
    """Mapa satelital de la seccion Ejecucion, o una nota si no hay ubicacion confiable.

    ESPEJO en JS: static/mapa-satelital.js + bloqueMapa() de static/ficha.js.
    La ficha que se sirve la pinta el JS (el shell es uno solo para 12.678
    contratos), asi que esta version ya no genera HTML publicado; se conserva
    como comportamiento de referencia y es la que ejerce test_privacy.py
    (mismo arreglo que data.py <-> formato.js). Si cambias la regla aqui,
    cambiala alla.

    El fallback 'defecto' (centro de Colombia) de coords_contrato() nunca llega
    aqui: un mapa generico centrado en Bogota para un contrato de otro
    departamento es peor que no mostrar mapa. Sin evidencia no se publica.
    """
    if not D.ciudad_visible(c.get("ciudad")):
        return '<p class="mapa-nota sin">Municipio no definido en la fuente: no hay dónde centrar un mapa.</p>', False
    coords = D.coords_contrato(c, geocache)
    if not coords:
        return '<p class="mapa-nota sin">Ubicación no geocodificada todavía.</p>', False
    direccion = ", ".join(x for x in (D.titulo(c.get("dir_ejecucion")), D.ciudad_visible(c.get("ciudad"))) if x)
    nota = NOTA_PRECISION.get(coords["precision"], "")
    # Click-to-load (Tanda B, B6): las imagenes satelitales las sirve Esri
    # (server.arcgisonline.com) y eso NO se puede vendorizar. Pero pedirlas
    # solas al abrir la ficha le dice a Esri, sin que el lector lo sepa, que
    # coordenadas esta mirando -- y el publico de este sitio son periodistas.
    # El div lleva id="mapa-satelital" desde YA (test_privacy.py lo exige) y
    # los data-* con las coordenadas; mapa-satelital.js no llama a Leaflet
    # hasta que el lector pulsa el boton.
    html_mapa = (f'<div id="mapa-satelital" class="mapa-placeholder" data-lat="{h(coords["lat"])}" '
                f'data-lon="{h(coords["lon"])}" data-direccion="{h(direccion)}">'
                f'<p class="mapa-direccion">{h(direccion) or "Ubicación sin dirección textual"}</p>'
                '<p class="nota">La imagen satelital la sirve Esri (arcgisonline.com): al cargarla, '
                'Esri recibe las coordenadas que está viendo. No se pide sola.</p>'
                '<button type="button" class="btn btn-secondary">Ver imagen satelital</button></div>'
                + (f'<p class="mapa-nota">{h(nota)}</p>' if nota else ""))
    return html_mapa, True


def ficha_contrato(c, glos, hermanos, geocache):
    items, grupos = D.banderas_encendidas(c, glos)
    ciudad = c["_ciudad"]
    objeto = D.titulo(c.get("descripcion")) or "Objeto contractual no publicado"
    ent = D.titulo(c.get("entidad"))
    dep = D.titulo(c.get("departamento"))
    valor = c.get("valor_plausible")
    url = c.get("_url")

    verificar = (f'<a class="btn-verificar" href="{h(url)}" rel="noopener nofollow" '
                 f'target="_blank">Verificar en SECOP II &rarr;</a>' if url else
                 '<p class="btn-verificar sin">La fuente no publicó enlace al proceso. '
                 'Sin verificación en origen, trátelo como no confirmado.</p>')

    # dinero
    filas_plata = [dato("Valor del contrato", D.plata(valor),
                        f'<small>{D.plata(valor, exacto=True)}</small>')]
    if c.get("valor") and c["valor"] != valor:
        filas_plata.append(dato("Valor publicado por la entidad",
            f'<span class="alerta">{D.plata(c["valor"])}</span>',
            '<small>Cifra aritméticamente imposible. Se trata como falla de publicación; '
            'todas las sumas de este sitio usan el valor saneado.</small>'))
    for etq, k in (("Pagado", "valor_pagado"), ("Pendiente de ejecución", "valor_pend_ejecucion"),
                   ("Anticipo", "valor_anticipo"), ("Precio base del estudio", "precio_base")):
        if c.get(k):
            filas_plata.append(dato(etq, D.plata(c[k])))

    recursos = [n for n, k in (("Regalías", "rec_regalias"), ("SGP", "rec_sgp"),
                               ("Recursos propios", "rec_propios_terr")) if c.get(k)]

    personas = [dato("Proveedor", h(D.titulo(c.get("proveedor"))) or "sin dato")]
    if c.get("ordenador"):
        personas.append(dato("Ordenador del gasto", h(D.titulo(c["ordenador"])),
                             "<small>Funcionario público. Se publica el nombre, no el documento.</small>"))
    personas.append(dato("Supervisor", h(D.titulo(c.get("supervisor")))
                         or '<span class="alerta">no reportado</span>'))

    herm = ""
    if hermanos:
        li = "".join(f'<li><a href="{url_contrato(x)}">{h(D.titulo(x.get("descripcion")) or x["id_contrato"])}</a>'
                     f' <span>{D.plata(x.get("valor_plausible"))} &middot; {h(x.get("fecha_firma"))}</span></li>'
                     for x in hermanos[:8])
        herm = f"""<section class="caja"><h2>Otros contratos marcados del mismo proveedor</h2>
<p class="nota">Coincidencia de proveedor dentro de este municipio. Es contexto para
reportear, no una relación probada entre los contratos.</p><ul class="lista-herm">{li}</ul></section>"""

    mapa_html, hay_mapa = bloque_mapa(c, geocache)

    cuerpo = f"""
<div class="aviso-fijo" role="note"><strong>Indicio, no acusación.</strong>
  Este contrato está marcado por patrones detectados en datos públicos. No afirma que
  alguien haya obrado de forma irregular. <a href="/metodologia/">Qué significa esto</a></div>

{migas(("Plomada", "/"), (dep, f"/mapa/?dep={D.slug(c['departamento'])}"),
       (ciudad or "Municipio sin definir", url_municipio(c["departamento"], c["ciudad"]) if ciudad else None),
       ("Contrato", None))}

<article class="ficha">
  <header class="ficha-cab">
    <p class="tipo">{h(D.titulo(c.get("tipo_contrato")))} &middot; {h(D.titulo(c.get("modalidad")))}</p>
    <h1>{h(objeto)}</h1>
    <p class="idc"><code>{h(c["id_contrato"])}</code></p>
    {verificar}
  </header>

  <dl class="cab-grid">
    {dato("Entidad", h(ent), f'<small>NIT {h(c.get("nit_entidad"))} &middot; orden {h(D.titulo(c.get("orden")))}</small>')}
    {dato("Municipio", (f'<a href="{url_municipio(c["departamento"], c["ciudad"])}">{h(ciudad)}</a>'
                        if ciudad else '<span class="alerta">no definido en la fuente</span>')
          , f'<small>{h(dep)}</small>')}
    {dato("Valor", D.plata(valor))}
    {dato("Firma", h(c.get("fecha_firma")), f'<small>Período {h(c.get("periodo_gobierno"))}</small>')}
    {dato("Estado", h(D.titulo(c.get("estado"))))}
    {dato("Plazo", f'{D.entero(c.get("dias_originales"))} días'
          + (f' <span class="alerta">+{D.entero(c["dias_adicionados"])} adicionados</span>'
             if c.get("dias_adicionados") else ""))}
  </dl>

  {barra_score(c)}

  <section class="caja principal">
    <h2>Señales de riesgo encendidas <span class="cuenta">{len(items)}</span></h2>
    <p class="nota">Agrupadas por tipo y ordenadas por peso. Cada una viene con el número
       que la disparó: si el número no le convence, el enlace a la fuente oficial está arriba.</p>
    {bloque_banderas(grupos, len(items))}
  </section>

  <div class="dos-col">
    <section class="caja"><h2>Dinero</h2><dl class="dl">{"".join(filas_plata)}</dl>
      {'<p class="fuentes">Fuente de recursos: ' + ", ".join(recursos) + "</p>" if recursos else ""}
    </section>
    <section class="caja"><h2>Personas y competencia</h2><dl class="dl">{"".join(personas)}
      {dato("Ofertas recibidas", D.entero(c.get("n_oferentes_unicos")))}
      {dato("Invitados", D.entero(c.get("n_invitados")))}
      {dato("Ventana de publicación", f'{D.entero(c.get("dias_ventana"))} días',
            f'<small>Mediana de su modalidad: {D.entero(c.get("ev_ventana_mediana_modalidad"))} días</small>')}
    </dl>
      <p class="nota">Los documentos de identidad de particulares no se publican.
         <a href="/metodologia/#privacidad">Por qué</a></p>
    </section>
  </div>

  <section class="caja"><h2>Ejecución</h2><dl class="dl">
    {dato("Dirección de ejecución", h(D.titulo(c.get("dir_ejecucion"))))}
    {dato("Clasificación UNSPSC", h(c.get("unspsc")))}
  </dl>
  {mapa_html}
  </section>

  {herm}
</article>
"""
    desc = (f"{len(items)} señales de riesgo en un contrato de {D.plata(valor)} de "
            f"{ent} en {ciudad or dep}. Indicio para revisión, no acusación.")
    head = LEAFLET_CSS if hay_mapa else ""
    js = (LEAFLET_JS + '<script src="/static/mapa-satelital.js"></script>') if hay_mapa else ""
    return pagina(objeto[:70], desc, cuerpo, url_contrato(c), head=head, js=js, clase="pg-ficha")


# ------------------------------------------------------------------ municipio
def pagina_municipio(m, contratos_mun, puesto, total_mun):
    ciudad = D.ciudad_visible(m["ciudad"])
    dep = D.titulo(m["departamento"])
    nombre = ciudad or f"Contratos sin municipio definido — {dep}"
    filas = "".join(
        f'<tr><td><a href="{url_contrato(c)}">{h(D.titulo(c.get("descripcion")) or c["id_contrato"])}</a>'
        f'<small>{h(D.titulo(c.get("entidad")))}</small></td>'
        f'<td class="num">{D.plata(c.get("valor_plausible"))}</td>'
        f'<td class="num">{h(c.get("anio"))}</td>'
        f'<td class="num">{c.get("n_banderas_fuertes") or 0}</td></tr>'
        for c in sorted(contratos_mun, key=lambda x: -(x.get("score") or 0)))

    conteos = [(k[2:].replace("_", " "), m[k]) for k in m
               if k.startswith("n_") and k not in ("n_contratos", "n_atipicos") and m[k]]
    chips = "".join(f'<li><b>{D.entero(v)}</b> {h(D.titulo(k))}</li>' for k, v in
                    sorted(conteos, key=lambda x: -x[1]))

    cuerpo = f"""
{migas(("Plomada", "/"), (dep, f"/mapa/?dep={D.slug(m['departamento'])}"), (nombre, None))}
<header class="cab-mun">
  <p class="tipo">{h(dep)}</p>
  <h1>{h(nombre)}</h1>
  <p class="puesto">Puesto {puesto} de {total_mun} municipios por tasa ajustada</p>
</header>
<dl class="cab-grid">
  {dato("Tasa ajustada", f'<b class="grande">{D.pct(m["tasa_ajustada"])}</b>',
        f'<small>Tasa cruda {D.pct(m["tasa_cruda"])} sobre {D.entero(m["n_contratos"])} contratos. '
        f'La ajustada corrige el azar de los municipios pequeños.</small>')}
  {dato("Contratos atípicos", f'{D.entero(m["n_atipicos"])} de {D.entero(m["n_contratos"])}')}
  {dato("Valor atípico", D.plata(m["valor_atipico"]),
        f'<small>{D.pct(m.get("share_valor_atipico") or 0)} de {D.plata(m["valor_total"])} contratados</small>')}
  {dato("Regalías en contratos atípicos", D.plata(m.get("regalias_atipicas")))}
</dl>
{'<section class="caja"><h2>Banderas más frecuentes</h2><ul class="chips">' + chips + "</ul></section>" if chips else ""}
<section class="caja principal">
  <h2>Contratos marcados <span class="cuenta">{len(contratos_mun)}</span></h2>
  <p class="nota">Ordenados por puntaje. Cada uno abre su ficha con la evidencia y el
     enlace a SECOP II.</p>
  <div class="tabla-scroll"><table class="table"><thead><tr><th>Objeto</th><th class="num">Valor</th>
    <th class="num">Año</th><th class="num">Señales fuertes</th></tr></thead>
    <tbody>{filas or '<tr><td colspan="4">Sin contratos en la muestra.</td></tr>'}</tbody></table></div>
  <p><a href="/buscar/?municipio={h(m['ciudad'])}">Ver en el buscador con filtros &rarr;</a></p>
</section>
"""
    desc = (f"{D.entero(m['n_atipicos'])} de {D.entero(m['n_contratos'])} contratos de obra "
            f"marcados en {nombre}. Tasa ajustada {D.pct(m['tasa_ajustada'])}.")
    return pagina(nombre, desc, cuerpo, url_municipio(m["departamento"], m["ciudad"]))


# ----------------------------------------------------------------------- 7.2 mapa
# El cruce ciudad (texto libre) -> DIVIPOLA lo resuelve otro frente del equipo.
# Aqui solo se consume: si aparece out/divipola_municipios.csv y geo/municipios.geojson,
# la capa municipal se pinta sola. Departamento si se resuelve por codigo oficial.
ALIAS_DEP = {
    "SANTAFE DE BOGOTA D.C": "BOGOTA D.C.",
    "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA": "SAN ANDRES Y PROVIDENCIA",
}


def clave_dep(nombre):
    n = D.sin_tildes(nombre).replace(".", "").strip()
    n = D.sin_tildes(ALIAS_DEP.get(D.sin_tildes(nombre), n)).replace(".", "")
    return n.replace("BOGOTA DC", "BOGOTA").replace("SAN ANDRES Y PROVIDENCIA", "SAN ANDRES")


def pagina_mapa(deps, muns):
    por_clave = {clave_dep(d["departamento"]): d for d in deps}
    geo = json.loads((RAIZ / "geo" / "departamentos.geojson").read_text(encoding="utf-8"))
    sin_datos = []
    for f in geo["features"]:
        k = clave_dep(f["properties"].get("NOMBRE_DPT", ""))
        d = por_clave.pop(k, None)
        f["properties"] = {
            "nombre": D.titulo(d["departamento"]) if d else D.titulo(f["properties"]["NOMBRE_DPT"]),
            "raw": d["departamento"] if d else "",
            "cod": f["properties"].get("DPTO"),
            "slug": D.slug(d["departamento"]) if d else "",
            "ajustada": d["tasa_ajustada"] if d else None,
            "cruda": d["tasa_cruda"] if d else None,
            "n": d["n_contratos"] if d else 0,
            "a": d["n_atipicos"] if d else 0,
            "valor": d["valor_atipico"] if d else 0,
            "valor_fmt": D.plata(d["valor_atipico"]) if d else "sin dato",
        }
        if not d:
            sin_datos.append(f["properties"]["nombre"])
    (SITE / "datos").mkdir(parents=True, exist_ok=True)
    def redondear(o):   # 4 decimales ~ 11 m: el archivo baja a la mitad y el mapa no cambia
        if isinstance(o, float):
            return round(o, 4)
        if isinstance(o, list):
            return [redondear(x) for x in o]
        return o
    for f in geo["features"]:
        f["geometry"]["coordinates"] = redondear(f["geometry"]["coordinates"])
    (SITE / "datos" / "departamentos.geojson").write_text(
        json.dumps(geo, separators=(",", ":")), encoding="utf-8")

    huerfanos = sorted(por_clave)
    cross = (RAIZ / "out" / "divipola_municipios.csv").exists() and \
            (RAIZ / "geo" / "municipios.geojson").exists()

    orden = sorted(muns, key=lambda m: -m["tasa_ajustada"])
    filas = "".join(
        f'<tr data-dep="{h(D.slug(m["departamento"]))}"><td class="num">{i}</td>'
        f'<td><a href="{url_municipio(m["departamento"], m["ciudad"])}">'
        f'{h(D.ciudad_visible(m["ciudad"]) or "Sin municipio definido")}</a>'
        f'<small>{h(D.titulo(m["departamento"]))}</small></td>'
        f'<td class="num destacado">{D.pct(m["tasa_ajustada"])}</td>'
        f'<td class="num tenue">{D.pct(m["tasa_cruda"])}</td>'
        f'<td class="num">{D.entero(m["n_contratos"])}</td>'
        f'<td class="num">{D.plata(m["valor_atipico"])}</td></tr>'
        for i, m in enumerate(orden, 1))

    nota_mun = ("" if cross else """
<p class="nota aviso-cruce"><strong>Capa municipal pendiente.</strong> El cruce entre el
campo <code>ciudad</code> (texto libre) y los códigos DIVIPOLA lo está resolviendo otro
frente del equipo. Este mapa no arma su propio pareo de nombres a propósito: pintar un
municipio equivocado es peor que no pintarlo. Mientras llega
<code>out/divipola_municipios.csv</code>, los 721 municipios están en la tabla de abajo,
ordenados por la misma métrica.</p>""")

    aviso_faltantes = (f'<p class="nota">Sin datos en el mapa: {", ".join(sin_datos)}.</p>'
                       if sin_datos else "")
    aviso_huerfanos = (f'<p class="nota alerta">Departamentos en los datos que no cruzaron con '
                       f'una frontera oficial: {", ".join(huerfanos)}.</p>' if huerfanos else "")

    cuerpo = f"""
<header class="cab">
  <h1>Mapa de señales de riesgo</h1>
  <p class="bajada">Coroplético por <strong>tasa ajustada</strong> de contratos de obra
     marcados. Nunca por tasa cruda: un municipio con 4 contratos y 2 marcados da 50% y
     encabezaría la lista por puro azar. <a href="/metodologia/#tasa">Cómo se corrige</a></p>
</header>
<div class="mapa-wrap">
  <div id="mapa" role="application" aria-label="Mapa coroplético de Colombia"></div>
  <aside id="panel" class="panel"><p class="vacio">Elija un departamento en el mapa.</p></aside>
</div>
{aviso_faltantes}{aviso_huerfanos}
<section class="caja principal">
  <h2>Municipios <span class="cuenta">{len(muns)}</span></h2>
  {nota_mun}
  <p class="nota">Se muestran las dos tasas juntas: la ajustada, que es la que ordena, y
     la cruda, para que la corrección sea visible.</p>
  <input id="filtro-mun" type="search" placeholder="Filtrar municipio o departamento"
         aria-label="Filtrar municipios">
  <div class="tabla-scroll"><table class="table" id="tabla-mun"><thead><tr><th class="num">#</th><th>Municipio</th>
    <th class="num">Tasa ajustada</th><th class="num">Tasa cruda</th>
    <th class="num">Contratos</th><th class="num">Valor atípico</th></tr></thead>
    <tbody>{filas}</tbody></table></div>
</section>
"""
    head = LEAFLET_CSS
    js = LEAFLET_JS + '<script src="/static/mapa.js"></script>'
    return pagina("Mapa", "Mapa de Colombia por tasa ajustada de contratos de obra pública "
                  "con señales de riesgo, por departamento y municipio.", cuerpo, "/mapa/",
                  head=head, js=js, clase="pg-mapa")


# --------------------------------------------------------------------- 7.3 buscar
def pagina_buscar():
    """Shell del buscador. Ya no incrusta facetas: static/buscar.js las trae
    del API (/v1/departamentos, /v1/municipios, /v1/banderas) y las cachea en
    sessionStorage. Antes este HTML pesaba 155 KB, casi todo <option>.

    Dos filtros del buscador viejo desaparecieron porque el API no los ofrece
    como parametro de consulta, y filtrarlos solo sobre la pagina cargada
    mentiria sobre el resto del resultado:
      - Periodo de gobierno: /v1/contratos no acepta ese filtro.
      - Orden por Objeto/Entidad/Municipio: el API solo ordena por
        fecha, riesgo, score y valor (devuelve 422 con cualquier otro).
    """
    def sel(nombre, etiqueta_vacia="Todos"):
        return (f'<select id="f-{nombre}" data-campo="{nombre}">'
                f'<option value="">{etiqueta_vacia}</option></select>')

    cuerpo = f"""
<header class="cab">
  <h1>Buscador de contratos marcados</h1>
  <p class="bajada">Filtre, ordene y llévese los datos. Cada búsqueda tiene su propia URL:
     el enlace de la barra de direcciones ya lleva los filtros puestos.</p>
</header>
<form class="filtros" id="filtros" role="search">
  <div><label for="f-q">Texto</label>
    <input id="f-q" data-campo="q" type="search" placeholder="Objeto, entidad o proveedor"></div>
  <div><label for="f-departamento">Departamento</label>{sel("departamento")}</div>
  <div><label for="f-municipio">Municipio</label>{sel("municipio")}</div>
  <div><label for="f-entidad">Entidad</label>
    <input id="f-entidad" data-campo="entidad" type="search" placeholder="Nombre de la entidad"></div>
  <div><label for="f-anio">Año</label>
    <input id="f-anio" data-campo="anio" type="number" min="2015" max="2030" placeholder="Todos"></div>
  <div><label for="f-tipo">Tipo</label>
    <input id="f-tipo" data-campo="tipo" type="search" placeholder="Todos"></div>
  <div><label for="f-modalidad">Modalidad</label>
    <input id="f-modalidad" data-campo="modalidad" type="search" placeholder="Todas"></div>
  <div><label for="f-bandera">Bandera</label>{sel("bandera", "Cualquiera")}</div>
  <div><label for="f-vmin">Valor mínimo (COP)</label>
    <input id="f-vmin" data-campo="vmin" type="number" min="0" step="1000000" placeholder="0"></div>
  <div><label for="f-vmax">Valor máximo (COP)</label>
    <input id="f-vmax" data-campo="vmax" type="number" min="0" step="1000000" placeholder="sin tope"></div>
  <div class="acciones">
    <button type="button" id="limpiar">Limpiar</button>
    <button type="button" id="exportar">Exportar CSV</button>
  </div>
</form>
<p id="resumen" class="resumen" aria-live="polite">Cargando…</p>
<div class="tabla-scroll"><table class="table" id="resultados">
  <thead><tr>
    <th>Objeto</th>
    <th>Entidad</th>
    <th>Municipio</th>
    <th class="num" data-orden="anio">Año</th>
    <th class="num" data-orden="valor">Valor</th>
    <th class="num" data-orden="fuertes">Señales</th>
    <th class="num" data-orden="score">Puntaje</th>
  </tr></thead><tbody></tbody>
</table></div>
<p><button type="button" id="mas" hidden>Ver más</button></p>
<p class="nota">El CSV que descarga es el mismo que ve, ya saneado: no incluye documentos
   de particulares ni números de cuenta. <a href="/metodologia/#privacidad">Por qué</a></p>
"""
    return pagina("Buscador", "Buscador de contratos de obra pública con señales de riesgo: "
                  "filtros por departamento, municipio, entidad, año, modalidad y bandera.",
                  cuerpo, "/buscar/", js='<script type="module" src="/static/buscar.js"></script>',
                  clase="pg-buscar")


# ---------------------------------------------------------------- 7.4 metodologia
def pagina_metodologia(glos, cifras, umbral):
    por_grupo = defaultdict(list)
    for b in glos.values():
        por_grupo[b["grupo"]].append(b)
    bloques = []
    for g in D.ORDEN_GRUPOS + [x for x in sorted(por_grupo) if x not in D.ORDEN_GRUPOS]:
        if g not in por_grupo:
            continue
        filas = "".join(
            f'<tr><td><b>{h(D.titulo(b["bandera"].removeprefix("f_").replace("_", " ")))}</b>'
            f'<code>{h(b["bandera"])}</code></td>'
            f'<td class="num">{D._num(b["peso"], 1)}</td><td>{h(b["glosa"])}</td></tr>'
            for b in sorted(por_grupo[g], key=lambda x: -x["peso"]))
        bloques.append(f'<h3>{h(g)}</h3><div class="tabla-scroll"><table class="table banderas"><thead><tr>'
                       f'<th>Bandera</th><th class="num">Peso</th>'
                       f'<th>Qué pregunta y en qué se apoya</th></tr></thead><tbody>{filas}</tbody></table></div>')

    fp = "".join(f"""<article class="caso"><h3>{h(t)}</h3>
      <p><span class="etq">Qué pasaba</span> {p}</p>
      <p><span class="etq">Qué se hizo</span> {q}</p></article>""" for t, p, q in C.FALSOS_POSITIVOS)
    lim = "".join(f"<li><strong>{h(t)}</strong> {p}</li>" for t, p in C.LIMITACIONES)
    cob = "".join(f'<tr><td><code>{h(k)}</code></td><td class="num">{v}</td></tr>'
                  for k, v in [("dir_ejecucion", "100%"), ("doc_proveedor", "87,4%"),
                               ("doc_ordenador", "64,5%"), ("doc_supervisor", "54,3%"),
                               ("doc_replegal", "30,9%"), ("cuenta bancaria", "23,7%")])

    cuerpo = f"""
<header class="cab">
  <h1>Metodología</h1>
  <p class="bajada">Qué mide Plomada, cómo lo mide, y sobre todo qué <em>no</em> puede
     afirmar. Esta página es parte del producto, no un anexo.</p>
</header>
{C.INTRO_METODOLOGIA}

<section class="caja"><h2>El universo analizado</h2>
<dl class="cab-grid">
  {dato("Contratos en SECOP II", "sin dato", "<small>el API no publica el total de todo SECOP II, solo el universo de obra</small>")}
  {dato("Universo de obra pública", f"<b class='grande'>{D.entero(cifras['n_universo'])}</b>",
        "<small>el API no desglosa por tipo de contrato (Obra/Interventoría/Consultoría/APP/Concesión)</small>")}
  {dato("Valor total", D.plata(cifras["valor_universo"]))}
  {dato("Contratos atípicos", f"{D.entero(cifras['n_atipicos'])} <span class='tenue'>({D.pct(cifras['pct_atipicos'])})</span>",
        f"<small>{D.plata(cifras['valor_atipico'])}</small>")}
</dl>
<p class="nota">En Colombia un billón son 10<sup>12</sup> pesos. Todo el dinero de este
   sitio se suma con <code>valor_plausible</code>, la versión saneada del valor
   publicado. <a href="#falsos">Por qué</a></p>
</section>

<section class="caja" id="banderas"><h2>Las {len(glos)} banderas</h2>
<p class="nota">Nombres, pesos y glosas salen de <code>banderas_glosario.csv</code>.
   No están escritas en el código del sitio: si el pipeline agrega una bandera, aparece
   aquí sola.</p>
{"".join(bloques)}
</section>

<section class="caja" id="puntaje"><h2>Cómo se calcula el puntaje</h2>
{C.PUNTAJE}
<p class="nota">En el corte vigente, el contrato marcado con menos señales acumula
   {_cifra(umbral, 1)} puntos crudos y el conjunto de atípicos promedia
   {_cifra(cifras["score_medio"], 2)} de puntaje.</p>
</section>

<section class="caja" id="tasa"><h2>Por qué la tasa ajustada y no el porcentaje</h2>
<p>Ordenar municipios por porcentaje de contratos marcados premia a los municipios
   pequeños. Con 4 contratos, dos marcados dan 50%: el mismo número que un municipio con
   200 contratos y 100 marcados, cuando la evidencia detrás es incomparable.</p>
<p>La <strong>tasa ajustada</strong> contrae cada municipio hacia la tasa nacional en
   proporción a lo poco que se sabe de él, con un prior Beta estimado sobre el conjunto
   de municipios. Un municipio con muchos contratos casi no se mueve; uno con cuatro se
   mueve mucho. Los parámetros <code>alpha</code> y <code>beta</code> viajan en el CSV de
   rankings para que el cálculo se pueda reproducir.</p>
<p>El sitio muestra siempre las dos tasas, la cruda al lado de la ajustada. Esconder la
   corrección no genera confianza; enseñarla sí.</p>
</section>

<section class="caja" id="falsos"><h2>Falsos positivos conocidos</h2>
<p class="nota">Casos reales en que una bandera se encendía sin que hubiera nada que
   revisar. Se listan porque un lector tiene derecho a saber dónde falla la herramienta.</p>
{fp}
</section>

<section class="caja" id="limitaciones"><h2>Limitaciones</h2>
<ul class="lista-lim">{lim}</ul>
<h3>Cobertura por campo</h3>
<p class="nota">El análisis de red solo puede calcularse sobre los contratos que traen el
   identificador. Es un piso, no un censo.</p>
<div class="tabla-scroll"><table class="table"><thead><tr><th>Campo</th><th class="num">Cobertura</th></tr></thead>
  <tbody>{cob}</tbody></table></div>
</section>

<section class="caja" id="privacidad"><h2>Qué no se publica</h2>
{C.PRIVACIDAD}
</section>

<section class="caja" id="fuentes"><h2>Datos crudos y código</h2>
{C.FUENTES}
</section>
"""
    return pagina("Metodología", "Las 22 banderas con su peso y su glosa, cómo se calcula "
                  "el puntaje, los falsos positivos conocidos y los límites de cobertura.",
                  cuerpo, "/metodologia/", clase="pg-texto")


# --------------------------------------------------------------------- portada
def portada(muns, cifras, top_contratos):
    top = sorted(muns, key=lambda m: -m["tasa_ajustada"])[:10]
    filas = "".join(
        f'<tr><td class="num">{i}</td><td><a href="{url_municipio(m["departamento"], m["ciudad"])}">'
        f'{h(D.ciudad_visible(m["ciudad"]) or "Sin municipio definido")}</a>'
        f'<small>{h(D.titulo(m["departamento"]))}</small></td>'
        f'<td class="num destacado">{D.pct(m["tasa_ajustada"])}</td>'
        f'<td class="num tenue">{D.pct(m["tasa_cruda"])}</td>'
        f'<td class="num">{D.entero(m["n_contratos"])}</td></tr>'
        for i, m in enumerate(top, 1))
    tarjetas = "".join(
        f'<a class="card elev-sm" href="{url_contrato(c)}">'
        f'<span class="card-kicker">{c["n_banderas_fuertes"]} señales fuertes</span>'
        f'<b class="card-title">{h((D.titulo(c.get("descripcion")) or "Objeto no publicado")[:80])}</b>'
        f'<span class="card-meta">{h(D.titulo(c.get("entidad")))[:60]} &middot; '
        f'{h(D.ciudad_visible(c.get("ciudad")) or D.titulo(c.get("departamento")))} &middot; '
        f'{D.plata(c.get("valor_plausible"))}</span></a>' for c in top_contratos)

    cabecera = f"""
<header class="hero">
  <p class="kicker">Obra pública &middot; SECOP II &middot; datos abiertos</p>
  <h1>La obra pública, medida contra la vertical.</h1>
  <p class="lema">Esta sigue <strong>personas</strong>, no empresas, en la contratación de
     obra pública del Estado colombiano.</p>
  <p class="bajada">Una empresa se disuelve y mañana aparece otra con otro NIT. Una cédula no.
     Por eso Plomada mira las cuatro personas que firman cada contrato: quién autorizó el
     gasto, quién debía supervisar, quién representa a la empresa y quién autorizó el pago.</p>
  <p class="bajada">{C.AVISO_CORTO} <a href="/metodologia/">Cómo se calcula.</a></p>
  <p class="cta"><a class="btn btn-primary" href="/buscar/">Buscar un contrato</a>
     <a class="btn btn-secondary" href="/mapa/">Ver el mapa</a></p>
</header>
"""

    # Cuarta celda de la franja: "Administraciones" (entidad x periodo de
    # gobierno) NO es derivable del API -- se imprimia siempre como "sin
    # dato" en tipografia de cifra, un hueco en la portada. La reemplaza una
    # cifra que el API si publica (titulares.json, la misma fuente de las
    # otras tres). Si tampoco esa esta (API caido, base vacia), la franja se
    # publica con tres celdas en vez de cuatro: preferimos una columna menos
    # a un "sin dato" del tamano de un titular.
    cuarta_cifra = (
        dato("Con indicio fuerte de red",
             f"<b class='grande'>{D.entero(cifras['n_red_fuerte'])}</b>",
             f"<small>contratos, {D.plata(cifras['valor_red_fuerte'])}</small>")
        if cifras.get("n_red_fuerte") else "")

    cuerpo = f"""
{isla("cifra-lider",
      '<p class="nota">Ver el desglose completo de indicios en el '
      '<a href="/tablero/">tablero</a>.</p>')}

<dl class="cab-grid cifras">
  {dato("Universo de obra pública", f"<b class='grande'>{D.entero(cifras['n_universo'])}</b>",
        f"<small>contratos, {D.plata(cifras['valor_universo'])}</small>")}
  {dato("Contratos atípicos", f"<b class='grande'>{D.entero(cifras['n_atipicos'])}</b>",
        f"<small>{D.pct(cifras['pct_atipicos'])} &middot; {D.plata(cifras['valor_atipico'])}</small>")}
  {dato("Municipios en el ranking", D.entero(cifras["n_municipios"]))}
  {cuarta_cifra}
</dl>
<section class="caja principal">
  <h2>Municipios con mayor tasa ajustada</h2>
  <p class="nota">Ordenado por tasa ajustada, nunca por la cruda. Las dos se muestran
     juntas. <a href="/metodologia/#tasa">Por qué</a></p>
  <div class="tabla-scroll"><table class="table"><thead><tr><th class="num">#</th><th>Municipio</th>
    <th class="num">Tasa ajustada</th><th class="num">Tasa cruda</th>
    <th class="num">Contratos</th></tr></thead><tbody>{filas}</tbody></table></div>
  <p><a href="/mapa/">Ver los {D.entero(cifras['n_municipios'])} municipios en el mapa &rarr;</a></p>
</section>
<section class="caja"><h2>Contratos con más señales fuertes</h2>
  <div class="tarjetas">{tarjetas}</div>
</section>
<section class="caja"><h2>Cómo explorar Plomada</h2>
  <div class="vistas">
    <a class="card elev-sm" href="/tablero/"><span class="card-kicker">Vista</span>
      <b class="card-title">Tablero</b>
      <span class="card-meta">Los indicios agregados, por grupo y por departamento.</span></a>
    <a class="card elev-sm" href="/mapa/"><span class="card-kicker">Vista</span>
      <b class="card-title">Mapa</b>
      <span class="card-meta">Cada obra sobre el territorio, hasta el municipio.</span></a>
    <a class="card elev-sm" href="/buscar/"><span class="card-kicker">Vista</span>
      <b class="card-title">Buscador</b>
      <span class="card-meta">Por entidad, contratista o proceso, con su evidencia.</span></a>
    <a class="card elev-sm" href="/asistente/"><span class="card-kicker">Nuevo</span>
      <b class="card-title">Asistente</b>
      <span class="card-meta">Pregúntele a los datos en lenguaje natural, vía MCP.</span></a>
  </div>
</section>

<div class="cierre">
  <div class="cierre-inner">
    <h2>Un indicio no es una acusación.</h2>
    <p>Todo lo que aparece en Plomada es un indicio calculado sobre datos públicos del
       SECOP II para priorizar revisión periodística y control social. No afirma que
       ninguna persona o entidad haya obrado de forma irregular.
       <a href="/metodologia/">Cómo se calcula</a> &middot; <a href="/datos/">Descargar los datos</a></p>
  </div>
</div>
"""
    return pagina(LEMA, "Plomada detecta indicios de irregularidad en la contratación de obra "
                  "pública en Colombia siguiendo a las personas que firman, no a las empresas. "
                  "Datos públicos del SECOP II.", cuerpo, "/plomada/", clase="pg-portada",
                  js=ISLAS_JS, cabecera=cabecera, pie_aviso=False)


# --------------------------------------------------------------- landing (/)
# La raiz del sitio es la landing comercial de Adjudica (Claude Design,
# proyecto "Rebranding project briefing", artboard "Adjudica Landing Fora").
# No pasa por pagina(): tiene su propio shell (nav, pie, tono unico oscuro)
# y su propia hoja, /static/landing.css, que compone design/construir.py.
# El HTML vive en landing.html como archivo completo -- es una pagina de
# marketing con mucho CSS de por medio, y meterla en un f-string solo
# obligaria a escapar llaves. build.py sigue siendo el UNICO escritor de
# site/: la copia pasa por escribir() y test_privacy.py la barre igual que
# a las demas vistas (vocabulario, URLs externas).
LANDING = RAIZ / "landing.html"


def landing():
    return LANDING.read_text(encoding="utf-8")


def pagina_tablero():
    """El tablero (B2): vision agregada sobre datos/*.json (Tanda A los deja
    en site/datos/ si existe out_web/; si no, tablero.js degrada avisando en
    vez de romper -- igual que el resto del sitio cuando falta un dato).

    Los cinco graficos viven en static/graficos/ (B3): un modulo = un
    grafico = una unidad de datos clara, cada uno importando formato.js
    (B4) en vez de reimplementar plata/pct/entero/titulo. tablero.js es
    el orquestador de pagina: hace fetch, reparte los datos y llama a
    cada modulo.
    """
    cuerpo = f"""
{aviso_fijo("Cada cifra de este tablero mide cuánta plata pública pasó por "
            "contratos con indicios verificables. Ninguna mide cuánta plata se "
            "robaron: eso requiere una investigación judicial que este proyecto "
            "no hace ni reemplaza.")}

<header class="cab">
  <h1>Tablero</h1>
  <p class="bajada">Visión agregada de los indicios: cuánta plata pública pasó por
     contratos marcados, por indicio, por territorio y por red de proveedores.</p>
</header>

<p class="nota vacio" id="t-error" hidden>El tablero se quedó sin plomada: no se pudieron
  cargar los datos. Corra <code>pipeline/export_web.py</code> y <code>plomada/build.py</code>
  otra vez.</p>

<section class="caja hero" id="t-hero">
  <p class="tipo">Obra pública adjudicada sin competencia real (un solo oferente)</p>
  <p class="valor grande" id="t-hero-valor">—</p>
  <p class="nota" id="t-hero-nota">—</p>
</section>
<dl class="cab-grid cifras" id="t-tiles"></dl>

<section class="caja principal">
  <h2>Dónde está la plata en riesgo</h2>
  <p class="nota">Un contrato puede presentar varios indicios a la vez, así que
     <b>las barras no se suman entre si</b>: cada una se compara contra el total
     del universo, no contra las otras.</p>
  <div id="t-indicios"></div>
  <details class="tbl"><summary>Ver tabla</summary><div id="t-tbl-indicios"></div></details>
</section>

<section class="caja">
  <h2>Territorio</h2>
  <form class="filtros" id="t-filtros-territorio">
    <div><label for="t-f-dep">Departamento</label>
      <select id="t-f-dep"><option value="">Todos</option></select></div>
    <div><label for="t-f-min">Mínimo de contratos</label>
      <select id="t-f-min"><option value="20">20</option><option value="40">40</option>
        <option value="80">80</option></select></div>
  </form>
</section>

<section class="caja">
  <h2>Municipios: por qué la tasa cruda engaña</h2>
  <p class="nota">Un municipio con 4 contratos y 2 marcados da 50% y encabeza cualquier
     lista sin significar nada. La tasa ajustada corrige eso con encogimiento bayesiano
     empírico. Se muestran <b>las dos</b>, siempre.</p>
  <div id="t-leyenda-municipios"></div>
  <div id="t-municipios"></div>
  <details class="tbl"><summary>Ver tabla</summary><div id="t-tbl-municipios"></div></details>
</section>

<section class="caja">
  <h2>Departamentos: tamaño del contrato vs. falta de competencia</h2>
  <p class="nota">Eje horizontal en escala logarítmica porque el gasto va de miles de
     millones a cientos de billones. El tamaño del punto es el número de contratos.</p>
  <div id="t-departamentos"></div>
  <details class="tbl"><summary>Ver tabla</summary><div id="t-tbl-departamentos"></div></details>
</section>

<section class="caja">
  <h2>Red de proveedores</h2>
  <p class="nota">Empresas unidas por una llave que debería ser única: la misma cuenta
     bancaria, el mismo representante legal o el mismo domicilio. Cuando un mismo grupo
     concentra la obra <b>y</b> su interventoría, el que vigila y el que construye son
     la misma red.</p>
  <form class="filtros" id="t-filtros-red">
    <div><label for="t-f-cl">Grupo</label><select id="t-f-cl"></select></div>
  </form>
  <div id="t-leyenda-red"></div>
  <div id="t-red"></div>
  <p class="nota" id="t-red-nota"></p>
  <details class="tbl"><summary>Ver tabla</summary><div id="t-tbl-red"></div></details>
</section>

<section class="caja">
  <h2>Limitaciones</h2>
  <ul class="lista-lim" id="t-limitaciones"></ul>
</section>

<section class="caja">
  <h2>¿Le nace una pregunta?</h2>
  <p>Estas cifras son el agregado. Si quiere bajar al caso concreto —qué contratos
     hay detrás de una barra, qué pasa en su municipio, qué significa una bandera—
     puede preguntárselo en español.</p>
  <p><a class="btn btn-primary" href="/asistente/">Pregúntale a los datos</a></p>
</section>
"""
    return pagina("Tablero", "Visión agregada de los indicios de riesgo en la contratación "
                  "de obra pública: por indicio, por territorio y por red de proveedores.",
                  cuerpo, "/tablero/", js='<script type="module" src="/static/tablero.js"></script>',
                  clase="pg-tablero")


def bloque_codigo(lineas, etiqueta=None):
    """Un <pre> copiable. Cada linea se escapa con h(): lo que va adentro son
    comandos y respuestas del API, no markup."""
    cuerpo = "\n".join(h(l) for l in lineas)
    cab = f'<p class="codigo-etiqueta">{h(etiqueta)}</p>' if etiqueta else ""
    return f'{cab}<pre class="codigo"><code>{cuerpo}</code></pre>'


def pagina_api():
    """La vista /api/: que es el API, como se empieza, que endpoints hay, y el
    servidor MCP para quien prefiera preguntarle a los datos desde su propio
    cliente.

    La base del API se interpola desde API_URL en TODOS los ejemplos y enlaces
    -- ni una URL escrita a mano. render.yaml ya declara un host futuro
    distinto del que esta vivo hoy, asi que el dia que se mude el servicio
    esta pagina se muda sola con una variable de entorno.
    """
    base = API_URL.rstrip("/")

    endpoints = "".join(
        f'<tr><td><code>{h(ruta)}</code></td><td>{h(desc)}</td></tr>'
        for ruta, desc in C.API_ENDPOINTS)

    tools = "".join(
        f'<tr><td><code>{h(nombre)}</code></td><td>{h(desc)}</td></tr>'
        for nombre, desc in C.MCP_TOOLS)

    # Los tres corridos y verificados contra produccion antes de publicarlos.
    empezar = bloque_codigo([
        "# la cobertura y las limitaciones: lea esto antes de citar una cifra",
        f"curl {base}/v1/meta",
        "",
        "# cinco contratos marcados en Santander",
        f"curl '{base}/v1/contratos?departamento=SANTANDER&limite=5'",
        "",
        "# lo mismo, en CSV",
        f"curl '{base}/v1/departamentos?formato=csv'",
    ])

    sobre = bloque_codigo([
        '{',
        '  "datos": [ ... ],',
        '  "meta": {',
        '    "version": "1.0.0",',
        '    "fuente": "SECOP II - datos.gov.co",',
        '    "aviso": "Riesgo no es fraude. Estas cifras son indicios ...",',
        '    "paginacion": { "limite": 5, "desplazamiento": 0,',
        '                    "total": 4794, "devueltas": 5 }',
        '  }',
        '}',
    ], "El sobre de toda respuesta")

    mcp_conexion = bloque_codigo([
        f"URL       {base}/mcp/",
        "Transporte  streamable-http",
        "Auth        ninguna",
    ])

    cuerpo = f"""
<header class="cab"><h1>API</h1>
<p class="bajada">Todo lo que este sitio muestra sale de un API pública y abierta.
   Si quiere construir encima, empezar toma menos de un minuto.</p></header>

{aviso_fijo("Lo que devuelve el API son indicios calculados sobre datos públicos "
            "para priorizar una revisión. Ninguna respuesta afirma que alguien "
            "haya obrado de forma irregular.")}

<section class="caja">
  <h2>Qué es</h2>
  {C.API_INTRO}
  <p class="enlaces-api">
    <a href="{h(base)}/docs" rel="noopener" class="externo">Explorador interactivo (Swagger)</a>
    <a href="{h(base)}/redoc" rel="noopener" class="externo">Referencia (ReDoc)</a>
    <a href="{h(base)}/openapi.json" rel="noopener" class="externo">openapi.json</a>
    <a href="{h(base)}/v1" rel="noopener" class="externo">Índice en vivo</a>
  </p>
</section>

<section class="caja">
  <h2>Empezar</h2>
  {empezar}
  <p class="nota">Los tres se pueden copiar y pegar tal cual.</p>
</section>

<section class="caja">
  <h2>Convenciones</h2>
  {C.API_CONVENCIONES}
  {sobre}
</section>

<section class="caja">
  <h2>La primera llamada tarda</h2>
  {C.API_COLD_START}
</section>

<section class="caja">
  <h2>Los endpoints</h2>
  <p>Veinte rutas bajo <code>/v1</code>, todas de solo lectura. El detalle de
     parámetros y respuestas está en
     <a href="{h(base)}/docs" rel="noopener" class="externo">el explorador interactivo</a>.</p>
  <div class="tabla-scroll"><table class="table"><thead><tr>
    <th>Ruta</th><th>Qué responde</th>
  </tr></thead><tbody>{endpoints}</tbody></table></div>
</section>

<section class="caja" id="mcp">
  <h2>Conecta tu propio cliente (MCP)</h2>
  {C.MCP_INTRO}
  {mcp_conexion}
  <p class="nota"><b>La barra final importa.</b> <code>{h(base)}/mcp/</code> con
     barra. Sin ella el servicio responde con una redirección 307, y hay clientes
     que no la siguen en un POST y fallan sin decir por qué.</p>
  <p>Cómo se declara un servidor MCP remoto cambia con cada cliente, así que la
     forma exacta la manda la documentación del suyo. Lo que necesita darle es lo
     de arriba: la URL con barra final y el transporte.</p>
  <h3>Las herramientas</h3>
  <div class="tabla-scroll"><table class="table"><thead><tr>
    <th>Herramienta</th><th>Qué responde</th>
  </tr></thead><tbody>{tools}</tbody></table></div>
  <h3>O pregúntele aquí mismo</h3>
  <p>Si no quiere configurar nada, <a href="/asistente/">el asistente de Plomada</a>
     ya está conectado a estas mismas herramientas. Funciona con su propia API key
     de Anthropic y corre en su navegador.</p>
  <p class="nota">Para el detalle de arquitectura:
     <a href="{h(REPO_URL)}/blob/main/API.md" rel="noopener" class="externo">API.md</a> y
     <a href="{h(REPO_URL)}/blob/main/MCP.md" rel="noopener" class="externo">MCP.md</a>.</p>
</section>
"""
    return pagina("API", "API pública y servidor MCP de Plomada: indicios de riesgo en "
                  "la contratación de obra pública de Colombia, en JSON y CSV.",
                  cuerpo, "/api/", clase="pg-texto")


def pagina_asistente():
    """La vista /asistente/: chat con los datos, contra el proxy /chat del API.

    Es una vista propia con URL propia, no un widget flotante. Tres razones:
    la tesis del sitio es que todo tiene una URL compartible (una burbuja no
    se puede enlazar ni entra al sitemap); el flujo BYOK necesita espacio
    para pedir la key y explicar que Plomada no cobra nada; y como pasa por
    pagina(), hereda nav, pie, aviso legal y tema sin trabajo extra.

    NO va en el nav: con «API» ya son seis entradas. Se llega desde /api/ y
    desde /tablero/, que es donde el lector tiene cifras delante y le nacen
    las preguntas.

    El cuerpo se pinta en JS (static/chat.js), pero el fallback sin JS va
    pre-renderizado aqui: sin el, quien no tenga JS ve una pagina en blanco.
    """
    sugerencias = "".join(
        f'<button type="button" class="sugerencia" data-pregunta="{h(q)}">{h(q)}</button>'
        for q in C.ASISTENTE_SUGERENCIAS)

    cuerpo = f"""
<header class="cab"><h1>Pregúntale a los datos</h1>
<p class="bajada">Un asistente conectado a los indicios de Plomada. Responde
   consultando el API en vivo, no de memoria.</p></header>

{aviso_fijo("Las respuestas del asistente son indicios calculados sobre datos "
            "públicos para priorizar una revisión. Ninguna afirma que alguien "
            "haya obrado de forma irregular.")}

<noscript><section class="caja">{C.ASISTENTE_SIN_JS}</section></noscript>

<section class="caja chat" id="chat" hidden>
  <div class="chat-hilo" id="chat-hilo" role="log" aria-live="polite"
       aria-label="Conversación con el asistente">
    <div class="chat-intro">{C.ASISTENTE_INTRO}</div>
    <div class="sugerencias" id="sugerencias">
      <p class="codigo-etiqueta">Para empezar</p>
      {sugerencias}
    </div>
  </div>

  <form class="chat-forma" id="chat-forma">
    <label for="chat-entrada">Su pregunta</label>
    <textarea id="chat-entrada" name="pregunta" rows="2"
              placeholder="¿Qué contratos atípicos hay en mi municipio?"
              autocomplete="off"></textarea>
    <div class="chat-acciones">
      <button type="submit" class="btn btn-primary" id="chat-enviar">Preguntar</button>
      <button type="button" class="btn" id="chat-detener" hidden>Detener</button>
      <span class="nota" id="chat-estado" aria-live="polite"></span>
    </div>
    <p class="nota">Enter envía · Mayús+Enter hace un salto de línea</p>
  </form>

  <p class="nota chat-pie">
    <span id="chat-key-quien"></span>
    <button type="button" class="enlace" id="chat-olvidar" hidden>Olvidar mi API key</button>
  </p>
</section>

<section class="caja" id="chat-key" hidden>
  <h2>Necesita su API key de Anthropic</h2>
  {C.ASISTENTE_KEY_AYUDA}
  <form class="chat-forma-key" id="chat-forma-key">
    <label for="chat-key-campo">API key de Anthropic</label>
    <input type="password" id="chat-key-campo" autocomplete="off" spellcheck="false"
           placeholder="sk-ant-…" aria-describedby="chat-key-error">
    <p class="nota" id="chat-key-error" role="alert"></p>
    <div class="chat-acciones">
      <button type="submit" class="btn btn-primary">Guardar y empezar</button>
      <a class="btn" href="https://console.anthropic.com/settings/keys"
         rel="noopener" target="_blank">Conseguir una llave ↗</a>
    </div>
  </form>
</section>
"""
    return pagina("Asistente", "Pregúntele en español a los indicios de riesgo en la "
                  "contratación de obra pública de Colombia. Usa su propia API key de "
                  "Anthropic.",
                  cuerpo, "/asistente/",
                  js='<script type="module" src="/static/chat.js"></script>',
                  clase="pg-asistente")


def pagina_datos(archivos):
    li = "".join(f'<li><a href="/datos/{h(n)}" download><code>{h(n)}</code></a> '
                 f'<span>{h(desc)}</span> <small>{k:,.0f} KB</small></li>'.replace(",", ".")
                 for n, desc, k in archivos)
    cuerpo = f"""
<header class="cab"><h1>Datos</h1>
<p class="bajada">Si el proyecto es público, la gente tiene que poder llevarse los datos.
   Estos archivos son los que alimentan el sitio, ya saneados de identificadores
   personales. <a href="/metodologia/#privacidad">Qué se quitó y por qué</a></p></header>
<section class="caja"><ul class="descargas">{li}</ul>
<p class="nota">Fuente primaria: SECOP II, Colombia Compra Eficiente. Fronteras: DANE.
   Estos CSV son derivados; para reproducir el análisis desde cero, empiece por la fuente.</p>
</section>"""
    return pagina("Datos", "Descarga de los datos derivados de Plomada en CSV y GeoJSON.",
                  cuerpo, "/datos/", clase="pg-texto")


# -------------------------------------------------------------------------- main
_API = None


def api():
    """(modulo api_tablero, cliente) — importado una sola vez.

    pipeline/ tiene su PROPIO build.py (el del warehouse): dejar su ruta en
    sys.path despues del import haria que el "import build" de
    test_privacy.py resuelva ese modulo por error en vez de este archivo. Se
    agrega y se quita al toque.
    """
    global _API
    if _API is None:
        sys.path.insert(0, str(PIPELINE))
        try:
            import api_tablero
            from api_cliente import ApiCliente
        finally:
            sys.path.remove(str(PIPELINE))
        _API = (api_tablero, ApiCliente())
    return _API


def datos_del_build(api_tablero, cli):
    """Lo que el build necesita del API para las paginas que sigue rindiendo
    en servidor (portada, mapa, metodologia). Devuelve
    (glosario, municipios, departamentos, top_contratos, ids).

    `ids` sale de recorrer los 12.678 atipicos (64 llamadas de 200, ~25 s).
    Ese mismo recorrido deja el score medio y el umbral que la metodologia
    necesita, asi que no cuesta ninguna llamada extra.
    """
    def seguro(nombre, fn, vacio):
        """Cada pieza degrada por separado, en vez de reventar en la primera.

        Que el build TERMINE no significa que se publique. Si el API estaba
        caido, la portada queda en "sin dato", el sitemap sin fichas y la
        metodologia sin banderas -- y test_privacy.py lo detecta y borra
        site/. Eso es deliberado: en un despliegue estatico, un build que
        falla deja en pie el despliegue anterior, que es preferible a
        reemplazarlo por un sitio vacio. La degradacion a "sin dato" es para
        el visitante cuando el API se cae DESPUES de publicar, no para
        publicar un cascaron.
        """
        try:
            return fn(cli)
        except Exception as e:                      # noqa: BLE001 - se reporta y sigue
            print(f"aviso: el API no pudo dar {nombre} ({e}); esa parte queda sin dato. "
                  "Si esto se repite en varias piezas, el build terminara pero "
                  "test_privacy.py no dejara publicar.", file=sys.stderr)
            return vacio

    return (seguro("el glosario de banderas", api_tablero.banderas, {}),
            seguro("los municipios", api_tablero.municipios_todos, []),
            seguro("los departamentos", api_tablero.departamentos, []),
            seguro("los contratos destacados", api_tablero.top_contratos, []),
            seguro("el listado de atipicos", api_tablero.todos_los_atipicos, []))


def agregados_de(filas):
    """score medio y umbral (el minimo de puntos crudos) sobre los atipicos."""
    if not filas:
        return {"score_medio": None, "umbral": None}
    return {
        "score_medio": sum(c.get("score") or 0 for c in filas) / len(filas),
        "umbral": min((c.get("puntos_crudos") or 0) for c in filas),
    }


def shell_ficha():
    """Una sola pagina para las 12.678 fichas. El cuerpo lo pinta
    static/ficha.js con GET /v1/contratos/{id}, derivando el id del slug.

    El aviso "Indicio, no acusacion" se queda AQUI, en el HTML estatico, no
    en el JS: es la salvedad que no puede depender de que una llamada de red
    funcione. Si el API no responde, el visitante igual la ve.

    Leaflet entra en TODAS las fichas, no solo en las que tienen mapa: el
    shell es uno solo para 12.678 contratos y aqui todavia no se sabe cual
    se va a pedir. Eso no dispara ninguna peticion a Esri -- el bundle es
    local (static/vendor/leaflet/) y las tiles siguen siendo click-to-load
    dentro de mapa-satelital.js.
    """
    cuerpo = f"""
{aviso_fijo("Este contrato está marcado por patrones detectados en datos públicos. "
            "No afirma que alguien haya obrado de forma irregular.")}
<p id="ficha-estado" class="nota" aria-live="polite">Cargando el contrato…</p>
<div id="ficha" hidden></div>
"""
    return pagina("Contrato", "Ficha de un contrato de obra pública con las señales de riesgo "
                  "detectadas sobre datos del SECOP II. Indicio para revisión, no acusación.",
                  cuerpo, "/contrato/", head=LEAFLET_CSS,
                  js=LEAFLET_JS + '<script type="module" src="/static/ficha.js"></script>',
                  clase="pg-ficha")


def shell_municipio():
    """Idem para los 721 municipios: static/municipio.js lo hidrata."""
    cuerpo = """
<p id="mun-estado" class="nota" aria-live="polite">Cargando el municipio…</p>
<div id="municipio" hidden></div>
"""
    return pagina("Municipio", "Contratos de obra pública marcados en un municipio, "
                  "ordenados por señales de riesgo. Indicio para revisión, no acusación.",
                  cuerpo, "/municipio/",
                  js='<script type="module" src="/static/municipio.js"></script>',
                  clase="pg-municipio")


def cifras_universo(datos_api):
    """Las cifras del universo que antes estaban escritas a mano en
    pagina_metodologia() y portada() (5.975.627, $209 billones, 11.121,
    14,3%...) -- ninguna calculada, y ya no coincidian con ningun corte real.
    Ahora salen de datos_api (lo que devolvio escribir_datos_tablero(), que a
    su vez viene del API real via pipeline/api_tablero.py).

    Si el API no tenia meta.json o titulares.json disponibles, cada clave
    queda en None: D.entero()/D.plata()/D.pct() ya saben imprimir "sin dato"
    para None, asi que la pagina degrada mostrando eso, nunca una cifra
    vieja ni inventada.

    Dos numeros del metodo viejo NO tienen equivalente en el API (el total
    de TODO SECOP II y el desglose por tipo_contrato Obra/Interventoria/
    Consultoria/APP/Concesion no son parte de ningun endpoint de /v1/*): esas
    dos quedan en None a proposito, no se resuelven con datos locales.
    """
    meta = datos_api.get("meta.json")
    titulares = datos_api.get("titulares.json") or []
    atipico = next((t for t in titulares
                     if str(t.get("concepto", "")).startswith("Clasificado atipico")), None)
    red = next((t for t in titulares
                if str(t.get("concepto", "")).startswith("Con indicio fuerte de red")), None)
    n_universo = meta.get("contratos") if meta else None
    n_atipicos = meta.get("contratos_atipicos") if meta else None
    return {
        "n_universo": n_universo,
        "valor_universo": meta.get("valor_total") if meta else None,
        "n_atipicos": n_atipicos,
        "pct_atipicos": (n_atipicos / n_universo) if n_universo else None,
        "valor_atipico": atipico["valor"] if atipico else None,
        # cuarta columna de la franja de cifras de portada. Sale del mismo
        # titulares.json que las otras tres; si el API no lo trae, queda en
        # None y la columna se cae entera (ver portada()), que es mejor que
        # publicar un "sin dato" en tipografia de cifra.
        "n_red_fuerte": red["n_contratos"] if red else None,
        "valor_red_fuerte": red["valor"] if red else None,
    }


def escribir_datos_tablero():
    """Escribe site/datos/*.json con datos REALES del API de Plomada
    (pipeline/api_tablero.py -> pipeline/api_cliente.py). Ya no lee out_web/
    ni ningun fixture local: cada archivo sale de una llamada al API en
    https://plumb-duy6.onrender.com (o $PLOMADA_API_URL).

    Si el API todavia no tiene datos cargados (base vacia,
    'datos_no_disponibles') o no respondio, el archivo correspondiente
    simplemente NO se escribe -- nunca se rellena con la ultima cifra local
    conocida ni con un numero inventado. El tablero (tablero.js) y la cifra
    de portada (CifraLider.vue) ya saben degradar cuando un /datos/*.json no
    existe: muestran "No se pudieron cargar los datos del tablero" o el
    enlace de respaldo al tablero. Es el mismo patron que ya usaban cuando
    faltaba out_web/, solo que ahora la causa es "el API esta vacio", no
    "no se corrio el pipeline local".
    """
    api_tablero, _ = api()

    destino = SITE / "datos"
    destino.mkdir(parents=True, exist_ok=True)
    archivos = api_tablero.construir()
    escritos = [n for n, datos in archivos.items() if datos is not None]
    faltantes = [n for n, datos in archivos.items() if datos is None]
    for nombre in escritos:
        with open(destino / nombre, "w", encoding="utf-8") as fh:
            json.dump(archivos[nombre], fh, ensure_ascii=False, separators=(",", ":"))

    if escritos:
        print(f"datos del tablero: {len(escritos)} archivo(s) del API real -> site/datos/ "
              f"({', '.join(sorted(escritos))})", file=sys.stderr)
    if faltantes:
        print(f"aviso: el API no tiene datos disponibles para {', '.join(sorted(faltantes))} "
              "-- el tablero mostrara que no hay datos, no una cifra local ni simulada.",
              file=sys.stderr)
    return archivos


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    shutil.copytree(RAIZ / "static", SITE / "static")
    datos_api = escribir_datos_tablero()

    api_tablero, cli = api()
    glos, muns, deps, tops, filas = datos_del_build(api_tablero, cli)
    ids = [c["id_contrato"] for c in filas]

    # 7.1 — UNA ficha, no 12.678: el contenido lo trae static/ficha.js del
    # API, derivando el id del propio slug de la URL.
    escribir("contrato/index.html", shell_ficha())

    # municipios: idem, un solo shell que static/municipio.js hidrata
    escribir("municipio/index.html", shell_municipio())

    # tablero (B2)
    escribir("tablero/index.html", pagina_tablero())

    # 7.2
    escribir("mapa/index.html", pagina_mapa(deps, muns))

    # 7.3 — el indice de 8,5 MB desaparecio: buscar.js consulta el API.
    escribir_json("datos/banderas.json", glos)

    # Geocodificacion para el mapa satelital de la ficha. El API no devuelve
    # coordenadas, asi que ficha.js las busca aqui con la misma clave que usa
    # data.coords_contrato(). Si geo/geocache.json no existe, se publica el
    # cache vacio y la ficha muestra "sin geocodificar" en vez de fallar.
    escribir_json("datos/geocache.json", D.cargar_geocache())
    escribir("buscar/index.html", pagina_buscar())

    # 7.4
    # (n_admin -- entidad x periodo de gobierno -- salio de aqui: no es
    # derivable del API, ContratoResumen no trae periodo_gobierno, y la
    # portada no publica una celda que solo sabe decir "sin dato".)
    cifras = {"n_municipios": len(muns)}
    cifras.update(agregados_de(filas))
    cifras.update(cifras_universo(datos_api))
    escribir("metodologia/index.html", pagina_metodologia(glos, cifras, cifras["umbral"]))

    # raiz: la landing comercial. La portada de Plomada (cifras, ranking,
    # vistas) sigue existiendo en /plomada/ y en el sitemap: es el hub del
    # producto, no desaparece, cambia de sitio.
    escribir("index.html", landing())
    escribir("plomada/index.html", portada(muns, cifras, tops))

    # descargas: los CSV completos ya no se generan aqui. El API los sirve,
    # pero `formato=csv` respeta `limite<=200`, asi que no hay descarga masiva
    # de una sola llamada: el buscador arma el CSV paginando (buscar.js).
    escribir("datos/index.html", pagina_datos([]))

    escribir("api/index.html", pagina_api())
    escribir("asistente/index.html", pagina_asistente())

    # sitemap + robots. Las fichas se hidratan en el navegador, pero SIGUEN
    # teniendo URL propia y entrando al sitemap: es lo que las mantiene
    # compartibles y rastreables (restriccion 2.3 del plan).
    urls = ["/", "/plomada/", "/tablero/", "/mapa/", "/buscar/", "/metodologia/", "/datos/",
            "/api/", "/asistente/"] + \
           [f"/contrato/{D.slug(i)}/" for i in ids] + \
           [url_municipio(m["departamento"], m["ciudad"]) for m in muns]
    escribir("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
             + "".join(f"<url><loc>{h(u)}</loc></url>" for u in urls) + "</urlset>")
    escribir("robots.txt", "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n")

    # Regla de reescritura para el host estatico: sin esto, /contrato/<slug>/
    # devuelve 404 porque no existe un archivo ahi. Formato _redirects, que
    # entienden Netlify y Cloudflare Pages. Si el host es otro, hay que
    # traducirla (Vercel: rewrites en vercel.json).
    escribir("_redirects", "/contrato/*   /contrato/index.html   200\n"
                           "/municipio/*  /municipio/index.html  200\n")

    print(f"site/: shells dinamicos, {len(ids)} fichas en el sitemap, "
          f"{len(muns)} municipios, {len(glos)} banderas, {len(urls)} URLs.")

    # La prueba de privacidad tumba el build. Si algo prohibido llego a un archivo,
    # no queda nada que alguien pueda publicar por error.
    import test_privacy
    try:
        test_privacy.main()
    except SystemExit:
        shutil.rmtree(SITE)
        sys.exit("  site/ borrado: no se publica hasta que la prueba pase.")


def escribir_json(ruta, obj):
    p = SITE / ruta
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def exportar_csvs(contratos, muns, deps, admins, glos):
    salida = []
    tablas = [("contratos_atipicos.csv", [D.publicar(c) for c in contratos],
               "Contratos marcados, saneado de documentos y cuentas"),
              ("ranking_municipios.csv", muns, "721 municipios con tasa cruda y ajustada"),
              ("ranking_departamentos.csv", deps, "34 departamentos, capa base del mapa"),
              ("ranking_administraciones.csv", admins, "Entidad x periodo de gobierno"),
              ("banderas_glosario.csv", list(glos.values()), "Las banderas con su peso y glosa")]
    for nombre, filas, desc in tablas:
        if not filas:
            continue
        cols = [k for k in filas[0] if not k.startswith("_")]
        ruta = SITE / "datos" / nombre
        with open(ruta, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(filas)
        salida.append((nombre, desc, ruta.stat().st_size / 1024))
    g = SITE / "datos" / "departamentos.geojson"
    if g.exists():
        salida.append(("departamentos.geojson", "Fronteras departamentales con la tasa ajustada",
                       g.stat().st_size / 1024))
    return salida


if __name__ == "__main__":
    main()

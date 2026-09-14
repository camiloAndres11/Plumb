# Plomada — frontend

Sitio estatico. Sin npm, sin build toolchain: Python 3 de la libreria estandar
genera HTML ya renderizado, y el navegador solo carga Leaflet desde CDN para el
mapa. Los 78.000 contratos caben en un portatil (seccion 9 del brief).

```bash
python3 gen_synthetic.py             # 1. datos falsos en fixtures/, con los headers del contrato (seccion 10)
.venv/bin/python geocode.py          # 2. (opcional) geocodifica a geo/geocache.json
python3 build.py                     # 3. genera site/ y corre la prueba de privacidad
python3 -m http.server -d site 8765
```

`build.py` **borra `site/` si la prueba falla**. No hay forma de publicar por error
un artefacto con una columna prohibida.

### De donde salen los datos

`data.py` resuelve el directorio de CSV en este orden, y **anuncia por stderr
cual eligio** — publicar una demo con datos sinteticos creyendo que son reales
es un problema, no un detalle de log:

1. `$PLOMADA_OUT`, si esta definida. Control explicito, para pruebas o CI.
2. `<raiz-del-repo>/out/`, si existe y trae `contratos_atipicos.csv`. Es el
   contrato de datos REAL: los mismos cinco CSV que exporta
   `pipeline/report.py` (ver su diccionario `exports`), con el mismo esquema.
3. `fixtures/` de este directorio, sinteticas, como ultimo recurso. Viven en
   `fixtures/` y no en `out/` a proposito, para que el nombre de la carpeta ya
   delate que no son datos de verdad.

Cuando llegue el pipeline real, no hay que tocar nada aqui: basta con que
`out/` exista en la raiz del repo (o apuntar `$PLOMADA_OUT` a donde sea). El
dia que `fixtures/` deje de hacer falta, borre `gen_synthetic.py` junto con
ella.

## Estructura

| Archivo | Que hace |
|---|---|
| `data.py` | **Capa de datos.** Unico punto que toca los CSV: resuelve que directorio usar (`$PLOMADA_OUT` &rarr; `out/` real &rarr; `fixtures/`), sanea identificadores, extrae la URL del struct `urlproceso`, formatea pesos colombianos, hace title-case sin destrozar siglas, arma las banderas con su evidencia y calcula las claves de geocodificacion. Cuando esto sea una API, se cambia solo este archivo. |
| `build.py` | Renderiza las cuatro vistas a `site/`. |
| `contenido.py` | Textos editoriales largos (metodologia, falsos positivos, limitaciones). Separados para poder corregirlos sin tocar codigo. |
| `geocode.py` | Offline. Geocodifica los CSV resueltos por `data.py` a `geo/geocache.json` con `geopy` (Nominatim &rarr; ArcGIS &rarr; cabecera municipal). Corre en un venv aparte; `build.py` nunca toca la red. |
| `test_privacy.py` | La prueba que tumba el build. |
| `gen_synthetic.py` | Datos falsos del dia uno. Escribe en `fixtures/`. Desechable. |
| `fixtures/` | Los CSV **sinteticos**, generados por `gen_synthetic.py`. Mismo esquema que `out/` en la raiz del repo (el contrato real, seccion 4), pero explicitamente no son datos reales — de ahi el nombre. Se usan solo cuando no hay `out/` real ni `$PLOMADA_OUT`. |
| `geo/` | Fronteras departamentales del DANE + `geocache.json` (generado, no a mano). |

### Mapa satelital en la ficha (geocodificacion)

`geocode.py` necesita `geopy`, que no esta en la libreria estandar. Vive en un
venv del proyecto para no tocar el Python del sistema:

```bash
python3 -m venv .venv && .venv/bin/pip install geopy
.venv/bin/python geocode.py                # corre la cascada completa
.venv/bin/python geocode.py --limit 10     # para probar sin esperar todo
.venv/bin/python geocode.py --solo-cabecera  # salta el intento de direccion exacta
```

Cascada de fallback, igual a la de `INSTRUCCIONES_AGENTE_GEOCODIFICACION.md`:
Nominatim (direccion exacta) &rarr; ArcGIS (direccion exacta) &rarr; ArcGIS
(solo cabecera municipal) &rarr; centro de Colombia. La cache queda en
`geo/geocache.json`, con `time.sleep(1)` entre llamadas reales (politica de
uso de Nominatim). Correr de nuevo es instantaneo: solo geocodifica lo que
falte.

`build.py` solo **lee** ese cache — nunca depende de la red ni de `geopy` — y
si una direccion todavia no esta geocodificada, la ficha muestra una nota en
vez de fallar. El fallback "centro de Colombia" (`precision: "defecto"`)
**nunca se pinta como mapa**: un mapa generico en Bogota para un contrato de
otro departamento seria peor que no mostrar nada. Con el CSV sintetico,
ArcGIS resuelve el 100% de las 204 filas a nivel de municipio o mejor, asi que
no aparece ningun caso "defecto" en la demo.

ponytail: a escala del pipeline real (78.000 contratos) el intento de
direccion exacta es el que domina el tiempo de geocodificacion, porque una
direccion rural rara vez calza exacto de todas formas. `--solo-cabecera` salta
directo al nivel de municipio (unas pocas centenas de consultas en vez de
decenas de miles). Subir a intento exacto de nuevo si en algun momento hace
falta precision de calle.

El popup del mapa se arma con `document.createElement`/`textContent`
(`static/mapa-satelital.js`), no interpolando la direccion dentro de un string
de HTML: la especificacion original inyectaba el texto con un template
literal de JS que un caracter de la fuente (una comilla, un `<script>`) podria
haber roto. `test_privacy.py` lo verifica.

## Las cuatro vistas

- **7.1 Ficha** `/contrato/<id>/` — cada bandera encendida con el numero que la
  disparo, agrupada por `grupo` y ordenada por `peso`. Boton a SECOP II. Aviso
  permanente de que es un indicio. Mapa satelital de la direccion de ejecucion
  (geocodificado offline, ver abajo).
- **7.2 Mapa** `/mapa/?dep=<slug>` — coropletico por `tasa_ajustada`, con la cruda
  al lado. Capa municipal a la espera del crosswalk DIVIPOLA (ver abajo).
- **7.3 Buscador** `/buscar/?...` — filtros en la query string, ordenable,
  exporta CSV ya saneado.
- **7.4 Metodologia** `/metodologia/` — las 22 banderas del CSV, el puntaje, los
  falsos positivos conocidos y los limites de cobertura.

## Lo que este frente NO resuelve, a proposito

**El cruce `ciudad` (texto libre) &rarr; DIVIPOLA.** Lo esta haciendo otro frente del
equipo. Este codigo no arma su propio pareo de nombres: pintar un municipio
equivocado es peor que no pintarlo. La capa municipal del mapa se enciende sola en
cuanto existan estos dos archivos:

- `out/divipola_municipios.csv` con `departamento,ciudad,cod_divipola`
- `geo/municipios.geojson` con los poligonos del DANE

Mientras tanto los municipios estan en la tabla ordenable bajo el mapa, con la
misma metrica, y cada uno tiene su pagina propia en `/municipio/<slug>/`.

A nivel de **departamento** si se cruza, y por codigo oficial, no por nombre: el
GeoJSON del DANE trae `DPTO`. Los dos unicos alias que hicieron falta
(`SANTAFE DE BOGOTA D.C`, el archipielago de San Andres) estan en `ALIAS_DEP` en
`build.py`, en un solo lugar y a la vista.

## Decisiones que conviene conocer antes de tocar el codigo

- **Nada se ordena por `tasa_cruda`.** Se muestra al lado de la ajustada, siempre,
  para que la correccion sea auditable.
- **Todo el dinero se suma con `valor_plausible`.** Los contratos con valor
  imposible no se borran: se muestran como falla de publicacion de la entidad.
- **Los nombres y textos de banderas no estan en el codigo.** Salen de
  `banderas_glosario.csv`. Una bandera nueva del pipeline aparece sola en la ficha
  y en la metodologia; lo unico que le faltaria es la frase con el numero, que se
  agrega en `_ev()` de `data.py`.
- **`ev_tipo_red_cuenta` no se trata igual en los tres casos, y cada uno es
  su propia bandera (F1.2b, alineado con `sql/02_flags.sql`).**
  `empresas_independientes` enciende `f_cuenta_compartida` (indicio fuerte,
  sin atenuar). `consorcios` enciende `f_cuenta_consorcios`, una bandera
  aparte y mas debil (peso 1), pintada atenuada con la razon a la vista.
  `comunitaria` **no enciende ninguna bandera**: en el pipeline real es ruido
  administrativo silencioso (el municipio canaliza pagos de varias juntas de
  accion comunal por la misma cuenta), no un indicio ni siquiera atenuado.
  Tratar los tres casos igual publica falsos positivos; y pintar `comunitaria`
  como si fuera indicio, aunque sea atenuado, iria mas alla de lo que el
  pipeline real justifica.
- **Vocabulario.** La prueba falla si aparece "corrupto", "fraude", "delito",
  "robo", "culpable" o similares en cualquier texto de la interfaz.

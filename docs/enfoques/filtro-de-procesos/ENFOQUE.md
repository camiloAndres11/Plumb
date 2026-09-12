# Enfoque 1 · Filtro de procesos

Rama `feature/filtro-de-procesos`. Diseño en [`diseno/`](diseno/README.md),
estilo base en [`estilo-base.md`](estilo-base.md).

## 1. Promesa al cliente

**"Deje de presentarse a licitaciones que no puede ganar."**

## 2. Problema que ataca

Una constructora mediana sin departamento de licitaciones revisa el SECOP a
mano, se ilusiona con procesos donde no cumple un habilitante (o donde
siempre gana el mismo) y gasta entre 40 y 80 horas de un ingeniero armando
una propuesta que se cae en la evaluación o pierde por historial. Ese tiempo
no se recupera: es plata y es moral del equipo. El filtro le devuelve una
lista corta con la razón de cada descarte y las horas que se ahorra.

## 3. Cómo funciona

**Datos**

- Procesos abiertos: el universo `accionable` del snapshot de alertas de
  Plomada (`alertas`, 565 procesos al 2026-08-22), con sus banderas
  pre-adjudicación (`f_ventana_corta`, `f_sin_interes_a_tiempo`,
  `f_cierre_movido`, tasa histórica de proponente único de la entidad).
- Histórico por entidad, calculado desde `base` (77.864 contratos): quién
  gana, cuántas veces (`share_top1`), tasa de proponente único, mediana de
  oferentes, y lo mismo por entidad × familia UNSPSC.
- Frecuencia de cada código UNSPSC en el histórico (proxy de "requisito muy
  específico": un código que casi nadie usa).
- Perfil de la constructora (fixture JSON ficticio): familias UNSPSC,
  regiones, experiencia en SMMLV, capacidad residual, índices financieros.

**Lógica** (`pliego/filtro/logica.py`, parámetros en `reglas.py`)

1. *Habilitantes (duros)*: objeto (familia UNSPSC del proceso ∈ familias del
   perfil), RUP vigente, capacidad residual ≥ presupuesto oficial, experiencia
   en la familia ≥ 100 % del presupuesto en SMMLV, índices financieros y
   organizacionales dentro de los umbrales usuales de los documentos tipo.
   Si uno falla → **no presentarse**. Si falta el dato → **revisar**.
2. *Señales (blandas)*: parten de 50 y suman o restan con pesos explícitos:
   región e cuantía objetivo (±), holgura de experiencia y capacidad (+),
   entidad con competencia real (+10), ganador recurrente en la entidad o en
   la familia (−18), entidad con ≥80 % de proponente único (−20), mucha
   competencia (−8), código UNSPSC raro (−10), ventana corta (−8), cierra en
   ≤3 días (−10).
3. *Recomendación*: ≥65 **presentarse**, <40 **no presentarse**, entre
   ambos **revisar**.
4. *Horas ahorradas*: por modalidad (licitación 80 h, selección abreviada
   40 h, concurso de méritos 60 h, mínima cuantía 12 h…), sumadas sobre los
   "no presentarse".

**Flujo del usuario**: entra a la lista (ya ordenada: presentarse → revisar
→ no presentarse), filtra por recomendación, abre un proceso y ve el veredicto
con cada razón y su cifra, más un consejo de "si igual quiere ir".

## 4. Qué se construyó

- `pliego/filtro/logica.py` — reglas puras, con `Razon` (código, texto,
  cumple, evidencia, peso) y `Evaluacion`.
- `pliego/filtro/reglas.py` — umbrales, pesos y horas por modalidad.
- `pliego/filtro/datos.py` — carga de fixtures y evaluación de todos.
- `pliego/filtro/semilla.py` — genera los fixtures desde el warehouse.
- `pliego/filtro/app.py` — FastAPI:
  - `GET /` lista con conteos, tabs por recomendación y horas ahorradas.
  - `GET /proceso/{id}` detalle: veredicto, habilitantes como checklist,
    señales con `+N/−N`, horas y consejo.
  - `GET /perfil` el perfil evaluado.
  - `GET /api/resumen`, `GET /api/procesos?recomendacion=&departamento=`,
    `GET /api/procesos/{id}`, `GET /api/perfil` (JSON).
- `pliego/comun/web.py` + `pliego/static/base.css` — shell y tokens del
  estilo `new-landing`.
- `pliego/tests/test_filtro.py` — 22 pruebas sobre reglas y puntaje.

## 5. Qué está simulado o pendiente

- **El perfil de la constructora es ficticio** (`fixtures/perfil_constructora.json`).
  En producción sale del RUP + estados financieros del cliente.
- **Los requisitos del pliego no se leen del pliego**: se asumen los valores
  usuales de los documentos tipo (experiencia = 100 % del presupuesto en
  SMMLV, liquidez ≥ 1,2, endeudamiento ≤ 70 %, etc.). Cada pliego fija los
  suyos; la rama `feature/checklist-habilitantes` es la que los extrae.
- **"Requisitos muy específicos"** se aproxima con la rareza del código
  UNSPSC; sin el texto del pliego no hay más señal.
- **Las horas por modalidad son de oficio**, no medidas con clientes.
- **El snapshot es del 2026-08-22** y el prototipo lo trata como "hoy":
  los `dias_restantes` son relativos a esa fecha. Refrescar =
  `python pipeline/ingest_abiertos.py && python pipeline/alertas.py &&
  python -m pliego.filtro.semilla`.
- SMMLV 2026 fijado en `reglas.py` (1.750.905).
- Sin autenticación ni multi-cliente: un solo perfil.

## 6. Cómo probarlo

```bash
# desde la raiz del repo, con el venv del pipeline (duckdb, fastapi, uvicorn)
python -m pytest pliego/tests -q            # 22 passed
uvicorn pliego.filtro.app:app --port 8010   # http://localhost:8010
```

Deberías ver: "565 procesos abiertos, 36 valen su tiempo", tres cifras
(36 / 143 / 386), la pastilla "Se ahorra 22.540 horas", y la lista ordenada.
Al abrir `http://localhost:8010/proceso/CO1.REQ.10723838` (Rama Judicial,
Pereira) sale **No presentarse · 44**, el habilitante de experiencia en
rojo vacío ("le faltan 408,1 SMMLV"), la señal "WORLDTEK SAS ganó el 44 %
de los 16 procesos" en −18, y "Se ahorra 40 h".

Los fixtures ya están commiteados; regenerarlos requiere el warehouse:
`python -m pliego.filtro.semilla`.

## 7. Cambios a código compartido

Ninguno. Todo vive en `pliego/` (paquete nuevo) y `docs/`. No se tocó
`pipeline/`, `sql/`, `api/` ni `plomada/`. Dependencias: ninguna nueva
(duckdb, fastapi, uvicorn ya están en `pipeline/requirements.txt` y
`api/requirements.txt`). Las fuentes Archivo se copiaron de
`plomada/static/fonts/` a `pliego/static/fonts/`.

## 8. Preguntas abiertas para el equipo

1. ¿Los pesos de las señales (−18 ganador recurrente, −20 entidad cerrada)
   deberían calibrarse con resultados reales de clientes o quedarse como
   reglas explícitas y discutibles, al estilo de las banderas de Plomada?
2. ¿"Ganador recurrente" es señal de no presentarse o de "presentarse en
   consorcio con él"? Hoy resta.
3. ¿El umbral de experiencia (100 % del presupuesto en SMMLV) se lee del
   pliego (rama 2) o se deja como parámetro por cliente?
4. ¿Se muestra "no presentarse" cuando la única falla es región/cuantía
   (elegible pero fuera de foco)? Hoy sí, con el consejo "es elegible".
5. ¿Qué hacer con los 27.114 procesos `sin_fecha_cierre` del snapshot? Hoy
   se excluyen; son el 85 % de lo "abierto" en la plataforma.

# Enfoque 2 · Checklist de habilitantes

Estilo base en [`../../estilo-base.md`](../../estilo-base.md). El canvas de diseño original quedó
en el tag `archivo/disenos-enfoques`.

## 1. Promesa al cliente

**"No vuelva a quedar por fuera por un papel."**

## 2. Problema que ataca

Una parte grande de las ofertas de constructoras pequeñas se rechaza o
queda "no hábil" por cosas que no tienen que ver con la obra: un certificado
de cámara de comercio con más de 30 días, la garantía de seriedad que no se
expidió a tiempo, un Formato 3 sin el consecutivo del RUP, o un índice
financiero que no se leyó bien en la Matriz 2. El pliego tiene 60–200
páginas y los requisitos están regados en cinco capítulos. El checklist
los saca, los verifica contra la carpeta de la constructora y enlaza cada
uno a la página exacta del pliego, para que quien arma la oferta sepa qué
falta y dónde dice que hace falta.

## 3. Cómo funciona

**Datos**

- Un **pliego real**: `SI-LP-004-2021`, licitación de obra pública del
  Municipio de Bucaramanga (documentos tipo, 66 páginas, 3 grupos/lotes),
  descargado de SECOP II y guardado como fixture.
- **20 requisitos extraídos** en `requisitos_SI-LP-004-2021.json`, cada uno
  con categoría (jurídico / financiero / técnico / experiencia), tipo de
  regla, parámetros, la **cita literal** y la **página**.
- **Trazabilidad automática al PDF** (`semilla.py`): localiza cada cita en
  su página con `pdftotext -bbox-layout` (poppler) y guarda las cajas en
  fracción de página (`citas_bbox.json`); renderiza las 12 páginas citadas
  a PNG. Las 20 citas se localizaron.
- **Carpeta de documentos ficticia** de Constructora Andina
  (`documentos_constructora.json`): RUP con contratos, cámara de comercio,
  estados financieros, Formato 5, etc. Faltan a propósito la garantía y el
  Formato 3, y la cámara está vencida.

**Lógica** (`pliego/checklist/logica.py`): un verificador por tipo de regla.

| Tipo | Regla |
|---|---|
| `documento` | Está en la carpeta; vigente / en firme / firmado; expedido ≤ N días antes del cierre |
| `indicador` | Campo de los estados financieros ≥ / ≤ umbral. Si el umbral no viene en el PDF (`umbral_simulado`), el estado es **revisar** aunque cumpla |
| `capital_trabajo` | AC − PC ≥ 10 % del presupuesto del lote (sección 3.7) |
| `capacidad_residual` | CRP ≥ CRPC = POE − anticipo (50 %), anualizado si el plazo > 12 meses (3.10) |
| `experiencia` | 1–6 contratos terminados en las actividades del lote, suma en SMMLV ≥ 75/120/150 % del presupuesto según cuántos se usen (3.5.8) |
| `experiencia_actividades` | Los contratos cubren las dos actividades de la Matriz 1 para el grupo |
| `duracion_sociedad` | Duración ≥ cierre + plazo + 1 año (3.3.2) |
| `garantia` | 10 % del presupuesto del lote, 3 meses de vigencia (7.1) |
| `revisar` | Juicio humano (inhabilidades, objeto social) |

Cuatro estados: **cumple / no cumple / falta documento / revisar**, con
la evidencia numérica y la página. "Hábil" = ni "no cumple" ni "falta".

**Flujo del usuario**: elige el grupo (los requisitos cambian con el
presupuesto del lote), ve primero lo que impide presentarse, abre cualquier
requisito y ve la página real del pliego con el fragmento resaltado y la
verificación al lado.

## 4. Qué se construyó

- `pliego/checklist/logica.py`, `datos.py`, `semilla.py`.
- `pliego/checklist/app.py` (FastAPI, puerto 8020):
  - `GET /?lote=N` checklist agrupado por urgencia, con conteos por estado.
  - `GET /requisito/{id}?lote=N` requisito + página renderizada con el
    fragmento resaltado + cita en bloque de papel + enlace al PDF en esa página.
  - `GET /carpeta` documentos de la constructora y contratos del RUP.
  - `GET /pliego.pdf`, `GET /paginas/pN.png`, `GET /api/checklist?lote=N`,
    `GET /api/carpeta`.
- `pliego/tests/test_checklist.py` — 19 pruebas (una por tipo de regla,
  los cuatro estados, y humo sobre el pliego real con sus cajas).
- Shell y hoja base iguales a las demás ramas (`pliego/comun`, `pliego/static`).

## 5. Qué está simulado o pendiente

- **La extracción de requisitos es manual.** El JSON se escribió leyendo
  el pliego; el pipeline de extracción automática (LLM sobre el texto por
  página → requisitos con cita y página) no existe en este repo. Lo que sí
  es automático es la localización del fragmento en la página.
- **Umbrales financieros**: el pliego remite a la "Matriz 2", un anexo que
  no viene en el PDF. Se usan los usuales de los documentos tipo y se marcan
  `umbral_simulado` → estado "revisar".
- **Fecha de cierre simulada** (2021-07-06): el cronograma es el Anexo 2.
- **Carpeta de documentos ficticia**, con campos ya "extraídos"; en
  producción cada PDF del cliente pasa por el mismo extractor.
- **Actividades de experiencia** se comparan por etiqueta
  (`edificaciones`, `espacio_publico`), no por el texto de la Matriz 1.
- **Proponentes plurales** (consorcios) no se modelan: las fórmulas del
  pliego para sumar indicadores entre integrantes no están.
- `pdftotext`/`pdftoppm` (poppler) solo hacen falta para regenerar los
  fixtures; la app y las pruebas corren con lo commiteado.

## 6. Cómo probarlo

```bash
python -m pytest pliego/tests -q                 # 19 passed
uvicorn pliego.checklist.app:app --port 8020     # http://localhost:8020
```

Deberías ver "Le faltan 3 cosas para quedar habilitado en el Grupo 1"
(cámara vencida, sin Formato 3, sin garantía), 10 cumple / 1 no cumple /
2 falta / 7 revisar. Al cambiar a Grupo 3 la experiencia pasa a **no
cumple** (1.776 SMMLV exigidos en edificaciones, solo 640 terminados).
Al abrir "Capacidad residual" se ve la página 37 del pliego con la frase
resaltada y CRP $3.800 mill. ≥ CRPC $369 mill.

Para regenerar cajas y páginas (requiere poppler):
`python -m pliego.checklist.semilla`.

## 7. Cambios a código compartido

Ninguno fuera de `pliego/` y `docs/`. Sin dependencias Python nuevas
(fastapi, uvicorn ya están). Herramienta del sistema opcional: poppler.
Fixture binario: `pliego_SI-LP-004-2021.pdf` (1,3 MB) y 12 PNG (1,4 MB).

## 8. Preguntas abiertas para el equipo

1. ¿El extractor automático se hace con un LLM sobre el texto por página
   (una llamada por capítulo) o con reglas sobre los documentos tipo, que
   son estables? Los documentos tipo hacen viable lo segundo para el 80 %.
2. ¿"Revisar" por umbral simulado es aceptable en producción, o hay que
   bloquear hasta tener la Matriz 2 (que sí está en SECOP como anexo)?
3. ¿Se modela el consorcio (sumar indicadores y experiencia entre
   integrantes)? Es el caso más común en constructoras pequeñas.
4. ¿La carpeta de documentos se extrae con el mismo pipeline o la llena el
   cliente a mano? Lo segundo es más rápido para el MVP.
5. ¿Se resalta sobre la página renderizada (como aquí) o sobre un visor
   PDF.js? Lo primero no tiene dependencias; lo segundo permite buscar.

# Enfoque 4 · Radar de competidores

Estilo base en [`../../estilo-base.md`](../../estilo-base.md). El canvas de diseño original quedó
en el tag `archivo/disenos-enfoques`.

## 1. Promesa al cliente

**"Sepa contra quién compite antes de presentarse."**

## 2. Problema que ataca

La constructora decide presentarse mirando el pliego y el presupuesto,
pero no sabe quién más va a estar en la mesa: si la entidad le adjudica
siempre al mismo, a qué fracción del presupuesto se gana ahí, ni si el
competidor fuerte está saturado con obras en ejecución (y por tanto con
menos capacidad residual). Esa información está regada en 78.000
contratos del SECOP II y nadie la cruza. El radar la convierte en tres
perfiles: la entidad, el competidor, y "contra quién compite" en un
proceso abierto.

## 3. Cómo funciona

**Datos** (`fixtures/`): 67.148 contratos de construcción (obra,
interventoría, consultoría) con proveedor, entidad, presupuesto, valor
adjudicado, oferentes, estado, fecha fin y saldo pendiente
(`contratos.parquet`, 5 MB); 554 procesos abiertos accionables
(`abiertos.parquet`).

**Lógica** (`pliego/radar/logica.py`)

- `perfil_entidad(contratos, nit, hoy, tipo)`: sobre los contratos
  *competitivos* (con presupuesto y no directa) del tipo pedido: quién
  gana (n, share, "ofrece al" = mediana adjudicado/presupuesto, último
  año), HHI, tasa de proponente único, mediana de oferentes, margen
  mediano, procesos por año, y la etiqueta:
  - **predecible**: share del primero ≥ 40 %, o HHI ≥ 0,25, o ≥ 60 % de
    procesos con proponente único;
  - **abierta**: nadie pasa del 20 % y ≥ 5 oferentes por proceso;
  - **intermedia** en el resto; **sin muestra** con < 5 procesos.
- `perfil_competidor(contratos, doc, hoy)`: contratos, obra vs.
  interventoría, entidades y departamentos donde gana, "ofrece al", y la
  **saturación** = saldo por ejecutar de los contratos vigentes (estado
  no cerrado y `fecha_fin ≥ hoy`) / valor adjudicado por año. ≥ 2 años =
  saturado, ≥ 1 = cargado, si no = con capacidad.
- `competidores_probables(contratos, proceso, hoy)`: 3 puntos por cada
  contrato competitivo del mismo tipo ganado en la entidad, 1 por cada uno
  en el mismo departamento y familia UNSPSC, 0,5 por cada uno de la
  familia en el país (tope 6), la mitad si tiene más de 3 años; la
  saturación resta hasta 50 %. Se devuelve el peso normalizado y las
  razones. **Es un orden, no una probabilidad calibrada**, y así se rotula.

**Flujo**: buscar entidad o competidor, o abrir un proceso → lista de
competidores probables con "ofrece al" y saturación → perfil de cada uno
→ perfil de la entidad con tabs Obra / Interventoría / Consultoría.

## 4. Qué se construyó

- `pliego/radar/logica.py`, `datos.py` (índices en memoria + caché), `semilla.py`.
- `pliego/radar/app.py` (FastAPI, puerto 8040): `/` (buscador y procesos
  abiertos), `/proceso/{id}`, `/entidad/{nit}?tipo=`, `/competidor/{doc}`,
  `/entidades`, `/competidores`, y `/api/entidad/{nit}`,
  `/api/competidor/{doc}`, `/api/proceso/{id}/competidores`, `/api/buscar?q=`.
- `pliego/tests/test_radar.py` — 14 pruebas (agregaciones, etiquetas,
  HHI, saturación con contratos vencidos, separación por tipo,
  competidores probables con recencia y saturación, humo).

## 5. Qué está simulado o pendiente

- **No hay oferentes perdedores** en SECOP: "se presenta" = "ha ganado".
  El peso de competidores probables es un ranking heurístico, no está
  calibrado contra participación real.
- **Saldo pendiente**: `valor_pend_ejecucion` viene vacío o en cero en
  muchos contratos vigentes (SIPCO SAS: 89 contratos, saldo $0), así que
  la saturación es un **piso**.
- **Consorcios**: cada consorcio es un proveedor distinto; no se
  desagrega a sus integrantes (el grafo de Plomada podría, es un
  siguiente paso).
- Pesos de la heurística (3 / 1 / 0,5, tope 6, mitad a 3 años) puestos
  a mano, no ajustados.
- Umbrales de las etiquetas: los de Plomada (p90 de proponente único
  ≈ 0,8 se relajó a 0,6 para entidades chicas); discutibles.
- La carga inicial tarda unos segundos (67k filas a dicts en Python) y se
  hace en un hilo al arrancar; en producción esto es una tabla `pro_*`
  como las de `feature/serving-pro`.
- Snapshot 2026-08-22 tratado como "hoy".

## 6. Cómo probarlo

```bash
python -m pytest pliego/tests -q             # 14 passed (~6 s)
uvicorn pliego.radar.app:app --port 8040     # http://localhost:8040
```

- `/entidad/890201222` (Municipio de Bucaramanga): "adjudica de forma
  **abierta**: nadie pasa del 2 %", 164 procesos, 133 proveedores, 27
  oferentes por proceso, al 94,8 %.
- `/competidor/829001805` (SOSDOM S.A.S): "está **cargado**: $9,6 mil
  mill. por ejecutar", ofrece al 92,4 %, 3 contratos vigentes.
- `/proceso/CO1.REQ.10751505` (CTP Bucaramanga, $3.048 mill.): 10
  competidores probables, EME ING primero ("ganó 4 aquí"), SOSDOM con
  etiqueta Cargado.

Regenerar fixtures: `python -m pliego.radar.semilla`.

## 7. Cambios a código compartido

Ninguno fuera de `pliego/` y `docs/`. Sin dependencias nuevas. Fixture de
5 MB (`contratos.parquet`). Nota: `feature/serving-pro` y
`feature/inteligencia-mercado` (rama local `mian`) ya calculan
`pro_entidad_mercado` con señales parecidas (tasa proponente único, HHI
por valor, share de recurrentes); este enfoque las reimplementa sobre
fixtures porque `dev` = `origin/main` no las tiene. Al integrar, conviene
unificarlas.

## 8. Preguntas abiertas para el equipo

1. ¿Se puede conseguir participación real (actas de cierre de SECOP II
   listan quién presentó oferta)? Cambiaría "probable" de heurística a
   dato.
2. ¿Desagregar consorcios con el grafo de Plomada (mismo representante
   legal / cuenta) para que "SOSDOM" y "Consorcio X liderado por SOSDOM"
   cuenten como uno?
3. ¿La saturación debe restar en el ranking (como hoy) o mostrarse solo
   como dato? Un competidor saturado igual puede presentarse en consorcio.
4. ¿Se unifica con `pro_entidad_mercado` de la rama comercial?
5. ¿Qué entidades "predecibles" son señal de riesgo (Plomada) vs. simple
   mercado chico? Para el cliente ambas significan "no gaste aquí".

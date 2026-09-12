# Enfoque 3 · Simulador de oferta

Rama `feature/simulador-oferta`. Diseño en [`diseno/`](diseno/README.md),
estilo base en [`estilo-base.md`](estilo-base.md).

## 1. Promesa al cliente

**"Oferte al precio que maximiza su puntaje, no al más bajo."**

## 2. Problema que ataca

En obra pública con documentos tipo el sobre económico vale 60 de 100
puntos y el método para calificarlo **no se conoce al ofertar**: lo eligen
los centavos de la TRM del día hábil siguiente a la apertura del sobre 2
(mediana con valor absoluto, media geométrica, media aritmética baja o
menor valor, 25 % cada uno). Tres de los cuatro premian estar cerca del
*centro* de las ofertas, no abajo. Una constructora que oferta "lo más
bajo posible" regala margen tres de cada cuatro veces; una que oferta al
100 % pierde con todos. El simulador estima dónde van a caer los
competidores y devuelve el precio que maximiza el puntaje esperado.

## 3. Cómo funciona

**Datos**

- `historico.parquet`: 18.827 contratos de obra por licitación pública y
  selección abreviada con presupuesto oficial, valor adjudicado y número
  de oferentes (desde `base`). Es la única huella pública de las ofertas:
  **SECOP solo publica la ganadora**.
- `abiertos.parquet`: 350 procesos abiertos de esas modalidades (snapshot
  2026-08-22, universo accionable).

**Lógica** (`pliego/simulador/`)

1. **Fórmulas configurables** (`metodos.py`): registro `VERSIONES` con,
   por versión de documentos tipo, los métodos, su fórmula, su rango de
   centavos de TRM y el puntaje máximo. `bucaramanga_2021` está transcrita
   del pliego real SI-LP-004-2021 (sección 4.1.4, p. 46–49). La simulación
   no conoce las fórmulas: recibe una `Version`.
2. **Competidores probables** (`armar_pool`): la distribución empírica de
   la razón adjudicado/presupuesto en procesos parecidos con ≥2 oferentes,
   al nivel más específico que tenga ≥10 procesos: misma entidad →
   mismo departamento y familia UNSPSC → familia nacional → todo.
3. **Simulación** (`recomendar`): 400 escenarios; en cada uno n
   competidores (n del histórico) con razones del pool + nuestra oferta.
   Para cada precio de una malla (85 %–100 %, paso 0,5 %) se califica con
   cada método y se pondera por su probabilidad. Sale el precio que
   maximiza el esperado y el rango a menos de 1 punto del máximo, más la
   probabilidad de quedar primero.
4. **Backtest** (`backtest`): sobre los 40 procesos históricos más
   recientes con ≥3 ofertas, recomienda el precio **sin ese proceso en el
   pool**, mete esa oferta junto con la ganadora real en escenarios
   simulados y mide (a) en qué fracción le gana a la ganadora real
   (ponderada por método) y (b) en qué fracción queda primera entre todos.

**Flujo**: elegir proceso → ver precio recomendado, rango y curva por
método → mover el slider para comparar cualquier precio → ir a Backtest.

## 4. Qué se construyó

- `pliego/simulador/metodos.py`, `logica.py`, `datos.py`, `semilla.py`.
- `pliego/simulador/app.py` (FastAPI, puerto 8030):
  - `GET /proceso/{id}` selección (lista con buscador), precio
    recomendado con rango, gráfico SVG del puntaje esperado por método,
    slider con puntaje por método a ese precio.
  - `GET /backtest` cifras y tabla proceso a proceso.
  - `GET /api/recomendacion/{id}?version=&n_sim=`, `/api/backtest`,
    `/api/procesos`, `/api/versiones`.
- `pliego/tests/test_simulador.py` — 17 pruebas: cada fórmula contra
  cálculos a mano, homogeneidad pesos/fracción, rangos de TRM, versión
  alternativa, pool por niveles, reproducibilidad, backtest y humo.

## 5. Qué está simulado o pendiente

- **Las ofertas perdedoras no existen en los datos.** Los competidores se
  simulan con la distribución de las *ganadoras* de procesos parecidos.
  Es un sesgo conocido: las ganadoras están más cerca del óptimo que una
  oferta cualquiera, así que el pool es "más duro" que la realidad.
- **La TRM se trata como uniforme** en centavos (25 % cada método). Es
  razonable pero no está medido.
- **Una sola versión de documentos tipo** transcrita. Otras versiones
  (p. ej. media geométrica con presupuesto oficial) se agregan al
  registro; la bandera `incluye_presupuesto_en_media` está declarada
  pero no implementada.
- **Sin piso de precio artificialmente bajo**: el pliego permite rechazar
  ofertas muy bajas (sección 4.1.3); la malla arranca en 85 % como
  aproximación.
- El backtest tarda ~13 s la primera vez (40 procesos × 120 escenarios en
  Python puro, sin numpy) y queda en caché.
- Snapshot 2026-08-22 tratado como "hoy".

## 6. Cómo probarlo

```bash
python -m pytest pliego/tests -q                 # 17 passed
uvicorn pliego.simulador.app:app --port 8030     # http://localhost:8030
```

Abrir `http://localhost:8030/proceso/CO1.REQ.10846514` (acueducto,
Municipio de Maripí, $512 mill.): "Oferte al 94,5 %: $484 millones",
rango 90,0–97,0 %, esperado 58,9 de 60, curva con el máximo de "menor
valor" en 85 % y el de mediana/geométrica en ~95 %. Mover el slider
cambia los puntajes por método. `/backtest`: ~64 % le gana al ganador
real, ~32 % queda primero entre ~12 ofertas.

Regenerar fixtures (requiere el warehouse): `python -m pliego.simulador.semilla`.

## 7. Cambios a código compartido

Ninguno fuera de `pliego/` y `docs/`. Sin dependencias nuevas (solo
`statistics` y `random` de la biblioteca estándar para la simulación).

## 8. Preguntas abiertas para el equipo

1. ¿Vale la pena comprar/raspar las actas de evaluación (que sí listan
   todas las ofertas) para calibrar el pool con ofertas perdedoras? Es el
   único camino para que el backtest sea real y no simulado.
2. ¿Qué versiones de documentos tipo hay que soportar (transporte v3+,
   agua, edificaciones)? Cada una es un registro nuevo en `metodos.py`.
3. ¿Se muestra "queda primero" (10–30 %, honesto pero desalentador) o
   solo el puntaje esperado? Con 20 ofertas nadie queda primero seguido.
4. ¿El pool por entidad debería ponderar por fecha (los últimos 2 años
   pesan más)? Las razones bajan cada año (0,986 en 2018 → 0,950 en 2026).
5. ¿Se integra con el enfoque 1 (solo simular procesos donde se recomienda
   presentarse)?

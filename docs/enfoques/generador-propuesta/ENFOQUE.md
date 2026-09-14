# Enfoque 5 · Generador de propuesta

Estilo base en [`../../estilo-base.md`](../../estilo-base.md). El canvas de diseño original quedó
en el tag `archivo/disenos-enfoques`.

## 1. Promesa al cliente

**"Prepare la propuesta en horas, no en días."**

## 2. Problema que ataca

Armar una oferta de obra pública son 9 formatos, una garantía y una
decena de anexos, y el 80 % del contenido es copiar datos que ya
existen: los del pliego (entidad, proceso, objeto, presupuesto del lote,
porcentajes) y los de la empresa (NIT, representante legal, RUP, estados
financieros, contratos en ejecución). Se copian a mano, se equivocan
(razón social distinta a la de cámara de comercio, valor de la garantía
sobre el presupuesto equivocado) y nadie sabe después de dónde salió cada
dato. El generador produce los borradores con **cada dato marcado por su
origen** y una lista ordenada de lo que falta.

## 3. Cómo funciona

**Datos**

- `pliego_SI-LP-004-2021.json`: extracción (simulada, a mano) del pliego
  real de Bucaramanga: 23 campos con su página (entidad p. 1, garantía
  p. 59, anticipo p. 64, tabla de experiencia p. 34…), 3 lotes (p. 5) y
  la lista de formatos exigidos (p. 64). El PDF va como fixture.
- `perfil_constructora.json`: perfil ficticio de Constructora Andina con
  todo lo que el cliente carga una vez (RL, cédula, tarjeta profesional,
  dirección, RUP, estados financieros, contratos en ejecución…). Faltan a
  propósito el plan de gerencia y el certificado de discapacidad.

**Lógica** (`pliego/generador/logica.py`): una función por documento que
produce un `Documento` con sus `Campo`s. Cada campo tiene `origen`:

| Origen | Qué es | Trazabilidad |
|---|---|---|
| `pliego` | dato del pliego | página exacta + ruta `pliego.campos.x` |
| `perfil` | dato del perfil | ruta `perfil.a.b` |
| `calculado` | derivado de ambos | la fórmula, con la página de la regla |
| `faltante` | no está en ninguno | qué pedir y a quién; `critico` si rechaza la oferta |
| `no_aplica` | no aplica a este proponente | la razón |

Documentos: Formato 1 (carta, con la regla del aval de ingeniero p. 14),
Formato 2 (no aplica a proponente individual), Formato 3 (elige los
contratos terminados de las actividades del lote hasta cumplir el % de
la tabla p. 34), Formato 4 (indicadores calculados desde los estados
financieros), Formato 5 (CRPC = presupuesto − anticipo; SCE lineal p. 43),
Formato 6, 7, 8, 9, garantía de seriedad (valor = 10 % × presupuesto del
lote, vigencia 3 meses, beneficiario del pliego) y anexos con vigencia de
30 días. Estado por documento: **listo / con faltantes / adjuntar / no
aplica**. `lo_que_falta` ordena críticos primero.

**Flujo**: elegir grupo → lista de documentos con estado y conteo de
orígenes → abrir un borrador: vista previa en papel con cada dato
subrayado por origen y, al lado, la tabla "de dónde sale cada dato" con
página o fórmula → descargar .md o el paquete .zip.

## 4. Qué se construyó

- `pliego/generador/logica.py`, `datos.py`.
- `pliego/generador/app.py` (FastAPI, puerto 8050): `/?lote=N`,
  `/documento/{id}?lote=N`, `/documento/{id}.md`, `/paquete.zip?lote=N`
  (todos los .md + `00_lo_que_falta.md` + `00_origenes.json`), `/perfil`,
  `/pliego.pdf`, `/api/paquete?lote=N`. Conversor markdown→HTML propio (sin
  dependencias) y marcado de valores por origen sobre la vista previa.
- `pliego/tests/test_generador.py` — 13 pruebas: toda cita del pliego trae
  página, carta mezcla orígenes, aval condicional, hueco `[CORREO]` cuando
  falta, garantía calculada, experiencia elegida por lote, CRPC/SCE,
  indicadores, no aplica, orden de faltantes, paquete por lote.

## 5. Qué está simulado o pendiente

- **La extracción del pliego es manual** (mismo estado que en la rama 2):
  el JSON se escribió leyendo el PDF. El pipeline que lo produzca no
  existe en el repo.
- **Los borradores son plantillas con datos**, no redacción generativa:
  la carta, la certificación y las declaraciones tienen texto fijo del
  estilo de los documentos tipo. Un LLM podría ajustar el tono al pliego,
  pero la trazabilidad exige que los *datos* vengan del mapeo, no del modelo.
- **El subrayado en la vista previa es best-effort** (busca el valor
  formateado en el HTML); valores muy cortos pueden no marcarse.
- **Exportación en Markdown/ZIP**, no en .docx: los formatos oficiales
  son Word y habría que rellenar la plantilla real (python-docx).
- Fecha de cierre simulada (2021-07-06); perfil ficticio.
- Umbrales financieros de la Matriz 2 no están (ver rama 2).

## 6. Cómo probarlo

```bash
python -m pytest pliego/tests -q                 # 13 passed
uvicorn pliego.generador.app:app --port 8050     # http://localhost:8050
```

Deberías ver "La propuesta está al 60 %: 6 borradores listos, falta 1
cosa que la rechaza" (la póliza), 26 datos del pliego / 41 del perfil /
20 calculados / 3 faltan. Abrir Formato 1: la carta completa con los
datos subrayados (rojo = pliego, gris = perfil, rosa = calculado) y la
tabla de fuentes con "p. 1", "p. 5"… Formato 5 muestra CRPC = $737,7 mill.
− $368,9 mill. y el SCE. Cambiar a Grupo 3: Formato 3 pasa a "con
faltantes" (falta experiencia en edificaciones). "Exportar paquete" baja
un .zip con los 11 .md.

## 7. Cambios a código compartido

Ninguno fuera de `pliego/` y `docs/`. Sin dependencias nuevas (`zipfile`,
`re`, `html` de la biblioteca estándar). Fixture: el PDF del pliego (1,3 MB).

## 8. Preguntas abiertas para el equipo

1. ¿Se rellenan los formatos oficiales en Word (python-docx sobre la
   plantilla de la entidad) o basta con el borrador en texto? Lo primero
   es lo que el cliente entrega; lo segundo es lo que revisa.
2. ¿Los textos fijos (declaraciones de la carta) deben salir del pliego
   (extraer el Formato 1 real de los anexos) en vez de una plantilla?
3. ¿Se integra con la rama 2 (checklist): un faltante aquí es un "falta
   documento" allá? Comparten fixtures y deberían compartir el modelo.
4. ¿Qué pasa con consorcios? Formato 2 y la suma de indicadores entre
   integrantes no están modelados.
5. ¿Quién mantiene el perfil: el cliente a mano, o se extrae del RUP y de
   los estados financieros con el mismo pipeline de extracción?

# Diseño del simulador de oferta

Producido con `/design`, base visual `new-landing` ([`../estilo-base.md`](../estilo-base.md)).

- Lienzo publicado: https://claude.ai/code/artifact/da9fe52a-da36-414a-9a31-cb8f2fff2720
- Artboards: `Main.dc.html` (selección de proceso + precio recomendado +
  control del precio + puntaje por método), `Backtest.dc.html`, `canvas.json`.
  Los artboards se generaron con datos reales (proceso de Maripí, pool de
  Boyacá/familia 7214).

## Decisiones

1. **Tres columnas en una pantalla**: lista de procesos a la izquierda
   (selección), y a la derecha el titular en imperativo ("Oferte al 94,5 %:
   $484 millones"), la tarjeta de recomendación (cifra grande en acento-2,
   rango como barra caliente) y el gráfico.
2. **Gráfico sin paleta categórica**, siguiendo la doctrina del tablero de
   Plomada: la serie principal (esperado ponderado) es la única en rojo; los
   cuatro métodos van en gris con trazos distintos y etiqueta directa al
   final. Banda translúcida = rango recomendado. Eje y 50–60 (el puntaje
   máximo del sobre económico es 60).
3. **Control del precio** como slider de papel sobre pista gris, con el
   puntaje por método a ese precio al lado (tabla "por qué"), y la
   probabilidad de cada método (rango de centavos de la TRM) como
   metadato en cada fila.
4. **Backtest** con tres cifras (le gana al ganador real / queda primero /
   procesos) y la tabla proceso a proceso; la nota al pie explica la
   limitación central: SECOP no publica las ofertas perdedoras.

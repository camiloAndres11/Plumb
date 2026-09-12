# Diseño del generador de propuesta

Producido con `/design`, base visual `new-landing` ([`../estilo-base.md`](../estilo-base.md)).

- Lienzo publicado: https://claude.ai/code/artifact/e85cc0e9-86ca-4f45-aae2-11ed4672980e
- Artboards: `Main.dc.html` (documentos de la oferta con estado y lo que
  falta), `Editor.dc.html` (borrador con el origen de cada dato), `canvas.json`.
  Generados con los datos reales del pliego SI-LP-004-2021 y el perfil ficticio.

## Decisiones

1. **Titular de avance**: "La propuesta está al 60 %: 6 borradores listos,
   falta 1 cosa que la rechaza". El selector de grupo y "Exportar paquete"
   van arriba a la derecha.
2. **Cuatro orígenes con cuatro pastillas**: Pliego (acento suave, con
   página), Perfil (gris), Calculado (rosa `--ad-accent-3`), Falta (borde
   rojo). Cada fila de documento muestra cuántos campos vienen de cada uno.
3. **Lo que falta, en orden** como tarjeta lateral: primero lo que rechaza
   la oferta (póliza), luego lo que solo resta puntos.
4. **El borrador va en papel** (`.draft`, como en la landing), con cada
   dato subrayado según su origen; a la derecha la tabla "de dónde sale
   cada dato" con la página o la ruta. "p. N" abre el PDF en esa página.
5. Descargar por documento (.md) o el paquete (.zip); sin dependencias.

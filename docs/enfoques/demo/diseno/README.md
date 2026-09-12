# Diseño del login y el panel (demo para el equipo)

Producido con `/design`, base visual `new-landing` ([`../../../estilo-base.md`](../../../estilo-base.md)).

- Lienzo publicado: https://claude.ai/code/artifact/87da6b63-2129-4204-a64c-19652c977d32
- Artboards: `Login.dc.html` (solo vista), `Main.dc.html` (panel de enfoques), `canvas.json`.

## Decisiones

1. **El login vive sobre el hero de la landing**: mismos fondos y glows
   (`.ad-hero-bg`, `.ad-glow-a/b` de `landing.css`), tarjeta de vidrio de
   440 px, badge rojo, H1 de 32 px en peso 500, botón de papel «Iniciar».
   No tiene lógica: el formulario hace GET a `/panel`.
2. **El panel usa el layout de app** (sidebar 230 px con los cinco enfoques
   y la sesión) y una grilla 3×2: una tarjeta por enfoque con ícono, número
   de enfoque, nombre, promesa, una cifra real del prototipo y «Abrir →».
   La primera va en acento; la sexta celda es la nota para el equipo.
3. **Cada app conserva su diseño**; solo se le agrega «← Panel» arriba de su
   sidebar para volver.

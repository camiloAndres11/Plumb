# ADR 0001 · Plomada queda aislada en `legacy/plomada/` y no se refactoriza

Fecha: 2026-09-14. Rama: `feature/legado-plomada`.

## Contexto

El repo nació como Plomada (pipeline de SECOP II, banderas de riesgo, API
REST + MCP, sitio estático) y en septiembre de 2026 pivotó a Pliego. Plomada
sigue en producción en Render y su despliegue sale de `main`. Los dos
productos convivían en la raíz con cuatro convenciones de import, y el 45 %
del código era de un producto que ya no se desarrolla.

## Decisión

- Todo lo de Plomada (`pipeline/ sql/ api/ plomada/ frontend/ web/ design/
  tests/ Makefile API.md MCP.md`) se mueve **intacto** a `legacy/plomada/`,
  con el mismo árbol relativo, para que sus rutas internas sigan valiendo.
- **No se refactoriza.** Solo recibe arreglos de seguridad (los de
  `feature/seguridad-urgente`: cédulas fuera del API, IP no falsificable,
  contenedor sin root).
- Conserva sus `requirements.txt` y sus Dockerfiles; sus tests corren desde
  la raíz vía `pyproject.toml` (extra `legacy`) y su CI es el job `legacy`,
  con los mismos pasos de siempre.
- No se borra de la rama ni se archiva en un tag: un merge futuro a `dev` y
  `main` no debe tumbar el despliegue.

## Consecuencias

- Pliego (`pliego/`, `plataforma/`, `demo/`) es el único producto de la
  raíz y el único que se remodela.
- La landing y sus assets, que Pliego usaba de `plomada/`, tienen copia en
  `plataforma/static/`; si se regeneran en `legacy/plomada/design/`, hay que
  copiarlos a mano (`legacy/plomada/design/VENDOR.md`).
- `deploy/render.yaml` apunta a las rutas nuevas; en el panel de Render hay
  que apuntar el blueprint a `deploy/render.yaml`.
- Los datos crudos y el warehouse de Plomada viven en `legacy/plomada/data/`.

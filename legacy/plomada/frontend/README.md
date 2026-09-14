# Plomada — frontend (islas de Vue)

Fuentes de las **islas de Vue** que se montan sobre el HTML que
`plomada/build.py` ya pre-renderiza. Ver `docs/PLAN_VUE.md` para la
arquitectura completa y el porque de cada decision — esto es solo el "como
correrlo".

## No hace falta Node para correr el sitio

El bundle compilado (`plomada/static/vendor/islas/`) esta **commiteado**,
igual que Leaflet (`design/VENDOR.md`). Si solo quieres correr o publicar el
sitio:

```bash
python3 design/construir.py
python3 plomada/build.py
python3 -m http.server -d plomada/site 8765
```

Node/npm **solo hacen falta si vas a cambiar un componente**.

## Instalar y compilar

```bash
npm --prefix frontend install
npm --prefix frontend run build     # escribe plomada/static/vendor/islas/
```

`npm run build` hace dos cosas, en orden (ver `package.json`):

1. `vite build` — compila `src/islas.js` y sus componentes a
   `plomada/static/vendor/islas/`.
2. `node scripts/manifiesto.mjs` — escribe `MANIFIESTO.txt` con el hash
   sha256 de todos los fuentes (`src/**/*.{vue,js}`). Ese hash lo verifica
   `plomada/test_privacy.py::test_bundle_corresponde_a_fuentes`: si editas un
   `.vue` y no vuelves a compilar, el build de Python **falla** en vez de
   publicar un bundle desfasado.

Despues de compilar, corre siempre la cadena completa para confirmar que
nada se rompio:

```bash
python3 design/construir.py
python3 plomada/build.py
```

## Agregar una isla nueva

1. Escribe el componente en `src/componentes/`.
2. Registralo en `src/islas.js` (mapa `nombre-de-isla -> () => import(...)`).
3. En `plomada/build.py`, envuelve el contenedor con el helper `isla()`:

   ```python
   isla("nombre-de-isla", fallback="<p>...</p>", algun_prop="valor")
   ```

   `fallback` es el HTML que ve un lector sin JavaScript **y** lo que barre
   `plomada/test_privacy.py` — nunca lo dejes vacio. La isla lo *reemplaza*
   al montar, nunca lo *crea* de la nada.
4. Recompila (`npm run build`) antes de correr `plomada/build.py`.

## Restricciones que no se negocian

- **`formato.js` no se reescribe.** Se importa desde los componentes con el
  alias `~formato` (`vite.config.js`), que apunta directo a
  `plomada/static/formato.js`. Es el espejo de `plomada/data.py`, amarrado
  por `tests/formato_casos.json` — tocar su semantica exige tocar los dos
  lados y regenerar el fixture.
- **Ningun componente trae color ni fuente propios.** Todo por token de
  `design/plomada/sitio.css` / `dataviz.css` (Modernist vendorizado). Si hace
  falta un token nuevo, entra por ahi, no por CSS inline en un `.vue`.
- **Nunca `v-html`.** `plomada/test_privacy.py::test_sin_v_html` lo prohibe
  sobre los fuentes. Es el mismo riesgo que `innerHTML` en JS plano.
- **Cero URLs externas en el bundle.** `test_bundle_sin_url_externa` lo
  verifica; unica excepcion documentada, `server.arcgisonline.com` (tiles
  satelitales, click-to-load).
- **El bundle es el unico artefacto que entra a `site/`.**
  `plomada/build.py` sigue siendo el unico escritor de `site/` — el bundle
  entra por su propio `copytree` de `plomada/static/`, nunca por un `dist/`
  servido aparte.

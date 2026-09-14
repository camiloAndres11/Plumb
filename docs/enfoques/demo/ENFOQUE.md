# Demo para el equipo · landing → login → panel → cinco enfoques

Rama temporal `demo/integracion-equipo`, creada desde `dev` con merges de
`new-landing` (más sus cambios que estaban sin commitear) y de las cinco
ramas `feature/*`. **No es candidata a `dev`**: existe para presentar las
ideas juntas. Las ramas `feature/*` no se tocaron.

## Cómo correrlo

```bash
python -m pytest pliego/tests -q      # 85 passed (las cinco suites)
uvicorn demo.app:app --port 8000      # http://localhost:8000
```

Flujo: `/` (landing de Pliego) → **Entrar** → `/login` (solo vista) →
**Iniciar** → `/panel` → tarjetas de los cinco enfoques →
`/filtro`, `/checklist`, `/simulador`, `/radar`, `/generador`. Cada app
tiene «← Panel» en su sidebar.

## Qué se construyó aquí

- `demo/app.py`: un FastAPI que sirve la landing (`plataforma/static/landing.html`
  con «Entrar» → `/login`), el login, el panel, y **monta las cinco apps
  de `pliego/` sin modificarlas** bajo un prefijo.
- `docs/enfoques/<enfoque>/ENFOQUE.md`: el documento de cada enfoque. Los canvas
  de diseño están en el tag `archivo/disenos-enfoques`.
- `docs/enfoques/demo/`: este documento.

## El truco que hay que saber

Las cinco apps enlazan con rutas absolutas (`/proceso/…`, `/static/…`)
porque nacieron para correr solas en su puerto. En vez de editar las
cinco, `demo.app.ConPrefijo` es un middleware ASGI que reescribe en el
HTML de cada app (y en la cabecera `Location` de sus redirecciones) las
URLs de raíz para que lleven el prefijo del montaje. Deja en paz `/panel`
y `/login`. Es un atajo de demo; si un enfoque pasa a `dev`, sus enlaces
deben construirse con el `root_path` de la petición.

`/static` del concentrador es el de la landing (`plataforma/static`); el
`base.css` de las apps se sirve por su propio montaje (`/filtro/static/…`).

## Qué está simulado

- El login no autentica: «Iniciar» abre el panel. No hay sesión.
- Las cifras de las tarjetas del panel están escritas a mano con los
  valores que muestran los prototipos (no se recalculan).
- Todo lo simulado de cada enfoque sigue igual (ver su `ENFOQUE.md`).

## Cambios a código compartido

`plataforma/static/landing.html` **no se modifica en disco**: el reemplazo de
`href="/tablero/"` por `/login` se hace al servirla. El resto del repo
queda como en `dev` + `new-landing`.

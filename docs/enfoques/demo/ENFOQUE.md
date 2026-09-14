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
  de `pliego/` sin modificarlas** bajo un prefijo (`app.mount`; sus plantillas
  arman las URLs con el `root_path` y un middleware les pone el enlace «Panel»).
- `docs/enfoques/<enfoque>/ENFOQUE.md`: el documento de cada enfoque. Los canvas
  de diseño están en el tag `archivo/disenos-enfoques`.
- `docs/enfoques/demo/`: este documento.

## Cómo se montan las apps

Cada app de `pliego/` arma sus enlaces y sus recursos con el `root_path` de
la petición (variable `raiz` en las plantillas, `data-raiz` en el `<body>`
para el JS), así que la demo las monta con `app.mount` y no reescribe nada.
Un middleware de la demo deja en `request.state.hub` el enlace «← Panel», y
`pliego/comun/templates/base.html` lo pinta en la sidebar de cada app.

`/static` del concentrador sirve la landing (`plataforma/static`) y el shell
de los enfoques (`pliego/static`); cada app montada sirve además el suyo por
su propio montaje (`/filtro/static/…`).

## Qué está simulado

- El login no autentica: «Iniciar» abre el panel. No hay sesión.
- Las cifras de las tarjetas del panel salen de los datos que se sirven
  (`pliego/comun/panel.py`); las de checklist y generador son fijas.
- Todo lo simulado de cada enfoque sigue igual (ver su `ENFOQUE.md`).

## Cambios a código compartido

`plataforma/static/landing.html` **no se modifica en disco**: el reemplazo de
`href="/tablero/"` por `/login` se hace al servirla. El resto del repo
queda como en `dev` + `new-landing`.

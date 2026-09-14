# ADR 0002 · HTML con Jinja2 (autoescape) y URLs con `root_path`, sin reescritura

Fecha: 2026-09-14. Rama: `feature/plantillas-jinja`.

## Contexto

Los cinco enfoques, la plataforma y la demo armaban el HTML con f-strings
en Python: unas 1.500 líneas de HTML, CSS y JS dentro de 19 archivos `.py`,
con el escape a cargo de que cada autor recordara llamar a `h()`. Las apps
enlazaban con rutas absolutas, así que montarlas bajo un prefijo (la demo
en `/filtro`, la plataforma en `/app/filtro`) exigía `ConPrefijo`, un
middleware que reescribía con cuatro regex todo el HTML servido y
parcheaba globalmente la sidebar. Ninguna de esas piezas tenía tests.

## Decisión

- Plantillas Jinja2 con **autoescape** en `pliego/<enfoque>/templates/`,
  `plataforma/templates/` y `demo/templates/`, sobre un `base.html` común
  (`pliego/comun/templates/`). `pliego/comun/web.py` da el entorno, los
  filtros de formato y `render()`.
- Las URLs se arman con `raiz` (el `root_path` de la petición) y el JS lee
  la raíz de `data-raiz` en el `<body>`. Montar una app bajo un prefijo es
  `app.mount`, sin tocar HTML. `ConPrefijo` y el parche de la sidebar se
  borran.
- Un concentrador puede cambiar la sidebar de una app dejando en
  `request.state.hub` sus items y su pie; `base.html` los pinta.
- Cero JS inline: todo en `/static`; los datos para JS van en
  `<script type="application/json">`. El CSP de la plataforma queda con
  `script-src 'self'`. `style-src` conserva `'unsafe-inline'` por los
  atributos `style=` de las plantillas (trabajo cosmético pendiente, riesgo
  menor).
- Lo que arma HTML fuera de plantillas (el markdown del generador, los
  titulares con `<span>`) se escapa antes y se marca `Markup`.

## Consecuencias

- Un XSS por olvido ya no es posible en las plantillas; hay un test que lo
  verifica (`pliego/tests/test_web.py`), más uno por cada ruta y uno de
  montaje bajo prefijo.
- Los handlers de los `app.py` quedan cortos: leen datos y renderizan.
- El CSS y el JS de cada enfoque viven en `pliego/static/<enfoque>.css|js`.

# Plataforma: Pliego para una empresa real

`plataforma/` es la versión de Pliego que una constructora usa sola: se registra,
verifica su correo, invita a su equipo, describe su empresa, sube sus pliegos, y los
cinco enfoques trabajan con sus datos. Corre en el **puerto 8100**; la demo
(`demo/app.py`, puerto 8000) sigue intacta como vitrina con el perfil ficticio, así
que se pueden mostrar las dos a la vez.

## Correr en local

```
docker compose up -d db                       # Postgres en 127.0.0.1:5432 (usuario plomada, clave POSTGRES_PASSWORD del .env)
cp .env.example .env                          # y llenar DATABASE_URL, SECRET_KEY, CROMA_API_KEY, ANTHROPIC_API_KEY
python -m plataforma.migrar                   # crea/actualiza el esquema `pliego`
uvicorn plataforma.app:app --port 8100        # la plataforma
uvicorn demo.app:app --port 8000              # la demo, en paralelo si se quiere
```

Con Docker completo: `docker compose up` levanta `db`, `api` (:8000, Plomada) y
`plataforma` (:8100). La demo no está en compose: es `uvicorn demo.app:app`.

`/health` responde `{"ok": true}` cuando Postgres tiene el esquema y dice qué hay:
warehouse (departamentos, `as_of`), cola de trabajos, último refresco, si hay llaves
de Croma y de Anthropic.

Sin `SMTP_URL`, los correos (verificación, reset, invitación) **no salen**: el enlace
se imprime en el log de uvicorn con nivel WARNING. Es el modo de desarrollo.

## Flujo de una empresa

1. `/registro`: empresa (NIT con dígito de verificación) + primer usuario → correo de
   verificación → `/verificar/<token>` inicia sesión.
2. `/empresa/perfil/{1,2,3}`: sede y departamentos donde licita y códigos UNSPSC;
   RUP, indicadores y capacidad; experiencia. Al guardar los departamentos, la
   plataforma descarga sus procesos y contratos de Croma en segundo plano
   (`/empresa/datos` muestra el estado; la primera vez son minutos).
3. `/panel`: tarjetas con cifras de la empresa; filtro, simulador y radar bajo
   `/app/<enfoque>` en cuanto un departamento esté listo.
4. `/pliegos`: subir el PDF; Claude extrae requisitos, lotes y formatos; con un pliego
   listo se activan checklist y generador. `/empresa/documentos`: qué documentos tiene
   la empresa y los datos para redactar la propuesta.
5. `/empresa/equipo`: invitar admins o miembros. `/cuenta`: nombre, contraseña,
   sesiones abiertas.

## Variables de entorno

| Variable | Qué hace |
|---|---|
| `DATABASE_URL` | Postgres con el esquema `pliego` |
| `SECRET_KEY` | firma de cookies y tokens (≥ 32 bytes) |
| `BASE_URL` | URL pública; va en los enlaces de los correos |
| `SMTP_URL` | `smtp://usuario:clave@host:587?tls=1`; vacío = los correos se imprimen en el log |
| `CORREO_REMITENTE` | remitente de los correos |
| `PLATAFORMA_ADMINS` | emails (coma) que ven `/admin` |
| `PLATAFORMA_DATOS` | raíz de datos en disco (warehouse, caché de Croma, PDFs); en Render, el disco persistente |
| `CROMA_API_KEY`, `CROMA_DESDE_ANIO`, `CROMA_*` | ver `docs/enfoques/croma.md`; sin llave no se descargan departamentos |
| `ANTHROPIC_API_KEY` | extracción de pliegos con Claude; sin llave los pliegos quedan en `subido` |

`PLIEGO_FUENTE` lo fija la plataforma en `warehouse` (validador en `plataforma/config.py`),
aunque el `.env` compartido con la demo diga otra cosa. Toda la configuración se lee una
vez al arrancar desde el entorno y el `.env` de la raíz (`pliego/comun/config.py`); ningún
otro módulo lee `os.environ`.

## Estructura

```
plataforma/
  app.py          FastAPI, middlewares (sesión, acceso), manejo de errores, /health
  config.py       extiende pliego/comun/config.py (pydantic-settings) y registra la instancia única
  db.py           el pool de pliego/comun/pg.py con el DSN y los mensajes de la plataforma
  migrar.py       aplica sql/*.sql una vez cada uno (tabla pliego.migraciones)
  seguridad.py    argon2id, firmas, rate limit (pliego.intentos), NIT con DV, email
  sesiones.py     cookie -> request.state.usuario/.empresa; contexto de empresa; guardias; CSRF
  cuentas.py      registro, verificación, login, reset, invitaciones, roles
  correo.py       SMTP por URL o consola
  esquemas.py     PerfilEmpresa (misma forma que perfil_constructora.json), pasos del wizard
  catalogos.py    departamentos y UNSPSC de construcción
  trabajos.py     cola en hilo: descargas de Croma por departamento, refresco diario, extracción de pliegos
  enfoques.py     monta pliego/*/app.py bajo /app/* con ConPrefijo + guardia Protegido
  pliegos.py      guardar PDF, extraer, elegir; extraccion.py: Claude + poppler; carpeta.py: documentos de la empresa
  vistas.py       layouts publica() y privada(), campos, mensajes, sidebar
  routers/        publico, panel, empresa (equipo, datos, documentos), perfil, cuenta, pliegos, admin
  sql/            001_esquema.sql, 002_pliegos.sql
  tests/          seguridad y esquemas (puros); flujo, datos y pliegos (Postgres real, warehouse temporal, sin red)
pliego/comun/
  contexto.py     la empresa (y su pliego) en un ContextVar durante cada petición
  warehouse.py    DuckDB en disco por departamento; consultar(sql, ambito) con vistas temporales
  cache.py        cache por ámbito + versión del warehouse (reemplaza lru_cache en los datos.py)
  prefijo.py      ConPrefijo (montar apps bajo un prefijo) y sidebar_con_hub (parche de la demo)
  panel.py        tarjetas con cifras, compartidas por demo y plataforma
```

## Cómo funciona por dentro

- **Cuentas**: la cuenta es la empresa (NIT). Quien se registra es `admin`; invita
  `admin` o `miembro`. Un correo es una sola cuenta. argon2id; sesión en servidor con
  cookie firmada (solo el id), 30 días sin uso; CSRF por sesión en todo POST; rate
  limit por IP y correo. Registro, "olvidé" y reenvío responden igual exista o no el
  correo. Cambiar/restablecer la contraseña cierra las demás sesiones. `/terminos` y
  `/privacidad` son borradores marcados `<!-- REVISAR LEGAL -->`.
- **Perfil**: `pliego.empresas.perfil` (JSONB) con exactamente la forma de
  `pliego/filtro/fixtures/perfil_constructora.json`, validada por `esquemas.py`.
  `pliego/comun/contexto.py` lo pone en contexto y `filtro/datos.perfil()` lo usa; sin
  contexto (demo, pruebas) todo sigue sobre fixtures.
- **Datos**: `pliego/comun/warehouse.py` es un DuckDB en disco
  (`$PLATAFORMA_DATOS/warehouse/pliego.duckdb`) con `base_todo`, `procesos_todo`,
  `abiertos_todo` (+ `departamento_descarga`), agregados, `meta` y la vista
  `alertas_todo` calculada contra `current_date`. Cada petición consulta con vistas
  temporales filtradas por los departamentos de la empresa, así que **las SQL de
  `pliego/*/semilla.py` corren sin cambios** (`fuente.py`, modo `warehouse`). El archivo
  queda bloqueado por el proceso que lo abre: para inspeccionarlo con la plataforma
  corriendo, usar `/health` o `/admin`. `trabajos.py` descarga por departamento
  (completo la primera vez, incremental después, refresco diario 05:00 Colombia, retoma
  pendientes al arrancar); una búsqueda fallida deja el departamento en `error`, nada a
  medias. `pliego/comun/cache.py` cachea por ámbito y versión del warehouse.
- **Enfoques**: `enfoques.py` monta las cinco apps bajo `/app/<enfoque>` con
  `ConPrefijo` (reescribe URLs, cambia la sidebar) detrás de `Protegido` (sesión,
  verificado, perfil completo, datos; checklist y generador exigen además un pliego).
- **Pliegos**: `extraccion.py` hace **una llamada a `claude-opus-5`** con el PDF y una
  tool obligatoria cuyo `input_schema` es el contrato; convierte a las formas de
  `requisitos_*.json` y `pliego_*.json`; poppler localiza las citas y renderiza las
  páginas. La carpeta de documentos sale de `carpeta.py` (perfil + lo declarado en
  `/empresa/documentos`). `checklist/datos.py` y `generador/datos.py` leen del contexto.
- **Operación**: `/admin` (solo `PLATAFORMA_ADMINS`): empresas, descargas (encolar),
  pliegos y costo, cola, créditos de Croma. Log de acceso por petición con usuario y
  empresa (`pliego.acceso`).

## Despliegue en Render

`deploy/render.yaml` define `pliego-app`: contenedor de `plataforma/Dockerfile`, `/health`,
**un disco persistente en `/app/data`** (warehouse, caché de Croma, PDFs; sin disco cada
deploy los borraría) y `numInstances: 1` (la cola y el warehouse viven en el proceso).
Variables `sync: false` que hay que poner en el panel: `SMTP_URL`, `PLATAFORMA_ADMINS`,
`CROMA_API_KEY`, `ANTHROPIC_API_KEY`. El contenedor corre `python -m plataforma.migrar`
antes de arrancar. `BASE_URL` debe ser el host real del servicio.

## Límites conocidos

- Croma tarda 1,5–30 s por página; la primera descarga de un departamento son minutos
  y ~50–100 créditos. `/catalog` anuncia "100 requests / 24h" que hoy no aplica; si
  aparece, limitaría el arranque en frío.
- Un solo worker de uvicorn. Para escalar: cola y candado del warehouse a Postgres
  (`SELECT … FOR UPDATE SKIP LOCKED`) y un proceso aparte para los trabajos.
- La extracción con Claude está probada con un cliente simulado (la extracción manual
  del fixture); la calidad y el costo reales se miden con `ANTHROPIC_API_KEY` subiendo
  `pliego_SI-LP-004-2021.pdf` y comparando con `requisitos_SI-LP-004-2021.json`.
- Sin poppler no hay resaltado ni páginas del pliego (el checklist funciona igual).
- `f_al_tope_minima` y `f_cierre_movido` quedan en NULL con datos de Croma (ver
  `docs/enfoques/croma.md`).

## Estado

| Fase | Entrega | Estado |
|---|---|---|
| 0 | esqueleto, config, Postgres, migraciones, landing, Dockerfile, compose | hecha |
| 1 | cuentas: registro, verificación, login, reset, equipo e invitaciones, CSRF, rate limit | hecha |
| 2 | perfil de la empresa (wizard) y contexto de empresa para los enfoques | hecha |
| 3 | datos de Croma por departamento en un warehouse DuckDB en disco, trabajos en segundo plano | hecha |
| 4 | filtro, radar y simulador montados bajo `/app/*` con sesión; panel con cifras de la empresa | hecha |
| 5 | pliegos: subir PDF, extracción con Claude, checklist y generador sobre él | hecha (llamada real a Claude por verificar) |
| 6 | admin, health, log de acceso, Render con disco, documentación, PR a `dev` | hecha |

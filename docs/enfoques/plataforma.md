# Plataforma: Pliego para una empresa real

`plataforma/` es la versión de Pliego que una constructora usa sola: se registra,
verifica su correo, invita a su equipo, describe su empresa y los enfoques trabajan
con sus datos (Croma, por sus departamentos). Corre en el **puerto 8100**; la demo
(`demo/app.py`, puerto 8000) sigue intacta como vitrina con el perfil ficticio, así
que se pueden mostrar las dos a la vez.

Plan completo por fases: `~/.claude/plans/mira-la-estructura-del-majestic-russell.md`
(resumen abajo en "Estado").

## Correr en local

```
docker compose up -d db                       # Postgres en 127.0.0.1:5432 (plomada/plomada)
cp .env.example .env                          # y llenar DATABASE_URL, SECRET_KEY, CROMA_API_KEY
python -m plataforma.migrar                   # crea el esquema `pliego`
uvicorn plataforma.app:app --port 8100        # la plataforma
uvicorn demo.app:app --port 8000              # la demo, en paralelo si se quiere
```

Con Docker completo: `docker compose up` levanta `db`, `api` (:8000, Plomada) y
`plataforma` (:8100). La demo no está en compose: es `uvicorn demo.app:app`.

`/health` responde `{"ok": true}` cuando Postgres tiene el esquema; con `ok: false`
dice qué falta (variable o migración).

## Variables de entorno

| Variable | Qué hace |
|---|---|
| `DATABASE_URL` | Postgres con el esquema `pliego` |
| `SECRET_KEY` | firma de cookies y tokens (≥ 32 bytes) |
| `BASE_URL` | URL pública; va en los enlaces de los correos |
| `SMTP_URL` | `smtp://usuario:clave@host:587?tls=1`; vacío = los correos se imprimen en el log |
| `CORREO_REMITENTE` | remitente de los correos |
| `PLATAFORMA_ADMINS` | emails (coma) que ven `/admin` |
| `PLATAFORMA_DATOS` | raíz de datos en disco (warehouse, caché de Croma, PDFs) |
| `PLIEGO_FUENTE`, `CROMA_*` | ver `docs/enfoques/croma.md` |

## Estructura

```
plataforma/
  app.py          FastAPI, mounts, manejo de errores
  config.py       pydantic-settings (patrón de api/app/config.py)
  db.py           pool psycopg + uno/todos/ejecutar/transaccion
  migrar.py       aplica sql/*.sql una vez cada uno (tabla pliego.migraciones)
  vistas.py       layouts publica() y privada(), campos de formulario, mensajes
  routers/        publico, empresa, panel, cuenta, admin, pliegos
  sql/            001_esquema.sql, ...
  tests/
```

## Estado

| Fase | Entrega | Estado |
|---|---|---|
| 0 | esqueleto, config, Postgres, migraciones, landing, Dockerfile, compose | hecha |
| 1 | cuentas: registro, verificación, login, reset, equipo e invitaciones, CSRF, rate limit | pendiente |
| 2 | perfil de la empresa (wizard) y contexto de empresa para los enfoques | pendiente |
| 3 | datos de Croma por departamento en un warehouse DuckDB en disco, trabajos en segundo plano | pendiente |
| 4 | filtro, radar y simulador montados bajo `/app/*` con sesión; panel con cifras de la empresa | pendiente |
| 5 | pliegos: subir PDF, extracción con Claude, checklist y generador sobre él | pendiente |
| 6 | admin, health, Render con disco, documentación, PR a `dev` | pendiente |

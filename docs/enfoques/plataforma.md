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

Sin `SMTP_URL`, los correos (verificación, reset, invitación) **no salen**: el enlace
se imprime en el log de uvicorn con nivel WARNING. Es el modo de desarrollo.

## Cuentas (fase 1)

- La cuenta es la empresa (NIT con dígito de verificación DIAN validado). Quien se
  registra es `admin`; invita por correo a `admin` o `miembro`. Un correo es una sola
  cuenta en toda la plataforma.
- Contraseñas con argon2id; sesión en servidor (`pliego.sesiones`) con la cookie
  `pliego_sesion` (solo el id, firmado); expira a los 30 días sin uso; CSRF por
  sesión en todo POST; rate limit por IP y por correo en login, registro, reset e
  invitaciones (`pliego.intentos`).
- Registro, "olvidé mi contraseña" y reenvío responden igual exista o no el correo.
- Cambiar la contraseña (o restablecerla) cierra las demás sesiones.
- `/terminos` y `/privacidad` son borradores marcados `<!-- REVISAR LEGAL -->`.

## Perfil de la empresa (fase 2)

Wizard de tres pasos en `/empresa/perfil/{1,2,3}` (solo admins editan): sede y
departamentos donde licita y códigos UNSPSC; RUP, indicadores financieros y
organizacionales, capacidad residual y cuantía objetivo; contratos de experiencia.
Se guarda en `pliego.empresas.perfil` (JSONB) con **la misma forma que
`pliego/filtro/fixtures/perfil_constructora.json`**, validada por
`plataforma/esquemas.py`. Los departamentos van también a `empresas.departamentos` y
quedan `pendiente` en `pliego.descargas_departamento` (la fase 3 los descarga).

`pliego/comun/contexto.py` lleva la empresa actual (ContextVar) durante cada petición
con sesión; `pliego/filtro/datos.perfil()` devuelve ese perfil si hay contexto y el
ficticio si no (demo, pruebas). Catálogos en `plataforma/catalogos.py`.

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
| 1 | cuentas: registro, verificación, login, reset, equipo e invitaciones, CSRF, rate limit | hecha |
| 2 | perfil de la empresa (wizard) y contexto de empresa para los enfoques | hecha |
| 3 | datos de Croma por departamento en un warehouse DuckDB en disco, trabajos en segundo plano | pendiente |
| 4 | filtro, radar y simulador montados bajo `/app/*` con sesión; panel con cifras de la empresa | pendiente |
| 5 | pliegos: subir PDF, extracción con Claude, checklist y generador sobre él | pendiente |
| 6 | admin, health, Render con disco, documentación, PR a `dev` | pendiente |

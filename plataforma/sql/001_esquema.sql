-- Esquema de la plataforma Pliego. Idempotente: se puede correr dos veces.
-- Lo aplica `python -m plataforma.migrar`, que anota cada archivo en
-- pliego.migraciones y no lo repite.

CREATE SCHEMA IF NOT EXISTS pliego;

-- La cuenta es la empresa (constructora). Quien se registra es su primer
-- admin. `perfil` tiene la misma forma que pliego/filtro/fixtures/
-- perfil_constructora.json, porque es lo que consumen los enfoques.
CREATE TABLE IF NOT EXISTS pliego.empresas (
  id              BIGSERIAL PRIMARY KEY,
  nit             TEXT UNIQUE NOT NULL,           -- solo digitos, sin DV
  nombre          TEXT NOT NULL,
  perfil          JSONB NOT NULL DEFAULT '{}',
  departamentos   TEXT[] NOT NULL DEFAULT '{}',   -- MAYUSCULAS sin tildes
  perfil_completo BOOLEAN NOT NULL DEFAULT FALSE,
  creada          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pliego.usuarios (
  id               BIGSERIAL PRIMARY KEY,
  empresa_id       BIGINT NOT NULL REFERENCES pliego.empresas ON DELETE CASCADE,
  email            TEXT UNIQUE NOT NULL,          -- en minusculas
  nombre           TEXT NOT NULL,
  hash             TEXT NOT NULL,                 -- argon2id
  rol              TEXT NOT NULL CHECK (rol IN ('admin', 'miembro')),
  email_verificado TIMESTAMPTZ,
  creado           TIMESTAMPTZ NOT NULL DEFAULT now(),
  ultimo_acceso    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS usuarios_empresa ON pliego.usuarios (empresa_id);

-- Sesiones en servidor: en la cookie solo viaja el id firmado. Asi se
-- pueden listar y cerrar desde /cuenta.
CREATE TABLE IF NOT EXISTS pliego.sesiones (
  id          TEXT PRIMARY KEY,
  usuario_id  BIGINT NOT NULL REFERENCES pliego.usuarios ON DELETE CASCADE,
  csrf        TEXT NOT NULL,
  creada      TIMESTAMPTZ NOT NULL DEFAULT now(),
  ultimo_uso  TIMESTAMPTZ NOT NULL DEFAULT now(),
  ip          TEXT,
  agente      TEXT
);
CREATE INDEX IF NOT EXISTS sesiones_usuario ON pliego.sesiones (usuario_id);

-- Tokens de un solo uso: verificar correo, restablecer contrasena,
-- invitacion a una empresa.
CREATE TABLE IF NOT EXISTS pliego.tokens (
  id          TEXT PRIMARY KEY,
  tipo        TEXT NOT NULL CHECK (tipo IN ('verificar', 'reset', 'invitacion')),
  usuario_id  BIGINT REFERENCES pliego.usuarios ON DELETE CASCADE,
  empresa_id  BIGINT REFERENCES pliego.empresas ON DELETE CASCADE,
  email       TEXT,
  rol         TEXT,
  expira      TIMESTAMPTZ NOT NULL,
  usado       TIMESTAMPTZ
);

-- Estado de la descarga de Croma por departamento (fase 3).
CREATE TABLE IF NOT EXISTS pliego.descargas_departamento (
  departamento TEXT PRIMARY KEY,
  estado       TEXT NOT NULL CHECK (estado IN ('pendiente', 'descargando', 'lista', 'error')),
  as_of        TIMESTAMPTZ,
  ultima_ok    TIMESTAMPTZ,
  paginas      INT NOT NULL DEFAULT 0,
  error        TEXT,
  actualizado  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Rate limit de login/registro/reset: contador por clave y ventana.
CREATE TABLE IF NOT EXISTS pliego.intentos (
  clave   TEXT NOT NULL,
  ventana TIMESTAMPTZ NOT NULL,
  n       INT NOT NULL DEFAULT 1,
  PRIMARY KEY (clave, ventana)
);

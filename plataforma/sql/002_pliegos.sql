-- Fase 5: pliegos subidos por la empresa y su extraccion.

CREATE TABLE IF NOT EXISTS pliego.pliegos (
  id          BIGSERIAL PRIMARY KEY,
  empresa_id  BIGINT NOT NULL REFERENCES pliego.empresas ON DELETE CASCADE,
  nombre      TEXT NOT NULL,                     -- nombre del archivo que subio la empresa
  sha256      TEXT NOT NULL,
  ruta_pdf    TEXT NOT NULL,                     -- relativa a PLATAFORMA_DATOS
  paginas     INT,
  estado      TEXT NOT NULL CHECK (estado IN ('subido', 'extrayendo', 'listo', 'error')),
  extraccion  JSONB,                             -- forma de pliego/generador/fixtures/pliego_*.json
  requisitos  JSONB,                             -- forma de pliego/checklist/fixtures/requisitos_*.json
  citas_bbox  JSONB,                             -- forma de pliego/checklist/fixtures/citas_bbox.json
  error       TEXT,
  costo_usd   NUMERIC(8, 4),                     -- estimado, por los tokens de la extraccion
  subido_por  BIGINT REFERENCES pliego.usuarios ON DELETE SET NULL,
  creado      TIMESTAMPTZ NOT NULL DEFAULT now(),
  listo       TIMESTAMPTZ,
  UNIQUE (empresa_id, sha256)
);

-- El pliego con el que cada usuario esta trabajando en checklist/generador.
ALTER TABLE pliego.usuarios ADD COLUMN IF NOT EXISTS pliego_actual BIGINT REFERENCES pliego.pliegos ON DELETE SET NULL;

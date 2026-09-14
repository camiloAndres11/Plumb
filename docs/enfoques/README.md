# Enfoques de producto de Pliego

Cinco enfoques (ya fusionados; las ramas `feature/*` de origen se archivaron),
la demo que los junta y la plataforma para empresas:

| Carpeta | Código | Promesa |
|---|---|---|
| [`filtro-de-procesos/`](filtro-de-procesos/ENFOQUE.md) | `pliego/filtro/` | Deje de presentarse a licitaciones que no puede ganar. |
| [`checklist-habilitantes/`](checklist-habilitantes/ENFOQUE.md) | `pliego/checklist/` | No vuelva a quedar por fuera por un papel. |
| [`simulador-oferta/`](simulador-oferta/ENFOQUE.md) | `pliego/simulador/` | Oferte al precio que maximiza su puntaje, no al más bajo. |
| [`radar-competidores/`](radar-competidores/ENFOQUE.md) | `pliego/radar/` | Sepa contra quién compite antes de presentarse. |
| [`generador-propuesta/`](generador-propuesta/ENFOQUE.md) | `pliego/generador/` | Prepare la propuesta en horas, no en días. |
| [`demo/`](demo/ENFOQUE.md) | `demo/` | Landing → login → panel → los cinco, en un solo servicio (puerto 8000). |
| [`plataforma.md`](plataforma.md) | `plataforma/` | La versión para empresas reales: cuentas, perfil, datos por empresa (puerto 8100). |

También: [`croma.md`](croma.md) (la fuente de datos) y, en la raíz, `CONTEXT.md`
(glosario) y `docs/adr/` (decisiones).

`uvicorn demo.app:app --port 8000` levanta la demo.

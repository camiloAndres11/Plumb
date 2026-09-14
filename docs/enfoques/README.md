# Enfoques de producto de Pliego

Cinco prototipos, uno por rama `feature/*`, más la demo que los junta:

| Carpeta | Rama | Promesa |
|---|---|---|
| [`filtro-de-procesos/`](filtro-de-procesos/ENFOQUE.md) | `feature/filtro-de-procesos` | Deje de presentarse a licitaciones que no puede ganar. |
| [`checklist-habilitantes/`](checklist-habilitantes/ENFOQUE.md) | `feature/checklist-habilitantes` | No vuelva a quedar por fuera por un papel. |
| [`simulador-oferta/`](simulador-oferta/ENFOQUE.md) | `feature/simulador-oferta` | Oferte al precio que maximiza su puntaje, no al más bajo. |
| [`radar-competidores/`](radar-competidores/ENFOQUE.md) | `feature/radar-competidores` | Sepa contra quién compite antes de presentarse. |
| [`generador-propuesta/`](generador-propuesta/ENFOQUE.md) | `feature/generador-propuesta` | Prepare la propuesta en horas, no en días. |
| [`demo/`](demo/ENFOQUE.md) | `demo/integracion-equipo` | Landing → login → panel → los cinco, en un solo servicio. |
| [`plataforma.md`](plataforma.md) | `rarechimera87` | La versión para empresas reales: cuentas, perfil, datos por empresa. Puerto 8100. |

`uvicorn demo.app:app --port 8000` levanta todo.

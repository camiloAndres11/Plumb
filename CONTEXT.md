# Pliego · contexto de dominio

Glosario de los términos que usa el código. Cuando un nombre nuevo no esté
aquí, o es un invento (reconsiderar) o falta (añadirlo). Las decisiones de
arquitectura están en `docs/adr/`.

| Término | Qué es | Dónde vive |
|---|---|---|
| **Proceso** | Una licitación publicada en SECOP II (`id_del_proceso`, `CO1.REQ.…`). Puede estar **abierto** (acepta ofertas) o **adjudicado**. | `pliego/comun/fuente.py` (`ESQUEMA_PROCESO`) |
| **Contrato** | Lo que resulta de un proceso adjudicado (`id_contrato`, `CO1.PCCNTR.…`), con proveedor, valor y estado de ejecución. Se enlaza a su proceso por `notice_uid`. | `ESQUEMA_BASE`; `mapeo_croma.notice_uid` |
| **Universo accionable** | Los procesos abiertos con fecha de cierre futura. Los `sin_fecha_cierre` y `cierre_vencido` se excluyen. | `fuente.sql_banderas` |
| **Banderas** (`f_*`) | Señales sobre un proceso abierto (ventana corta, entidad con proponente único, sin interés a tiempo…). Riesgo no es fraude. | `fuente.sql_banderas`; `pliego/filtro/reglas.py` |
| **Habilitante** | Requisito que, si no se cumple, deja fuera la oferta (experiencia, capacidad residual, indicadores). Distinto de una **señal**, que solo suma o resta puntaje. | `pliego/filtro/logica.py` |
| **Familia UNSPSC** | Los cuatro dígitos tras `V1.` del código de clasificación; es la unidad con la que se compara la experiencia. | `pliego/filtro/logica.familia` |
| **Perfil** | Lo que la empresa declara de sí misma: sede, departamentos donde licita, UNSPSC, RUP, indicadores, capacidad, experiencia. Una sola forma, la de `plataforma/esquemas.py`; el ficticio es `pliego/filtro/fixtures/perfil_constructora.json`. | `plataforma/esquemas.py` |
| **Carpeta** | Los documentos que la empresa tiene al día, con la forma que el checklist verifica. Sale del perfil más lo declarado en `/empresa/documentos`. | `plataforma/carpeta.py` |
| **Pliego** | El PDF de condiciones de un proceso, y su **extracción**: requisitos, lotes, formatos, citas con página. | `plataforma/extraccion.py`, `pliego/checklist` |
| **Lote** (grupo) | Cada parte licitable de un proceso, con presupuesto y plazo propios. El checklist y el generador trabajan por lote. | `pliego/checklist/datos.lote` |
| **Formato** | Un anexo que la propuesta debe incluir (Formato 1, 2…); el generador produce un borrador por formato con cada dato marcado por **origen** (pliego, perfil, calculado, faltante). | `pliego/generador/logica.py` |
| **Fuente** | De dónde salen las filas de los enfoques: `fixtures` (parquet commiteados), `croma` (DuckDB en memoria con datos de hoy) o `warehouse` (DuckDB en disco por departamento, el de la plataforma). | `pliego/comun/fuente.py` |
| **Semilla** | El SQL con el que un enfoque genera sus fixtures desde el warehouse de Plomada; la misma SQL corre sobre Croma y sobre el warehouse. | `pliego/*/semilla.py`, `pliego/comun/semillas.py` |
| **Warehouse** | El DuckDB en disco de la plataforma, con las tablas `*_todo` por departamento descargado y la vista `alertas_todo`. | `pliego/comun/warehouse.py` |
| **Ámbito** | Los departamentos de la empresa en contexto, ordenados; decide qué filas ve y es la llave de caché compartida entre empresas con los mismos departamentos. | `pliego/comun/contexto.py` |
| **Contexto** (de empresa) | La empresa, su perfil, su ámbito y su pliego elegido durante una petición (`ContextVar`). Sin contexto, todo lee fixtures. | `pliego/comun/contexto.py` |
| **Enfoque** | Cada una de las cinco apps de producto (filtro, checklist, simulador, radar, generador): `app.py` + `templates/` + `datos.py` + `logica.py`. | `pliego/<enfoque>/` |
| **Hub** | Un concentrador que monta los enfoques bajo un prefijo (la demo, la plataforma) y les impone su sidebar vía `request.state.hub`. | `pliego/comun/templates/base.html` |
| **Empresa / usuario** | La cuenta es la empresa (NIT); quien se registra es `admin` e invita `admin` o `miembro`. Un correo es una sola cuenta. | `plataforma/cuentas.py` |
| **Croma** | Proveedor de datos (`api.croma.run`) con SECOP I y II como dataset; 1 crédito por consulta. No es competidor. | `pliego/comun/croma.py`, `docs/enfoques/croma.md` |
| **Plomada** | El producto anterior (riesgo en contratación); legado en `legacy/plomada/`, en producción, sin refactorizar. | ADR 0001 |

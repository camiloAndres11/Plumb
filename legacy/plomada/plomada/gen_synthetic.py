"""Genera los CSV sinteticos de fixtures/ con EXACTAMENTE los encabezados del
contrato de datos (FRONT.md seccion 4). Se borra el dia que llegue el pipeline
real.

Viven en fixtures/, no en out/: out/ es el nombre que usa pipeline/report.py
para el contrato de datos REAL (raiz del repo). Que la carpeta se llame
distinto es a proposito, para que a nadie se le ocurra publicar esto
creyendo que son datos de verdad (ver data.py: _resolver_out()).

Incluye a proposito los casos dificiles de la seccion 10: 'NO DEFINIDO',
urlproceso como struct, valor imposible, municipio de 4 contratos, siglas.
"""
import csv, random
from pathlib import Path

OUT = Path(__file__).parent / "fixtures"
random.seed(1971)

# --- glosario: 22 banderas, copiadas TAL CUAL de la tabla `pesos` de
# sql/03_ranking.sql (F1.2b). Esa tabla es la fuente de verdad; esto no se
# reescribe a mano, se transcribe. Es un ARCHIVO, no codigo — el pipeline
# real lo reemplaza con el export de "banderas_glosario.csv": SELECT * FROM
# pesos ORDER BY peso DESC, bandera.
BANDERAS = [
    # bandera, peso, grupo, glosa
    ("f_cuenta_compartida", 3.0, "Red", "Proveedores distintos cobrando a la misma cuenta bancaria"),
    ("f_ordenador_es_supervisor", 3.0, "Red", "El mismo funcionario autoriza el gasto y supervisa la ejecucion"),
    ("f_sobrepago", 3.0, "Dinero", "Se pago mas del valor del contrato"),
    ("f_anticipo_no_declarado", 3.0, "Dinero", "Declara no tener anticipo pero registra anticipo girado"),
    ("f_anticipo_al_tope", 2.0, "Dinero", "Agota exactamente el anticipo maximo legal del 50%"),
    ("f_fraccionamiento", 3.0, "Umbrales", "Contratos hermanos al mismo proveedor, misma categoria, en 30 dias"),
    ("f_proponente_unico", 2.0, "Competencia", "Un solo oferente en el proceso"),
    ("f_obra_directa", 2.0, "Competencia", "Obra publica adjudicada por contratacion directa"),
    ("f_ratio_calcado", 2.0, "Competencia", "Adjudicado al 99.5-100% del presupuesto oficial, sin competencia"),
    ("f_invitacion_vacia", 2.0, "Competencia", "Cinco o mas invitados y un solo oferente efectivo"),
    ("f_replegal_multiempresa", 2.0, "Red", "Representante legal compartido por 3+ empresas proveedoras"),
    ("f_ordenador_concentrado", 2.0, "Red", "El ordenador concentra >50% de su valor en un solo proveedor"),
    ("f_al_tope_minima", 2.0, "Umbrales", "Valor pegado al techo de la minima cuantia de la entidad"),
    ("f_ventana_corta", 1.0, "Competencia", "Plazo de ofertas en el decil mas corto de su modalidad"),
    ("f_supervisor_sobrecargado", 1.0, "Red", "Supervisor con 30+ contratos a cargo"),
    ("f_ordenador_itinerante", 1.0, "Red", "El ordenador ha firmado en 3+ entidades distintas"),
    ("f_prorroga_mayor", 1.0, "Ejecucion", "Plazo adicionado en mas del 50% del original"),
    ("f_cierre_de_periodo", 1.0, "Ejecucion", "Firmado en la segunda quincena de diciembre del ultimo ano de gobierno"),
    ("f_datos_faltantes", 1.0, "Opacidad", "Faltan campos de publicacion obligatoria"),
    ("f_sin_proceso", 1.0, "Opacidad", "El contrato no tiene proceso publicado en SECOP II"),
    ("f_valor_implausible", 1.0, "Opacidad", "Valor publicado imposible (por encima de 10 billones COP)"),
    ("f_cuenta_consorcios", 1.0, "Red", "Consorcio comparte cuenta con su propio miembro (indicio debil)"),
]
FLAGS = [b[0] for b in BANDERAS]
PESO = {b[0]: b[1] for b in BANDERAS}
# "fuerte" = peso 3, exactamente los 5 que sql/03_ranking.sql suma en
# n_banderas_fuertes (f_cuenta_compartida, f_ordenador_es_supervisor,
# f_sobrepago, f_anticipo_no_declarado, f_fraccionamiento).
FUERTE = {b for b in FLAGS if PESO[b] >= 3.0}
# suma de todos los pesos: el score real es puntos_crudos / este total
# (sql/03_ranking.sql, tabla puntajes), no un techo arbitrario.
WTOT = sum(PESO.values())

# Las 11 columnas ev_* que de verdad emite sql/02_flags.sql (tabla `flags`,
# la que alimenta contratos_atipicos.csv). Hay otras 4 ev_* (ev_proveedores_
# cluster y companeras) pero esas viven en sql/06_banderas_grafo.sql, una
# capa de RED aparte con su propia tabla de pesos (pesos_grafo, banderas
# g_*) que no es la que se esta reconciliando en F1.2b.
EV = ["ev_share_top1_ordenador", "ev_hhi_ordenador", "ev_contratos_supervisor",
      "ev_entidades_ordenador", "ev_proveedores_por_cuenta", "ev_tipo_red_cuenta",
      "ev_empresas_por_replegal", "ev_hermanos_30d", "ev_ventana_mediana_modalidad",
      "ev_tope_minima_entidad", "ev_tasa_autosupervision_entidad"]

HEADERS = ("id_contrato nit_entidad entidad departamento ciudad orden tipo_contrato "
    "modalidad estado unspsc fecha_firma anio periodo_gobierno descripcion "
    "dir_ejecucion urlproceso valor valor_plausible valor_pagado valor_pend_ejecucion "
    "valor_anticipo precio_base rec_regalias rec_sgp rec_propios_terr "
    "n_oferentes_unicos n_invitados dias_ventana dias_originales dias_adicionados "
    "proveedor ordenador supervisor doc_proveedor doc_ordenador doc_supervisor "
    "doc_replegal cuenta_key puntos_crudos score n_banderas_fuertes es_atipico"
    ).split() + FLAGS + EV

# --- vocabulario en MAYUSCULAS SIN TILDES, como sale del pipeline ---
MUNICIPIOS = [
    # departamento, ciudad, n_contratos, n_atipicos  (casos del brief incluidos)
    ("ANTIOQUIA", "EL BAGRE", 256, 202),
    ("CUNDINAMARCA", "SOACHA", 2229, 1676),
    ("BOGOTA D.C.", "BOGOTA D.C.", 340, 61),
    ("CHOCO", "QUIBDO", 180, 61),
    ("CHOCO", "NO DEFINIDO", 42, 19),
    ("LA GUAJIRA", "URIBIA", 97, 44),
    ("BOYACA", "SOGAMOSO", 133, 21),
    ("BOYACA", "TUNJA", 210, 30),
    ("NARINO", "PUERRES", 61, 27),
    ("NARINO", "IPIALES", 88, 19),
    ("VALLE DEL CAUCA", "BUENAVENTURA", 174, 79),
    ("ATLANTICO", "SOLEDAD", 122, 40),
    ("SUCRE", "SINCELEJO", 90, 25),
    ("CORDOBA", "MONTERIA", 105, 22),
    ("MAGDALENA", "SANTA MARTA", 118, 37),
    ("SANTANDER", "BARRANCABERMEJA", 140, 33),
    ("CESAR", "VALLEDUPAR", 99, 18),
    ("META", "PUERTO GAITAN", 76, 34),
    ("CASANARE", "YOPAL", 82, 20),
    ("ARAUCA", "SARAVENA", 55, 21),
    ("PUTUMAYO", "MOCOA", 47, 12),
    ("VICHADA", "CUMARIBO", 4, 2),          # trampa: 50% crudo con n=4
    ("AMAZONAS", "LETICIA", 6, 3),          # trampa: 50% crudo con n=6
    ("GUAINIA", "INIRIDA", 12, 4),
    ("TOLIMA", "IBAGUE", 130, 26),
    ("HUILA", "NEIVA", 111, 24),
    ("CAUCA", "POPAYAN", 108, 31),
    ("CALDAS", "MANIZALES", 95, 15),
    ("RISARALDA", "PEREIRA", 101, 17),
    ("QUINDIO", "ARMENIA", 70, 11),
    ("NORTE DE SANTANDER", "CUCUTA", 126, 35),
    ("BOLIVAR", "CARTAGENA", 160, 52),
    ("CAQUETA", "FLORENCIA", 58, 14),
    ("GUAVIARE", "SAN JOSE DEL GUAVIARE", 31, 9),
    ("VAUPES", "MITU", 18, 5),
    ("ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA", "SAN ANDRES", 24, 8),
]

ENTIDADES = [
    ("899999061", "INSTITUTO DE INFRAESTRUCTURA Y CONCESIONES DE CUNDINAMARCA - ICCU", "DEPARTAMENTAL"),
    ("890905211", "MUNICIPIO DE EL BAGRE", "TERRITORIAL"),
    ("891680011", "GOBERNACION DEL CHOCO", "DEPARTAMENTAL"),
    ("800103913", "E.S.E. HOSPITAL SAN RAFAEL", "TERRITORIAL"),
    ("899999034", "AGENCIA NACIONAL DE INFRAESTRUCTURA - ANI", "NACIONAL"),
    ("899999063", "SERVICIO NACIONAL DE APRENDIZAJE - SENA", "NACIONAL"),
    ("892000501", "ALCALDIA MUNICIPAL DE PUERTO GAITAN", "TERRITORIAL"),
    ("890801150", "EMPRESA DE ACUEDUCTO Y ALCANTARILLADO E.S.P.", "TERRITORIAL"),
]
PROVEEDORES = [
    ("900412345", "MYG LINARES S.A.S."), ("901556677", "MYG PUERRES S.A.S."),
    ("830112233", "CONSTRUCCIONES DEL NORTE LTDA"), ("900778899", "INGENIERIA Y OBRAS CIVILES SAS"),
    ("901223344", "CONSORCIO VIAS DEL SUR"), ("860334455", "INTERVENTORIAS TECNICAS ANDINAS S.A."),
    ("900990011", "UNION TEMPORAL PROGRESO 2024"), ("901445566", "GRUPO EMPRESARIAL DEL CARIBE SAS"),
    ("800556677", "JUNTA DE ACCION COMUNAL VEREDA LA ESPERANZA"),
    ("901667788", "CONSTRUCTORA VIBORAL S.A.S."),
]
NOMBRES = ["JAIRO ANTONIO MENDOZA PALACIOS", "LUZ MARINA CARDENAS OSPINA",
    "HERNAN DARIO QUINTERO BEDOYA", "MARTHA CECILIA ROJAS VILLAMIL",
    "OSCAR IVAN BETANCUR GIRALDO", "GLORIA ESPERANZA NINO ARAUJO",
    "WILSON ALBERTO GUERRERO PAZ", "SANDRA PATRICIA MOSQUERA RENTERIA",
    "ALVARO JOSE PENALOZA SIERRA", "DIANA CAROLINA ZAPATA TORO"]
TIPOS = ["OBRA"]*10 + ["INTERVENTORIA"]*3 + ["CONSULTORIA"]*2 + ["APP", "CONCESION"]
MODALIDADES = ["LICITACION PUBLICA", "SELECCION ABREVIADA", "CONTRATACION DIRECTA",
               "MINIMA CUANTIA", "CONCURSO DE MERITOS"]
MEDIANA_VENTANA = {"LICITACION PUBLICA": 24, "SELECCION ABREVIADA": 12,
    "CONTRATACION DIRECTA": 1, "MINIMA CUANTIA": 4, "CONCURSO DE MERITOS": 15}
ESTADOS = ["EN EJECUCION", "TERMINADO", "CELEBRADO", "LIQUIDADO"]
OBJETOS = [
    "MEJORAMIENTO DE VIA TERCIARIA EN LA VEREDA EL PORVENIR",
    "CONSTRUCCION DE PLACA HUELLA EN ZONA RURAL DEL MUNICIPIO",
    "MANTENIMIENTO DE LA INFRAESTRUCTURA EDUCATIVA DE LA I.E. SANTO TOMAS",
    "INTERVENTORIA TECNICA ADMINISTRATIVA Y FINANCIERA AL CONTRATO DE OBRA",
    "OPTIMIZACION DEL SISTEMA DE ACUEDUCTO Y ALCANTARILLADO",
    "ADECUACION DEL PARQUE PRINCIPAL Y ESPACIO PUBLICO ADYACENTE",
]
CUENTAS = ["CTA-BAN-0091823", "CTA-BAN-0044517", "CTA-BAN-0077310", "CTA-BAN-0012004"]
PERIODOS = ["2016-2019", "2020-2023", "2024-2027"]


def periodo(anio):
    return PERIODOS[0] if anio <= 2019 else (PERIODOS[1] if anio <= 2023 else PERIODOS[2])


def gen_contrato(i, dpto, ciudad, forzar=None):
    ent_nit, ent, orden = random.choice(ENTIDADES)
    prov_nit, prov = random.choice(PROVEEDORES)
    tipo = random.choice(TIPOS)
    mod = random.choice(MODALIDADES)
    anio = random.choice([2017, 2019, 2021, 2022, 2023, 2024, 2025])
    base = random.choice([48_000_000, 320_000_000, 1_450_000_000, 8_900_000_000, 63_500_000_000])
    valor = int(base * random.uniform(0.85, 1.6))
    tope_minima = 111_000_000
    dias_orig = random.choice([60, 90, 120, 180, 240])

    r = {h: "" for h in HEADERS}
    r.update(
        id_contrato=f"CO1.PCCNTR.{4_000_000 + i}", nit_entidad=ent_nit, entidad=ent,
        departamento=dpto, ciudad=ciudad, orden=orden, tipo_contrato=tipo, modalidad=mod,
        estado=random.choice(ESTADOS), unspsc=random.choice(["72141100", "72151500", "81101500"]),
        fecha_firma=f"{anio}-{random.randint(1,12):02d}-{random.randint(1,28):02d}", anio=anio,
        periodo_gobierno=periodo(anio), descripcion=random.choice(OBJETOS),
        dir_ejecucion=f"KM {random.randint(1,40)} VIA {ciudad} - ZONA RURAL",
        urlproceso="{'url': 'https://community.secop.gov.co/Public/Tendering/"
                   f"OpportunityDetail/Index?noticeUID=CO1.NTC.{5_000_000+i}&isFromPublicArea=True'" + "}",
        valor=valor, valor_plausible=valor,
        valor_pagado=int(valor * random.uniform(0.2, 1.0)),
        valor_pend_ejecucion=int(valor * random.uniform(0.0, 0.6)),
        valor_anticipo=0, precio_base=int(valor / random.uniform(0.95, 1.35)),
        rec_regalias=random.choice([0, 0, 1]), rec_sgp=random.choice([0, 1]),
        rec_propios_terr=random.choice([0, 1]),
        n_oferentes_unicos=random.randint(1, 7), n_invitados=random.randint(1, 12),
        dias_ventana=random.randint(1, 30), dias_originales=dias_orig,
        dias_adicionados=random.choice([0, 0, 30, 60, 150]),
        proveedor=prov, doc_proveedor=prov_nit,
        ordenador=random.choice(NOMBRES), doc_ordenador=str(random.randint(10**7, 10**8)),
        supervisor=random.choice(NOMBRES), doc_supervisor=str(random.randint(10**7, 10**8)),
        doc_replegal=str(random.randint(10**7, 10**8)), cuenta_key=random.choice(CUENTAS),
    )
    for f in FLAGS:
        r[f] = 0
    r.update(ev_share_top1_ordenador=round(random.uniform(0.2, 0.998), 3),
             ev_hhi_ordenador=round(random.uniform(0.1, 0.95), 3),
             ev_contratos_supervisor=random.randint(1, 200),
             ev_entidades_ordenador=random.randint(1, 5),
             ev_proveedores_por_cuenta=random.randint(1, 5),
             ev_tipo_red_cuenta=random.choice(["empresas_independientes", "consorcios", "comunitaria"]),
             ev_empresas_por_replegal=random.randint(1, 24),
             ev_hermanos_30d=random.randint(0, 6),
             ev_ventana_mediana_modalidad=MEDIANA_VENTANA[mod],
             ev_tope_minima_entidad=tope_minima,
             # tasa de autosupervision de LA ENTIDAD (no del contrato): siempre
             # por debajo de 0.5 para que la bandera, si se fuerza, sea de
             # verdad la excepcion y no la norma de publicacion (ver README).
             ev_tasa_autosupervision_entidad=round(random.uniform(0.02, 0.4), 3))

    encendidas = forzar if forzar is not None else random.sample(FLAGS, random.randint(1, 4))
    for f in encendidas:
        r[f] = 1

    # coherencia bandera <-> evidencia: la evidencia tiene que sostener la
    # bandera. El orden importa cuando dos banderas tocan el mismo campo
    # (random.sample puede encender varias a la vez): la que va despues
    # gana el valor final, y se eligio el orden para que quede la version
    # mas exigente o mas especifica.
    if r["f_proponente_unico"]: r["n_oferentes_unicos"] = 1
    if r["f_invitacion_vacia"]:                      # 5+ invitados, uno solo respondio
        r["n_invitados"] = random.randint(5, 12)
        r["n_oferentes_unicos"] = 1
    if r["f_ventana_corta"]: r["dias_ventana"] = max(1, r["ev_ventana_mediana_modalidad"] // 4)
    if r["f_obra_directa"]:
        r["tipo_contrato"], r["modalidad"] = "OBRA", "CONTRATACION DIRECTA"
        r["descripcion"] = random.choice(OBJETOS[:3] + OBJETOS[4:])   # objeto de obra, no de interventoria

    # cuenta compartida: empresas_independientes y consorcios son DOS
    # columnas distintas en sql/02_flags.sql, no una atenuada de la otra.
    # 'comunitaria' no enciende ninguna de las dos en el pipeline real -> no
    # se fuerza como bandera aqui tampoco (ver nota junto a RED_CUENTA en data.py).
    if r["f_cuenta_compartida"]:
        r["ev_tipo_red_cuenta"] = "empresas_independientes"
        r["ev_proveedores_por_cuenta"] = random.randint(2, 5)
    elif r["f_cuenta_consorcios"]:
        r["ev_tipo_red_cuenta"] = "consorcios"
        r["ev_proveedores_por_cuenta"] = random.randint(2, 4)
    else:
        r["ev_proveedores_por_cuenta"] = 1

    if r["f_replegal_multiempresa"]: r["ev_empresas_por_replegal"] = random.randint(3, 24)
    else: r["ev_empresas_por_replegal"] = 1
    if r["f_supervisor_sobrecargado"]: r["ev_contratos_supervisor"] = random.randint(30, 200)
    else: r["ev_contratos_supervisor"] = random.randint(1, 12)
    if r["f_ordenador_concentrado"]:
        r["ev_share_top1_ordenador"] = round(random.uniform(0.85, 0.998), 3)
        r["ev_hhi_ordenador"] = round(r["ev_share_top1_ordenador"] ** 2, 3)   # el HHI no puede contradecir al share
    if r["f_ordenador_itinerante"]: r["ev_entidades_ordenador"] = random.randint(3, 6)
    else: r["ev_entidades_ordenador"] = 1
    if r["f_ordenador_es_supervisor"]:     # mismo funcionario ordena y supervisa
        r["doc_supervisor"] = r["doc_ordenador"]
        r["supervisor"] = r["ordenador"]
    if r["f_fraccionamiento"]: r["ev_hermanos_30d"] = random.randint(2, 6)
    else: r["ev_hermanos_30d"] = 0

    if r["f_al_tope_minima"]:
        r["valor"] = r["valor_plausible"] = int(tope_minima * random.uniform(0.96, 0.999))
    if r["f_ratio_calcado"]:               # adjudicado al 99.5-100% del presupuesto, un solo oferente
        r["precio_base"] = int(r["valor_plausible"] / random.uniform(0.995, 1.0))
        r["n_oferentes_unicos"] = 1
    if r["f_sobrepago"]:                   # se PAGO mas de lo que vale el contrato (no: "sobre el precio base")
        r["valor_pagado"] = int(r["valor_plausible"] * random.uniform(1.02, 1.3))
        r["valor_pend_ejecucion"] = 0
    if r["f_anticipo_no_declarado"]: r["valor_anticipo"] = int(r["valor_plausible"] * 0.3)
    if r["f_anticipo_al_tope"]:             # agota EXACTAMENTE el 50% legal, no "es alto"
        r["valor_anticipo"] = int(r["valor_plausible"] * 0.5)
    if r["f_prorroga_mayor"]: r["dias_adicionados"] = int(r["dias_originales"] * random.uniform(1.2, 2.5))
    if r["f_cierre_de_periodo"]:           # firmado en dic 16-31 del ultimo anio del periodo
        r["anio"] = random.choice([2019, 2023])
        r["fecha_firma"] = f"{r['anio']}-12-{random.randint(16, 31):02d}"
        r["periodo_gobierno"] = periodo(r["anio"])
    if r["f_sin_proceso"]:                 # sin estudio de precio ni enlace SECOP publicados
        r["precio_base"] = r["urlproceso"] = ""
    if r["f_datos_faltantes"]:
        campo = random.choice(["doc_ordenador", "doc_supervisor", "doc_proveedor", "valor", "fecha_firma"])
        if campo == "doc_supervisor":
            r["supervisor"] = r["doc_supervisor"] = ""
        elif campo == "doc_ordenador":
            r["ordenador"] = r["doc_ordenador"] = ""
        elif campo == "valor":
            r["valor"] = ""    # solo el "publicado": valor_plausible se deja, ver data.py._ev()
        else:
            r[campo] = ""
    if r["f_valor_implausible"]:
        base_referencia = r["precio_base"] or r["valor_plausible"] or 100_000_000
        r["valor"] = 6_000_000_000_000_000_000  # 6e18 COP: falla de publicacion
        r["valor_plausible"] = int(base_referencia * 1.05)

    puntos = sum(PESO[f] for f in FLAGS if r[f])
    r["puntos_crudos"] = round(puntos, 2)
    r["score"] = round(puntos / WTOT, 3)   # igual que sql/03_ranking.sql: puntos_crudos / suma de pesos
    r["n_banderas_fuertes"] = sum(1 for f in FUERTE if r[f])
    r["es_atipico"] = 1
    return r


def main():
    OUT.mkdir(exist_ok=True)
    with open(OUT / "banderas_glosario.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["bandera", "peso", "grupo", "glosa"]); w.writerows(BANDERAS)

    # 200 contratos repartidos entre municipios, proporcional a n_atipicos
    total_at = sum(m[3] for m in MUNICIPIOS)
    cupos = [(m, max(1, round(200 * m[3] / total_at))) for m in MUNICIPIOS]
    filas, i = [], 0
    for (dpto, ciudad, _n, _a), cupo in cupos:
        for _ in range(cupo):
            i += 1
            filas.append(gen_contrato(i, dpto, ciudad))
    # casos obligatorios de la seccion 10, mas F1.2b: cada una de las 22
    # banderas reales tiene AQUI al menos una fila que la enciende a proposito
    # (ademas de las que caigan por azar en la poblacion aleatoria de arriba).
    # Una bandera que nunca se prueba es una frase que nadie verifico.
    filas[0] = gen_contrato(901, "ANTIOQUIA", "EL BAGRE", forzar=[
        "f_proponente_unico", "f_obra_directa", "f_cuenta_compartida",
        "f_ordenador_concentrado", "f_fraccionamiento", "f_supervisor_sobrecargado"])
    filas[1] = gen_contrato(902, "BOGOTA D.C.", "BOGOTA D.C.", forzar=["f_valor_implausible", "f_sobrepago"])
    # JAC de vereda: cuenta comunitaria, canaliza pagos de mas de una junta.
    # NO se fuerza ninguna bandera de cuenta aqui a proposito: en el pipeline
    # real (sql/02_flags.sql) 'comunitaria' no enciende ni f_cuenta_compartida
    # ni f_cuenta_consorcios, es ruido administrativo silencioso, no un
    # indicio atenuado (ver la nota junto a RED_CUENTA en data.py). Se deja
    # como caso de opacidad (f_datos_faltantes) para no perder la fila.
    filas[2] = gen_contrato(903, "CHOCO", "NO DEFINIDO", forzar=["f_datos_faltantes"])
    filas[2]["ev_tipo_red_cuenta"], filas[2]["ev_proveedores_por_cuenta"] = "comunitaria", 3
    filas[2]["proveedor"] = "JUNTA DE ACCION COMUNAL VEREDA LA ESPERANZA"
    filas[3] = gen_contrato(904, "NARINO", "PUERRES", forzar=["f_cuenta_compartida", "f_replegal_multiempresa"])
    filas[3]["proveedor"], filas[3]["cuenta_key"] = "MYG PUERRES S.A.S.", "CTA-BAN-0091823"
    filas[3]["ev_empresas_por_replegal"] = 24
    # las banderas nuevas o renombradas de F1.2b: cada una con su propia fila
    # dedicada para no depender de que random.sample() las toque por azar.
    filas[4] = gen_contrato(905, "BOYACA", "TUNJA", forzar=["f_ordenador_es_supervisor"])
    filas[5] = gen_contrato(906, "TOLIMA", "IBAGUE", forzar=["f_ratio_calcado"])
    filas[6] = gen_contrato(907, "HUILA", "NEIVA", forzar=["f_invitacion_vacia"])
    filas[7] = gen_contrato(908, "CAUCA", "POPAYAN", forzar=["f_cierre_de_periodo"])
    filas[8] = gen_contrato(909, "CALDAS", "MANIZALES", forzar=["f_sin_proceso"])
    filas[9] = gen_contrato(910, "RISARALDA", "PEREIRA", forzar=["f_al_tope_minima"])
    filas[10] = gen_contrato(911, "QUINDIO", "ARMENIA", forzar=["f_anticipo_al_tope"])
    filas[11] = gen_contrato(912, "SANTANDER", "BARRANCABERMEJA", forzar=["f_cuenta_consorcios"])
    filas[12] = gen_contrato(913, "CESAR", "VALLEDUPAR", forzar=["f_prorroga_mayor"])
    filas[13] = gen_contrato(914, "META", "PUERTO GAITAN", forzar=["f_anticipo_no_declarado"])
    filas[14] = gen_contrato(915, "SUCRE", "SINCELEJO", forzar=["f_ventana_corta"])
    filas[15] = gen_contrato(916, "CORDOBA", "MONTERIA", forzar=["f_ordenador_itinerante"])

    with open(OUT / "contratos_atipicos.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADERS); w.writeheader(); w.writerows(filas)

    # --- rankings ---
    por_mun = {}
    for r in filas:
        por_mun.setdefault((r["departamento"], r["ciudad"]), []).append(r)

    # prior empirico Beta(alpha,beta) para la tasa ajustada (shrinkage)
    tasas = [a / n for _, _, n, a in MUNICIPIOS]
    m = sum(tasas) / len(tasas)
    v = sum((t - m) ** 2 for t in tasas) / len(tasas)
    k = max(1.0, m * (1 - m) / v - 1)
    ALPHA, BETA = round(m * k, 4), round((1 - m) * k, 4)

    conteo_cols = ["n_proponente_unico", "n_obra_directa", "n_cuenta_compartida",
                   "n_fraccionamiento", "n_anticipo_no_declarado", "n_sobrepago"]
    mun_rows = []
    for dpto, ciudad, n, a in MUNICIPIOS:
        muestra = por_mun.get((dpto, ciudad), [])
        esc = a / len(muestra) if muestra else 0        # la muestra representa a atipicos
        vt = sum(r["valor_plausible"] for r in muestra) * esc * (n / a if a else 1)
        va = sum(r["valor_plausible"] for r in muestra) * esc
        row = dict(departamento=dpto, ciudad=ciudad, n_contratos=n, n_atipicos=a,
                   valor_total=int(vt), valor_atipico=int(va),
                   regalias_atipicas=int(sum(r["valor_plausible"] for r in muestra if r["rec_regalias"]) * esc),
                   score_medio=round(sum(r["score"] for r in muestra) / len(muestra), 3) if muestra else 0,
                   tasa_cruda=round(a / n, 4),
                   tasa_ajustada=round((a + ALPHA) / (n + ALPHA + BETA), 4),
                   share_valor_atipico=round(va / vt, 4) if vt else 0,
                   alpha=ALPHA, beta=BETA)
        for c in conteo_cols:
            row[c] = int(sum(r["f_" + c[2:]] for r in muestra) * esc)
        mun_rows.append(row)
    with open(OUT / "ranking_municipios.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(mun_rows[0])); w.writeheader(); w.writerows(mun_rows)

    # departamentos. OJO (F1.2b): el SELECT real de ranking_departamentos en
    # sql/03_ranking.sql NO agrega score_medio, alpha ni beta (a diferencia de
    # ranking_municipios y ranking_administraciones, que si los traen). Antes
    # este fixture los inventaba; ya no.
    dep = {}
    for r in mun_rows:
        d = dep.setdefault(r["departamento"], dict(departamento=r["departamento"], n_contratos=0,
            n_atipicos=0, valor_total=0, valor_atipico=0))
        for c in ("n_contratos", "n_atipicos", "valor_total", "valor_atipico"):
            d[c] += r[c]
    dep_rows = []
    for d in dep.values():
        n, a = d["n_contratos"], d["n_atipicos"]
        dep_rows.append(dict(departamento=d["departamento"], n_contratos=n, n_atipicos=a,
            valor_total=d["valor_total"], valor_atipico=d["valor_atipico"],
            tasa_cruda=round(a / n, 4), tasa_ajustada=round((a + ALPHA) / (n + ALPHA + BETA), 4),
            share_valor_atipico=round(d["valor_atipico"] / d["valor_total"], 4) if d["valor_total"] else 0))
    with open(OUT / "ranking_departamentos.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dep_rows[0])); w.writeheader(); w.writerows(dep_rows)

    # administraciones (entidad x periodo)
    adm = {}
    for r in filas:
        k2 = (r["nit_entidad"], r["periodo_gobierno"])
        d = adm.setdefault(k2, dict(nit_entidad=r["nit_entidad"], entidad=r["entidad"],
            departamento=r["departamento"], ciudad=r["ciudad"], orden=r["orden"],
            periodo_gobierno=r["periodo_gobierno"], n_contratos=0, n_atipicos=0,
            valor_total=0, valor_atipico=0, _s=0.0))
        d["n_atipicos"] += 1; d["valor_atipico"] += r["valor_plausible"]; d["_s"] += r["score"]
    adm_rows = []
    for d in adm.values():
        a = d["n_atipicos"]
        n = int(a / random.uniform(0.15, 0.78)) + 1
        vt = int(d["valor_atipico"] / random.uniform(0.2, 0.9))
        adm_rows.append(dict(nit_entidad=d["nit_entidad"], entidad=d["entidad"],
            departamento=d["departamento"], ciudad=d["ciudad"], orden=d["orden"],
            periodo_gobierno=d["periodo_gobierno"], n_contratos=n, n_atipicos=a,
            valor_total=vt, valor_atipico=d["valor_atipico"], score_medio=round(d["_s"] / a, 3),
            tasa_cruda=round(a / n, 4), tasa_ajustada=round((a + ALPHA) / (n + ALPHA + BETA), 4),
            share_valor_atipico=round(d["valor_atipico"] / vt, 4) if vt else 0))
    with open(OUT / "ranking_administraciones.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(adm_rows[0])); w.writeheader(); w.writerows(adm_rows)

    print(f"fixtures/: {len(filas)} contratos, {len(mun_rows)} municipios, "
          f"{len(dep_rows)} departamentos, {len(adm_rows)} administraciones, "
          f"{len(BANDERAS)} banderas. prior Beta({ALPHA}, {BETA})")


if __name__ == "__main__":
    main()

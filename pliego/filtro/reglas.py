"""Parametros del filtro. Viven aparte de la logica porque cambian con cada
version de los documentos tipo y con cada cliente; la logica no.

Los umbrales habilitantes son los de los documentos tipo de obra publica
de Colombia Compra Eficiente (indicadores financieros y organizacionales)
SIMPLIFICADOS: cada pliego fija los suyos y aqui, sin el pliego, se toma
el valor mas comun. Ver docs/ENFOQUE.md, "Que esta simulado".
"""

# Salario minimo 2026. La experiencia y el presupuesto se comparan en SMMLV
# porque asi lo exigen los pliegos.
SMMLV = 1_750_905

# Habilitantes (documentos tipo, valores usuales)
LIQUIDEZ_MIN = 1.2
ENDEUDAMIENTO_MAX = 0.70
COBERTURA_INTERESES_MIN = 1.0
RENTABILIDAD_PATRIMONIO_MIN = 0.01
RENTABILIDAD_ACTIVO_MIN = 0.005
# Experiencia acreditada en la familia UNSPSC del proceso, como fraccion
# del presupuesto oficial (en SMMLV). Los pliegos tipo piden entre 0,5 y 1,5.
EXPERIENCIA_FRACCION_MIN = 1.0

# Senales de riesgo / oportunidad sobre el historico de la entidad
GANADOR_RECURRENTE_SHARE = 0.40   # el mismo proveedor gana >= 40% ...
GANADOR_RECURRENTE_N = 5          # ... sobre al menos 5 contratos
ENTIDAD_CERRADA_TASA = 0.80       # >= 80% adjudicado con proponente unico (p90 medido)
MUCHA_COMPETENCIA_MEDIANA = 15    # mediana de oferentes en la entidad
CODIGO_RARO_N = 20                # el UNSPSC aparece < 20 veces en el historico
PLAZO_CORTO_DIAS = 3

# Peso de cada senal blanda sobre el puntaje (parte de 50). Positivo suma.
PESOS = {
    "departamento_interes": +12,
    "fuera_de_region": -12,
    "cuantia_objetivo": +8,
    "cuantia_fuera_rango": -8,
    "experiencia_holgada": +10,
    "capacidad_holgada": +6,
    "entidad_competitiva": +10,
    "ganador_recurrente": -18,
    "entidad_cerrada": -20,
    "mucha_competencia": -8,
    "codigo_raro": -10,
    "ventana_corta": -8,
    "plazo_corto": -10,
    "sin_interes_cerca_del_cierre": -4,
    "cierre_movido": -4,
}

# Umbrales de la recomendacion sobre el puntaje 0-100.
PRESENTARSE_MIN = 65
NO_PRESENTARSE_MAX = 40

# Horas que cuesta preparar una propuesta, por modalidad. Estimacion de
# oficio para un equipo de licitaciones chico; es lo que se "ahorra" al no
# presentarse. Pendiente: medirlo con clientes.
HORAS_POR_MODALIDAD = {
    "LICITACION PUBLICA OBRA PUBLICA": 80,
    "LICITACION PUBLICA": 80,
    "SELECCION ABREVIADA DE MENOR CUANTIA": 40,
    "SELECCION ABREVIADA MENOR CUANTIA SIN MANIFESTACION INTERES": 40,
    "CONCURSO DE MERITOS ABIERTO": 60,
    "CONCURSO DE MERITOS CON PRECALIFICACION": 60,
    "MINIMA CUANTIA": 12,
    "CONTRATACION REGIMEN ESPECIAL (CON OFERTAS)": 24,
    "CONTRATACION DIRECTA (CON OFERTAS)": 8,
}
HORAS_DEFECTO = 30

"""Listas canonicas para los formularios: departamentos y familias UNSPSC.

Los departamentos van como los guarda el warehouse (MAYUSCULAS sin tildes),
que es como los comparan filtro/logica.py y fuente.py. Los codigos UNSPSC son
los que mas aparecen en la contratacion de construccion del SECOP II (los
30 mas frecuentes de lo descargado de Croma el 2026-09-13); los nombres son
orientativos y en el formulario tambien se puede escribir cualquier codigo
V1.xxxxxxxx que no este aqui.
"""
from __future__ import annotations

DEPARTAMENTOS = [
    "AMAZONAS", "ANTIOQUIA", "ARAUCA", "ATLANTICO", "BOGOTA D.C.", "BOLIVAR", "BOYACA", "CALDAS",
    "CAQUETA", "CASANARE", "CAUCA", "CESAR", "CHOCO", "CORDOBA", "CUNDINAMARCA", "GUAINIA",
    "GUAVIARE", "HUILA", "LA GUAJIRA", "MAGDALENA", "META", "NARINO", "NORTE DE SANTANDER",
    "PUTUMAYO", "QUINDIO", "RISARALDA", "SAN ANDRES, PROVIDENCIA Y SANTA CATALINA", "SANTANDER",
    "SUCRE", "TOLIMA", "VALLE DEL CAUCA", "VAUPES", "VICHADA",
]

# (codigo, nombre orientativo). Familia = digitos 4-7 del codigo (7214 ...).
UNSPSC = [
    ("V1.72141000", "Construcción de autopistas y carreteras"),
    ("V1.72141100", "Pavimentación y superficies de infraestructura"),
    ("V1.72141003", "Mantenimiento de vías"),
    ("V1.72141119", "Pavimento rígido"),
    ("V1.72141120", "Pavimento flexible"),
    ("V1.72141500", "Preparación de tierras y movimiento de suelos"),
    ("V1.72101500", "Apoyo para la construcción (obras menores)"),
    ("V1.72101507", "Mantenimiento de edificaciones"),
    ("V1.72102900", "Mantenimiento y reparación de instalaciones"),
    ("V1.72103300", "Mantenimiento y reparación de infraestructura"),
    ("V1.72121400", "Edificios públicos especializados (colegios, hospitales)"),
    ("V1.72151500", "Sistemas eléctricos e iluminación"),
    ("V1.72151800", "Acueductos y alcantarillados"),
    ("V1.72151900", "Albañilería y mampostería"),
    ("V1.72152700", "Acabados"),
    ("V1.72153900", "Obras de urbanismo y espacio público"),
    ("V1.81101500", "Ingeniería civil (consultoría y diseño)"),
    ("V1.81101516", "Estudios y diseños"),
    ("V1.81101700", "Ingeniería eléctrica y electrónica"),
    ("V1.81141500", "Control de calidad e interventoría técnica"),
    ("V1.80101500", "Consultoría de gestión"),
    ("V1.80101600", "Gerencia de proyectos e interventoría"),
    ("V1.80101602", "Gerencia de proyectos de construcción"),
    ("V1.80101604", "Interventoría de obra"),
    ("V1.80111600", "Personal temporal y apoyo"),
    ("V1.80111614", "Apoyo a la gestión"),
    ("V1.77101500", "Evaluación ambiental"),
    ("V1.77101600", "Planeación ambiental"),
    ("V1.77101700", "Asesoría ambiental"),
    ("V1.83101500", "Servicios públicos (agua, energía)"),
    ("V1.84111600", "Auditoría"),
]
UNSPSC_NOMBRE = dict(UNSPSC)

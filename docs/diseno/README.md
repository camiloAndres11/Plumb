# Diseño del radar de competidores

Producido con `/design`, base visual `new-landing` ([`../estilo-base.md`](../estilo-base.md)).

- Lienzo publicado: https://claude.ai/code/artifact/60737c82-5be9-480f-b211-b1596ec084cd
- Artboards: `Main.dc.html` (competidores probables de un proceso abierto),
  `Entidad.dc.html` (perfil de entidad), `Competidor.dc.html` (perfil de
  competidor), `canvas.json`. Generados con datos reales (Municipio de
  Bucaramanga, SOSDOM S.A.S, proceso CO1.REQ.10751505).

## Decisiones

1. **Titular con veredicto**: "adjudica de forma *abierta*: nadie pasa del
   3 %", "está *cargado*: $9.645 mill. por ejecutar", "contra quién compite:
   6 proveedores probables, ninguno dominante". La etiqueta va en acento-2.
2. **Cuatro cifras** por perfil, con una sola en acento (la que decide el
   precio: "adjudica al 94,8 %" / "ofrece al 92,4 %").
3. **Quién gana** como lista con barras de 8 px (proporcionales al número
   de contratos), la primera caliente; "ofrece al" como texto en cada fila.
4. **Saturación** como barra de 0 a 3 años con marcas "cargado" (1) y
   "saturado" (2), y debajo los contratos vigentes con su saldo.
5. **Competidores probables** como ranking con peso (barra chica) y las
   razones en texto ("ganó 4 aquí · 2 de esta familia en el país"), más una
   tarjeta lateral "cómo se calcula" con los pesos explícitos.
6. Toda pantalla cierra con la limitación: SECOP no publica quién se
   presentó y perdió.

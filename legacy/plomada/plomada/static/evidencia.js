/* flag -> frase con el numero que la disparo. Puerto a JS de
 * plomada/data.py::_ev() (lineas 245-350), que sigue siendo el
 * comportamiento de referencia.
 *
 * "Sin evidencia no se publica": una bandera sin entrada aqui se muestra
 * igual, con su glosa (que el API ya trae en BanderaEncendida.glosa), pero
 * sin la frase con el numero. Las 22 claves son, una a una, las 22 banderas
 * de la tabla `pesos` de sql/03_ranking.sql.
 *
 * Devuelve {texto, atenuada}. `atenuada` marca las banderas cuyo disparo
 * tiene una explicacion administrativa conocida (consorcios, cuentas
 * comunitarias): se pintan mas tenues y con la razon a la vista, nunca se
 * esconden.
 *
 * NINGUNA plantilla emite un documento. Las dos que dependian de ellos usan
 * los booleanos derivados que sanear() de api.js deja en su lugar
 * (_tiene_doc_*, _mismo_ordenador_supervisor).
 */
import { plata, pct, entero, titulo, _num } from './formato.js';

const RED_CUENTA = {
  empresas_independientes: [false, 'empresas sin relación societaria declarada'],
  consorcios: [true, 'consorcio: la cuenta suele estar a nombre del líder, es esperable'],
  comunitaria: [true, 'cuenta comunitaria: el municipio canaliza pagos, es ruido administrativo'],
};

// Espejo de CAMPOS_OBLIGATORIOS (data.py:234-240). Se comprueba la presencia
// con los booleanos _tiene_*, nunca con el valor.
const CAMPOS_OBLIGATORIOS = [
  ['_tiene_doc_ordenador', 'la cédula del ordenador'],
  ['_tiene_doc_supervisor', 'la cédula del supervisor'],
  ['_tiene_doc_proveedor', 'el documento del proveedor'],
  ['valor', 'el valor del contrato'],
  ['fecha_firma', 'la fecha de firma'],
];

const DIC_FIRMA_CIERRE = /^\d{4}-12-(1[6-9]|2\d|3[01])$/;

/**
 * Aplana un ContratoDetalle del API ({dinero, competencia, partes, riesgo})
 * al objeto plano de una sola capa que estas plantillas esperan, que es la
 * forma que tienen las filas de out/*.csv en data.py. Suma la `evidencia` de
 * cada bandera, que es donde el API entrega los ev_*.
 */
export function aplanar(d) {
  const r = { ...d, ...(d.dinero || {}), ...(d.competencia || {}),
    ...(d.partes || {}), ...(d.riesgo || {}) };
  for (const b of d.banderas || []) {
    Object.assign(r, b.evidencia || {});
  }
  return r;
}

export function evidencias(r) {
  const t = {};
  const num = (k) => {
    const v = r[k];
    return v === null || v === undefined || v === '' ? null : Number(v);
  };
  const set = (k, texto, atenuada = false) => { t[k] = { texto, atenuada }; };

  if (num('n_oferentes_unicos') !== null) {
    const n = num('n_oferentes_unicos');
    set('f_proponente_unico', `este proceso recibió ${entero(n)} oferta${n === 1 ? '' : 's'}`);
  }
  if (num('n_invitados') !== null && num('n_oferentes_unicos') !== null) {
    const nOf = num('n_oferentes_unicos');
    set('f_invitacion_vacia', `se invitó a ${entero(num('n_invitados'))} proponentes y solo ` +
      `${entero(nOf)} presentó oferta${nOf === 1 ? '' : 's'}`);
  }
  if (num('dias_ventana') !== null && num('ev_ventana_mediana_modalidad')) {
    set('f_ventana_corta', `${entero(num('dias_ventana'))} días de ventana frente a ` +
      `${entero(num('ev_ventana_mediana_modalidad'))} de mediana en su modalidad`);
  }
  if (num('ev_contratos_supervisor')) {
    set('f_supervisor_sobrecargado',
      `esta persona figura en ${entero(num('ev_contratos_supervisor'))} contratos a cargo`);
  }
  if (num('ev_share_top1_ordenador') !== null) {
    let s = `${pct(num('ev_share_top1_ordenador'))} del valor que autorizó fue a un solo proveedor`;
    if (num('ev_hhi_ordenador') !== null) {
      s += ` (índice de concentración ${_num(num('ev_hhi_ordenador'), 2)})`;
    }
    set('f_ordenador_concentrado', s);
  }
  if (num('ev_entidades_ordenador')) {
    set('f_ordenador_itinerante',
      `ha firmado en ${entero(num('ev_entidades_ordenador'))} entidades distintas`);
  }
  // La frase tiene que decir por que ESTE caso se marca y no los de una
  // entidad donde es costumbre (README, decision 11).
  if (num('ev_tasa_autosupervision_entidad') !== null && r._mismo_ordenador_supervisor) {
    set('f_ordenador_es_supervisor',
      'el mismo funcionario autoriza el gasto y supervisa la ejecución; en esta entidad eso ocurre ' +
      `en el ${pct(num('ev_tasa_autosupervision_entidad'))} de los contratos — es la excepción, no ` +
      'la costumbre de publicación de la entidad');
  }
  if (num('ev_proveedores_por_cuenta')) {
    const tipo = r.ev_tipo_red_cuenta || '';
    const [aten, nota] = RED_CUENTA[tipo] || [false, tipo.replace(/_/g, ' ')];
    set('f_cuenta_compartida', `${entero(num('ev_proveedores_por_cuenta'))} proveedores comparten ` +
      `la misma cuenta bancaria — ${nota}`, aten);
    // f_cuenta_consorcios es OTRA bandera (peso 1), no una variante atenuada
    // de f_cuenta_compartida: en sql/02_flags.sql cada una es su propia
    // columna, y solo se enciende una u otra segun el tipo de red.
    if (tipo === 'consorcios') {
      set('f_cuenta_consorcios', `${entero(num('ev_proveedores_por_cuenta'))} proveedores del ` +
        `consorcio comparten cuenta bancaria — ${RED_CUENTA.consorcios[1]}`, true);
    }
  }
  if (num('ev_empresas_por_replegal')) {
    set('f_replegal_multiempresa', 'el mismo representante legal figura en ' +
      `${entero(num('ev_empresas_por_replegal'))} empresas proveedoras`);
  }
  if (num('ev_hermanos_30d')) {
    set('f_fraccionamiento',
      `${entero(num('ev_hermanos_30d'))} contratos hermanos al mismo proveedor en 30 días`);
  }
  if (num('ev_tope_minima_entidad') && num('valor_plausible')) {
    set('f_al_tope_minima', `${plata(num('valor_plausible'))} frente a un tope de mínima cuantía de ` +
      `${plata(num('ev_tope_minima_entidad'))} en esta entidad`);
  }
  if (num('valor_plausible') && num('precio_base') && num('n_oferentes_unicos') === 1) {
    const ratio = num('valor_plausible') / num('precio_base');
    set('f_ratio_calcado', `adjudicado en ${plata(num('valor_plausible'))} sobre un presupuesto ` +
      `oficial de ${plata(num('precio_base'))} (${pct(ratio)} del presupuesto), con un solo oferente`);
  }
  // f_sobrepago real (sql/02_flags.sql, C2): se PAGO mas de lo que vale el
  // contrato, no "se adjudico por encima del precio base" — eso es
  // f_ratio_calcado, otra bandera.
  if (num('valor_pagado') && num('valor_plausible') && num('valor_pagado') > num('valor_plausible')) {
    set('f_sobrepago', `se pagaron ${plata(num('valor_pagado'))}, por encima de los ` +
      `${plata(num('valor_plausible'))} que vale el contrato según el valor saneado`);
  }
  if (num('valor_anticipo') && num('valor_plausible')) {
    const p = num('valor_anticipo') / num('valor_plausible');
    set('f_anticipo_no_declarado', `anticipo de ${plata(num('valor_anticipo'))} (${pct(p)} del valor) ` +
      'girado sin que el contrato declare tener anticipo');
    // f_anticipo_al_tope real: agota el 50% legal, no "es alto" (README,
    // decision metodologica 5).
    set('f_anticipo_al_tope', `el anticipo de ${plata(num('valor_anticipo'))} agota exactamente ` +
      'el tope legal del 50% del valor del contrato');
  }
  if (num('dias_adicionados') && num('dias_originales')) {
    const pAdicion = num('dias_adicionados') / num('dias_originales');
    set('f_prorroga_mayor', `${entero(num('dias_adicionados'))} días adicionados sobre ` +
      `${entero(num('dias_originales'))} pactados, un ${pct(pAdicion)} de adición`);
  }
  if (r.fecha_firma && DIC_FIRMA_CIERRE.test(r.fecha_firma)) {
    set('f_cierre_de_periodo', `firmado el ${r.fecha_firma}, en la segunda quincena de diciembre ` +
      'del último año del período de gobierno: contratación de última hora ' +
      'antes de entregar la administración');
  }
  if (!r.precio_base && !r.urlproceso) {
    set('f_sin_proceso', 'no hay proceso de selección publicado en SECOP II al cual enlazar; ' +
      'sin ficha de proceso, esto no se puede verificar en el origen');
  }
  const faltan = CAMPOS_OBLIGATORIOS.filter(([campo]) => !r[campo]).map(([, nombre]) => nombre);
  if (faltan.length) {
    set('f_datos_faltantes', `faltan campos de publicación obligatoria: ${faltan.join(', ')}`);
  }
  if (num('valor') && num('valor_plausible') && num('valor') !== num('valor_plausible')) {
    set('f_valor_implausible', `la entidad publicó ${plata(num('valor'))}; se usa ` +
      `${plata(num('valor_plausible'))} como valor saneado`);
  }
  if (r.modalidad) {
    set('f_obra_directa', `${titulo(r.tipo_contrato)} adjudicada por ` +
      `${titulo(r.modalidad)}, sin proceso competitivo`);
  }
  return t;
}

// Estos son los valores literales de la columna `grupo` de
// banderas_glosario.csv, no texto editorial: van sin tilde porque asi
// salen del pipeline y por ese string se emparejan las banderas.
export const ORDEN_GRUPOS = ['Competencia', 'Red', 'Dinero', 'Umbrales', 'Ejecucion', 'Opacidad'];

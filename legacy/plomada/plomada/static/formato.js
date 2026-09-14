/* Formateo de presentacion, en JS. Espejo de plomada/data.py.
 *
 * El frontend final se alimenta por fetch y termina en Vue, asi que esta es
 * la version que sobrevive: Python conserva la suya (data.py) para lo poco
 * que pre-renderiza, y las dos quedan amarradas por el fixture compartido
 * en tests/formato_casos.json. Si tocas la semantica de una, toca la otra
 * y regenera el fixture desde data.py, que es el comportamiento de
 * referencia.
 */

// ---------------------------------------------------------------- texto
// El pipeline entrega MAYUSCULAS SIN TILDES. Estas siglas no se title-casean.
// Debe ser IDENTICO al SIGLAS de data.py.
const SIGLAS = new Set(`ICCU ANI SENA ANH ANLA DANE DNP IDU IDU SGP SGR ESE EPS IPS ARL
UT AIU APP PGN CGR SIC UAE UNGRD INVIAS ICBF UPME UNAL UPTC UIS UDEA IE ONG SA SAS
LTDA ESP DC AA BID BM ONU OEA CAR CVC CRC CDA NIT RUT SECOP CO COP EU USA`.split(/\s+/));

const MINUSCULAS = new Set('de del la las el los y e en al a con por para o u da do'.split(' '));

const ROMANO = /^[IVXLC]+$/;
const LIMPIO_RE = /[^A-Za-zÁÉÍÓÚÑÜ]/g;
const PUNTUACION_BORDE = /^[.,;:()[\]"']+|[.,;:()[\]"']+$/g;

function esMayuscula(s) {
  // Espejo de str.isupper(): al menos un caracter con mayus/minus distintas,
  // y ninguno en minuscula.
  return s.length > 0 && s === s.toUpperCase() && s !== s.toLowerCase();
}

/** Title-case que no destroza siglas ni abreviaturas con punto. */
export function titulo(texto) {
  if (!texto) return '';
  const palabras = String(texto).split(/\s+/).filter(Boolean);
  const salida = palabras.map((p, i) => {
    const nucleo = p.replace(PUNTUACION_BORDE, '');
    const limpio = nucleo.replace(LIMPIO_RE, '');
    const sigla = SIGLAS.has(nucleo.toUpperCase())
      || (nucleo.includes('.') && limpio.length <= 5)          // E.S.E., S.A.S., D.C.
      || (esMayuscula(limpio) && limpio.length >= 2 && !/[AEIOU]/.test(limpio))
      || (ROMANO.test(nucleo) && nucleo.length > 1);
    if (sigla) return p.toUpperCase();
    if (i > 0 && MINUSCULAS.has(p.toLowerCase())) return p.toLowerCase();
    return p.charAt(0).toUpperCase() + p.slice(1).toLowerCase();
  });
  return salida.join(' ');
}

/** Espejo de sin_tildes(): NFD, se quitan las marcas combinantes, mayusculas. */
export function sinTildes(t) {
  const s = t ? String(t) : '';   // 't or ""' de Python: falsy -> cadena vacia
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().trim();
}

/** Slug de URL a partir de varias partes, sin tildes ni caracteres raros. */
export function slug(...partes) {
  const s = sinTildes(partes.filter(Boolean).map(String).join('-')).toLowerCase();
  return s.replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-+|-+$/g, '');
}

// --------------------------------------------------------------- numeros
// Tolerante: null/undefined/''/'abc' -> null. Espejo del try/except float()
// de data.py.
function _numero(valor) {
  if (valor === null || valor === undefined) return null;
  if (typeof valor === 'boolean') return null;
  if (typeof valor === 'string') {
    const t = valor.trim();
    if (t === '') return null;
    const v = Number(t);
    return Number.isFinite(v) ? v : null;
  }
  const v = Number(valor);
  return Number.isFinite(v) ? v : null;
}

// separador de miles '.', decimal ',' (formato es-CO). Espejo de _num().
// exportada para evidencia.js, que replica el `_num(x, 2)` con que data.py
// imprime el indice de concentracion del ordenador
export function _num(x, dec) {
  const negativo = x < 0;
  const abs = Math.abs(x);
  const fijo = abs.toFixed(dec);
  const [ent, frac] = fijo.split('.');
  const conMiles = ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (negativo ? '-' : '') + conMiles + (frac !== undefined ? ',' + frac : '');
}

// En Colombia billon = 10^12.
const ESCALAS = [
  [1e12, 'billones', 'billon'],
  [1e9, 'mil millones', 'mil millones'],
  [1e6, 'millones', 'millon'],
];

/** $209 billones / $500 mil millones / $63,5 mil millones. */
export function plata(valor, exacto = false) {
  const v = _numero(valor);
  if (v === null) return 'sin dato';
  if (exacto || Math.abs(v) < 1e6) return '$' + _num(v, 0);
  for (const [corte, plural, singular] of ESCALAS) {
    if (Math.abs(v) >= corte) {
      const n = v / corte;
      const dec = Math.abs(n) >= 100 || Math.abs(n - Math.round(n)) < 0.05 ? 0 : 1;
      const factor = 10 ** dec;
      const redondeado = Math.round(Math.abs(n) * factor) / factor;
      const unidad = redondeado === 1 ? singular : plural;
      return `$${_num(n, dec)} ${unidad}`;
    }
  }
  return '$' + _num(v, 0);
}

export function pct(x, dec = 1) {
  const v = _numero(x);
  if (v === null) return 'sin dato';
  return _num(v * 100, dec) + '%';
}

export function entero(x) {
  const v = _numero(x);
  if (v === null) return 'sin dato';
  return _num(v, 0);
}

/* Buscador contra el API en vivo (GET /v1/contratos), con paginacion
 * server-side. Antes esto filtraba en memoria un indice de 8,5 MB que se le
 * descargaba entero a cada visitante antes de que pudiera teclear (~3 s en
 * 4G, ~8 s en 3G). Ahora cada consulta pesa ~4,5 KB y tarda ~0,7 s.
 *
 * El estado sigue viviendo en la query string: la URL de la barra es el
 * enlace compartible con los filtros puestos. Eso no cambio.
 *
 * HIDRATACION DEL OBJETO CONTRACTUAL
 * El API busca dentro de `descripcion` (?texto=puente encuentra contratos
 * cuyo objeto dice "puente") pero NO la devuelve en el listado: el modelo
 * ContratoResumen no la trae. Sin ella la tabla no tiene titulo legible y el
 * usuario no puede ver POR QUE coincidio su busqueda.
 * Mientras el API no la incluya (ver el plan, §4.2), se pide el detalle de
 * las filas visibles en paralelo y el titulo se rellena en cuanto llega. La
 * fila se pinta de inmediato con lo que si vino: no se bloquea la tabla
 * esperando.
 */
import { plata } from './formato.js';
import { pedir, pedirCacheado, listar, listarCacheado, enParalelo, mensajeVacio } from './api.js';

const PAGINA = 25;          // 25 filas => 25 detalles a hidratar (~0,4 s)
const TOPE_EXPORTAR = 2000; // arriba de esto, exportar tarda demasiado

// Nombre del campo en el formulario -> nombre del parametro en el API.
const A_PARAM = {
  q: 'texto', departamento: 'departamento', municipio: 'ciudad',
  entidad: 'entidad', anio: 'anio', tipo: 'tipo_contrato',
  modalidad: 'modalidad', bandera: 'bandera',
  vmin: 'valor_min', vmax: 'valor_max',
};

// El API solo ordena por estos cuatro (probado: devuelve 422 con cualquier
// otro). Las columnas de texto dejaron de ser ordenables -- ordenar solo la
// pagina cargada mentiria sobre el resto del resultado.
const A_ORDEN = { valor: 'valor', score: 'score', anio: 'fecha', fuertes: 'riesgo' };

const COP = new Intl.NumberFormat('es-CO');
const tbody = document.querySelector('#resultados tbody');
const resumen = document.getElementById('resumen');
const campos = [...document.querySelectorAll('[data-campo]')];
const mas = document.getElementById('mas');

let orden = { campo: 'score', asc: false };
let cargados = [];     // filas ya pintadas
let total = 0;
let enVuelo = null;    // AbortController de la consulta activa
let debounce = null;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function urlFicha(id) {
  return '/contrato/' + String(id).toLowerCase().replace(/[^a-z0-9]+/g, '-') + '/';
}

function estado() {
  const o = {};
  campos.forEach((el) => { if (el.value) o[el.dataset.campo] = el.value; });
  return o;
}

function aParams(f) {
  const p = { solo_atipicos: true, limite: PAGINA };
  for (const [campo, valor] of Object.entries(f)) {
    if (A_PARAM[campo]) p[A_PARAM[campo]] = valor;
  }
  const base = A_ORDEN[orden.campo] || 'score';
  p.orden = orden.asc ? base : '-' + base;
  return p;
}

function fila(c) {
  const objeto = c.descripcion
    ? esc(c.descripcion)
    : '<span class="cargando-objeto">' + esc(c.id_contrato) + '</span>';
  return '<tr data-id="' + esc(c.id_contrato) + '">' +
    '<td><a href="' + urlFicha(c.id_contrato) + '">' + objeto + '</a>' +
    '<small>' + esc(c.proveedor) + '</small></td>' +
    '<td>' + esc(c.entidad) + '</td>' +
    '<td>' + esc(c.ciudad || 'Sin municipio definido') + '</td>' +
    '<td class="num">' + esc(c.anio) + '</td>' +
    '<td class="num">' + plata(c.valor_plausible) + '</td>' +
    '<td class="num">' + (c.n_banderas_fuertes || 0) + '</td>' +
    '<td class="num">' + Number(c.score || 0).toFixed(2).replace('.', ',') + '</td></tr>';
}

/** Pide el detalle de las filas recien pintadas y les pone el objeto
 *  contractual encima, en cuanto llega cada uno. */
async function hidratarObjetos(filas, signal) {
  await enParalelo(filas, async (c) => {
    if (c.descripcion) return null;
    const { datos } = await pedir('/v1/contratos/' + encodeURIComponent(c.id_contrato), null, { signal });
    c.descripcion = datos.descripcion || 'Objeto no publicado';
    const tr = tbody.querySelector('[data-id="' + CSS.escape(c.id_contrato) + '"] a');
    if (tr) tr.textContent = c.descripcion;
    return null;
  });
}

function pintarMas(filas) {
  tbody.insertAdjacentHTML('beforeend', filas.map(fila).join(''));
  mas.hidden = cargados.length >= total;
  mas.textContent = 'Ver más (' + COP.format(Math.max(total - cargados.length, 0)) + ' restantes)';
}

async function consultar({ anexar = false } = {}) {
  if (enVuelo) enVuelo.abort();
  enVuelo = new AbortController();
  const signal = enVuelo.signal;
  const f = estado();

  if (!anexar) {
    cargados = [];
    tbody.innerHTML = '';
    mas.hidden = true;
  }
  resumen.textContent = anexar ? 'Cargando más…' : 'Buscando…';

  try {
    const { datos, meta } = await pedir('/v1/contratos',
      { ...aParams(f), desplazamiento: cargados.length },
      { signal, alDespertar: () => { resumen.textContent = 'Despertando el servicio, puede tardar hasta un minuto…'; } });

    total = (meta.paginacion && meta.paginacion.total) || datos.length;
    cargados = cargados.concat(datos);
    pintarMas(datos);

    resumen.textContent = total
      ? COP.format(total) + ' contrato' + (total === 1 ? '' : 's') + ' marcado' +
        (total === 1 ? '' : 's') + ' · mostrando ' + COP.format(cargados.length)
      : 'Ningún contrato del universo de obra cae dentro de estos filtros.';

    sincronizarURL(f);
    hidratarObjetos(datos, signal).catch(() => { /* el titulo se queda con el id */ });
  } catch (e) {
    if (signal.aborted) return;   // el usuario siguio tecleando: no es un error
    resumen.textContent = mensajeVacio(e);
    mas.hidden = true;
  }
}

function sincronizarURL(f) {
  const u = new URL(location.href);
  u.search = '';
  Object.keys(f).forEach((k) => u.searchParams.set(k, f[k]));
  if (orden.campo !== 'score' || orden.asc) {
    u.searchParams.set('orden', orden.campo);
    if (orden.asc) u.searchParams.set('asc', '1');
  }
  history.replaceState(null, '', u.pathname + (u.search || ''));
}

function desdeURL() {
  const p = new URL(location.href).searchParams;
  campos.forEach((el) => {
    const v = p.get(el.dataset.campo);
    if (v != null) el.value = v;
  });
  if (p.get('orden')) orden = { campo: p.get('orden'), asc: p.get('asc') === '1' };
  marcarOrden();
}

function marcarOrden() {
  document.querySelectorAll('#resultados th[data-orden]').forEach((th) => {
    if (th.dataset.orden === orden.campo) {
      th.setAttribute('aria-sort', orden.asc ? 'ascending' : 'descending');
    } else {
      th.removeAttribute('aria-sort');
    }
  });
}

/** Rellena los <select> de facetas desde el API, en vez de incrustar miles de
 *  <option> en el HTML de la pagina. */
async function cargarFacetas() {
  const poner = (id, valores, etiqueta = (x) => x) => {
    const sel = document.getElementById(id);
    if (!sel || !valores) return;
    const elegido = sel.value;
    sel.insertAdjacentHTML('beforeend', valores
      .map((v) => '<option value="' + esc(v) + '">' + esc(etiqueta(v)) + '</option>').join(''));
    if (elegido) sel.value = elegido;
  };
  try {
    // Municipios va por listarCacheado: son 721 y el tope del API es 200, asi
    // que pedir una sola pagina dejaba fuera dos tercios de la lista sin que
    // nada lo avisara -- un filtro que no ofrece el municipio que buscas.
    const [deps, muns, bands] = await Promise.all([
      pedirCacheado('/v1/departamentos'),
      listarCacheado('/v1/municipios', { min_contratos: 0 }),
      pedirCacheado('/v1/banderas'),
    ]);
    poner('f-departamento', deps.datos.map((d) => d.departamento).sort());
    poner('f-municipio', [...new Set(muns.map((m) => m.ciudad))].sort());
    poner('f-bandera', bands.datos.map((b) => b.bandera),
      (b) => b.replace(/^f_/, '').replace(/_/g, ' '));
  } catch {
    /* Sin facetas el buscador sigue sirviendo: el campo de texto y los
       filtros numericos no dependen de esto. */
  }
}

document.getElementById('exportar').addEventListener('click', async (ev) => {
  const boton = ev.currentTarget;
  const original = boton.textContent;
  if (total > TOPE_EXPORTAR) {
    resumen.textContent = 'Son ' + COP.format(total) + ' resultados: afine los filtros a ' +
      COP.format(TOPE_EXPORTAR) + ' o menos para exportar.';
    return;
  }
  boton.disabled = true;
  boton.textContent = 'Preparando…';
  try {
    const f = estado();
    const params = aParams(f);
    delete params.limite;
    const filas = await listar('/v1/contratos', params, {
      alAvanzar: (n, t) => { boton.textContent = 'Preparando… ' + n + '/' + t; },
    });
    boton.textContent = 'Trayendo objetos…';
    await enParalelo(filas, async (c) => {
      if (c.descripcion) return null;
      const { datos } = await pedir('/v1/contratos/' + encodeURIComponent(c.id_contrato));
      c.descripcion = datos.descripcion || '';
      return null;
    });

    const cols = ['id_contrato', 'objeto', 'entidad', 'departamento', 'municipio', 'proveedor',
      'anio', 'tipo_contrato', 'modalidad', 'valor_plausible', 'score',
      'n_banderas_fuertes', 'banderas', 'url_secop', 'ficha_plomada'];
    const esq = (v) => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
    const cuerpo = filas.map((c) => [
      c.id_contrato, c.descripcion, c.entidad, c.departamento, c.ciudad, c.proveedor,
      c.anio, c.tipo_contrato, c.modalidad, c.valor_plausible, c.score,
      c.n_banderas_fuertes, (c.banderas || []).join(' '), c.urlproceso,
      location.origin + urlFicha(c.id_contrato),
    ].map(esq).join(','));
    // BOM para que Excel en es-CO no destroce las tildes
    const blob = new Blob(['﻿' + cols.join(',') + '\n' + cuerpo.join('\n')],
      { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'plomada-contratos-' + filas.length + '.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  } catch {
    resumen.textContent = 'Se cortó el hilo a media descarga: el API no respondió y el CSV quedó sin armar.';
  } finally {
    boton.disabled = false;
    boton.textContent = original;
  }
});

document.getElementById('limpiar').addEventListener('click', () => {
  campos.forEach((el) => { el.value = ''; });
  orden = { campo: 'score', asc: false };
  marcarOrden();
  consultar();
});

campos.forEach((el) => {
  const evento = el.tagName === 'SELECT' ? 'change' : 'input';
  el.addEventListener(evento, () => {
    clearTimeout(debounce);
    // Teclear no dispara una consulta por letra: se espera a que pare.
    debounce = setTimeout(() => consultar(), evento === 'input' ? 300 : 0);
  });
});

document.querySelectorAll('#resultados th[data-orden]').forEach((th) => {
  th.addEventListener('click', () => {
    const c = th.dataset.orden;
    orden = { campo: c, asc: orden.campo === c ? !orden.asc : false };
    marcarOrden();
    consultar();
  });
});

mas.addEventListener('click', () => consultar({ anexar: true }));

desdeURL();
consultar();
cargarFacetas();

/* Ficha de municipio, hidratada del API.
 *
 * La URL es /municipio/<slug-departamento-ciudad>/ y el slug NO es reversible
 * (junta departamento y ciudad con el mismo separador que usa dentro de cada
 * uno: "cesar-valledupar" no dice donde termina el departamento). Asi que en
 * vez de invertirlo, se traen los 721 municipios de /v1/municipios -- una
 * lista chica, cacheada en sessionStorage -- y se busca cual produce ese
 * mismo slug. De paso eso da el puesto en el ranking nacional sin otra
 * llamada.
 */
import { plata, pct, entero, titulo, slug } from './formato.js';
import { pedir, listarCacheado, enParalelo, mensajeVacio } from './api.js';

const PAGINA = 25;
const raiz = document.getElementById('municipio');
const estado = document.getElementById('mun-estado');

let ctx = null;      // {m, puesto, total}
let cargados = 0;
let totalContratos = 0;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function urlFicha(id) {
  return '/contrato/' + String(id).toLowerCase().replace(/[^a-z0-9]+/g, '-') + '/';
}

function slugDeURL() {
  const p = new URL(location.href).searchParams.get('m');
  if (p) return p;
  return location.pathname.replace(/\/+$/, '').split('/').pop() || null;
}

function cabecera(m, puesto, totalMun) {
  const ciudad = m.ciudad && m.ciudad !== 'NO DEFINIDO' ? titulo(m.ciudad) : null;
  const dep = titulo(m.departamento);
  const nombre = ciudad || ('Contratos sin municipio definido — ' + dep);
  document.title = nombre + ' · Plomada';
  return '<header class="cab">' +
    '<h1>' + esc(nombre) + '</h1>' +
    '<p class="bajada">' + esc(dep) + ' · puesto ' + entero(puesto) + ' de ' +
      entero(totalMun) + ' por tasa ajustada</p>' +
    '</header>' +
    '<dl class="cab-grid">' +
      '<div class="dato"><dt>Tasa ajustada</dt><dd class="destacado">' +
        pct(m.tasa_ajustada) + '</dd></div>' +
      '<div class="dato"><dt>Tasa cruda</dt><dd class="tenue">' + pct(m.tasa_cruda) + '</dd></div>' +
      '<div class="dato"><dt>Contratos</dt><dd>' + entero(m.n_contratos) + '</dd></div>' +
      '<div class="dato"><dt>Marcados</dt><dd>' + entero(m.n_atipicos) + '</dd></div>' +
      '<div class="dato"><dt>Valor total</dt><dd>' + plata(m.valor_total) + '</dd></div>' +
      '<div class="dato"><dt>Valor marcado</dt><dd>' + plata(m.valor_atipico) + '</dd></div>' +
    '</dl>' +
    '<p class="nota">Ordenado por tasa ajustada, nunca por la cruda. Las dos se muestran ' +
      'juntas. <a href="/metodologia/#tasa">Por qué</a></p>' +
    '<div class="tabla-scroll"><table class="table" id="mun-tabla"><thead><tr>' +
      '<th>Objeto</th><th class="num">Valor</th><th class="num">Año</th>' +
      '<th class="num">Señales</th></tr></thead><tbody></tbody></table></div>' +
    '<p><button type="button" id="mun-mas" hidden>Ver más</button></p>' +
    '<p><a href="/buscar/?departamento=' + encodeURIComponent(m.departamento) +
      '&municipio=' + encodeURIComponent(m.ciudad) + '">Ver en el buscador con filtros &rarr;</a></p>';
}

function fila(c) {
  return '<tr data-id="' + esc(c.id_contrato) + '">' +
    '<td><a href="' + urlFicha(c.id_contrato) + '">' +
      '<span class="objeto">' + esc(c.id_contrato) + '</span></a>' +
      '<small>' + esc(titulo(c.entidad)) + '</small></td>' +
    '<td class="num">' + plata(c.valor_plausible) + '</td>' +
    '<td class="num">' + esc(c.anio) + '</td>' +
    '<td class="num">' + (c.n_banderas_fuertes || 0) + '</td></tr>';
}

/** El listado del API no trae `descripcion` (ver el plan, §4.2): se pide el
 *  detalle de las filas visibles y el titulo se rellena al llegar. */
async function hidratarObjetos(filas) {
  const tbody = document.querySelector('#mun-tabla tbody');
  await enParalelo(filas, async (c) => {
    const { datos } = await pedir('/v1/contratos/' + encodeURIComponent(c.id_contrato));
    const el = tbody.querySelector('[data-id="' + CSS.escape(c.id_contrato) + '"] .objeto');
    if (el) el.textContent = titulo(datos.descripcion) || 'Objeto no publicado';
    return null;
  });
}

async function traerPagina() {
  const { m } = ctx;
  const { datos, meta } = await pedir('/v1/contratos', {
    solo_atipicos: true, departamento: m.departamento, ciudad: m.ciudad,
    orden: '-riesgo', limite: PAGINA, desplazamiento: cargados,
  });
  totalContratos = (meta.paginacion && meta.paginacion.total) || datos.length;
  cargados += datos.length;

  const tbody = document.querySelector('#mun-tabla tbody');
  tbody.insertAdjacentHTML('beforeend', datos.map(fila).join(''));
  const mas = document.getElementById('mun-mas');
  mas.hidden = cargados >= totalContratos;
  mas.textContent = 'Ver más (' + (totalContratos - cargados) + ' restantes)';
  hidratarObjetos(datos).catch(() => { /* el titulo se queda con el id */ });
}

async function cargar() {
  const s = slugDeURL();
  if (!s) {
    estado.textContent = 'No hay nada que medir: la dirección no trae ningún municipio.';
    return;
  }
  try {
    // Los 721 completos, no la primera pagina: el puesto en el ranking solo
    // significa algo si se compara contra todos.
    const muns = await listarCacheado('/v1/municipios', { min_contratos: 0 });
    const orden = [...muns].sort((a, b) => (b.tasa_ajustada || 0) - (a.tasa_ajustada || 0));
    const i = orden.findIndex((m) => slug(m.departamento, m.ciudad) === s);
    if (i === -1) {
      estado.innerHTML = 'Este municipio queda fuera del corte: no tiene contratos de obra ' +
        'en el universo analizado. <a href="/mapa/">Ver el mapa</a>.';
      return;
    }
    ctx = { m: orden[i], puesto: i + 1, total: orden.length };

    raiz.innerHTML = cabecera(ctx.m, ctx.puesto, ctx.total);
    estado.hidden = true;
    raiz.hidden = false;
    document.getElementById('mun-mas')
      .addEventListener('click', () => traerPagina().catch(() => {}));
    await traerPagina();
  } catch (e) {
    estado.innerHTML = mensajeVacio(e) + ' <a href="/mapa/">Ir al mapa</a>.';
  }
}

cargar();

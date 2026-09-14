/* Ficha de contrato, hidratada desde GET /v1/contratos/{id}.
 *
 * El id sale de la propia URL: /contrato/co1-pccntr-8462295/ -> el slug es
 * reversible (mayusculas + '-' por '.'), asi que no hace falta ninguna tabla
 * de lookup ni un indice previo.
 *
 * Lo que NO se pinta desde aqui: el aviso "Indicio, no acusacion", la
 * cabecera y el enlace a la metodologia. Esos van en el shell estatico que
 * genera build.py, para que sigan visibles aunque el API no responda: son
 * justamente las salvedades que no pueden depender de una llamada de red.
 */
import { plata, entero, titulo, slug } from './formato.js';
import { pedir, mensajeVacio } from './api.js';
import { aplanar, evidencias, ORDEN_GRUPOS } from './evidencia.js';
import { montar as montarMapa, coordsContrato } from './mapa-satelital.js';

const raiz = document.getElementById('ficha');
const estado = document.getElementById('ficha-estado');

/* El API no devuelve coordenadas: la geocodificacion vive en
   plomada/geo/geocache.json y build.py la publica en /datos/geocache.json.
   Se pide una sola vez, en paralelo con el contrato, y si falta (build sin
   geocodificar) la ficha degrada a la nota de "sin geocodificar" en vez de
   romperse. */
async function traerGeocache() {
  try {
    const r = await fetch('/datos/geocache.json');
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

const NOTA_PRECISION = {
  cabecera_municipal: 'Ubicación aproximada: cabecera municipal. No se pudo geocodificar ' +
    'la dirección exacta, común en zona rural.',
};

/** Espejo de build.bloque_mapa(): el placeholder con el boton, o la nota que
    explica por que no hay mapa. Nunca pide una tile por su cuenta. */
function bloqueMapa(d, geocache) {
  if (!d.ciudad || d.ciudad === 'NO DEFINIDO') {
    return '<p class="mapa-nota sin">Municipio no definido en la fuente: ' +
      'no hay dónde centrar un mapa.</p>';
  }
  const coords = coordsContrato(d, geocache);
  if (!coords) return '<p class="mapa-nota sin">Ubicación no geocodificada todavía.</p>';
  const direccion = [titulo(d.dir_ejecucion), titulo(d.ciudad)].filter(Boolean).join(', ');
  const nota = NOTA_PRECISION[coords.precision] || '';
  return '<div id="mapa-satelital" class="mapa-placeholder" data-lat="' + esc(coords.lat) +
      '" data-lon="' + esc(coords.lon) + '" data-direccion="' + esc(direccion) + '">' +
      '<p class="mapa-direccion">' + (esc(direccion) || 'Ubicación sin dirección textual') + '</p>' +
      '<p class="nota">La imagen satelital la sirve Esri (arcgisonline.com): al cargarla, ' +
      'Esri recibe las coordenadas que está viendo. No se pide sola.</p>' +
      '<button type="button" class="btn btn-secondary">Ver imagen satelital</button></div>' +
      (nota ? '<p class="mapa-nota">' + esc(nota) + '</p>' : '');
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function idDesdeURL() {
  const p = new URL(location.href).searchParams.get('id');
  if (p) return p.toUpperCase();
  // /contrato/co1-pccntr-8462295/ -> CO1.PCCNTR.8462295
  const m = location.pathname.replace(/\/+$/, '').split('/').pop();
  return m ? m.toUpperCase().replace(/-/g, '.') : null;
}

/** `12 días` cuando hay numero, `sin dato` a secas cuando no: entero() ya
    devuelve 'sin dato', y pegarle la unidad daba "sin dato días". */
function dias(x) {
  const t = entero(x);
  return t === 'sin dato' ? t : t + ' días';
}

function dato(etiqueta, valor, nota) {
  if (valor === null || valor === undefined || valor === '') return '';
  return '<div class="dato"><dt>' + esc(etiqueta) + '</dt><dd>' + valor +
    (nota ? '<small>' + nota + '</small>' : '') + '</dd></div>';
}

function bloqueBanderas(d, r) {
  const ev = evidencias(r);
  const encendidas = d.banderas || [];
  if (!encendidas.length) {
    return '<p class="nota">Este contrato no tiene señales encendidas.</p>';
  }
  const porGrupo = new Map();
  for (const b of encendidas) {
    if (!porGrupo.has(b.grupo)) porGrupo.set(b.grupo, []);
    porGrupo.get(b.grupo).push(b);
  }
  const grupos = [...ORDEN_GRUPOS, ...[...porGrupo.keys()].filter((g) => !ORDEN_GRUPOS.includes(g))];

  let salida = '';
  for (const g of grupos) {
    const lista = porGrupo.get(g);
    if (!lista) continue;
    lista.sort((a, b) => (b.peso || 0) - (a.peso || 0));
    const items = lista.map((b) => {
      const e = ev[b.bandera];
      const nombre = titulo(b.bandera.replace(/^f_/, '').replace(/_/g, ' '));
      return '<li class="bandera' + (e && e.atenuada ? ' atenuada' : '') + '">' +
        '<b>' + esc(nombre) + '</b>' +
        '<p class="glosa">' + esc(b.glosa) + '</p>' +
        (e ? '<p class="evidencia">' + esc(e.texto) + '</p>'
           : '<p class="evidencia sin">Sin el número que la disparó en esta versión del API.</p>') +
        '<span class="peso">peso ' + esc(b.peso) + '</span></li>';
    }).join('');
    salida += '<h3>' + esc(g) + '</h3><ul class="banderas">' + items + '</ul>';
  }
  return salida;
}

function pintar(d, geocache) {
  const r = aplanar(d);
  const objeto = titulo(d.descripcion) || 'Objeto contractual no publicado';
  const dinero = d.dinero || {};
  const partes = d.partes || {};
  const comp = d.competencia || {};
  const ciudad = d.ciudad && d.ciudad !== 'NO DEFINIDO' ? titulo(d.ciudad) : null;
  const valor = dinero.valor_plausible;

  document.title = objeto.slice(0, 70) + ' · Plomada';

  const verificar = d.urlproceso
    ? '<a class="btn-verificar" href="' + esc(d.urlproceso) + '" rel="noopener nofollow" ' +
      'target="_blank">Verificar en SECOP II &rarr;</a>'
    : '<p class="btn-verificar sin">La fuente no publicó enlace al proceso. ' +
      'Sin verificación en origen, trátelo como no confirmado.</p>';

  let filasPlata = dato('Valor del contrato', plata(valor),
    '<small>' + plata(valor, true) + '</small>');
  if (dinero.valor && dinero.valor !== valor) {
    filasPlata += dato('Valor publicado por la entidad',
      '<span class="alerta">' + plata(dinero.valor) + '</span>',
      'Cifra aritméticamente imposible. Se trata como falla de publicación; ' +
      'todas las sumas de este sitio usan el valor saneado.');
  }
  for (const [etq, k] of [['Pagado', 'valor_pagado'], ['Pendiente de ejecución', 'valor_pend_ejecucion'],
    ['Anticipo', 'valor_anticipo'], ['Precio base del estudio', 'precio_base']]) {
    if (dinero[k]) filasPlata += dato(etq, plata(dinero[k]));
  }

  const recursos = [['Regalías', 'rec_regalias'], ['SGP', 'rec_sgp'],
    ['Recursos propios', 'rec_propios_terr']]
    .filter(([, k]) => dinero[k]).map(([n]) => n);

  let personas = dato('Proveedor', esc(titulo(partes.proveedor)) || 'sin dato');
  if (partes.ordenador) {
    personas += dato('Ordenador del gasto', esc(titulo(partes.ordenador)),
      'Funcionario público. Se publica el nombre, no el documento.');
  }
  personas += dato('Supervisor', esc(titulo(partes.supervisor)) ||
    '<span class="alerta">no reportado</span>');

  raiz.innerHTML =
    '<article class="ficha">' +
    '<header class="ficha-cab">' +
      '<p class="tipo">' + esc(titulo(d.tipo_contrato)) + ' &middot; ' + esc(titulo(d.modalidad)) + '</p>' +
      '<h1>' + esc(objeto) + '</h1>' +
      '<p class="idc"><code>' + esc(d.id_contrato) + '</code></p>' +
      verificar +
    '</header>' +
    '<dl class="cab-grid">' +
      dato('Entidad', esc(titulo(d.entidad)),
        'NIT ' + esc(d.nit_entidad) + ' &middot; orden ' + esc(titulo(d.orden))) +
      dato('Municipio', ciudad
        ? '<a href="/municipio/' + esc(slug(d.departamento, d.ciudad)) + '/">' + esc(ciudad) + '</a>'
        : '<span class="alerta">no definido en la fuente</span>',
        esc(titulo(d.departamento))) +
      dato('Valor', plata(valor)) +
      dato('Firma', esc(d.fecha_firma), 'Período ' + esc(d.periodo_gobierno)) +
      dato('Estado', esc(titulo(d.estado))) +
      dato('Plazo', dias(comp.dias_originales) +
        (comp.dias_adicionados
          ? ' <span class="alerta">+' + entero(comp.dias_adicionados) + ' adicionados</span>' : '')) +
    '</dl>' +
    '<section class="caja principal">' +
      '<h2>Señales de riesgo encendidas <span class="cuenta">' +
        ((d.banderas || []).length) + '</span></h2>' +
      '<p class="nota">Agrupadas por tipo y ordenadas por peso. Cada una viene con el número ' +
        'que la disparó: si el número no le convence, el enlace a la fuente oficial está arriba.</p>' +
      bloqueBanderas(d, r) +
    '</section>' +
    '<div class="dos-col">' +
      '<section class="caja"><h2>Dinero</h2><dl class="dl">' + filasPlata + '</dl>' +
        (recursos.length ? '<p class="fuentes">Fuente de recursos: ' + esc(recursos.join(', ')) + '</p>' : '') +
      '</section>' +
      '<section class="caja"><h2>Personas y competencia</h2><dl class="dl">' + personas +
        dato('Ofertas recibidas', entero(comp.n_oferentes_unicos)) +
        dato('Invitados', entero(comp.n_invitados)) +
        dato('Ventana de publicación', dias(comp.dias_ventana),
          'Mediana de su modalidad: ' + dias(r.ev_ventana_mediana_modalidad)) +
      '</dl>' +
        '<p class="nota">Los documentos de identidad de particulares no se publican. ' +
        '<a href="/metodologia/#privacidad">Por qué</a></p>' +
      '</section>' +
    '</div>' +
    '<section class="caja"><h2>Ejecución</h2><dl class="dl">' +
      dato('Dirección de ejecución', esc(titulo(d.dir_ejecucion))) +
      dato('Clasificación UNSPSC', esc(d.unspsc)) +
    '</dl>' + bloqueMapa(d, geocache) + '</section>' +
    '</article>';

  // despues de pintar, no antes: el contenedor acaba de existir
  montarMapa(document.getElementById('mapa-satelital'));

  estado.hidden = true;
  raiz.hidden = false;
}

async function cargar() {
  const id = idDesdeURL();
  if (!id) {
    estado.textContent = 'No hay nada que medir: la dirección no trae ningún contrato.';
    return;
  }
  const geocache = traerGeocache();   // en paralelo con el contrato, no en serie
  try {
    const { datos } = await pedir('/v1/contratos/' + encodeURIComponent(id), null, {
      alDespertar: () => {
        estado.textContent = 'Despertando el servicio, puede tardar hasta un minuto…';
      },
    });
    pintar(datos, await geocache);
  } catch (e) {
    // El API responde 404 CON cuerpo {error:{codigo:'no_encontrado'}}, y
    // pedir() mira el cuerpo antes que el status: el codigo que llega aqui es
    // 'no_encontrado', no '404'. Se aceptan los dos por si eso cambia.
    if (e && (e.codigo === 'no_encontrado' || e.codigo === '404')) {
      estado.innerHTML = 'Este contrato queda fuera del corte: no aparece en el universo ' +
        'de obra pública analizado. <a href="/buscar/">Buscar otro contrato</a>.';
      return;
    }
    estado.innerHTML = mensajeVacio(e) + ' <a href="/buscar/">Ir al buscador</a>.';
  }
}

cargar();

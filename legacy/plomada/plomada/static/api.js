/* Cliente del API de Plomada para el navegador. Gemelo en JS de
 * pipeline/api_cliente.py: un solo modulo habla HTTP, para que el
 * saneamiento, los reintentos y los estados de "sin datos" se escriban una
 * vez y ninguna vista pueda saltarselos por descuido.
 *
 * ---------------------------------------------------------------- PRIVACIDAD
 * El API DEVUELVE DOCUMENTOS PROHIBIDOS. Verificado en produccion:
 * GET /v1/contratos/{id} trae partes.doc_ordenador (cedula de una persona
 * natural), doc_supervisor, doc_replegal y doc_proveedor; y el listado trae
 * doc_proveedor en cada fila.
 *
 * Esos campos son los que plomada/data.py marca como PROHIBIDAS /
 * PROHIBIDAS_CONDICIONALES y por los que existe plomada/test_privacy.py.
 *
 * sanear() de aqui abajo los borra apenas llega la respuesta, ANTES de que
 * ninguna vista los vea. Hay que ser honesto sobre el alcance de eso:
 *
 *   - SI evita que Plomada publique, pinte, indexe o exporte un documento.
 *     Ninguna vista puede mostrarlo porque para cuando recibe el objeto, el
 *     campo ya no existe.
 *   - NO cierra la fuga de origen: el dato igual viajo por la red hasta el
 *     navegador y se ve en la pestana de red de DevTools. Eso NO se puede
 *     arreglar desde el cliente -- ningun front puede: el arreglo va en el
 *     serializador del API (ver el plan, §4.1).
 *
 * Mientras el API siga devolviendolos, tests/test_api_privacidad.py falla a
 * proposito en CI. Ese test es la unica alarma que queda y no debe silenciarse:
 * su fallo no es un test roto, es la fuga que sigue abierta.
 */

const BASE = (typeof window !== 'undefined' && window.PLOMADA_API_URL) ||
  'https://plumb-duy6.onrender.com';

// Espejo de D.PROHIBIDAS | D.PROHIBIDAS_CONDICIONALES (plomada/data.py:48-53).
// doc_proveedor entra igual aunque sea condicional: la regla de "solo si es
// persona juridica" necesita clasificar el nombre, y equivocarse aqui publica
// la cedula de un contratista. Se borra siempre; el nombre del proveedor, que
// es lo que el sitio muestra, se conserva intacto.
const DOCS_PROHIBIDOS = [
  'doc', 'doc_a', 'doc_b',
  'doc_proveedor', 'doc_ordenador', 'doc_supervisor', 'doc_replegal',
  'cuenta_bancaria', 'cuenta_key',
];

/**
 * Borra recursivamente todo campo prohibido. Puro: no toca red ni DOM.
 *
 * En vez de borrar a secas, deja en su lugar `_tiene_<campo>: bool`. Dos
 * banderas del sitio dependen de la PRESENCIA del documento, nunca de su
 * valor, y sin esto se romperian:
 *   - f_datos_faltantes  enumera que campos de publicacion obligatoria faltan
 *     (data.py:234-240 ya insiste: "solo se comprueba presencia, jamas se
 *     emite el dato").
 *   - f_ordenador_es_supervisor  compara doc_ordenador con doc_supervisor.
 *     La igualdad se calcula aqui, dentro del saneador, y sale como el
 *     booleano `_mismo_ordenador_supervisor`: la comparacion ocurre sin que
 *     ninguna vista llegue a ver los dos numeros.
 */
export function sanear(valor) {
  if (Array.isArray(valor)) return valor.map(sanear);
  if (valor && typeof valor === 'object') {
    const limpio = {};
    for (const [k, v] of Object.entries(valor)) {
      if (DOCS_PROHIBIDOS.includes(k)) {
        limpio['_tiene_' + k] = v !== null && v !== undefined && v !== '';
        continue;
      }
      limpio[k] = sanear(v);
    }
    if (valor.doc_ordenador || valor.doc_supervisor) {
      limpio._mismo_ordenador_supervisor =
        !!valor.doc_ordenador && valor.doc_ordenador === valor.doc_supervisor;
    }
    // El API ya no manda las cedulas: manda su presencia (tiene_doc_*) y la
    // coincidencia (mismo_ordenador_supervisor). Se traducen a los nombres
    // que las vistas ya usan, asi el sitio no cambia.
    for (const k of Object.keys(valor)) {
      if (k.startsWith('tiene_doc_')) limpio['_' + k] = !!valor[k];
    }
    if ('mismo_ordenador_supervisor' in valor) {
      limpio._mismo_ordenador_supervisor = !!valor.mismo_ordenador_supervisor;
    }
    return limpio;
  }
  return valor;
}

export class ApiError extends Error {
  constructor(mensaje, codigo) {
    super(mensaje);
    this.codigo = codigo;
  }
}

/** El API respondio, pero su base no tiene datos ('datos_no_disponibles'). */
export class SinDatos extends ApiError {}

/**
 * La frase que ve el lector cuando una consulta vuelve vacia o rota.
 *
 * Vive aqui y no en cada vista por lo mismo que sanear(): si cada pagina
 * redacta su propio "no hay datos", el sitio termina hablando con tres voces
 * distintas del mismo silencio. La imagen es la del proyecto -- una plomada
 * que no cuelga no mide nada, y un hilo cortado no es lo mismo que una pared
 * derecha -- pero la segunda mitad de cada frase dice en seco que paso, para
 * que nadie tenga que descifrar la metafora para entender el estado.
 *
 * Devuelve texto plano sin punto final ni espacio: la vista le pega el enlace
 * de salida que corresponda ("Ir al buscador", "Ver el mapa").
 */
export function mensajeVacio(e) {
  return e instanceof SinDatos
    ? 'La plomada todavía no cuelga: el API aún no tiene cargada la base.'
    : 'Se cortó el hilo: no se pudo consultar el API.';
}

const TIMEOUT_PRIMERA = 60000;   // Render puede estar dormido: 30-60s
const TIMEOUT_NORMAL = 15000;
const REINTENTOS = 3;
const AVISO_DESPERTANDO = 3000;  // a los 3s sin respuesta, avisar al usuario

let primeraLlamada = true;
const memoria = new Map();

function url(ruta, params) {
  const u = new URL(BASE.replace(/\/$/, '') + ruta);
  for (const [k, v] of Object.entries(params || {})) {
    if (v === null || v === undefined || v === '') continue;
    if (Array.isArray(v)) v.forEach((x) => u.searchParams.append(k, x));
    else u.searchParams.set(k, v);
  }
  return u.toString();
}

function esperar(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * GET que desenvuelve {datos, meta} y SANEA antes de devolver.
 *
 * opciones.signal      AbortSignal de la vista (para cancelar al re-teclear).
 * opciones.alDespertar callback que se llama si la respuesta tarda > 3s,
 *                      para que la vista avise "el servicio esta despertando"
 *                      en vez de dejar un spinner mudo.
 */
export async function pedir(ruta, params, opciones = {}) {
  const destino = url(ruta, params);
  let ultimo = null;

  for (let intento = 0; intento < REINTENTOS; intento++) {
    const ctrl = new AbortController();
    const limite = primeraLlamada ? TIMEOUT_PRIMERA : TIMEOUT_NORMAL;
    const corte = setTimeout(() => ctrl.abort(), limite);
    const aviso = opciones.alDespertar
      ? setTimeout(opciones.alDespertar, AVISO_DESPERTANDO)
      : null;
    // El signal de la vista cancela de verdad: si el usuario ya se fue o
    // volvio a teclear, no se reintenta nada.
    if (opciones.signal) {
      opciones.signal.addEventListener('abort', () => ctrl.abort(), { once: true });
    }

    try {
      const r = await fetch(destino, { signal: ctrl.signal });
      primeraLlamada = false;

      let cuerpo;
      try {
        cuerpo = await r.json();
      } catch {
        throw new ApiError(`${ruta}: la respuesta no es JSON (HTTP ${r.status})`);
      }

      if (cuerpo && cuerpo.error) {
        const { codigo, mensaje } = cuerpo.error;
        if (codigo === 'datos_no_disponibles') throw new SinDatos(mensaje, codigo);
        throw new ApiError(mensaje || `${ruta}: error del API`, codigo);
      }
      if (r.status >= 500) {
        ultimo = new ApiError(`${ruta}: HTTP ${r.status}`);
      } else if (!r.ok) {
        throw new ApiError(`${ruta}: HTTP ${r.status}`, String(r.status));
      } else {
        return { datos: sanear(cuerpo.datos), meta: cuerpo.meta || {} };
      }
    } catch (e) {
      // Cancelacion deliberada de la vista: propagar tal cual, no reintentar.
      if (opciones.signal && opciones.signal.aborted) throw e;
      if (e instanceof SinDatos) throw e;
      if (e instanceof ApiError && e.codigo && !/^5/.test(e.codigo)) throw e;
      ultimo = e instanceof ApiError ? e : new ApiError(`${ruta}: ${e.message}`);
    } finally {
      clearTimeout(corte);
      if (aviso) clearTimeout(aviso);
    }

    if (intento < REINTENTOS - 1) await esperar(2000 * 2 ** intento);
  }
  throw ultimo || new ApiError(`${ruta}: no se pudo consultar el API`);
}

/** Como pedir(), pero cachea en sessionStorage. Solo para datos estables y
 *  pequenos (meta, departamentos, banderas). NUNCA para datos de contratos:
 *  se quedarian viejos sin que el usuario se entere. */
export async function pedirCacheado(ruta, params, opciones = {}) {
  const clave = 'plomada:' + url(ruta, params);
  if (memoria.has(clave)) return memoria.get(clave);
  try {
    const guardado = sessionStorage.getItem(clave);
    if (guardado) {
      const v = JSON.parse(guardado);
      memoria.set(clave, v);
      return v;
    }
  } catch { /* sessionStorage lleno o bloqueado: seguir sin cache */ }

  const v = await pedir(ruta, params, opciones);
  memoria.set(clave, v);
  try {
    sessionStorage.setItem(clave, JSON.stringify(v));
  } catch { /* idem */ }
  return v;
}

/** Pagina un listado hasta traerlo entero, respetando el tope de 200 del API
 *  y guiandose por meta.paginacion.total. */
export async function listar(ruta, params, opciones = {}) {
  const limite = Math.min(opciones.limite || 200, 200);
  const filas = [];
  let desplazamiento = 0;
  let total = null;

  while (total === null || desplazamiento < total) {
    const { datos, meta } = await pedir(
      ruta, { ...params, limite, desplazamiento }, opciones);
    filas.push(...datos);
    const pag = meta.paginacion || {};
    total = pag.total ?? filas.length;
    const devueltas = pag.devueltas ?? datos.length;
    if (!devueltas) break;
    desplazamiento += devueltas;
    if (opciones.alAvanzar) opciones.alAvanzar(filas.length, total);
  }
  return filas;
}

/** listar() + cache de sesion. Para listados completos, estables y chicos
 *  (los 721 municipios, los 34 departamentos). Existe porque pedirCacheado()
 *  con `limite` cachea UNA pagina y el resto se pierde en silencio: asi es
 *  como el ranking llego a decir "puesto 1 de 200" en vez de "de 721". */
export async function listarCacheado(ruta, params, opciones = {}) {
  const clave = 'plomada:todo:' + url(ruta, params);
  if (memoria.has(clave)) return memoria.get(clave);
  try {
    const guardado = sessionStorage.getItem(clave);
    if (guardado) {
      const v = JSON.parse(guardado);
      memoria.set(clave, v);
      return v;
    }
  } catch { /* sessionStorage lleno o bloqueado: seguir sin cache */ }

  const filas = await listar(ruta, params, opciones);
  memoria.set(clave, filas);
  try {
    sessionStorage.setItem(clave, JSON.stringify(filas));
  } catch { /* idem */ }
  return filas;
}

/** Corre `tareas` con concurrencia limitada. Medido: el API aguanta 16
 *  simultaneas a 84 req/s sin errores; 8 deja margen para el resto del sitio. */
export async function enParalelo(items, fn, concurrencia = 8) {
  const salida = new Array(items.length);
  let siguiente = 0;
  const obreros = Array.from({ length: Math.min(concurrencia, items.length) }, async () => {
    while (siguiente < items.length) {
      const i = siguiente++;
      try {
        salida[i] = await fn(items[i], i);
      } catch {
        salida[i] = null;   // una falla suelta no tumba el lote entero
      }
    }
  });
  await Promise.all(obreros);
  return salida;
}

export const API_BASE = BASE;

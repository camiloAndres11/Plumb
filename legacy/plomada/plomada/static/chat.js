/* Asistente de /asistente/: chat contra el proxy POST /chat del API, que a
 * su vez habla con el servidor MCP (las 7 tools de api/app/mcp/server.py).
 *
 * ---------------------------------------------------------------- BYOK
 * La API key es DEL LECTOR. Plomada no tiene una llave compartida, no la
 * quiere y no la guarda: viaja en el header X-Anthropic-Api-Key de cada
 * peticion y vive en localStorage de este navegador. Reglas que no se
 * negocian y que este modulo tiene que seguir cumpliendo si alguien lo toca:
 *
 *   - NUNCA se escribe la key en consola, ni dentro del texto de un error,
 *     ni en la URL, ni en un atributo del DOM. Solo se lee para armar el
 *     header. Por eso aqui no hay un solo console.log de la peticion.
 *   - Si el API la rechaza (422 por header ausente, o el evento SSE de key
 *     invalida), se BORRA la guardada y se vuelve a pedir. Nada de
 *     reintentar en silencio con una llave que no sirve.
 *   - Hay un boton para olvidarla. Es la contraparte honesta de pedirla.
 *
 * ------------------------------------------------------------- por que asi
 * JS plano, como el resto de static/: esto es un formulario mas un stream,
 * no necesita reactividad profunda, y mantenerlo fuera de frontend/src/
 * evita recompilar el bundle y el MANIFIESTO en cada ajuste.
 *
 * El texto del modelo se inserta SIEMPRE con textContent, jamas con
 * innerHTML: es la unica defensa real contra que una respuesta traiga markup
 * (restriccion del proyecto; los saltos de linea los pone white-space:
 * pre-wrap en el CSS).
 */
import { API_BASE } from './api.js';

const CLAVE_KEY = 'plomada:anthropic-key';
// Mismo umbral que api.js (AVISO_DESPERTANDO): a los 3s sin el primer delta,
// avisar en vez de dejar un spinner mudo. Render duerme el servicio.
const AVISO_DESPERTANDO = 3000;
// Tope de turnos que se mandan de vuelta. El historial vive en el navegador y
// se manda entero en cada pregunta, asi que sin tope crece sin limite y cada
// peticion cuesta mas. 12 turnos son 6 idas y vueltas.
const TOPE_TURNOS = 12;

const $ = (id) => document.getElementById(id);

const vista = {
  chat: $('chat'),
  hilo: $('chat-hilo'),
  intro: null,
  sugerencias: $('sugerencias'),
  forma: $('chat-forma'),
  entrada: $('chat-entrada'),
  enviar: $('chat-enviar'),
  detener: $('chat-detener'),
  estado: $('chat-estado'),
  pie: $('chat-key-quien'),
  olvidar: $('chat-olvidar'),
  panelKey: $('chat-key'),
  formaKey: $('chat-forma-key'),
  campoKey: $('chat-key-campo'),
  errorKey: $('chat-key-error'),
};

let historial = [];
let enVuelo = null;   // AbortController de la peticion viva, si hay una

/* ----------------------------------------------------------------- la key */

function leerKey() {
  try {
    return localStorage.getItem(CLAVE_KEY) || null;
  } catch {
    return null;   // modo privado: se pide en cada visita, no rompe
  }
}

function guardarKey(k) {
  try { localStorage.setItem(CLAVE_KEY, k); } catch { /* se pierde al cerrar */ }
}

function olvidarKey() {
  try { localStorage.removeItem(CLAVE_KEY); } catch { /* nada que borrar */ }
}

/** Muestra el chat o el formulario de la key, segun haya llave o no. */
function montar() {
  const hay = !!leerKey();
  vista.chat.hidden = !hay;
  vista.panelKey.hidden = hay;
  vista.olvidar.hidden = !hay;
  vista.pie.textContent = hay
    ? 'Usando su API key de Anthropic, guardada solo en este navegador.'
    : '';
  if (hay) vista.entrada.focus();
  else vista.campoKey.focus();
}

/** La key no sirvio: se borra y se vuelve a pedir, diciendo por que.
 *
 * `pregunta` se devuelve al cuadro de texto en vez de quedar como una
 * burbuja que nunca va a tener respuesta: cuando el lector arregle la llave,
 * su pregunta lo esta esperando y solo tiene que volver a enviarla. */
function pedirKeyDeNuevo(motivo, pregunta) {
  olvidarKey();
  montar();
  vista.errorKey.textContent = motivo;
  vista.campoKey.value = '';
  if (pregunta) vista.entrada.value = pregunta;
  // sin burbujas en el hilo, las sugerencias vuelven: la vista no puede
  // quedar como un cuadro de texto vacio
  if (vista.sugerencias && !vista.hilo.querySelector('.burbuja')) {
    vista.sugerencias.hidden = false;
  }
  vista.campoKey.focus();
}

/* -------------------------------------------------------------- el hilo */

function burbuja(quien, texto) {
  const div = document.createElement('div');
  div.className = 'burbuja burbuja-' + quien;
  const rol = document.createElement('p');
  rol.className = 'burbuja-quien';
  rol.textContent = quien === 'usuario' ? 'Usted' : 'Asistente';
  const cuerpo = document.createElement('p');
  cuerpo.className = 'burbuja-texto';
  // textContent, no innerHTML: vale para lo que escribe el lector y, sobre
  // todo, para lo que devuelve el modelo.
  cuerpo.textContent = texto;
  div.append(rol, cuerpo);
  vista.hilo.appendChild(div);
  vista.hilo.scrollTop = vista.hilo.scrollHeight;
  return cuerpo;
}

function estado(txt) {
  vista.estado.textContent = txt;
}

/* -------------------------------------------------------------- el stream */

/**
 * Lee el SSE de /chat y llama onDelta con cada fragmento.
 *
 * EventSource no sirve aqui: no permite headers (la key va en uno) ni POST.
 * Asi que fetch + getReader() a mano, acumulando en un buffer y partiendo
 * por \n\n -- un evento puede llegar partido entre dos chunks, y sin el
 * buffer se pierde justo el fragmento que cruza el corte.
 *
 * Devuelve el texto completo. Lanza si el API rechaza la key.
 */
async function preguntar(mensaje, onDelta, signal) {
  const r = await fetch(API_BASE.replace(/\/$/, '') + '/chat', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'X-Anthropic-Api-Key': leerKey() || '',
    },
    body: JSON.stringify({ mensaje, historial: historial.slice(-TOPE_TURNOS) }),
    signal,
  });

  // 422 = el header no llego o no paso la validacion. El cuerpo trae el
  // detalle, pero al lector se le dice lo util, no el volcado de pydantic.
  if (r.status === 422) {
    throw new KeyInvalida('El API no aceptó la llave. Revísela y vuelva a guardarla.');
  }
  // 429 = el techo por IP del servicio (no la cuota de Anthropic del
  // lector): no es un fallo, es un "espere un momento".
  if (r.status === 429) {
    throw new LimiteAlcanzado('Demasiadas consultas seguidas. Espere un minuto y vuelva a intentarlo.');
  }
  if (!r.ok) {
    throw new Error(`El asistente respondió con un error (HTTP ${r.status}).`);
  }

  const lector = r.body.getReader();
  const dec = new TextDecoder();
  let buffer = '';
  let completo = '';

  for (;;) {
    const { done, value } = await lector.read();
    if (done) break;
    buffer += dec.decode(value, { stream: true });

    let corte;
    while ((corte = buffer.indexOf('\n\n')) !== -1) {
      const bruto = buffer.slice(0, corte);
      buffer = buffer.slice(corte + 2);
      for (const linea of bruto.split('\n')) {
        if (!linea.startsWith('data:')) continue;
        const carga = linea.slice(5).trim();
        if (!carga) continue;
        let ev;
        try {
          ev = JSON.parse(carga);
        } catch {
          continue;   // fragmento que no es JSON: se ignora, no tumba el hilo
        }
        if (ev.error) {
          // Asi manda el proxy la key invalida de Anthropic. Reenvia el texto
          // de Anthropic tal cual, sin tildes, asi que se reemplaza por uno
          // propio: es lo que ve el lector.
          if (/api key/i.test(ev.error)) {
            throw new KeyInvalida(
              'Anthropic rechazó esa API key. Revísela y vuelva a guardarla.');
          }
          throw new Error(ev.error);
        }
        if (ev.done) return completo;
        if (ev.delta) {
          completo += ev.delta;
          onDelta(completo);
        }
      }
    }
  }
  return completo;
}

class KeyInvalida extends Error {}
class LimiteAlcanzado extends Error {}

/* ------------------------------------------------------------- el ciclo */

async function enviar(pregunta) {
  const texto = pregunta.trim();
  if (!texto || enVuelo) return;

  if (vista.sugerencias) vista.sugerencias.hidden = true;

  const burbujaPregunta = burbuja('usuario', texto).closest('.burbuja');
  vista.entrada.value = '';
  const destino = burbuja('asistente', '');
  destino.classList.add('escribiendo');

  const ctrl = new AbortController();
  enVuelo = ctrl;
  vista.enviar.disabled = true;
  vista.detener.hidden = false;
  estado('Consultando los datos…');

  // Si a los 3s no llego el primer delta, decir que el servicio despierta.
  let primero = true;
  const avisoDormido = setTimeout(() => {
    if (primero) estado('El servicio está despertando, puede tardar hasta un minuto…');
  }, AVISO_DESPERTANDO);

  try {
    const completo = await preguntar(texto, (acum) => {
      if (primero) { primero = false; clearTimeout(avisoDormido); estado(''); }
      destino.textContent = acum;
      vista.hilo.scrollTop = vista.hilo.scrollHeight;
    }, ctrl.signal);

    destino.textContent = completo;
    historial.push({ role: 'user', content: texto });
    historial.push({ role: 'assistant', content: completo });
    if (historial.length > TOPE_TURNOS) {
      historial = historial.slice(-TOPE_TURNOS);
      estado('La conversación es larga: el asistente ya no recuerda el principio.');
    } else {
      estado('');
    }
  } catch (e) {
    if (ctrl.signal.aborted) {
      destino.textContent = destino.textContent || 'Cancelado.';
      estado('');
    } else if (e instanceof KeyInvalida) {
      // La key no sirve: se borra y se vuelve a pedir. NUNCA se reintenta.
      destino.closest('.burbuja').remove();
      if (burbujaPregunta) burbujaPregunta.remove();
      pedirKeyDeNuevo(e.message, texto);
    } else if (e instanceof LimiteAlcanzado) {
      // La pregunta vuelve al cuadro, como con la key: cuando pase el
      // minuto, solo hay que volver a enviarla.
      destino.closest('.burbuja').remove();
      if (burbujaPregunta) burbujaPregunta.remove();
      vista.entrada.value = texto;
      if (vista.sugerencias && !vista.hilo.querySelector('.burbuja')) {
        vista.sugerencias.hidden = false;
      }
      estado(e.message);
    } else {
      destino.textContent = 'El asistente no está disponible ahora. ' +
        'Puede consultar los mismos datos en el buscador o en el API.';
      estado('');
    }
  } finally {
    clearTimeout(avisoDormido);
    destino.classList.remove('escribiendo');
    enVuelo = null;
    vista.enviar.disabled = false;
    vista.detener.hidden = true;
  }
}

/* ------------------------------------------------------------- conexiones */

vista.forma.addEventListener('submit', (e) => {
  e.preventDefault();
  enviar(vista.entrada.value);
});

// Enter envia, Mayus+Enter hace salto de linea. En un textarea hay que
// interceptarlo: el comportamiento nativo es siempre el salto.
vista.entrada.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    enviar(vista.entrada.value);
  }
});

vista.detener.addEventListener('click', () => {
  if (enVuelo) enVuelo.abort();
});

// Salir de la pagina con una peticion viva: cancelarla en vez de dejarla
// colgada consumiendo tokens de la cuenta del lector.
addEventListener('pagehide', () => { if (enVuelo) enVuelo.abort(); });

if (vista.sugerencias) {
  vista.sugerencias.addEventListener('click', (e) => {
    const b = e.target.closest('.sugerencia');
    if (b) enviar(b.dataset.pregunta);
  });
}

vista.formaKey.addEventListener('submit', (e) => {
  e.preventDefault();
  const k = vista.campoKey.value.trim();
  if (!k) {
    vista.errorKey.textContent = 'Escriba su API key para continuar.';
    return;
  }
  vista.errorKey.textContent = '';
  guardarKey(k);
  vista.campoKey.value = '';   // no dejarla en el DOM mas de lo necesario
  montar();
});

vista.olvidar.addEventListener('click', () => {
  olvidarKey();
  historial = [];
  montar();
});

montar();

/* Conmutador de tono. El tema YA esta aplicado cuando esto corre: lo fijo el
 * script inline del <head> (build.py, TEMA_INLINE) antes del primer pintado.
 * Este modulo solo (a) sincroniza el boton con el estado real y (b) conmuta.
 *
 * Emite un evento 'plomada:tema' en document cuando el tono cambia, con
 * detail = { tema: 'claro' | 'oscuro' }. Los graficos y el mapa se
 * suscriben a eso para re-leer los tokens --viz-* (F2). El CSS no necesita
 * el evento: los tokens cambian solos, porque design/plomada/tema.css cuelga
 * el delta oscuro de :root[data-tema="oscuro"].
 */
const CLAVE = 'plomada:tema';

/** El tono que se esta pintando ahora mismo, leido del DOM (no de
 *  localStorage): el DOM es la verdad, localStorage solo la preferencia. */
export function temaActual() {
  return document.documentElement.getAttribute('data-tema') === 'oscuro' ? 'oscuro' : 'claro';
}

/** La eleccion guardada, o null si el lector nunca pulso el boton. Mientras
 *  devuelva null, el sitio sigue al sistema en vivo. */
function guardado() {
  try {
    const t = localStorage.getItem(CLAVE);
    return t === 'claro' || t === 'oscuro' ? t : null;
  } catch {
    return null;   // modo privado: se lee como "nunca eligio"
  }
}

function sincronizarBoton() {
  const boton = document.getElementById('conmutar-tema');
  if (!boton) return;
  const oscuro = temaActual() === 'oscuro';
  boton.setAttribute('aria-pressed', String(oscuro));
  // El texto nombra la ACCION, no el estado: en claro ofrece pasar a oscuro.
  const texto = boton.querySelector('.nav-tema-texto');
  if (texto) texto.textContent = oscuro ? 'Tono claro' : 'Tono oscuro';
}

/** Pinta un tono. `recordar` en false lo aplica sin guardarlo, que es lo que
 *  necesita el seguimiento en vivo del sistema: cambiar de tono sin que eso
 *  cuente como una eleccion del lector. */
export function aplicar(tema, recordar = true) {
  document.documentElement.setAttribute('data-tema', tema);
  if (recordar) {
    try { localStorage.setItem(CLAVE, tema); } catch { /* modo privado: se pierde al cerrar, no rompe */ }
  }
  sincronizarBoton();
  document.dispatchEvent(new CustomEvent('plomada:tema', { detail: { tema } }));
}

sincronizarBoton();

const boton = document.getElementById('conmutar-tema');
if (boton) {
  boton.addEventListener('click', () => {
    aplicar(temaActual() === 'oscuro' ? 'claro' : 'oscuro');
  });
}

// Quien nunca eligio sigue al sistema EN VIVO: si cambia el tono del sistema
// con la pestana abierta, la pagina acompana. En cuanto el lector pulsa el
// boton una vez, guardado() deja de ser null y esta suscripcion no manda mas.
const consulta = window.matchMedia('(prefers-color-scheme: dark)');
consulta.addEventListener('change', (e) => {
  if (guardado() === null) aplicar(e.matches ? 'oscuro' : 'claro', false);
});

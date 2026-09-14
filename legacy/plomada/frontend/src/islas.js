/* Punto de entrada unico de las islas de Vue (docs/PLAN_VUE.md §4.3).
 *
 * build.py no aprende nada de Vue: solo emite un <div data-isla="..."> con
 * un fallback pre-renderizado adentro, y este script monta el componente
 * que corresponda por encima de ese fallback. Los props entran por
 * data-* -- el servidor decide, el cliente pinta.
 *
 * Degradar avisando, nunca romper: si una isla no monta (JSON ausente, red
 * caida, lo que sea), el fallback pre-renderizado sigue visible porque
 * nunca se toco. Mismo patron que tablero.js y data.py.
 */
import { createApp } from 'vue'

const ISLAS = {
  'cifra-lider': () => import('./componentes/CifraLider.vue'),
}

for (const el of document.querySelectorAll('[data-isla]')) {
  const cargar = ISLAS[el.dataset.isla]
  if (!cargar) continue
  cargar()
    .then(({ default: Componente }) => {
      const { isla, ...props } = el.dataset
      createApp(Componente, props).mount(el)
    })
    .catch((e) => console.error(`isla ${el.dataset.isla}:`, e))
}

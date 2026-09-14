<script setup>
/* Reemplaza plomada/static/portada.js (docs/PLAN_VUE.md §6.5, la isla
 * piloto de T1). No inventa una cifra nueva: reutiliza el MISMO dato que ya
 * alimenta el tablero (titulares.json + meta.json, que build.py copia de
 * out_web/). Si el dato no esta, degrada a un enlace al tablero -- nunca un
 * numero plausible (restriccion 7 del plan).
 */
import { ref, onMounted } from 'vue'
import { plata, pct } from '~formato'

const CONCEPTO = 'Adjudicado sin competencia real'

const estado = ref('cargando') // cargando | error | listo
const valor = ref('')
const nota = ref('')

onMounted(async () => {
  try {
    const [titulares, meta] = await Promise.all(
      ['titulares', 'meta'].map((n) =>
        fetch(`/datos/${n}.json`).then((r) => {
          if (!r.ok) throw new Error(`${n}.json: HTTP ${r.status}`)
          return r.json()
        })
      )
    )
    const t = titulares.find((x) => x.concepto === CONCEPTO)
    if (!t) throw new Error(`titulares.json no trae "${CONCEPTO}"`)
    valor.value = plata(t.valor)
    const share = meta && meta.valor_total ? pct(t.valor / meta.valor_total) : null
    nota.value =
      (share ? `${share} del universo de obra pública analizado. ` : '') +
      'Indicio, no acusación.'
    estado.value = 'listo'
  } catch (e) {
    console.error('cifra-lider:', e)
    estado.value = 'error'
  }
})
</script>

<template>
  <section v-if="estado === 'listo'" class="cifra-lider">
    <p class="tipo">Obra pública adjudicada sin competencia real (un solo oferente)</p>
    <p class="valor">{{ valor }}</p>
    <p class="nota">{{ nota }}</p>
  </section>
  <p v-else-if="estado === 'error'" class="nota">
    Ver el desglose completo de indicios en el <a href="/tablero/">tablero</a>.
  </p>
</template>

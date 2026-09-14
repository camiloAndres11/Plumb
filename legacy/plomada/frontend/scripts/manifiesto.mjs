// Genera plomada/static/vendor/islas/MANIFIESTO.txt despues de `vite build`.
//
// El hash tiene que coincidir BYTE A BYTE con el que calcula
// plomada/test_privacy.py::_hash_fuentes_frontend() -- es la puerta T0.4 de
// docs/PLAN_VUE.md: "el bundle corresponde a los fuentes". Si alguien edita
// un .vue y no recompila, esa puerta lo atrapa comparando este hash contra
// el que recalcula en el momento de correr la prueba.
//
// Mismo algoritmo en los dos lados: por cada archivo .vue/.js bajo
// frontend/src/, en orden alfabetico de su ruta relativa a frontend/,
// concatenar (ruta relativa como texto) + (bytes crudos del archivo) al
// hash sha256.
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const FRONTEND = fileURLToPath(new URL('..', import.meta.url))
const SRC = join(FRONTEND, 'src')
const SALIDA = join(FRONTEND, '..', 'plomada', 'static', 'vendor', 'islas', 'MANIFIESTO.txt')

function caminar(dir) {
  let out = []
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry)
    if (statSync(p).isDirectory()) out = out.concat(caminar(p))
    else if (/\.(vue|js)$/.test(entry)) out.push(p)
  }
  return out
}

const archivos = caminar(SRC)
  .map((p) => relative(FRONTEND, p).split(sep).join('/'))
  .sort()

const hash = createHash('sha256')
for (const rel of archivos) {
  hash.update(Buffer.from(rel, 'utf8'))
  hash.update(readFileSync(join(FRONTEND, rel)))
}
const digest = hash.digest('hex')

writeFileSync(
  SALIDA,
  `# GENERADO por 'npm run build' (frontend/scripts/manifiesto.mjs) — NO EDITAR A MANO.\n` +
    `# Verificado por plomada/test_privacy.py::test_bundle_corresponde_a_fuentes.\n` +
    `generado: ${new Date().toISOString()}\n` +
    `archivos-fuente: ${archivos.length}\n` +
    `hash-fuentes: ${digest}\n`
)

console.log(`MANIFIESTO.txt escrito (${archivos.length} fuentes, hash ${digest.slice(0, 12)}…)`)

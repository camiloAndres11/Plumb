// Corredor sobre el fixture compartido tests/formato_casos.json.
//
// Verifica que plomada/static/formato.js produce lo mismo que quedo
// registrado en el fixture, generado leyendo plomada/data.py (la
// referencia). El otro lado del mismo fixture es tests/test_formato.py.
//
// Corre con: node tests/test_formato.mjs

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { plata, pct, entero, titulo, slug, sinTildes } from '../plomada/static/formato.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const casos = JSON.parse(readFileSync(path.join(__dirname, 'formato_casos.json'), 'utf-8'));

// sin_tildes en data.py se llama sinTildes en formato.js: unico nombre que
// cambia entre los dos lados del fixture (los demas son iguales en Python
// y en JS).
const FNS = { plata, pct, entero, titulo, slug, sin_tildes: sinTildes };

let fallos = 0;
casos.forEach((c, i) => {
  const fn = FNS[c.fn];
  let obtenido;
  try {
    obtenido = fn(...c.args);
  } catch (e) {
    obtenido = `<excepcion: ${e.message}>`;
  }
  if (obtenido !== c.esperado) {
    fallos++;
    console.log(`  FALLO caso ${i}: ${c.fn}(${JSON.stringify(c.args)}) = ` +
      `${JSON.stringify(obtenido)}, esperaba ${JSON.stringify(c.esperado)}`);
  }
});

if (fallos) {
  console.log(`\n${fallos} de ${casos.length} casos fallaron`);
  process.exit(1);
}
console.log(`${casos.length} casos OK (node / formato.js)`);

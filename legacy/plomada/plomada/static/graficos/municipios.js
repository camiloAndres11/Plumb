/* Municipios -- dumbbell tasa cruda -> tasa ajustada (Tanda B, B3/B5).
 *
 * Dos series, identidad por FORMA, no por color categorico (dataviz.css):
 * tasa cruda = .viz-hueco (aro de 2px, centro del fondo), tasa ajustada =
 * .viz-hallazgo (el acento: es el hallazgo del metodo, hacia donde jala el
 * encogimiento bayesiano). Conector de 2px en --viz-eje. Leyenda
 * OBLIGATORIA (2+ series). La forma ES el argumento metodologico: se ve el
 * jalon hacia la media donde hay poca evidencia.
 */
import { el, svgRoot, hover, tabla, niceMax, leyenda, tonosViz } from "./comun.js";
import { plata, pct, entero, titulo } from "../formato.js";

export function dibujar(contenedorSvg, contenedorTabla, contenedorLeyenda, datos) {
  const T = tonosViz();
  const filas = datos.slice(0, 22);
  if (!filas.length) {
    contenedorSvg.textContent = "Ningún municipio cae dentro de este filtro.";
    contenedorTabla.replaceChildren();
    return;
  }
  leyenda(contenedorLeyenda, [
    ["viz-hueco-m", "Tasa cruda"],
    ["viz-hallazgo-m", "Tasa ajustada"],
  ]);

  const W = 1100, L = 250, R = 90, top = 10, row = 26;
  const H = top + filas.length * row + 34;
  const s = svgRoot(W, H);
  const max = Math.min(1, niceMax(Math.max(...filas.map((d) => Math.max(d.tasa_cruda, d.tasa_ajustada)))));
  const x = (v) => L + (v / max) * (W - L - R);

  for (let i = 0; i <= 5; i++) {
    const v = (max * i) / 5;
    s.appendChild(el("line", { x1: x(v), x2: x(v), y1: top, y2: H - 30, class: "viz-rejilla" }));
    s.appendChild(el("text", { x: x(v), y: H - 14, class: "viz-tick", "text-anchor": "middle" },
      Math.round(v * 100) + "%"));
  }
  s.appendChild(el("line", { x1: L, x2: L, y1: top, y2: H - 30, class: "viz-eje" }));

  filas.forEach((d, i) => {
    const y = top + i * row + 8;
    s.appendChild(el("text", { x: L - 12, y: y + 4, class: "viz-etiqueta", "text-anchor": "end" },
      titulo(d.ciudad) + " · " + titulo(d.departamento).slice(0, 16)));
    s.appendChild(el("line", {
      x1: x(d.tasa_ajustada), x2: x(d.tasa_cruda), y1: y, y2: y, class: "viz-eje", "stroke-width": 2,
    }));
    s.appendChild(el("circle", { cx: x(d.tasa_cruda), cy: y, r: 5, class: "viz-hueco viz-nodo" }));
    s.appendChild(el("circle", { cx: x(d.tasa_ajustada), cy: y, r: 5, class: "viz-hallazgo viz-nodo" }));
    s.appendChild(el("text", { x: W - R + 10, y: y + 4, class: "viz-valor" }, pct(d.tasa_ajustada)));
    const hit = el("rect", { x: L, y: y - row / 2, width: W - L, height: row, class: "viz-hit" });
    hover(hit, titulo(d.ciudad) + ", " + titulo(d.departamento), [
      ["Contratos", entero(d.n_contratos)], ["Atipicos", entero(d.n_atipicos)],
      ["Tasa cruda", pct(d.tasa_cruda)], ["Tasa ajustada", pct(d.tasa_ajustada)],
      ["Valor atipico", plata(d.valor_atipico)],
      ["Un solo oferente", entero(d.n_proponente_unico)],
      ["Fraccionamiento", entero(d.n_fraccionamiento)],
    ]);
    s.appendChild(hit);
  });
  contenedorSvg.replaceChildren(s);

  tabla(contenedorTabla, [
    { titulo: "Municipio", valor: (d) => titulo(d.ciudad) },
    { titulo: "Departamento", valor: (d) => titulo(d.departamento) },
    { titulo: "Contratos", num: 1, valor: (d) => entero(d.n_contratos) },
    { titulo: "Atipicos", num: 1, valor: (d) => entero(d.n_atipicos) },
    { titulo: "Tasa cruda", num: 1, valor: (d) => pct(d.tasa_cruda) },
    { titulo: "Tasa ajustada", num: 1, valor: (d) => pct(d.tasa_ajustada) },
    { titulo: "Valor atipico", num: 1, valor: (d) => plata(d.valor_atipico) },
  ], filas);
}

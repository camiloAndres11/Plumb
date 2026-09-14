/* Plata por indicio -- barras horizontales (Tanda B, B3/B5).
 *
 * Serie unica: .viz-relleno para todas las barras, SIN caja de leyenda (el
 * titulo de la seccion ya dice que se grafica -- leyenda.css la exige solo
 * con 2+ series). Puntas RECTAS: Modernist es radio 0 en todo, tambien en
 * las puntas de barra, aunque la convencion generica de graficos pida
 * puntas redondeadas de 4px. Un modulo = un grafico = una unidad de datos
 * clara (sera un componente Vue en fase 2): entra `datos` ya resuelto,
 * sale un SVG + su tabla gemela, nada mas.
 */
import { el, svgRoot, hover, tabla, niceMax, tonosViz } from "./comun.js";
import { plata, pct, entero } from "../formato.js";

export function dibujar(contenedorSvg, contenedorTabla, datos, totalUniverso) {
  const T = tonosViz();
  const filas = datos.filter((d) => d.valor > 0).sort((a, b) => b.valor - a.valor);
  if (!filas.length) {
    contenedorSvg.textContent = "Ningún indicio se enciende en este corte.";
    return;
  }
  const W = 1100, L = 330, R = 130, top = 8, row = 30, ALTO_BARRA = 16;
  const H = top + filas.length * row + 34;
  const s = svgRoot(W, H);
  const max = niceMax(Math.max(...filas.map((d) => d.valor)));
  const x = (v) => L + (v / max) * (W - L - R);

  for (let i = 0; i <= 4; i++) {
    const v = (max * i) / 4;
    s.appendChild(el("line", { x1: x(v), x2: x(v), y1: top, y2: H - 30, class: "viz-rejilla" }));
    s.appendChild(el("text", { x: x(v), y: H - 14, class: "viz-tick", "text-anchor": "middle" },
      i === 0 ? "0" : entero(v / 1e9) + " mil M"));
  }
  s.appendChild(el("line", { x1: L, x2: L, y1: top, y2: H - 30, class: "viz-eje" }));

  filas.forEach((d, i) => {
    const y = top + i * row;
    const ancho = Math.max(2, x(d.valor) - L);
    s.appendChild(el("text", { x: L - 12, y: y + ALTO_BARRA / 2 + 1, class: "viz-etiqueta", "text-anchor": "end" },
      d.indicio.length > 46 ? d.indicio.slice(0, 45) + "…" : d.indicio));
    s.appendChild(el("text", { x: L - 12, y: y + ALTO_BARRA / 2 + 13, class: "viz-tick", "text-anchor": "end" }, d.grupo));
    // punta RECTA: <rect>, no un path con arco en la esquina
    s.appendChild(el("rect", { x: L, y, width: ancho, height: ALTO_BARRA, class: "viz-relleno" }));
    s.appendChild(el("text", { x: L + ancho + 8, y: y + ALTO_BARRA / 2 + 4, class: "viz-valor" }, plata(d.valor)));
    const hit = el("rect", { x: L, y: y - 5, width: W - L - R + 120, height: row - 2, class: "viz-hit" });
    hover(hit, d.indicio, [
      ["Grupo", d.grupo], ["Contratos", entero(d.n_contratos)], ["Valor", plata(d.valor)],
      ["Del universo", pct(d.valor / totalUniverso)],
    ]);
    s.appendChild(hit);
  });
  contenedorSvg.replaceChildren(s);

  tabla(contenedorTabla, [
    { titulo: "Indicio", valor: (d) => d.indicio },
    { titulo: "Grupo", valor: (d) => d.grupo },
    { titulo: "Contratos", num: 1, valor: (d) => entero(d.n_contratos) },
    { titulo: "Valor", num: 1, valor: (d) => plata(d.valor) },
    { titulo: "% del universo", num: 1, valor: (d) => pct(d.valor / totalUniverso) },
  ], filas);
}

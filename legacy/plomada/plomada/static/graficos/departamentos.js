/* Departamentos -- dispersion tamano de contrato vs. falta de competencia
 * (Tanda B, B3/B5).
 *
 * Serie unica: .viz-relleno + .viz-nodo (aro del color de la superficie,
 * para que las burbujas que se traslapan no se fundan entre si). Sin
 * leyenda: una sola serie no la necesita. Tamano = n_contratos. Eje X
 * logaritmico porque el gasto va de miles de millones a cientos de
 * billones; nunca dos escalas verticales.
 */
import { el, svgRoot, hover, tabla, niceMax, tonosViz } from "./comun.js";
import { plata, pct, entero, titulo } from "../formato.js";

export function dibujar(contenedorSvg, contenedorTabla, datos) {
  const T = tonosViz();
  const filas = datos.filter((d) => d.total > 0 && d.departamento);
  if (!filas.length) {
    contenedorSvg.textContent = "Ningún departamento cae dentro de este filtro.";
    contenedorTabla.replaceChildren();
    return;
  }
  const W = 1100, H = 440, L = 62, R = 26, TOP = 14, B = 46;
  const s = svgRoot(W, H);
  const lx = (d) => Math.log10(Math.max(d.total, 1e8));
  const xmin = Math.floor(Math.min(...filas.map(lx))), xmax = Math.ceil(Math.max(...filas.map(lx)));
  const X = (v) => L + ((v - xmin) / Math.max(0.001, xmax - xmin)) * (W - L - R);
  const ymax = Math.min(1, niceMax(Math.max(...filas.map((d) => d.sin_competencia / d.total))));
  const Y = (v) => H - B - (v / ymax) * (H - B - TOP);
  const rMax = Math.max(...filas.map((d) => d.n_contratos));
  const radio = (n) => 5 + 13 * Math.sqrt(n / rMax);

  for (let i = 0; i <= 5; i++) {
    const v = (ymax * i) / 5;
    s.appendChild(el("line", { x1: L, x2: W - R, y1: Y(v), y2: Y(v), class: "viz-rejilla" }));
    s.appendChild(el("text", { x: L - 10, y: Y(v) + 4, class: "viz-tick", "text-anchor": "end" },
      Math.round(v * 100) + "%"));
  }
  for (let e = xmin; e <= xmax; e++) {
    s.appendChild(el("text", { x: X(e), y: H - B + 20, class: "viz-tick", "text-anchor": "middle" },
      Math.pow(10, e) >= 1e12 ? entero(Math.pow(10, e) / 1e12) + " bill"
                              : entero(Math.pow(10, e) / 1e9) + " mil mill"));
  }
  s.appendChild(el("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, class: "viz-eje" }));
  s.appendChild(el("text", { x: L, y: H - 8, class: "viz-tick" }, "Valor total contratado (escala logaritmica) →"));
  s.appendChild(el("text", { x: L - 46, y: TOP + 4, class: "viz-tick" }, "% sin competencia"));

  [...filas].sort((a, b) => b.n_contratos - a.n_contratos).forEach((d) => {
    const p = d.sin_competencia / d.total, cx = X(lx(d)), cy = Y(p), r = radio(d.n_contratos);
    s.appendChild(el("circle", { cx, cy, r, class: "viz-relleno viz-nodo" }));
    if (p > ymax * 0.62 || d.total > 4e12) {
      s.appendChild(el("text", { x: cx, y: cy - r - 6, class: "viz-etiqueta", "text-anchor": "middle" },
        titulo(d.departamento).slice(0, 18)));
    }
    const hit = el("circle", { cx, cy, r: Math.max(r + 4, 13), class: "viz-hit" });
    hover(hit, titulo(d.departamento), [
      ["Contratos", entero(d.n_contratos)], ["Valor total", plata(d.total)],
      ["Sin competencia", plata(d.sin_competencia) + " (" + pct(p) + ")"],
      ["En riesgo", plata(d.en_riesgo)],
      ["Regalias", plata(d.regalias)],
      ["Tasa atípicos ajustada", d.tasa_ajustada == null ? "sin dato" : pct(d.tasa_ajustada)],
    ]);
    s.appendChild(hit);
  });
  contenedorSvg.replaceChildren(s);

  tabla(contenedorTabla, [
    { titulo: "Departamento", valor: (d) => titulo(d.departamento) },
    { titulo: "Contratos", num: 1, valor: (d) => entero(d.n_contratos) },
    { titulo: "Valor total", num: 1, valor: (d) => plata(d.total) },
    { titulo: "Sin competencia", num: 1, valor: (d) => plata(d.sin_competencia) },
    { titulo: "% sin competencia", num: 1, valor: (d) => pct(d.sin_competencia / d.total) },
    { titulo: "Regalias", num: 1, valor: (d) => plata(d.regalias) },
  ], [...filas].sort((a, b) => b.sin_competencia - a.sin_competencia));
}

/* Helpers compartidos por los modulos de graficos/ (Tanda B, B3).
 *
 * Un modulo = un grafico = una unidad con entrada de datos clara: en la
 * fase 2 cada uno de indicios.js/municipios.js/departamentos.js/red.js se
 * vuelve un componente Vue, y comun.js se vuelve el equivalente a un
 * composable. Por eso esta separado — nada de logica de un grafico
 * especifico vive aqui, solo lo que los cuatro necesitan por igual: dibujo
 * de SVG a mano (sin libreria), tooltip, tabla gemela, y lectura de los
 * tokens de color de design/plomada/dataviz.css (nunca un hex a pelo: el
 * color sale del CSS via getComputedStyle, igual que en mapa.js).
 */

export const SVGNS = "http://www.w3.org/2000/svg";

/** Los tokens --viz-* de dataviz.css, leidos en vivo. Si alguien cambia un
 * color en el CSS, los graficos lo reflejan sin tocar JS. */
export function tonosViz() {
  const cs = getComputedStyle(document.documentElement);
  const v = (nombre) => cs.getPropertyValue(nombre).trim();
  return {
    marca: v('--viz-marca'),
    marcaHueco: v('--viz-marca-hueco'),
    marcaAro: v('--viz-marca-aro'),
    hallazgo: v('--viz-marca-hallazgo'),
    aroGrosor: v('--viz-aro-grosor') || '2',
    superficie: v('--viz-superficie'),
    separador: v('--viz-separador'),
    rejilla: v('--viz-rejilla'),
    eje: v('--viz-eje'),
    tinta: v('--viz-tinta'),
    tintaTenue: v('--viz-tinta-tenue'),
    seq: [1, 2, 3, 4, 5].map((i) => v(`--viz-seq-${i}`)),
    sinDato: v('--viz-sin-dato'),
  };
}

export function el(tag, attrs = {}, texto) {
  const n = document.createElementNS(SVGNS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (texto != null) n.textContent = texto;
  return n;
}

export function svgRoot(w, h) {
  const s = el("svg", { viewBox: `0 0 ${w} ${h}`, role: "img" });
  s.style.maxWidth = w + "px";
  return s;
}

/* Tooltip: realza, nunca la unica via al valor -- cada grafico tiene su
 * gemelo en tabla y etiquetas directas selectivas (dataviz.css: ".viz-tip"). */
let tipEl = null;
function tip() {
  if (tipEl) return tipEl;
  tipEl = document.createElement("div");
  tipEl.className = "viz-tip";
  tipEl.style.opacity = 0;
  document.body.appendChild(tipEl);
  return tipEl;
}

export function hover(nodo, titulo, filas) {
  const t = tip();
  const pintar = () => {
    t.replaceChildren();
    const h = document.createElement("div");
    h.style.fontWeight = "700";
    h.style.marginBottom = "4px";
    h.textContent = titulo;
    t.appendChild(h);
    filas.forEach(([k, v]) => {
      const fila = document.createElement("div");
      fila.style.display = "flex";
      fila.style.justifyContent = "space-between";
      fila.style.gap = "12px";
      const kk = document.createElement("span");
      kk.textContent = k;
      const vv = document.createElement("b");
      vv.textContent = v;
      fila.append(kk, vv);
      t.appendChild(fila);
    });
  };
  nodo.addEventListener("mousemove", (e) => {
    pintar();
    t.style.opacity = 1;
    const r = t.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY - 10;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = innerHeight - r.height - 8;
    t.style.left = Math.max(8, x) + "px";
    t.style.top = Math.max(8, y) + "px";
  });
  nodo.addEventListener("mouseleave", () => { t.style.opacity = 0; });
  nodo.setAttribute("tabindex", "0");
  nodo.addEventListener("focus", () => {
    pintar();
    t.style.opacity = 1;
    const b = nodo.getBoundingClientRect();
    t.style.left = (b.right + 10) + "px";
    t.style.top = b.top + "px";
  });
  nodo.addEventListener("blur", () => { t.style.opacity = 0; });
}

/** Esconde el tooltip. Lo necesita el re-dibujo por cambio de tono (F2): el
 * nodo que lo abrio se reemplaza, asi que su mouseleave nunca llega y el
 * tooltip quedaria colgado sobre un grafico que ya no existe. */
export function ocultarTip() {
  if (tipEl) tipEl.style.opacity = 0;
}

/** Tabla gemela: cada grafico conserva la suya (regla transversal de B5),
 * armada con DOM/textContent, nunca con un string de HTML. */
export function tabla(host, columnas, datos) {
  const t = document.createElement("table");
  t.className = "table";
  const trCab = document.createElement("tr");
  columnas.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c.titulo;
    if (c.num) th.className = "num";
    trCab.appendChild(th);
  });
  const thead = document.createElement("thead");
  thead.appendChild(trCab);
  t.appendChild(thead);
  const tbody = document.createElement("tbody");
  datos.forEach((d) => {
    const tr = document.createElement("tr");
    columnas.forEach((c) => {
      const td = document.createElement("td");
      td.textContent = c.valor(d);
      if (c.num) td.className = "num";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  t.appendChild(tbody);
  host.replaceChildren(t);
}

/** Redondea el tope del eje a un numero limpio. */
export function niceMax(v) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  return Math.ceil(v / p) * p;
}

/** Leyenda (dataviz.css: .viz-leyenda). Obligatoria con 2+ series (B5). */
export function leyenda(host, items) {
  host.replaceChildren();
  host.className = "viz-leyenda";
  items.forEach(([clase, texto]) => {
    const span = document.createElement("span");
    const i = document.createElement("i");
    i.className = clase;
    const t = document.createElement("span");
    t.textContent = texto;
    span.append(i, t);
    host.appendChild(span);
  });
}

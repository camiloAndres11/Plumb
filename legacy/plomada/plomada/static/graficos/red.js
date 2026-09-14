/* Red de proveedores -- grafo de fuerzas (Tanda B, B3/B5).
 *
 * obra = .viz-relleno, interventoria = .viz-hueco, y AMBOS a la vez =
 * .viz-hallazgo (el acento): ese es el hallazgo del proyecto -- quien
 * vigila tambien construye. Leyenda OBLIGATORIA (3 series) + etiqueta
 * directa en los nodos de mayor valor.
 *
 * Los nodos/aristas ya vienen saneados por pipeline/export_web.py
 * (sanear_red(), Tanda A): 'id' en vez de 'doc', 'a'/'b' en vez de
 * 'doc_a'/'doc_b'. Este modulo nunca ve un documento crudo.
 *
 * Layout determinista (arranque en circulo, sin Math.random): el mismo
 * grupo se dibuja igual en cada carga.
 */
import { el, svgRoot, hover, tabla, leyenda, tonosViz } from "./comun.js";
import { plata, entero, titulo } from "../formato.js";

export function dibujar(contenedorSvg, contenedorTabla, contenedorLeyenda, contenedorNota, cluster) {
  const T = tonosViz();
  const nodos = cluster.nodos, N = nodos.length;
  if (!N) {
    contenedorSvg.textContent = "Este grupo no teje ninguna red: no hay proveedores que enlazar.";
    return;
  }
  leyenda(contenedorLeyenda, [
    ["viz-relleno-m", "Solo construye"],
    ["viz-hueco-m", "Solo interventoria"],
    ["viz-hallazgo-m", "Construye y vigila"],
  ]);

  const W = 1100, H = Math.min(760, Math.max(420, 300 + N * 9));
  const s = svgRoot(W, H);
  const idx = new Map(nodos.map((n, i) => [n.id, i]));

  const P = nodos.map((n, i) => {
    const a = (2 * Math.PI * i) / N;
    const rad0 = Math.min(W, H) * 0.34;
    return { x: W / 2 + Math.cos(a) * rad0, y: H / 2 + Math.sin(a) * rad0, vx: 0, vy: 0 };
  });
  const E = cluster.aristas
    .map((a) => ({ i: idx.get(a.a), j: idx.get(a.b), w: a.peso, t: a.tipos }))
    .filter((e) => e.i != null && e.j != null);

  for (let it = 0; it < 320; it++) {
    const k = 1 - it / 320;
    for (let a = 0; a < N; a++) for (let b = a + 1; b < N; b++) {
      const dx = P[b].x - P[a].x, dy = P[b].y - P[a].y;
      const d2 = dx * dx + dy * dy || 0.01, d = Math.sqrt(d2);
      const f = 5200 / d2;
      P[a].vx -= (f * dx) / d; P[a].vy -= (f * dy) / d;
      P[b].vx += (f * dx) / d; P[b].vy += (f * dy) / d;
    }
    E.forEach((e) => {
      const dx = P[e.j].x - P[e.i].x, dy = P[e.j].y - P[e.i].y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01, f = (d - 108) * 0.055;
      P[e.i].vx += (f * dx) / d; P[e.i].vy += (f * dy) / d;
      P[e.j].vx -= (f * dx) / d; P[e.j].vy -= (f * dy) / d;
    });
    P.forEach((p) => {
      p.vx += (W / 2 - p.x) * 0.012; p.vy += (H / 2 - p.y) * 0.012;
      p.x += p.vx * k * 0.55; p.y += p.vy * k * 0.55;
      p.vx *= 0.62; p.vy *= 0.62;
      p.x = Math.max(70, Math.min(W - 70, p.x)); p.y = Math.max(28, Math.min(H - 28, p.y));
    });
  }

  E.forEach((e) => s.appendChild(el("line", {
    x1: P[e.i].x, y1: P[e.i].y, x2: P[e.j].x, y2: P[e.j].y,
    class: "viz-eje", "stroke-width": Math.min(3, 1 + e.w / 4),
  })));

  const vMax = Math.max(...nodos.map((n) => n.valor), 1);
  // Etiquetar selectivamente, nunca los N nodos: en un grupo de 50 las
  // etiquetas se pisan. Se rotulan los 12 de mayor valor y todos los que
  // construyen Y vigilan -- esos son la historia. El resto vive en el
  // tooltip y en la tabla (el gemelo obligatorio de cada grafico).
  const topIds = new Set([...nodos].sort((a, b) => b.valor - a.valor).slice(0, 12).map((n) => n.id));
  nodos.forEach((n, i) => {
    const ambos = n.n_obra > 0 && n.n_interventoria > 0;
    const clase = ambos ? "viz-hallazgo" : (n.n_obra > 0 ? "viz-relleno" : "viz-hueco");
    const r = 7 + 13 * Math.sqrt(n.valor / vMax);
    s.appendChild(el("circle", { cx: P[i].x, cy: P[i].y, r, class: clase + " viz-nodo" }));
    if (topIds.has(n.id) || ambos) {
      const nm = titulo(n.nombre || "").replace(/^Consorcio /i, "Cons. ");
      s.appendChild(el("text", { x: P[i].x, y: P[i].y + r + 12, class: "viz-etiqueta", "text-anchor": "middle" },
        nm.length > 24 ? nm.slice(0, 23) + "…" : nm));
    }
    const hit = el("circle", { cx: P[i].x, cy: P[i].y, r: Math.max(r + 5, 14), class: "viz-hit" });
    hover(hit, titulo(n.nombre || "sin nombre"), [
      ["Contratos", entero(n.n_contratos)], ["Obras", entero(n.n_obra)],
      ["Interventorias", entero(n.n_interventoria)], ["Entidades", entero(n.n_entidades)],
      ["Valor", plata(n.valor)],
    ]);
    s.appendChild(hit);
  });
  contenedorSvg.replaceChildren(s);

  const rotulados = nodos.filter((n) => topIds.has(n.id) || (n.n_obra > 0 && n.n_interventoria > 0)).length;
  contenedorNota.textContent = rotulados < N
    ? `Se rotulan ${rotulados} de ${N} empresas para que las etiquetas no se pisen. Las demas estan en el tooltip y en la tabla.`
    : "";

  tabla(contenedorTabla, [
    { titulo: "Empresa", valor: (n) => titulo(n.nombre || "sin dato") },
    { titulo: "Rol", valor: (n) => (n.n_obra > 0 && n.n_interventoria > 0) ? "Construye y vigila"
                                    : (n.n_obra > 0 ? "Solo construye" : "Solo interventoria") },
    { titulo: "Contratos", num: 1, valor: (n) => entero(n.n_contratos) },
    { titulo: "Obras", num: 1, valor: (n) => entero(n.n_obra) },
    { titulo: "Interventorias", num: 1, valor: (n) => entero(n.n_interventoria) },
    { titulo: "Entidades", num: 1, valor: (n) => entero(n.n_entidades) },
    { titulo: "Valor", num: 1, valor: (n) => plata(n.valor) },
  ], [...nodos].sort((a, b) => b.valor - a.valor));
}

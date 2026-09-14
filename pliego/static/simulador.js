// Simulador de oferta: buscador de la lista y control deslizante del precio.
// Los datos de la malla llegan en <script type="application/json" id="malla">
// (no se ejecuta: el CSP solo permite scripts de /static).
(function () {
  var i = document.getElementById('busca');
  if (i) {
    var f = Array.prototype.slice.call(document.querySelectorAll('.proc'));
    i.addEventListener('input', function () {
      var q = i.value.toLowerCase();
      f.forEach(function (a) { a.hidden = q && a.dataset.busca.indexOf(q) < 0; });
    });
  }
  var s = document.getElementById('slider'), datos = document.getElementById('malla');
  if (!s || !datos) return;
  var D = JSON.parse(datos.textContent), M = D.malla, PB = D.precio_base;
  function f1(x) { return x.toFixed(1).replace('.', ','); }
  function pct(x, d) { return (100 * x).toFixed(d).replace('.', ',') + ' %'; }
  function mill(x) { return '$' + Math.round(x / 1e6).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ' mill.'; }
  s.addEventListener('input', function () {
    var p = M[+s.value];
    document.getElementById('su-pct').textContent = pct(p.ratio, 1);
    document.getElementById('su-cop').textContent = mill(p.ratio * PB);
    document.getElementById('su-esp').textContent = f1(p.esperado);
    document.getElementById('su-pri').textContent = pct(p.prob_primero, 0);
    document.querySelectorAll('.met[data-metodo]').forEach(function (el) {
      el.querySelector('.val').textContent = f1(p.por_metodo[el.dataset.metodo]);
    });
    var c = document.getElementById('cursor');
    if (c) { var x = 46 + (p.ratio - 0.85) / 0.15 * (640 - 46 - 110); c.setAttribute('x1', x); c.setAttribute('x2', x); }
  });
})();

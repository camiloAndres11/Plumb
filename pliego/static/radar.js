// Radar: buscador de entidades y competidores contra /api/buscar. Las rutas
// llevan la raiz de la app (data-raiz del body) para funcionar montada.
(function () {
  var i = document.getElementById('q'), r = document.getElementById('res');
  if (!i) return;
  var raiz = document.body.dataset.raiz || '', t;
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  i.addEventListener('input', function () {
    clearTimeout(t);
    t = setTimeout(function () {
      var q = i.value.trim();
      if (q.length < 3) { r.innerHTML = ''; return; }
      fetch(raiz + '/api/buscar?q=' + encodeURIComponent(q)).then(function (x) { return x.json(); }).then(function (d) {
        r.innerHTML =
          d.entidades.map(function (e) { return '<a href="' + raiz + '/entidad/' + encodeURIComponent(e.nit) + '"><span>' + esc(e.entidad) + '</span><small>entidad · ' + esc(e.departamento || '') + '</small></a>'; }).join('') +
          d.competidores.map(function (c) { return '<a href="' + raiz + '/competidor/' + encodeURIComponent(c.doc) + '"><span>' + esc(c.nombre) + '</span><small>competidor</small></a>'; }).join('') ||
          '<span class="mute" style="font-size:13px">Nada con ese nombre.</span>';
      });
    }, 200);
  });
})();

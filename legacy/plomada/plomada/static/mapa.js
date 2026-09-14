/* Mapa coropletico por tasa ajustada. El estado vive en la URL (?dep=slug)
   para que un enlace al mapa llegue con el departamento ya seleccionado. */
(function () {
  var mapa = L.map('mapa', { scrollWheelZoom: false, attributionControl: true })
    .setView([4.6, -74.1], 5);
  L.control.attribution({ prefix: false }).addAttribution(
    'Fronteras: DANE · Datos: SECOP II');

  // Cortes fijos, no cuantiles: la escala no cambia de significado entre
  // cargas (design/plomada/VALIDACION.md). 5 pasos, no 6 (Tanda B, B5): los
  // colores salen de --viz-seq-1..5 / --viz-sin-dato via getComputedStyle,
  // NUNCA un hex a pelo -- la fuente de verdad del color sigue siendo el CSS.
  var CORTES = [0, .10, .20, .35, .55];
  var TONO = leerTonosViz();

  function leerTonosViz() {
    var cs = getComputedStyle(document.documentElement);
    var v = function (nombre) { return cs.getPropertyValue(nombre).trim(); };
    return {
      seq: [1, 2, 3, 4, 5].map(function (i) { return v('--viz-seq-' + i); }),
      sinDato: v('--viz-sin-dato'),
      separador: v('--viz-separador'),
      tinta: v('--viz-tinta'),
    };
  }

  function color(t) {
    if (t == null) return TONO.sinDato;
    for (var i = CORTES.length - 1; i >= 0; i--) if (t >= CORTES[i]) return TONO.seq[i];
    return TONO.seq[0];
  }
  function pct(x) {
    return x == null ? 'sin dato' : (x * 100).toFixed(1).replace('.', ',') + '%';
  }

  var capa, porSlug = {}, panel = document.getElementById('panel');

  function estilo(f) {
    return { fillColor: color(f.properties.ajustada), weight: 1, color: TONO.separador,
             fillOpacity: f.properties.ajustada == null ? .45 : .85 };
  }

  function pintar(p) {
    if (!p || p.ajustada == null) {
      panel.innerHTML = '<p class="vacio">' + (p ? p.nombre : '') +
        ' no tiene contratos de obra en el corte analizado.</p>';
      return;
    }
    var muns = [].slice.call(document.querySelectorAll('#tabla-mun tbody tr[data-dep="' + p.slug + '"]'));
    var li = muns.slice(0, 8).map(function (tr) {
      var a = tr.querySelector('a');
      return '<li><a href="' + a.getAttribute('href') + '">' + a.textContent + '</a>' +
             '<span class="num">' + tr.children[2].textContent + '</span></li>';
    }).join('');
    panel.innerHTML =
      '<h2>' + p.nombre + '</h2>' +
      '<dl class="dl">' +
      fila('Tasa ajustada', '<b class="grande">' + pct(p.ajustada) + '</b>',
           'Tasa cruda ' + pct(p.cruda) + '. La ajustada es la que ordena.') +
      fila('Contratos marcados', p.a.toLocaleString('es-CO') + ' de ' + p.n.toLocaleString('es-CO')) +
      fila('Valor atipico', p.valor_fmt) +
      '</dl>' +
      (li ? '<h3>Municipios</h3><ul class="lista-herm panel-muns">' + li + '</ul>' : '') +
      '<p><a href="/buscar/?departamento=' + encodeURIComponent(p.raw || '') +
      '">Ver contratos en el buscador &rarr;</a></p>';
  }
  function fila(t, v, s) {
    return '<div class="dato"><dt>' + t + '</dt><dd>' + v +
           (s ? '<small>' + s + '</small>' : '') + '</dd></div>';
  }

  function seleccionar(slug, mover) {
    var lyr = porSlug[slug];
    if (!lyr) return;
    capa.resetStyle();
    lyr.setStyle({ weight: 3, color: TONO.tinta, fillOpacity: .9 });
    lyr.bringToFront();
    pintar(lyr.feature.properties);
    if (mover) mapa.fitBounds(lyr.getBounds(), { maxZoom: 7, padding: [20, 20] });
    var u = new URL(location.href);
    u.searchParams.set('dep', slug);
    history.replaceState(null, '', u);
  }

  // La leyenda se re-dibuja al conmutar el tono: sus muestras llevan el
  // color YA RESUELTO en un atributo style, asi que el CSS no puede
  // recolorearlas solo. Se destruye y se rehace en vez de mutarla, que es
  // lo que hace el resto del mapa con cada repintado.
  var leyenda = null;
  function pintarLeyenda() {
    if (leyenda) mapa.removeControl(leyenda);
    leyenda = L.control({ position: 'bottomright' });
    leyenda.onAdd = function () {
      var d = L.DomUtil.create('div', 'leyenda');
      d.innerHTML = '<b>Tasa ajustada</b><br>' + CORTES.map(function (c, i) {
        var sig = CORTES[i + 1];
        return '<i style="background:' + TONO.seq[i] + '"></i>' +
               (c * 100) + (sig ? '–' + (sig * 100) : '+') + '%';
      }).join('<br>') + '<br><i style="background:' + TONO.sinDato + '"></i>sin medición';
      return d;
    };
    leyenda.addTo(mapa);
  }

  fetch('/datos/departamentos.geojson').then(function (r) { return r.json(); }).then(function (geo) {
    capa = L.geoJSON(geo, {
      style: estilo,
      onEachFeature: function (f, lyr) {
        if (f.properties.slug) porSlug[f.properties.slug] = lyr;
        lyr.bindTooltip(f.properties.nombre + '<br><b>' + pct(f.properties.ajustada) +
          '</b> ajustada · <span style="opacity:.7">' + pct(f.properties.cruda) + ' cruda</span>',
          { sticky: true });
        lyr.on('click', function () { seleccionar(f.properties.slug, false); });
        lyr.on('mouseover', function () { lyr.setStyle({ weight: 2, color: TONO.tinta }); });
        lyr.on('mouseout', function () {
          if (new URL(location.href).searchParams.get('dep') !== f.properties.slug) capa.resetStyle(lyr);
        });
      }
    }).addTo(mapa);
    mapa.fitBounds(capa.getBounds(), { padding: [10, 10] });

    pintarLeyenda();

    var dep = new URL(location.href).searchParams.get('dep');
    if (dep) seleccionar(dep, true);

    // Cambio de banda (F1 -> F2). TONO se cacheo al cargar el modulo con los
    // valores de la banda anterior: hay que REASIGNARLO (no declarar una
    // variable nueva) porque estilo(), color() y seleccionar() lo leen por
    // closure. Con eso, setStyle() recolorea la coropleta entera.
    //
    // La coropleta no tiene tile layer: es GeoJSON sobre el fondo de la
    // pagina, asi que el fondo se oscurece solo con el CSS. La leyenda si
    // hay que rehacerla, porque sus muestras llevan el color resuelto en un
    // atributo style.
    document.addEventListener('plomada:tema', function () {
      TONO = leerTonosViz();
      capa.setStyle(estilo);
      pintarLeyenda();
      // el departamento seleccionado perdio su realce con el setStyle de
      // arriba (resetStyle no distingue): se vuelve a aplicar.
      var actual = new URL(location.href).searchParams.get('dep');
      var lyr = actual && porSlug[actual];
      if (lyr) {
        lyr.setStyle({ weight: 3, color: TONO.tinta, fillOpacity: .9 });
        lyr.bringToFront();
      }
    });
  });

  // filtro de la tabla de municipios
  var filtro = document.getElementById('filtro-mun');
  if (filtro) filtro.addEventListener('input', function () {
    var q = filtro.value.trim().toLowerCase();
    [].forEach.call(document.querySelectorAll('#tabla-mun tbody tr'), function (tr) {
      tr.hidden = q && tr.textContent.toLowerCase().indexOf(q) === -1;
    });
  });
})();

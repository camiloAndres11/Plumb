// Plataforma: lo que antes iba inline (el CSP solo permite scripts de /static).
(function () {
  // Formularios con confirmacion: <form data-confirmar="¿Seguro?">
  document.querySelectorAll('form[data-confirmar]').forEach(function (f) {
    f.addEventListener('submit', function (e) { if (!window.confirm(f.dataset.confirmar)) e.preventDefault(); });
  });
  // Perfil, paso 3: filas de experiencia que se agregan y se quitan.
  var b = document.getElementById('agregar-exp');
  if (b) {
    var tpl = document.getElementById('fila-exp').content, exp = document.getElementById('exp');
    b.addEventListener('click', function () { exp.appendChild(document.importNode(tpl, true)); });
    exp.addEventListener('click', function (e) { if (e.target.dataset.quitar !== undefined) e.target.closest('.exp-fila').remove(); });
  }
})();

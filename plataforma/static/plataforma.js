// Plataforma: lo que antes iba inline (el CSP solo permite scripts de /static).
(function () {
  // Formularios con confirmacion: <form data-confirmar="¿Seguro?">. Y los que
  // ademas llevan data-clave piden la contrasena actual (reautenticacion:
  // cambiar roles, quitar gente, borrar pliegos) y la mandan en `clave`.
  document.querySelectorAll('form[data-confirmar], form[data-clave]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (f.dataset.confirmar !== undefined && !window.confirm(f.dataset.confirmar)) { e.preventDefault(); return; }
      if (f.dataset.clave !== undefined) {
        var c = window.prompt('Confirme con su contraseña actual:');
        if (!c) { e.preventDefault(); return; }
        f.querySelector('input[name=clave]').value = c;
      }
    });
  });
  // Perfil, paso 3: filas de experiencia que se agregan y se quitan.
  var b = document.getElementById('agregar-exp');
  if (b) {
    var tpl = document.getElementById('fila-exp').content, exp = document.getElementById('exp');
    b.addEventListener('click', function () { exp.appendChild(document.importNode(tpl, true)); });
    exp.addEventListener('click', function (e) { if (e.target.dataset.quitar !== undefined) e.target.closest('.exp-fila').remove(); });
  }
})();

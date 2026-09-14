/* Landing de Pliego (/). Tres comportamientos, cero dependencias:
   1. pestañas de "Funciones" (role=tablist, flechas y clic);
   2. revelado al hacer scroll de los bloques [data-reveal];
   3. el parrafo de intro que cruza el centro de la pantalla se enciende.
   Sin IntersectionObserver todo queda visible: degradacion, no un olvido.
   Origen: el script data-dc-script de "Adjudica Landing Fora" en Claude
   Design, traducido de React (DCLogic) a DOM plano. */
(function () {
  'use strict';
  // Antes iba inline en el <head>; el CSP solo permite scripts de /static.
  document.documentElement.classList.add('ad-js');

  // 1. pestañas
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.ad-tab'));
  var panels = tabs.map(function (t) { return document.getElementById(t.getAttribute('aria-controls')); });

  function seleccionar(i) {
    tabs.forEach(function (t, j) {
      var on = i === j;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    panels.forEach(function (p, j) {
      if (!p) return;
      if (j === i) {
        p.hidden = false;
        p.classList.remove('ad-enter');
        void p.offsetWidth;            // reinicia la animacion de entrada
        p.classList.add('ad-enter');
      } else {
        p.hidden = true;
      }
    });
  }

  tabs.forEach(function (t, i) {
    t.addEventListener('click', function () { seleccionar(i); });
    t.addEventListener('keydown', function (e) {
      var d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      var n = (i + d + tabs.length) % tabs.length;
      seleccionar(n);
      tabs[n].focus();
    });
  });

  // 2 y 3. observadores de scroll
  var reveal = document.querySelectorAll('[data-reveal]');
  var intro = document.querySelectorAll('[data-intro]');

  if (!('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(reveal, function (el) { el.setAttribute('data-in', '1'); });
    Array.prototype.forEach.call(intro, function (el) { el.setAttribute('data-active', '1'); });
    return;
  }

  var io = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.setAttribute('data-in', '1');
      io.unobserve(e.target);
    });
  }, { threshold: 0.15 });
  Array.prototype.forEach.call(reveal, function (el) { io.observe(el); });

  var io2 = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (e) {
      if (!e.isIntersecting) return;
      Array.prototype.forEach.call(intro, function (p) { p.removeAttribute('data-active'); });
      e.target.setAttribute('data-active', '1');
    });
  }, { rootMargin: '-42% 0px -42% 0px', threshold: 0 });
  Array.prototype.forEach.call(intro, function (el) { io2.observe(el); });
})();

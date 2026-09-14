/* Mapa satelital de la ficha de contrato. Click-to-load (Tanda B, B6): las
   imagenes las sirve Esri (server.arcgisonline.com), y eso no se puede
   vendorizar -- son imagenes satelitales del mundo. Pero pedirlas SOLAS al
   abrir la ficha le dice a Esri, sin que el lector lo sepa, que coordenadas
   esta mirando. El publico de este sitio son periodistas: eso delata interes
   investigativo a un tercero. Por eso no se pide nada hasta el clic.

   Modulo, no IIFE: la ficha ya no la pre-renderiza build.py sino ficha.js
   con GET /v1/contratos/{id}, asi que el contenedor no existe cuando el
   script se evalua. Un IIFE que buscara #mapa-satelital al cargar no
   encontraba nada y salia en silencio -- por eso la imagen satelital dejo
   de aparecer al migrar la ficha al API. Ahora ficha.js llama a montar()
   cuando ya pinto el contenedor.

   El popup se arma con DOM/createElement/textContent, nunca interpolando
   HTML en un string (test_privacy.py lo verifica: nada de asignar
   contenido HTML crudo ni de un template literal armando markup). Lee
   lat/lon/direccion de atributos data-* (ya escapados por quien pinta el
   contenedor). */
import { titulo, sinTildes } from './formato.js';

const NO_DEFINIDO = 'NO DEFINIDO';

/** Espejo de data.ciudad_visible(): null cuando la fuente no dice municipio. */
export function ciudadVisible(ciudad) {
  const s = sinTildes(ciudad);
  return (s === '' || s === NO_DEFINIDO || s === 'NO APLICA') ? null : titulo(ciudad);
}

/** Espejo de data.claves_geocodificacion(): [claveExacta, claveMunicipio]. */
export function clavesGeocodificacion(direccion, ciudad, departamento) {
  const ciu = ciudadVisible(ciudad);
  if (!ciu || !departamento) return [null, null];
  const dep = titulo(departamento);
  const dir = String(direccion || '').trim();
  return [dir ? `${titulo(dir)}, ${ciu}, ${dep}, Colombia` : null, `${dep}|${ciu}`];
}

/** Espejo de data.coords_contrato(): null si no hay ubicacion publicable.
    El fallback 'defecto' (centro de Colombia) NUNCA se devuelve: un mapa
    generico centrado en Bogota para un contrato de otro departamento es
    peor que no mostrar mapa. */
export function coordsContrato(contrato, geocache) {
  if (!geocache) return null;
  const [exacta, mun] = clavesGeocodificacion(
    contrato.dir_ejecucion, contrato.ciudad, contrato.departamento);
  const c = (exacta && (geocache.exacta || {})[exacta])
    || (mun && (geocache.municipio || {})[mun]) || null;
  return c && c.precision !== 'defecto' ? c : null;
}

/** Conecta el boton del placeholder: al primer clic pide las tiles y monta
    Leaflet sobre el mismo contenedor. Sin clic no sale ni una peticion. */
export function montar(contenedor) {
  if (!contenedor) return;
  const lat = parseFloat(contenedor.dataset.lat);
  const lon = parseFloat(contenedor.dataset.lon);
  if (isNaN(lat) || isNaN(lon)) return;
  const direccion = contenedor.dataset.direccion || '';
  const boton = contenedor.querySelector('button');
  if (!boton) return;

  boton.addEventListener('click', function () {
    contenedor.classList.remove('mapa-placeholder');
    contenedor.replaceChildren();  // limpia el placeholder por DOM, nunca con un string de HTML

    const mapa = L.map(contenedor, { scrollWheelZoom: false }).setView([lat, lon], 15);
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, ' +
        'Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    }).addTo(mapa);

    const popup = document.createElement('div');
    const b = document.createElement('b');
    b.textContent = 'Ubicación de ejecución:';
    popup.appendChild(b);
    popup.appendChild(document.createElement('br'));
    popup.appendChild(document.createTextNode(direccion));

    L.marker([lat, lon]).addTo(mapa).bindPopup(popup).openPopup();
  }, { once: true });
}

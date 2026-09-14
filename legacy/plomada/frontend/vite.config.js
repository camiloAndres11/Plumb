// docs/PLAN_VUE.md §5 y §4.2. El bundle se escribe DENTRO de
// plomada/static/vendor/islas/ (no en un dist/ propio): asi entra a site/
// por el copytree que plomada/build.py ya hace, y sigue habiendo un unico
// escritor de site/ (restriccion 0 de la seccion 3 del plan).
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      // formato.js es el espejo de plomada/data.py (restriccion 4 del
      // plan): NO se reescribe. Los componentes lo importan tal cual desde
      // su ubicacion real, vendorizado aparte.
      '~formato': fileURLToPath(new URL('../plomada/static/formato.js', import.meta.url)),
    },
  },
  build: {
    outDir: '../plomada/static/vendor/islas',
    emptyOutDir: true,
    rollupOptions: {
      input: 'src/islas.js',
      output: {
        entryFileNames: 'islas.js',
        chunkFileNames: '[name].js',
        assetFileNames: '[name].[ext]',
      },
    },
  },
})

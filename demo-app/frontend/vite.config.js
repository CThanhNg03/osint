import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __VITE_API_URL_REQUIRED__: JSON.stringify(Boolean(process.env.VITE_API_URL)),
  },
  resolve: {
    alias: {
      'neovis.js': resolve(__dirname, 'node_modules/neovis.js/dist/neovis.js'),
    },
  },
})

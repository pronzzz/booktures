import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const API = process.env.BOOKTURES_API || 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // The Python package serves the built app from booktures/web.
    outDir: '../booktures/web',
    emptyOutDir: true,
    chunkSizeWarningLimit: 800,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API, changeOrigin: true },
      '/media': { target: API, changeOrigin: true },
    },
  },
})

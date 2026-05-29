import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../gateway/src/gateway/dashboard_dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/config': 'http://localhost:8000',
    },
  },
})

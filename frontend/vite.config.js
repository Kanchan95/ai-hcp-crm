import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy /api calls to the FastAPI backend so we avoid CORS issues in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

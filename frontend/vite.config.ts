import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Using Vite proxy so we don't need CORS in development.
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/ingest': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        timeout: 0,          // disable socket timeout (SSE is long-lived)
        proxyTimeout: 0,     // disable proxy timeout
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, req) => {
            if (req.url?.endsWith('/stream')) {
              proxyRes.headers['cache-control'] = 'no-cache'
              proxyRes.headers['x-accel-buffering'] = 'no'
            }
          })
        },
      },
      '/admin': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/truncate-db': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },

    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/prescription': { target: 'http://localhost:8000', changeOrigin: true },
      '/order-medicines': { target: 'http://localhost:8000', changeOrigin: true },
      '/consultation': { target: 'http://localhost:8000', changeOrigin: true },
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/static': { target: 'http://localhost:8000', changeOrigin: true },
      '/shared-static': { target: 'http://localhost:8000', changeOrigin: true },
      '/public': { target: 'http://localhost:8000', changeOrigin: true },
      '/new': { target: 'http://localhost:8000', changeOrigin: true },
      '/appointments': { target: 'http://localhost:8000', changeOrigin: true },
      '/device-check': { target: 'http://localhost:8000', changeOrigin: true },
      '/feature-status': { target: 'http://localhost:8000', changeOrigin: true },
      '/cases': { target: 'http://localhost:8000', changeOrigin: true },
      '/emr': { target: 'http://localhost:8000', changeOrigin: true },
      '/patients': { target: 'http://localhost:8000', changeOrigin: true },
      '/telemedicine': { target: 'http://localhost:8000', changeOrigin: true },
      '/pharmacy': { target: 'http://localhost:8000', changeOrigin: true },
      '/lab': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// When running inside Docker Compose the api service is reachable at http://api:8000.
// When running npm run dev natively on the host, the API is at http://localhost:8000.
// Set VITE_API_TARGET in your environment to override (e.g. in docker-compose).
// In production (Vercel), VITE_API_BASE_URL is set to the Railway backend URL and
// the dev proxy is not used — the frontend calls the backend directly.
const API_TARGET = process.env.VITE_API_TARGET || 'http://localhost:8000';
const isDev = process.env.NODE_ENV !== 'production';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Proxy is only used during local development; in production the frontend
    // uses VITE_API_BASE_URL to call the Railway backend directly.
    proxy: isDev
      ? {
          '/api': {
            target: API_TARGET,
            changeOrigin: true,
            secure: false,
          },
        }
      : undefined,
  },
  build: {
    // Produce source maps for Railway/Vercel error tracking
    sourcemap: false,
    rollupOptions: {
      output: {
        // Split vendor chunks for better caching
        manualChunks: (id: string) => {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) {
            return 'react-vendor';
          }
        },
      },
    },
  },
});

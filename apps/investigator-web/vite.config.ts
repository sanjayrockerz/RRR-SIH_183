import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// When running inside Docker Compose the api service is reachable at http://api:8000.
// When running npm run dev natively on the host, the API is at http://localhost:8000.
// Set VITE_API_TARGET in your environment to override (e.g. in docker-compose).
const API_TARGET = process.env.VITE_API_TARGET || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});

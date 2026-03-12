import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  server: {
    port: 9021,
    proxy: {
      '/api': {
        target: 'http://localhost:9022',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://localhost:9022',
        changeOrigin: true,
      },
    },
  },
});

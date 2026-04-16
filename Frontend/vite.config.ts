import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig, loadEnv} from 'vite';

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react(), tailwindcss()],
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        // Module 3 on separate port 8003 (config namespace conflict)
        '/api/m3': {
          target: 'http://localhost:8003',
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api\/m3/, '/api/v1'),
          timeout: 900000,
        },
        // Everything else on port 8000 (M1 + M2 + M5)
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api/, ''),
          timeout: 900000,
        },
      },
    },
  };
});

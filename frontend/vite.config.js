import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// Variables (frontend/.env) : VITE_PORT (défaut 5178), VITE_API_BASE_URL (défaut http://localhost:8005).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [vue()],
    resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
    server: {
      host: '0.0.0.0',
      port: parseInt(env.VITE_PORT || '5178'),
      strictPort: true,
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8005',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ''),
        },
      },
    },
  }
})

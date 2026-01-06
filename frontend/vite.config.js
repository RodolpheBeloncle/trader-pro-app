import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env variables
  const env = loadEnv(mode, process.cwd(), '')

  // Use Docker service name when DOCKER_ENV is set, localhost otherwise
  const backendUrl = env.BACKEND_URL || process.env.BACKEND_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      host: true,
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true
        },
        '/ws': {
          target: backendUrl,
          ws: true
        }
      }
    }
  }
})

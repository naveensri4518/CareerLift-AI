import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server on 5173.
//
// API calls default to the same-origin "/api" prefix (see src/api/client.js) and are proxied here to the
// backend. This makes the browser talk only to the Vite origin, so it is immune to the Windows
// localhost(IPv6 ::1) vs uvicorn(IPv4 127.0.0.1) mismatch, to CORS, and to a stale VITE_API_BASE pointing
// at a dead port. Override the backend target with CAREERLIFT_API_TARGET if you run it elsewhere.
const API_TARGET = process.env.CAREERLIFT_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // Strip the /api prefix: the backend serves routes at the root (/coding, /students, /register…).
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})

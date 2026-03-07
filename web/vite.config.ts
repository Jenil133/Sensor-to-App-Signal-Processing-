import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      manifest: {
        name: 'Baseline',
        short_name: 'Baseline',
        start_url: '/',
        display: 'standalone',
        theme_color: '#1a1a2e',
        background_color: '#ffffff',
        icons: [
          { src: '/icons/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/pwa-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
  server: { proxy: { '/api': 'http://localhost:8000' } }, // no CORS pain in dev
  preview: { proxy: { '/api': 'http://localhost:8000' } },
})

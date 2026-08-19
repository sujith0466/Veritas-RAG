import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@stores': path.resolve(__dirname, './src/stores'),
      '@api': path.resolve(__dirname, './src/api'),
      '@services': path.resolve(__dirname, './src/services'),
      '@contexts': path.resolve(__dirname, './src/contexts'),
      '@providers': path.resolve(__dirname, './src/providers'),
      '@theme': path.resolve(__dirname, './src/theme'),
      '@motion': path.resolve(__dirname, './src/motion'),
      '@design-system': path.resolve(__dirname, './src/design-system'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@layouts': path.resolve(__dirname, './src/layouts'),
      '@routes': path.resolve(__dirname, './src/routes'),
    },
  },
  server: {
    port: 5173,
    watch: {
      ignored: ['**/playwright-report/**', '**/test-results/**'],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  preview: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          motion: ['framer-motion'],
          query: ['@tanstack/react-query'],
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu', '@radix-ui/react-select', '@radix-ui/react-toast', '@radix-ui/react-tooltip'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/tests/setup.ts',
    css: true,
  },
})

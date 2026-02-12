import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  worker: {
    format: 'es',
  },
  build: {
    outDir: '../static/assets',
    emptyOutDir: true,
    manifest: 'manifest.json',
    assetsDir: '.',
  },
  base: '/static/assets/',
});

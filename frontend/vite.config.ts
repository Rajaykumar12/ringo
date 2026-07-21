import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // The project lives on an NTFS/fuseblk mount, which doesn't reliably deliver
    // inotify events — without polling, HMR silently stops picking up file changes.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});

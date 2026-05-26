import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration with explicit server settings to match dev server port
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5176, // match the actual dev server port
    host: true, // allow network access (useful for HMR)
  },
});

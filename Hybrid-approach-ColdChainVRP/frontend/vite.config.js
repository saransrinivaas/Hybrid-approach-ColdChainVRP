import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Vite configuration with explicit server settings and es-toolkit compat overrides
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5176, // match the actual dev server port
    host: true, // allow network access (useful for HMR)
  },
  resolve: {
    alias: [
      {
        find: /^es-toolkit\/compat\/(object|function|array|string|math|collection|date|lang|number|seq|util)\/(.*)$/,
        replacement: 'lodash/$2'
      },
      {
        find: /^es-toolkit\/compat\/(.*)$/,
        replacement: 'lodash/$1'
      }
    ]
  }
});

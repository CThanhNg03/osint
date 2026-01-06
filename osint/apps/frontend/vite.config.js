import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration for the OSINT frontend.
export default defineConfig({
  plugins: [react()],
});

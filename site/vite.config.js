import { defineConfig } from 'vite';

// Library-style IIFE build: one classic script, dist/app.js. page.html / index.html are
// assembled by scripts/postbuild.mjs (the host needs an HTML fragment, see BIBLE section 7).
export default defineConfig({
  base: './',
  publicDir: 'public',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    copyPublicDir: true,
    target: 'es2020',
    minify: true,
    reportCompressedSize: false,
    lib: {
      entry: 'src/main.js',
      formats: ['iife'],
      name: 'SixtyStories',
      fileName: () => 'app.js',
    },
  },
});

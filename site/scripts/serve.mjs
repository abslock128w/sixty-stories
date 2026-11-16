// Tiny static server for dist/, mounted under a sub-path to prove all URLs are relative.
// node scripts/serve.mjs [port] [basePath]   ->  http://localhost:4173/deep/base/path/
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'dist');
const port = Number(process.argv[2] || 4173);
const base = (process.argv[3] || '/deep/base/path/').replace(/\/?$/, '/');
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.bin': 'application/octet-stream', '.css': 'text/css' };
http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split('?')[0]);
  if (!url.startsWith(base)) { res.writeHead(404); res.end('outside base'); return; }
  let rel = url.slice(base.length) || 'index.html';
  const filmDir = process.env.FILM_DIR ? path.resolve(process.env.FILM_DIR) : null;
  const rootDir = filmDir && rel.startsWith('film/') ? filmDir : dist;
  if (rootDir === filmDir) rel = rel.slice(5);
  const file = path.join(rootDir, path.normalize(rel));
  if (!file.startsWith(rootDir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); res.end('not found'); return; }
  res.writeHead(200, { 'content-type': types[path.extname(file)] || 'application/octet-stream', 'content-length': fs.statSync(file).size, 'cache-control': 'no-cache' });
  fs.createReadStream(file).pipe(res);
}).listen(port, () => console.log(`serving ${dist} at http://localhost:${port}${base}`));

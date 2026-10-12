// Renderiza arquitetura.html em GIF animado (loop) + PNG estático (quadro final, 2x).
// Uso: node render.mjs [diretorio-de-saida]
import { chromium } from 'playwright-core';
import gifenc from 'gifenc';
const { GIFEncoder, quantize, applyPalette } = gifenc;
import { PNG } from 'pngjs';
import { pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { mkdirSync, writeFileSync, statSync } from 'node:fs';

const OUT = resolve(process.argv[2] || '.');
const CHROME = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const W = 1200, H = 675;
const DELAY_MS = 70;                 // ~14 fps
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME });
const url = pathToFileURL(resolve('arquitetura.html')).href;

// ---- quadros do GIF ----
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
await page.goto(url);
const total = await page.evaluate(() => window.TOTAL);
const n = Math.round((total * 1000) / DELAY_MS);
const frames = [];
for (let i = 0; i < n; i++) {
  await page.evaluate(t => window.renderAt(t), (i * DELAY_MS) / 1000);
  const png = PNG.sync.read(await page.screenshot({ type: 'png' }));
  frames.push(new Uint8Array(png.data.buffer, png.data.byteOffset, png.data.length));
}

// ---- paleta global (255 cores + 1 índice reservado para transparência) ----
const sample = [];
for (let i = 0; i < n; i += 6) sample.push(frames[i]);
const merged = new Uint8Array(sample.reduce((a, f) => a + f.length, 0));
let off = 0;
for (const f of sample) { merged.set(f, off); off += f.length; }
const palette = quantize(merged, 255, { format: 'rgb565' });
while (palette.length < 255) palette.push([0, 0, 0]);
palette.push([0, 0, 0]);
const TRANSP = 255;

// ---- codificação com diferença entre quadros ----
const gif = GIFEncoder();
let prev = null;
for (let i = 0; i < n; i++) {
  const idx = applyPalette(frames[i], palette, 'rgb565');
  for (let j = 0; j < idx.length; j++) if (idx[j] === TRANSP) idx[j] = TRANSP - 1; // nunca usar o reservado
  if (!prev) {
    gif.writeFrame(idx, W, H, { palette, delay: DELAY_MS, repeat: 0 });
  } else {
    const diff = new Uint8Array(idx.length);
    for (let j = 0; j < idx.length; j++) diff[j] = idx[j] === prev[j] ? TRANSP : idx[j];
    gif.writeFrame(diff, W, H, { delay: DELAY_MS, transparent: true, transparentIndex: TRANSP, dispose: 1 });
  }
  prev = idx;
}
gif.finish();
const gifPath = join(OUT, 'arquitetura.gif');
writeFileSync(gifPath, gif.bytes());

// ---- PNG estático (quadro com tudo aceso), 2x ----
const hi = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
await hi.goto(url);
await hi.evaluate(t => window.renderAt(t), 7.6);
const pngPath = join(OUT, 'arquitetura.png');
await hi.screenshot({ path: pngPath, type: 'png' });
await browser.close();

const kb = p => (statSync(p).size / 1024).toFixed(0);
console.log(`frames=${n} duracao=${total}s`);
console.log(`GIF  ${gifPath}  ${kb(gifPath)} KB`);
console.log(`PNG  ${pngPath}  ${kb(pngPath)} KB`);

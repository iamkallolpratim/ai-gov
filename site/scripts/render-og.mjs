// Renders public/og.png (1200x630) from an inline SVG. Run with `npm run og` and commit
// the result; the image is static, so CI does not regenerate it.
import sharp from 'sharp';
import { fileURLToPath } from 'node:url';

const out = fileURLToPath(new URL('../public/og.png', import.meta.url));
const chips = ['EU AI Act', 'California ADMT', 'China GenAI', 'India DPDP'];
let x = 80;
const chipSvg = chips
  .map((label) => {
    const w = label.length * 13 + 40;
    const svg = `<rect x="${x}" y="430" width="${w}" height="48" rx="24" fill="#ffffff" fill-opacity="0.12" stroke="#ffffff" stroke-opacity="0.35"/>
      <text x="${x + w / 2}" y="461" font-size="22" font-weight="600" fill="#ffffff" text-anchor="middle">${label}</text>`;
    x += w + 16;
    return svg;
  })
  .join('');

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630"
  font-family="Helvetica Neue, Helvetica, Arial, sans-serif">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#12284a"/><stop offset="1" stop-color="#1d4277"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <g transform="translate(80 80) scale(2.2)">
    <path d="M16 2.5 4.5 7v8.2c0 7.1 4.9 12.6 11.5 14.3 6.6-1.7 11.5-7.2 11.5-14.3V7L16 2.5Z" fill="#ffffff"/>
    <path d="m10.5 16.2 3.8 3.8 7.4-8" stroke="#1d4277" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <text x="166" y="128" font-size="30" font-weight="700" fill="#ffffff">AI Governance Console</text>
  <text x="80" y="260" font-size="62" font-weight="700" fill="#ffffff" letter-spacing="-1">Know which AI rules apply.</text>
  <text x="80" y="336" font-size="62" font-weight="700" fill="#c9dbf6" letter-spacing="-1">Prove you follow them.</text>
  <text x="80" y="392" font-size="26" fill="#ffffff" fill-opacity="0.8">Open-source AI compliance as code · OPA policies · evidence on demand</text>
  ${chipSvg}
  <text x="80" y="560" font-size="22" fill="#ffffff" fill-opacity="0.7">github.com/iamkallolpratim/ai-gov · Apache 2.0</text>
</svg>`;

await sharp(Buffer.from(svg)).png().toFile(out);
console.log(`wrote ${out}`);

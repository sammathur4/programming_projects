import fs from 'fs';
import path from 'path';
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';

const pdfPath = process.argv[2];
const outDir = process.argv[3] || path.dirname(pdfPath);

const data = new Uint8Array(fs.readFileSync(pdfPath));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
let fullText = '';
for (let i = 1; i <= doc.numPages; i++) {
  const page = await doc.getPage(i);
  const textContent = await page.getTextContent();
  const pageText = textContent.items.map(item => item.str || '').join(' ');
  fullText += pageText + '\n\n';
}
const outTxt = path.join(outDir, path.basename(pdfPath).replace('.pdf', '.txt'));
fs.writeFileSync(outTxt, fullText);
console.log('done', fullText.length);

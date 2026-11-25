import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const require = createRequire(join(resolve(process.argv[2]), 'package.json'));
const { zipSync, strToU8 } = require('fflate');
const { createConverter, discoverRuntime } = await import(
    pathToFileURL(require.resolve('@deepseek-ai/libreoffice-kit'))
);
assert.equal((await discoverRuntime()).backend, 'wasm');

const mime = 'application/vnd.oasis.opendocument.text';
const odt = zipSync({
    mimetype: [strToU8(mime), { level: 0 }],
    'META-INF/manifest.xml': strToU8(
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">' +
        '<manifest:file-entry manifest:full-path="/" manifest:media-type="' + mime + '"/>' +
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>'
    ),
    'content.xml': strToU8(
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" ' +
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">' +
        '<office:body><office:text><text:p>devneya</text:p></office:text></office:body></office:document-content>'
    ),
});
const scratch = await mkdtemp(join(tmpdir(), 'devneya-office-'));
try {
    const inputPath = join(scratch, 'sample.odt');
    const outputPath = join(scratch, 'sample.pdf');
    await writeFile(inputPath, odt);
    const converter = await createConverter({ fontMetadataCacheDirectory: false, fontDirectories: [] });
    try {
        const result = await converter.render({ inputPath, outputPath });
        assert.equal(result.backend, 'wasm');
        assert.equal((await readFile(outputPath)).subarray(0, 5).toString('ascii'), '%PDF-');
    } finally {
        await converter.dispose();
    }
    console.log('Windows Office WASM conversion produced a PDF');
} finally {
    await rm(scratch, { recursive: true, force: true });
}

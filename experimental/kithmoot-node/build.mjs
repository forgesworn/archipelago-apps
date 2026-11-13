import { build } from 'esbuild'
import { mkdir, copyFile } from 'node:fs/promises'
await mkdir('dist/public', { recursive: true })
await build({ entryPoints: ['client.mjs'], outfile: 'dist/public/client.js', bundle: true, minify: true, platform: 'browser', target: 'es2022', legalComments: 'eof' })
await build({ entryPoints: ['entrypoint.mjs'], outfile: 'dist/controller.mjs', bundle: true, minify: true, platform: 'node', format: 'esm', target: 'node24', packages: 'bundle', legalComments: 'eof', banner: { js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);" } })
for (const name of ['index.html', 'style.css']) await copyFile('public/' + name, 'dist/public/' + name)
await copyFile('../../apps/spry/public/nostr-provider.js', 'dist/public/nostr-provider.js')

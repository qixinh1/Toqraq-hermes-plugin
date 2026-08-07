import { build } from 'esbuild'
import { mkdir } from 'node:fs/promises'

const outdir = 'desktop'
await mkdir(outdir, { recursive: true })

await build({
  entryPoints: ['src/renderer/index.ts'],
  outfile: `${outdir}/plugin.js`,
  bundle: true,
  format: 'esm',
  target: 'es2022',
  platform: 'browser',
  external: ['@hermes/plugin-sdk', 'react', 'react/jsx-runtime'],
  legalComments: 'eof',
  logLevel: 'info',
})

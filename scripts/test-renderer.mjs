import { build } from 'esbuild'
import { readdirSync } from 'node:fs'
import { mkdtemp, rm } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import path from 'node:path'

const RENDERER_ROOT = path.resolve('src/renderer')
const TEST_DIRECTORY_PREFIX = 'toqraq-renderer-tests-'
const HOST_RUNTIME_MODULES = Object.freeze([
  '@hermes/plugin-sdk',
  'react',
  'react/jsx-runtime',
])

const tests = rendererTests(RENDERER_ROOT)
if (tests.length === 0) throw new Error('Renderer test source is missing')

const outputDirectory = await mkdtemp(path.join(tmpdir(), TEST_DIRECTORY_PREFIX))
let testStatus = 1

try {
  const result = await build({
    entryPoints: tests,
    outbase: RENDERER_ROOT,
    outdir: outputDirectory,
    bundle: true,
    external: HOST_RUNTIME_MODULES,
    format: 'esm',
    logLevel: 'silent',
    metafile: true,
    platform: 'node',
    target: 'node22',
  })
  const compiledTests = Object.entries(result.metafile.outputs)
    .filter(([, output]) => output.entryPoint !== undefined)
    .map(([output]) => path.resolve(output))
    .sort((left, right) => left.localeCompare(right))
  if (compiledTests.length !== tests.length) {
    throw new Error('Renderer test compilation did not preserve every test entry')
  }

  const execution = spawnSync(process.execPath, ['--test', ...compiledTests], {
    stdio: 'inherit',
  })
  if (execution.error) throw execution.error
  if (execution.signal) throw new Error(`Renderer tests ended with signal ${execution.signal}`)
  testStatus = execution.status ?? 1
} finally {
  await discardOwnedTestDirectory(outputDirectory)
}

process.exitCode = testStatus

function rendererTests(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap(entry => {
      const absolute = path.join(directory, entry.name)
      if (entry.isDirectory()) return rendererTests(absolute)
      return entry.isFile() && entry.name.endsWith('.test.ts') ? [path.resolve(absolute)] : []
    })
}

async function discardOwnedTestDirectory(directory) {
  const parent = path.resolve(path.dirname(directory))
  if (parent !== path.resolve(tmpdir()) || !path.basename(directory).startsWith(TEST_DIRECTORY_PREFIX)) {
    throw new Error('Refusing to remove an unowned Renderer test directory')
  }
  await rm(directory, { recursive: true, force: true })
}

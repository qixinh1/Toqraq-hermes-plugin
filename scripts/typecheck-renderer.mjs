import { createRequire } from 'node:module'
import { existsSync, readdirSync, realpathSync } from 'node:fs'
import path from 'node:path'

const HERMES_SOURCE_ENV = 'TOQRAQ_HERMES_SOURCE'
const RENDERER_ROOT = path.resolve('src/renderer')
const HERMES_DESKTOP_PATH = path.join('apps', 'desktop')
const HERMES_TYPESCRIPT_PATH = path.join('node_modules', 'typescript', 'lib', 'typescript.js')
const HERMES_SDK_MODULE = '@hermes/plugin-sdk'
const HOST_RUNTIME_MODULES = Object.freeze(['react', 'react/jsx-runtime'])

const hermesSource = requiredHermesSource()
const desktopRoot = path.join(hermesSource, HERMES_DESKTOP_PATH)
const configPath = path.join(desktopRoot, 'tsconfig.json')
const typescriptPath = path.join(hermesSource, HERMES_TYPESCRIPT_PATH)
requireFile(configPath, 'Hermes Desktop tsconfig')
requireFile(typescriptPath, 'Hermes-owned TypeScript')

const require = createRequire(import.meta.url)
const ts = require(typescriptPath)
const parsed = readHermesCompilerOptions(ts, configPath, desktopRoot)
const options = rendererCompilerOptions(ts, parsed.options, desktopRoot)
const roots = rendererTypeScript(RENDERER_ROOT)
const rootSet = new Set(roots.map(root => path.normalize(root)))
const program = ts.createProgram(roots, options)
const diagnostics = [...parsed.errors, ...ts.getPreEmitDiagnostics(program)].filter(
  diagnostic => !diagnostic.file || rootSet.has(path.normalize(diagnostic.file.fileName)),
)
const explicitAny = explicitAnyLocations(ts, program, rootSet)

if (diagnostics.length > 0 || explicitAny.length > 0) {
  const formatHost = {
    getCanonicalFileName: fileName => fileName,
    getCurrentDirectory: () => process.cwd(),
    getNewLine: () => '\n',
  }
  process.stderr.write(ts.formatDiagnostics(diagnostics, formatHost))
  for (const location of explicitAny) process.stderr.write(`${location}: explicit any is prohibited\n`)
  process.stderr.write(
    `Renderer typecheck failed: ${diagnostics.length} diagnostics, ${explicitAny.length} explicit any nodes.\n`,
  )
  process.exitCode = 1
} else {
  process.stdout.write(`Renderer typecheck passed: ${roots.length} source and test files, 0 diagnostics.\n`)
}

function requiredHermesSource() {
  const configured = process.env[HERMES_SOURCE_ENV]?.trim()
  if (!configured) {
    throw new Error(`${HERMES_SOURCE_ENV} must point to the paired Hermes source checkout`)
  }
  const source = path.resolve(configured)
  if (!existsSync(source)) throw new Error(`${HERMES_SOURCE_ENV} does not exist: ${source}`)
  return realpathSync(source)
}

function requireFile(filePath, label) {
  if (!existsSync(filePath)) throw new Error(`${label} is missing: ${filePath}`)
}

function readHermesCompilerOptions(ts, configPath, desktopRoot) {
  const loaded = ts.readConfigFile(configPath, ts.sys.readFile)
  if (loaded.error) return { options: {}, errors: [loaded.error] }
  return ts.parseJsonConfigFileContent(loaded.config, ts.sys, desktopRoot, undefined, configPath)
}

function rendererCompilerOptions(ts, hostOptions, desktopRoot) {
  if (!hostOptions.paths?.[HERMES_SDK_MODULE]) {
    throw new Error(`Hermes Desktop tsconfig must map ${HERMES_SDK_MODULE}`)
  }
  const containingFile = path.join(desktopRoot, 'src', 'sdk', 'index.ts')
  const runtimePaths = Object.fromEntries(
    HOST_RUNTIME_MODULES.map(moduleName => [
      moduleName,
      [resolveHostRuntimeType(ts, moduleName, containingFile, hostOptions)],
    ]),
  )
  return {
    ...hostOptions,
    allowJs: false,
    checkJs: false,
    exactOptionalPropertyTypes: true,
    isolatedModules: true,
    noEmit: true,
    noUncheckedIndexedAccess: true,
    noUnusedLocals: true,
    noUnusedParameters: true,
    strict: true,
    typeRoots: hostTypeRoots(desktopRoot),
    types: ['node'],
    verbatimModuleSyntax: true,
    paths: { ...hostOptions.paths, ...runtimePaths },
  }
}

function hostTypeRoots(desktopRoot) {
  const candidates = [
    path.join(desktopRoot, 'node_modules', '@types'),
    path.join(desktopRoot, '..', '..', 'node_modules', '@types'),
  ]
  const existing = candidates.filter(existsSync)
  if (existing.length === 0) throw new Error('Hermes Desktop Node type declarations are missing')
  return existing
}

function resolveHostRuntimeType(ts, moduleName, containingFile, options) {
  const resolved = ts.resolveModuleName(moduleName, containingFile, options, ts.sys).resolvedModule
  if (!resolved) throw new Error(`Hermes Desktop cannot resolve ${moduleName}`)
  return resolved.resolvedFileName
}

function rendererTypeScript(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap(entry => {
      const absolute = path.join(directory, entry.name)
      if (entry.isDirectory()) return rendererTypeScript(absolute)
      return entry.isFile() && (entry.name.endsWith('.ts') || entry.name.endsWith('.d.ts'))
        ? [path.resolve(absolute)]
        : []
    })
}

function explicitAnyLocations(ts, program, rootSet) {
  const locations = []
  for (const source of program.getSourceFiles()) {
    const normalized = path.normalize(source.fileName)
    if (!rootSet.has(normalized) || source.isDeclarationFile) continue
    visit(source)

    function visit(node) {
      if (node.kind === ts.SyntaxKind.AnyKeyword) {
        const position = source.getLineAndCharacterOfPosition(node.getStart(source))
        locations.push(`${source.fileName}:${position.line + 1}:${position.character + 1}`)
      }
      ts.forEachChild(node, visit)
    }
  }
  return locations.sort((left, right) => left.localeCompare(right))
}

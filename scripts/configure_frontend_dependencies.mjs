import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const packageJsonPath = path.join(projectRoot, 'package.json')
const packageJson = JSON.parse(await readFile(packageJsonPath, 'utf8'))

packageJson.scripts = {
    ...(packageJson.scripts || {}),
    'vendor-assets': 'node ./scripts/vendor_frontend_assets.mjs',
    'verify-vendor-assets': 'node ./scripts/verify_frontend_assets.mjs',
}

const dependencies = {
    ...(packageJson.devDependencies || {}),
    alpinejs: '3.15.12',
    'chart.js': '4.5.1',
    'htmx.org': '2.0.10',
    lucide: '1.20.0',
}

packageJson.devDependencies = Object.fromEntries(
    Object.entries(dependencies).sort(([left], [right]) => left.localeCompare(right))
)

await writeFile(packageJsonPath, `${JSON.stringify(packageJson, null, 2)}\n`, 'utf8')
console.log('Configured exact frontend runtime dependency versions in package.json.')

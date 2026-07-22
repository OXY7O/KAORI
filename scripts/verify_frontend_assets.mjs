import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { access, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const manifestPath = path.join(projectRoot, 'app', 'static', 'vendor', 'manifest.json')
const packageJson = JSON.parse(await readFile(path.join(projectRoot, 'package.json'), 'utf8'))
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'))

const expectedPackages = new Map([
    ['alpinejs', 'app/static/vendor/alpine/alpine.min.js'],
    ['htmx.org', 'app/static/vendor/htmx/htmx.min.js'],
    ['lucide', 'app/static/vendor/lucide/lucide.min.js'],
    ['chart.js', 'app/static/vendor/chartjs/chart.umd.min.js'],
])

const expectedFonts = new Map([
    ['@fontsource-variable/inter', 'app/static/fonts/inter/inter-latin-wght-normal.woff2'],
])

function sha256(buffer) {
    return createHash('sha256').update(buffer).digest('hex')
}

if (
    manifest.schema_version !== 1 ||
    !Array.isArray(manifest.assets) ||
    !Array.isArray(manifest.fonts)
) {
    throw new Error('Invalid frontend vendor manifest schema.')
}

const records = new Map(manifest.assets.map((record) => [record.package, record]))
const fontRecords = new Map(manifest.fonts.map((record) => [record.package, record]))

for (const [packageName, runtimePath] of expectedPackages) {
    const record = records.get(packageName)
    if (!record) {
        throw new Error(`Missing vendor manifest entry for ${packageName}.`)
    }

    const pinnedVersion = packageJson.devDependencies?.[packageName]
    if (!pinnedVersion || pinnedVersion !== record.version || /[~^*xX]/u.test(pinnedVersion)) {
        throw new Error(
            `${packageName} must use one exact version in package.json and manifest.`
        )
    }

    if (record.runtime_path !== runtimePath) {
        throw new Error(`Unexpected runtime path for ${packageName}: ${record.runtime_path}`)
    }

    const absolutePath = path.join(projectRoot, runtimePath)
    const content = await readFile(absolutePath)
    if (content.length !== record.bytes || sha256(content) !== record.sha256) {
        throw new Error(`${runtimePath} does not match its committed manifest checksum.`)
    }

    if (/sourceMappingURL=/u.test(content.toString('utf8'))) {
        throw new Error(`${runtimePath} still references a source map that is not shipped.`)
    }

    if (record.license_path) {
        await access(path.join(projectRoot, record.license_path))
    }

    execFileSync(process.execPath, ['--check', absolutePath], { stdio: 'pipe' })
}

if (records.size !== expectedPackages.size) {
    throw new Error('Vendor manifest contains an unexpected or unmanaged runtime package.')
}

for (const [packageName, runtimePath] of expectedFonts) {
    const record = fontRecords.get(packageName)
    if (!record) {
        throw new Error(`Missing local font manifest entry for ${packageName}.`)
    }

    const pinnedVersion = packageJson.devDependencies?.[packageName]
    if (!pinnedVersion || pinnedVersion !== record.version || /[~^*xX]/u.test(pinnedVersion)) {
        throw new Error(`${packageName} must use one exact version in package.json and manifest.`)
    }

    if (record.runtime_path !== runtimePath) {
        throw new Error(`Unexpected runtime path for ${packageName}: ${record.runtime_path}`)
    }

    const absolutePath = path.join(projectRoot, runtimePath)
    const content = await readFile(absolutePath)
    if (content.length !== record.bytes || sha256(content) !== record.sha256) {
        throw new Error(`${runtimePath} does not match its committed manifest checksum.`)
    }

    if (record.license_path) {
        await access(path.join(projectRoot, record.license_path))
    }
}

if (fontRecords.size !== expectedFonts.size) {
    throw new Error('Vendor manifest contains an unexpected or unmanaged local font package.')
}

console.log(
    `Verified ${expectedPackages.size} pinned frontend runtime assets and ${expectedFonts.size} local font.`
)

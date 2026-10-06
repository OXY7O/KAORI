import { createHash } from 'node:crypto'
import { access, copyFile, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const vendorRoot = path.join(projectRoot, 'app', 'static', 'vendor')

const assets = [
    {
        packageName: 'alpinejs',
        source: 'dist/cdn.min.js',
        target: 'alpine/alpine.min.js',
        minimumBytes: 30000,
        globalName: 'Alpine',
    },
    {
        packageName: 'htmx.org',
        source: 'dist/htmx.min.js',
        target: 'htmx/htmx.min.js',
        minimumBytes: 30000,
        globalName: 'htmx',
    },
    {
        packageName: 'lucide',
        source: 'dist/umd/lucide.min.js',
        target: 'lucide/lucide.min.js',
        minimumBytes: 250000,
        globalName: 'lucide',
    },
    {
        packageName: 'chart.js',
        source: 'dist/chart.umd.min.js',
        target: 'chartjs/chart.umd.min.js',
        minimumBytes: 150000,
        globalName: 'Chart',
    },
]

const fonts = [
    {
        packageName: '@fontsource-variable/inter',
        source: 'files/inter-latin-wght-normal.woff2',
        target: 'inter/inter-latin-wght-normal.woff2',
        minimumBytes: 30000,
        family: 'Inter Variable',
        weight: '100 900',
        style: 'normal',
    },
]

function sha256(buffer) {
    return createHash('sha256').update(buffer).digest('hex')
}

function normalizeJavascript(buffer) {
    return Buffer.from(
        buffer
            .toString('utf8')
            .replace(/\n?\/\/[#@]\s*sourceMappingURL=.*?\s*$/u, '')
            .replace(/\n?\/\*[#@]\s*sourceMappingURL=.*?\*\/\s*$/u, '')
            .trimEnd() + '\n',
        'utf8'
    )
}

async function packageMetadata(packageName) {
    const packageRoot = path.join(projectRoot, 'node_modules', packageName)
    const packageJsonPath = path.join(packageRoot, 'package.json')
    const metadata = JSON.parse(await readFile(packageJsonPath, 'utf8'))
    return { packageRoot, metadata }
}

async function findLicense(packageRoot) {
    const entries = await readdir(packageRoot)
    const licenseName = entries.find((name) => /^(licen[cs]e|copying)(\..*)?$/iu.test(name))
    return licenseName ? path.join(packageRoot, licenseName) : null
}

await mkdir(vendorRoot, { recursive: true })

const manifest = {
    schema_version: 1,
    policy: 'Runtime assets are committed and served by KAORI. Network access is not required at runtime.',
    assets: [],
    fonts: [],
}

for (const asset of assets) {
    const { packageRoot, metadata } = await packageMetadata(asset.packageName)
    const sourcePath = path.join(packageRoot, asset.source)
    const targetPath = path.join(vendorRoot, asset.target)
    const targetDirectory = path.dirname(targetPath)

    await access(sourcePath)
    await mkdir(targetDirectory, { recursive: true })

    const sourceBuffer = await readFile(sourcePath)
    const vendoredBuffer = normalizeJavascript(sourceBuffer)

    if (vendoredBuffer.length < asset.minimumBytes) {
        throw new Error(`${asset.packageName} asset is unexpectedly small: ${vendoredBuffer.length} bytes`)
    }

    await writeFile(targetPath, vendoredBuffer)

    const licensePath = await findLicense(packageRoot)
    let licenseTarget = null
    if (licensePath) {
        licenseTarget = path.join(targetDirectory, 'LICENSE.txt')
        await copyFile(licensePath, licenseTarget)
    }

    manifest.assets.push({
        package: asset.packageName,
        version: metadata.version,
        license: metadata.license || null,
        source_path: path.posix.join('node_modules', asset.packageName, asset.source),
        runtime_path: path.posix.join('app/static/vendor', asset.target),
        source_sha256: sha256(sourceBuffer),
        sha256: sha256(vendoredBuffer),
        bytes: vendoredBuffer.length,
        browser_global: asset.globalName,
        license_path: licenseTarget ? path.posix.relative(projectRoot, licenseTarget).replaceAll('\\', '/') : null,
    })
}

for (const font of fonts) {
    const { packageRoot, metadata } = await packageMetadata(font.packageName)
    const sourcePath = path.join(packageRoot, font.source)
    const targetPath = path.join(projectRoot, 'app', 'static', 'fonts', font.target)
    const targetDirectory = path.dirname(targetPath)

    await access(sourcePath)
    await mkdir(targetDirectory, { recursive: true })

    const content = await readFile(sourcePath)
    if (content.length < font.minimumBytes) {
        throw new Error(`${font.packageName} font is unexpectedly small: ${content.length} bytes`)
    }

    await writeFile(targetPath, content)

    const licensePath = await findLicense(packageRoot)
    let licenseTarget = null
    if (licensePath) {
        licenseTarget = path.join(targetDirectory, 'LICENSE.txt')
        await copyFile(licensePath, licenseTarget)
    }

    manifest.fonts.push({
        package: font.packageName,
        version: metadata.version,
        license: metadata.license || null,
        source_path: path.posix.join('node_modules', font.packageName, font.source),
        runtime_path: path.posix.join('app/static/fonts', font.target),
        sha256: sha256(content),
        bytes: content.length,
        family: font.family,
        weight: font.weight,
        style: font.style,
        license_path: licenseTarget ? path.posix.relative(projectRoot, licenseTarget).replaceAll('\\', '/') : null,
    })
}

manifest.assets.sort((left, right) => left.package.localeCompare(right.package))
manifest.fonts.sort((left, right) => left.package.localeCompare(right.package))
await writeFile(path.join(vendorRoot, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')

const managedDirectories = new Set(assets.map((asset) => asset.target.split('/')[0]))
for (const directory of managedDirectories) {
    const sourceMapFiles = (await readdir(path.join(vendorRoot, directory))).filter((name) => name.endsWith('.map'))
    await Promise.all(sourceMapFiles.map((name) => rm(path.join(vendorRoot, directory, name), { force: true })))
}

console.log(`Vendored ${manifest.assets.length} frontend runtime assets and ${manifest.fonts.length} local font.`)

import { watch } from 'node:fs'
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/postcss'
import postcss from 'postcss'

const root = fileURLToPath(new URL('../', import.meta.url))
const inputPath = resolve(root, 'frontend/styles.css')
const outputPath = resolve(root, 'app/static/css/output.css')
const processor = postcss([tailwindcss({ base: root, optimize: { minify: true } })])

async function build() {
    const source = await readFile(inputPath, 'utf8')
    const result = await processor.process(source, {
        from: inputPath,
        to: outputPath,
        map: false,
    })
    await mkdir(dirname(outputPath), { recursive: true })
    const temporaryPath = `${outputPath}.${process.pid}.tmp`
    try {
        // PostCSS appends a final newline; retain the historical minified output bytes.
        await writeFile(temporaryPath, result.css.replace(/\n$/, ''))
        await rename(temporaryPath, outputPath)
    } finally {
        await rm(temporaryPath, { force: true })
    }
    console.log('KAORI Tailwind CSS build complete.')
}

await build()

if (process.argv.includes('--watch')) {
    // Keep the documented source directories watched without a glob-matching dependency.
    // Serialize builds, retaining the last complete stylesheet if an edit is invalid.
    let timer
    let pending = false
    let running = false
    async function drain() {
        if (running) return
        running = true
        try {
            while (pending) {
                pending = false
                try {
                    await build()
                } catch (error) {
                    console.error('KAORI CSS rebuild failed:', error)
                }
            }
        } finally {
            running = false
        }
    }
    function schedule() {
        clearTimeout(timer)
        timer = setTimeout(() => {
            pending = true
            void drain()
        }, 100)
    }
    for (const directory of ['frontend', 'app/templates', 'app/static/js']) {
        watch(resolve(root, directory), { recursive: true }, schedule)
    }
    console.log('Watching KAORI frontend, templates, and scripts.')
}

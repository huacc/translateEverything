import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  rmSync,
  statSync,
} from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const projectRoot = path.resolve(__dirname, '..')

const sources = [
  {
    from: path.join(projectRoot, 'node_modules', 'pdfjs-dist', 'cmaps'),
    to: path.join(projectRoot, 'public', 'pdfjs', 'cmaps'),
  },
  {
    from: path.join(
      projectRoot,
      'node_modules',
      'pdfjs-dist',
      'standard_fonts'
    ),
    to: path.join(projectRoot, 'public', 'pdfjs', 'standard_fonts'),
  },
]

function copyDirectory(sourceDir, targetDir) {
  mkdirSync(targetDir, { recursive: true })

  for (const entry of readdirSync(sourceDir)) {
    const sourcePath = path.join(sourceDir, entry)
    const targetPath = path.join(targetDir, entry)
    const entryStat = statSync(sourcePath)

    if (entryStat.isDirectory()) {
      copyDirectory(sourcePath, targetPath)
      continue
    }

    copyFileSync(sourcePath, targetPath)
  }
}

for (const { from, to } of sources) {
  if (!existsSync(from)) {
    throw new Error(`Missing PDF.js asset directory: ${from}`)
  }

  rmSync(to, { recursive: true, force: true })
  copyDirectory(from, to)
}

console.log('PDF.js assets synced to public/pdfjs')

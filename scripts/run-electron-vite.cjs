const { spawn } = require('child_process')
const path = require('path')

const args = process.argv.slice(2)
const electronViteBin = path.join(
  __dirname,
  '..',
  'node_modules',
  'electron-vite',
  'bin',
  'electron-vite.js'
)

const env = { ...process.env }
delete env.ELECTRON_RUN_AS_NODE

const child = spawn(process.execPath, [electronViteBin, ...args], {
  stdio: 'inherit',
  env,
  shell: false
})

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }
  process.exit(code ?? 1)
})

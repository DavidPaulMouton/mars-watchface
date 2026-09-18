const fs = require('fs')
const path = require('path')
const Module = require('module')
const origLoad = Module._load

Module._load = function (request, parent, isMain) {
  const loaded = origLoad.apply(this, arguments)
  if (request === 'qrcode-terminal' && loaded && typeof loaded.generate === 'function' && !loaded.__marsHooked) {
    const orig = loaded.generate.bind(loaded)
    loaded.generate = function (url, opts, cb) {
      const dest = path.resolve('preview-url.txt')
      fs.writeFileSync(dest, String(url), 'utf8')
      process.stderr.write('PREVIEW_URL=' + url + '\n')
      return orig(url, opts, cb)
    }
    loaded.__marsHooked = true
  }
  return loaded
}

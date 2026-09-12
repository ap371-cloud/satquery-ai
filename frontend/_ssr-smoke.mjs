import { createServer } from 'vite'
import { createElement } from 'react'
import { renderToString } from 'react-dom/server'

const STUB = 'C:\\Users\\ARYANP~1\\AppData\\Local\\Temp\\opencode\\maplibre-stub.mjs'
const server = await createServer({
  root: 'C:\\Users\\ARYAN PANDEY\\Dropbox\\satquery-main\\satquery-main\\frontend',
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'silent',
  resolve: {
    alias: [
      { find: /^maplibre-gl/, replacement: STUB },
    ],
  },
  ssr: { noExternal: [/^maplibre-gl/] },
})
try {
  const mod = await server.ssrLoadModule('/src/App.jsx')
  const html = renderToString(createElement(mod.default))
  console.log('SSR RENDER OK, length:', html.length)
} catch (e) {
  console.error('SSR RENDER FAILED:')
  console.error(e && e.stack ? e.stack : String(e))
}
await server.close()
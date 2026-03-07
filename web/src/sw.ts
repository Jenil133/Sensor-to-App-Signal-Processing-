/// <reference lib="webworker" />
import { precacheAndRoute } from 'workbox-precaching'
import { registerRoute } from 'workbox-routing'
import { NetworkOnly } from 'workbox-strategies'
import { BackgroundSyncPlugin } from 'workbox-background-sync'

declare let self: ServiceWorkerGlobalScope

precacheAndRoute(self.__WB_MANIFEST)

// Failed ingest POSTs are queued and replayed by the browser when connectivity
// returns (Chromium). The in-page flusher is the universal fallback layer.
const ingestQueue = new BackgroundSyncPlugin('ingest-queue', {
  maxRetentionTime: 24 * 60,
})
registerRoute(
  ({ url, request }) =>
    request.method === 'POST' && url.pathname === '/api/v1/ingest',
  new NetworkOnly({ plugins: [ingestQueue] }),
  'POST',
)

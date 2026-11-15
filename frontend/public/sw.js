// 이음 서비스워커: 앱 셸(정적 파일)만 캐시한다.
// 원문 보호: /api 는 절대 가로채지도 저장하지도 않는다 (교사 · 학부모 응답에 원문 또는 정제문이 들어 있다).
// __BUILD_ID__ 는 빌드 때 치환된다 (vite.config.ts). 새 빌드마다 캐시 이름이 바뀌어 옛 캐시가 지워진다.
const CACHE = 'ieum-shell-__BUILD_ID__'
const SHELL = '/index.html'
const NETWORK_FIRST = new Set([SHELL, '/sw.js', '/manifest.webmanifest'])

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.filter((k) => k.startsWith('ieum-shell-') && k !== CACHE).map((k) => caches.delete(k)))
      await self.clients.claim()
    })(),
  )
})

async function put(request, response) {
  if (response.status === 200 && response.type === 'basic') {
    const cache = await caches.open(CACHE)
    await cache.put(request, response.clone())
  }
}

async function networkFirst(request, fallbackKey) {
  try {
    const response = await fetch(request)
    await put(fallbackKey || request, response)
    return response
  } catch (err) {
    const cached = await caches.match(fallbackKey || request)
    if (cached) return cached
    throw err
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached
  const response = await fetch(request)
  await put(request, response)
  return response
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api')) return // 원문 보호: respondWith 를 부르지 않고 그대로 통과

  if (request.mode === 'navigate') {
    // 화면 주소(/teacher 등)는 모두 같은 앱 셸이다. 오프라인이면 캐시된 index.html
    event.respondWith(networkFirst(request, SHELL))
    return
  }
  if (NETWORK_FIRST.has(url.pathname)) {
    event.respondWith(networkFirst(request))
    return
  }
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/') || url.pathname === '/favicon.svg') {
    event.respondWith(cacheFirst(request))
  }
  // 그 밖: 개입하지 않는다
})

// 푸시 알림을 붙일 때 이 파일에 push · notificationclick 핸들러를 추가한다 (지금은 구현하지 않음).

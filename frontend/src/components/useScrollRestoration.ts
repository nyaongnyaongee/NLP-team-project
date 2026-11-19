import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react'
import { useLocation, type Location } from 'react-router-dom'

// 하단 탭 주소. 탭마다 「초기 화면」(탭 루트)이 있고, 그 아래로 들어가면 하위 화면이다:
//   /teacher/students/5 (학생 화면) · /teacher/notices/3 · /teacher?chat=12 (대화방) · 학생 화면의 「삭제한 대화」(history state)
const TABS = new Set(['todos', 'calendar', 'students', 'notices', 'chats'])

type Screen = { tab: string; level: number; key: string }

// 화면을 (탭, 깊이, 키)로 본다. 깊이 0 = 탭의 초기 화면, 1 이상 = 그 아래 하위 화면.
function describe(loc: Location): Screen {
  const segs = loc.pathname.split('/').filter(Boolean)
  const hasTab = segs.length > 1 && TABS.has(segs[1])
  const tab = '/' + segs.slice(0, hasTab ? 2 : 1).join('/')
  const chat = new URLSearchParams(loc.search).get('chat')
  const deleted = (loc.state as { viewDeleted?: { id?: number } } | null)?.viewDeleted?.id
  const level = Math.max(segs.length - (hasTab ? 2 : 1), 0) + (chat ? 1 : 0) + (deleted ? 1 : 0)
  return { tab, level, key: loc.pathname + (chat ? `?chat=${chat}` : '') + (deleted ? `#deleted-${deleted}` : '') }
}

// 스크롤하는 곳(AppShell 의 .content)의 위치를 화면 이동에 맞춘다.
//  - 하위 화면에서 같은 탭의 상위 화면으로 돌아오면(‹ 버튼 · 브라우저 뒤로 가기) 떠날 때의 스크롤 위치로 돌아간다.
//  - 그 밖의 이동(탭 바꾸기 · 하위 화면으로 들어가기)은 맨 위에서 시작한다.
// 위치는 화면 키별로 스크롤할 때마다 적어 둔다 (화면이 바뀐 뒤에는 이미 내용이 바뀌어 읽을 수 없으므로).
// 돌아온 화면의 내용이 아직 덜 불러와져 있으면 그 길이만큼만 내려간다.
export function useScrollRestoration(scrollerRef: RefObject<HTMLElement | null>) {
  const screen = describe(useLocation())
  const current = useRef(screen)
  const positions = useRef(new Map<string, number>())

  useEffect(() => {
    const el = scrollerRef.current
    if (!el) return
    const onScroll = () => positions.current.set(current.current.key, el.scrollTop)
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [scrollerRef])

  useLayoutEffect(() => {
    const prev = current.current
    if (prev.key === screen.key) return
    current.current = screen
    const el = scrollerRef.current
    if (!el) return
    const back = prev.tab === screen.tab && prev.level > screen.level
    el.scrollTo({ top: back ? (positions.current.get(screen.key) ?? 0) : 0 })
  }, [screen, scrollerRef])
}

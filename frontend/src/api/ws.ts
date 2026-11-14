// 명세 1.6, 4.2: 서버 알림 연결. 알림에는 내용이 없고 "바뀌었다"만 알린다.
// 내용은 항상 GET 으로 다시 받는다 (원문 차단이 서버 한 곳에 있게 하려는 설계).

// 서버가 보내는 알림. 모르는 종류는 버린다.
export type ServerEvent =
  | { type: 'changed'; conversationId: number } // 대화가 바뀜
  | { type: 'notice'; noticeId: number | null } // 공지 게시 (시험용 초기화에서는 번호가 없다)

export type SocketHandlers = {
  onReady: () => void
  onEvent: (event: ServerEvent) => void
  onClose: () => void // 우리가 닫은 경우에는 부르지 않는다
}

function parseEvent(data: unknown): ServerEvent | null {
  if (!data || typeof data !== 'object') return null
  const msg = data as { type?: unknown; conversation_id?: unknown; notice_id?: unknown }
  if (msg.type === 'changed' && typeof msg.conversation_id === 'number') {
    return { type: 'changed', conversationId: msg.conversation_id }
  }
  if (msg.type === 'notice') {
    return { type: 'notice', noticeId: typeof msg.notice_id === 'number' ? msg.notice_id : null }
  }
  return null
}

// 연결을 열고, 연결을 닫는 함수를 돌려준다.
export function openSocket(token: string, handlers: SocketHandlers): () => void {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${location.host}/api/ws`) // 토큰은 주소에 넣지 않는다
  let closedByUs = false

  // 서버는 열린 뒤 5초 안에 첫 메시지로 토큰을 받지 못하면 1008 로 닫는다.
  ws.onopen = () => ws.send(JSON.stringify({ token }))

  ws.onmessage = (ev) => {
    try {
      const data: unknown = JSON.parse(String(ev.data))
      if (data && typeof data === 'object' && (data as { type?: unknown }).type === 'ready') {
        handlers.onReady()
        return
      }
      const event = parseEvent(data)
      if (event) handlers.onEvent(event)
    } catch {
      // JSON 이 아니면 무시한다.
    }
  }

  ws.onclose = () => {
    if (!closedByUs) handlers.onClose()
  }

  return () => {
    closedByUs = true
    ws.close()
  }
}

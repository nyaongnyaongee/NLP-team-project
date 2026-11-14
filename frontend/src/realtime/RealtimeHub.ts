import { openSocket, type ServerEvent } from '../api/ws'

const RETRY_MS = 3000 // 끊긴 연결을 다시 시도하는 간격 (횟수 제한은 두지 않는다)

type EventListener = (event: ServerEvent) => void
type ReadyListener = (ready: boolean) => void

// 로그인한 동안 서버 알림 연결 하나를 들고 있고, 필요한 화면들이 나눠 쓴다 (S3 의 연결을 S6 에서 재사용).
// 끊기면 3초 뒤 다시 연결을 시도한다. 연결이 없는 동안 화면은 폴링으로 대신한다 (useSync).
export class RealtimeHub {
  private events = new Set<EventListener>()
  private readyListeners = new Set<ReadyListener>()
  private ready = false
  private token: string | null = null
  private closeSocket: (() => void) | null = null
  private retryTimer: number | undefined

  isReady(): boolean {
    return this.ready
  }

  subscribe(listener: EventListener): () => void {
    this.events.add(listener)
    return () => this.events.delete(listener)
  }

  onReadyChange(listener: ReadyListener): () => void {
    this.readyListeners.add(listener)
    return () => this.readyListeners.delete(listener)
  }

  connect(token: string): void {
    this.disconnect()
    this.token = token
    this.open()
  }

  // 로그아웃하거나 화면을 떠나면 연결을 닫는다.
  disconnect(): void {
    this.token = null
    if (this.retryTimer !== undefined) {
      window.clearTimeout(this.retryTimer)
      this.retryTimer = undefined
    }
    this.closeSocket?.()
    this.closeSocket = null
    this.setReady(false)
  }

  private open(): void {
    if (this.token === null) return
    this.closeSocket = openSocket(this.token, {
      onReady: () => this.setReady(true),
      onEvent: (event) => this.events.forEach((listener) => listener(event)),
      onClose: () => {
        this.closeSocket = null
        this.setReady(false)
        if (this.token !== null) {
          this.retryTimer = window.setTimeout(() => {
            this.retryTimer = undefined
            this.open()
          }, RETRY_MS)
        }
      },
    })
  }

  private setReady(ready: boolean): void {
    if (this.ready === ready) return
    this.ready = ready
    this.readyListeners.forEach((listener) => listener(ready))
  }
}

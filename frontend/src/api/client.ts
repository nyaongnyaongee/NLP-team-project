// 모든 서버 요청이 지나는 곳 (명세 4.4-1): 토큰 붙이기, 오류 변환, 401 처리.

import { clearSession, loadSession } from '../auth/authStorage'

const API_PREFIX = '/api'

export const NETWORK_ERROR_MESSAGE = '서버에 연결할 수 없습니다'

export class ApiError extends Error {
  status: number | null // 네트워크 오류면 null

  constructor(message: string, status: number | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// 401 을 받으면 AuthContext 가 로그인 상태를 비우도록 알리는 통로.
let unauthorizedHandler: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn
}

// FastAPI 오류 모양 {"detail": "..."}; 422 는 detail 이 배열일 수 있다(명세 3.1).
function detailOf(body: unknown): string | null {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return null
}

// 명세 3.1 오류 처리 표의 문장. 화면 이동은 화면이 정하고, 여기서는 문장만 만든다.
function messageFor(status: number, detail: string | null): string {
  switch (status) {
    case 401:
      return detail ?? '로그인이 필요합니다'
    case 403:
      return '권한이 없습니다'
    case 404:
      return '찾을 수 없습니다'
    case 409:
    case 502:
    case 503:
      return detail ?? `요청에 실패했습니다 (${status})`
    case 422:
      return '입력을 확인해 주세요'
    default:
      return detail ?? `요청에 실패했습니다 (${status})`
  }
}

type Options = {
  method?: string
  json?: unknown
  // false 면 토큰을 붙이지 않고 401 을 "로그아웃"으로 취급하지 않는다 (로그인 요청용).
  auth?: boolean
}

export async function request<T>(path: string, opts: Options = {}): Promise<T> {
  const { method = 'GET', json, auth = true } = opts

  const headers: Record<string, string> = {}
  if (json !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const session = loadSession()
    if (session) headers['Authorization'] = `Bearer ${session.token}`
  }

  let res: Response
  try {
    res = await fetch(API_PREFIX + path, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    })
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, null)
  }

  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // 본문이 없거나 JSON 이 아니면 body 는 null 로 둔다.
  }

  if (!res.ok) {
    const detail = detailOf(body)
    // 서버가 꺼져 있으면 개발 서버 프록시가 본문 없는 502 를 돌려준다. 서버 자신의 502(AI 실패)는
    // detail 문장이 있으므로, detail 이 없는 502/504 만 "연결할 수 없음"으로 본다.
    if ((res.status === 502 || res.status === 504) && detail === null) {
      throw new ApiError(NETWORK_ERROR_MESSAGE, null)
    }
    if (res.status === 401 && auth) {
      clearSession()
      unauthorizedHandler?.()
    }
    throw new ApiError(messageFor(res.status, detail), res.status)
  }
  return body as T
}

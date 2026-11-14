import { request } from './client'

export type HealthRes = { ok: boolean }

export function getHealth(): Promise<HealthRes> {
  return request<HealthRes>('/health')
}

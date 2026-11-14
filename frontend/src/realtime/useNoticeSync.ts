import { useSync } from './useSync'

// 공지 목록을 최신으로 유지한다: {"type":"notice","notice_id":N} 이 오면 목록을 다시 읽는다 (S3 의 연결을 재사용).
export function useNoticeSync(refresh: () => void) {
  useSync('notices', refresh, (e) => e.type === 'notice')
}

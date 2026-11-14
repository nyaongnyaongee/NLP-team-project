import AppShell from '../../components/AppShell'

// 민원이관팀 화면: 서버 설계가 합의되기 전까지는 빈 화면과 "준비 중" 안내입니다 (명세 S10).
export default function TeamHome() {
  return (
    <AppShell title="민원이관팀">
      <div className="empty">
        <div className="big">▤</div>
        민원이관팀 화면은 준비 중이에요
      </div>
    </AppShell>
  )
}

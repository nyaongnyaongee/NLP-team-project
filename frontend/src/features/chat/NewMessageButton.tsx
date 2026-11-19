// 위를 보는 중에 새 메시지가 왔을 때 입력창 위에 뜨는 버튼. 부모(.chat-compose, sticky) 안에 두면 입력창 바로 위에 붙는다.
// 개수는 보이지 않는다. 스크린 리더에는 나타날 때 「새 메시지」를 읽어 준다.
export default function NewMessageButton({ visible, onClick }: { visible: boolean; onClick: () => void }) {
  return (
    <div className="new-message-wrap" role="status" aria-live="polite">
      {visible && (
        <button type="button" className="new-message-btn" onClick={onClick}>
          ↓ 새 메시지
        </button>
      )}
    </div>
  )
}

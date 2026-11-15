# 시연 접속 환경 (HTTPS · Tailscale · PWA) — 직접 할 일

서버 PC 한 대가 앱을 켜고, 다른 폰(안드로이드·아이폰)이 `https://<호스트>.<tailnet>.ts.net` 으로 접속합니다.
같은 Tailscale 계정(tailnet)에 들어 있는 기기만 접속할 수 있고, 인터넷에 공개되지 않습니다 (Funnel · 포트포워딩을 쓰지 않습니다).

```
폰 ─https/wss─▶ tailscale serve (:443) ─http/ws─▶ uvicorn app.server:app (127.0.0.1:8000)
                                                    ├─ /api/*  → 기존 API
                                                    └─ 그 외   → frontend/dist
```

아래를 **순서대로** 하고, 각 단계의 확인 명령 결과가 맞는지 봅니다.

## 1. Tailscale 설치·로그인
- [ ] 서버 PC와 폰 2대에 Tailscale 을 설치하고 **같은 계정**으로 로그인
- 확인 (서버 PC):
  ```powershell
  tailscale status
  ```
  서버 PC와 폰들이 목록에 보이면 됩니다.

## 2. 관리 콘솔 설정 (https://login.tailscale.com/admin/dns)
- [ ] **MagicDNS** 켜기
- [ ] **HTTPS Certificates** 켜기
- 알아 둘 것: 인증서를 받으면 기기의 전체 이름(`<호스트>.<tailnet>.ts.net`)이 공개 인증서 투명성 로그에 남습니다.
- 확인: 관리 콘솔 DNS 화면에서 두 항목이 켜져 있는지 봅니다.

## 3. 기기 이름
- [ ] 서버 PC의 Tailscale 기기 이름을 **바꾸지 않습니다** (인증서 호스트명이 기기 이름 기반)
- [ ] 이름에 개인 이름·학교 이름 같은 정보가 들어 있지 않은지 확인 (공개 로그에 남기 때문)
- 확인: `tailscale status` 의 서버 PC 이름

## 4. 서버 PC 설정
- [ ] Tailscale 의 **Run unattended** 켜기 (로그아웃해도 연결 유지)
- [ ] 절전 · 최대 절전 끄기 (전원 옵션에서 "절전 모드: 사용 안 함")
- [ ] Windows 방화벽에 **인바운드 규칙을 추가하지 않습니다** (백엔드는 127.0.0.1 에만 열립니다)
- [ ] PostgreSQL 서비스 시작 유형을 **자동**으로
- 확인:
  ```powershell
  Get-Service postgresql*
  powercfg /query SCHEME_CURRENT SUB_SLEEP
  ```

## 5. 빌드 → 기동
```powershell
cd frontend
npm run build          # frontend\dist 를 덮어씁니다
cd ..
powershell -ExecutionPolicy Bypass -File deploy\start-demo.ps1
tailscale serve status
```
- 스크립트가 사전 점검 → DB → 8000 포트 → 백엔드 → `tailscale serve` → 자체 점검까지 합니다.
- 마지막에 `폰에서 열 주소: https://...ts.net` 이 나오면 성공입니다.
- 이전 시험용 매핑이 남아 있으면 스크립트가 보여 주고 **물어본 뒤에만** 해제합니다.
- 끄기: `powershell -ExecutionPolicy Bypass -File deploy\start-demo.ps1 -Stop`
- 확인 (서버 PC, 선택): `curl.exe -I https://<호스트>.<tailnet>.ts.net/` 가 200 계열이고, `curl.exe -si https://<호스트>.<tailnet>.ts.net/api/conversations` 가 **401** (307 리다이렉트가 아님) 이면 정상입니다.

## 6. 폰에서 접속·설치
**안드로이드 (Chrome)**
- [ ] Tailscale 앱 켜기 → Chrome 으로 위 주소 접속 → 로그인
- [ ] 메뉴 ⋮ → **앱 설치** → 홈 화면 아이콘으로 실행 (주소창이 없으면 성공)

**아이폰 (Safari 만 가능)**
- [ ] Tailscale 앱 켜기 → **Safari** 로 접속 → 로그인
- [ ] 공유 버튼 → **홈 화면에 추가** → 홈 화면 아이콘으로 실행
- 이 경로는 아직 실기기에서 확인된 적이 없습니다. 결과를 그대로 기록해 주세요.

설치형 앱을 완전히 종료하면 다시 로그인해야 할 수 있습니다 (로그인 정보를 탭 단위로만 보관하기 때문 — 원문 보호를 위한 현행 동작).
옛 화면이 남으면: 안드로이드는 앱 정보 → 저장공간 → 데이터·캐시 삭제, 아이폰은 앱 삭제 후 다시 추가.

## 7. 경고
- 같은 tailnet 에 들어 있는 **다른 기기도 이 서버에 닿을 수 있습니다.** tailnet 에 시연과 무관한 기기가 없는지 확인하세요.
- 시드(시험용) 계정의 비밀번호는 고정값입니다. 시연 전에 따로 처리해야 합니다 (이 문서에는 적지 않습니다).

## 8. 인증서 만료 점검
인증서 유효기간은 90일이고 Serve 경로의 자동 갱신은 아직 확인하지 못했습니다.
- [ ] 시연 **3일 전 · 전날 · 당일** 폰 브라우저에서 주소창 자물쇠 → 인증서 만료일 확인
- [ ] 관리 콘솔 Machines 에서 서버 PC의 기기 키 만료일이 시연일 이후인지 확인 (기본 180일)

## 참고: 아이콘
`frontend/public/icons/*` 와 `apple-touch-icon.png` 는 **임시 아이콘**입니다 (`frontend/scripts/make_icons.py` 로 생성). 정식 아이콘으로 파일만 바꾸면 됩니다.
`frontend/public/favicon.svg` 는 아직 Vite 기본 로고입니다.

---

# 공개 주소 + QR 로 시연 (Tailscale Funnel) — 폰에 아무것도 안 깔기

위 절차(serve)는 **같은 tailnet 기기만** 접속됩니다. 관객 폰마다 Tailscale 을 깔 수 없으니, 시연 때는 `-Funnel` 로 켭니다.
Funnel 주소는 **인터넷 누구나** 접속할 수 있습니다 (켜 둔 동안만). 주소는 serve 와 같습니다 (`https://<호스트>.<tailnet>.ts.net`).

## 처음 한 번 (위 1~4번에 더해)
- [ ] 서버 PC에만 Tailscale 설치 · 로그인 (관객 폰에는 필요 없음)
- [ ] 기기 이름에 개인 이름이 없게 (예: `eum-demo`). 공개 주소 · QR 에 그대로 보입니다 (3번)
- [ ] 처음 `-Funnel` 로 켜면 Funnel 허용 링크가 나옵니다 → 열어서 허용 → 다시 실행

## 매번
```powershell
cd frontend; npm run build; cd ..        # 화면을 바꿨을 때만 (또는 -Build)
powershell -ExecutionPolicy Bypass -File deploy\start-demo.ps1 -Funnel
```
- 마지막에 `폰에서 열 주소: https://...ts.net` 이 나오면 성공
- **QR**: PC 의 Edge 나 Chrome 으로 그 주소를 열고 주소창의 공유(또는 QR) 아이콘 → QR 코드 → 이미지 저장. 주소가 바뀌지 않으니 한 번 만들어 발표 자료에 넣어 두면 됩니다
- 끄기 (**반드시**): `powershell -ExecutionPolicy Bypass -File deploy\start-demo.ps1 -Stop` — 백엔드와 공개 주소를 같이 닫습니다. 끄지 않으면 계속 공개된 채로 남습니다

## 알아 둘 것 (실제로 해 본 결과, 2026-11-15 · 맥 + 아이폰)
- 켠 직후 몇 분은 일부 폰에서 「보안 연결을 할 수 없음」이 납니다 (공개 중계 서버 일부에 설정이 늦게 퍼짐). **시연 10분 전에 켜고 폰으로 한 번 열어 보기**
- 켜자마자 인터넷 봇이 `/graphql` 같은 주소를 찔러 봅니다 (모두 404/405 로 막힘). 시드 계정 비밀번호가 고정값이니 진짜 내용은 넣지 않기
- 학부모 글마다 Claude 정제 비용(약 $0.006)이 듭니다. 콘솔에 사용 한도를 걸어 두기
- 여럿이 같은 계정으로 들어오면 대화가 섞입니다 → 학부모 계정 `parent1`~`parent20` 을 나눠 주기
- 아이폰은 **홈 화면에 추가한 앱**으로 쓰기. Safari 탭에서는 대화 목록을 밀어 나온 「삭제」를 눌러도 확인 창이 안 뜹니다 (원인 미확인)
- PC 가 잠들면 끊깁니다 (위 4번 절전 끄기)

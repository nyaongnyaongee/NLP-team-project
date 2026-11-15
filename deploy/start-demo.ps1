# 이음 시연 기동 스크립트 (Windows PowerShell 5.1)
#
#   켜기:  powershell -ExecutionPolicy Bypass -File deploy\start-demo.ps1            (프런트를 새로 빌드하려면 -Build)
#   끄기:  powershell -ExecutionPolicy Bypass -File deploy\start-demo.ps1 -Stop
#
# 하는 일: 사전 점검 -> PostgreSQL 서비스 -> 8000 포트 확인 -> 백엔드(app.server) 기동 -> 상태 확인
#          -> tailscale serve(https 443 -> 127.0.0.1:8000) -> 자체 점검(/api/dev/* 가 막혀 있는지)
# 비밀 값(.env 내용, 토큰)은 출력하거나 기록하지 않는다. tailscale funnel(공개 노출)은 쓰지 않는다.
param(
    [switch]$Build,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$Root     = Split-Path -Parent $PSScriptRoot
$Backend  = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$RunDir   = Join-Path $PSScriptRoot 'run'
$LogDir   = Join-Path $PSScriptRoot 'logs'
$PidFile  = Join-Path $RunDir 'uvicorn.pid'
$Port     = 8000
$Base     = "http://127.0.0.1:$Port"

function Fail([string]$what, [string]$next) {
    Write-Host ""
    Write-Host "[실패] $what" -ForegroundColor Red
    if ($next) { Write-Host "       다음 행동: $next" -ForegroundColor Yellow }
    exit 1
}
function Ok([string]$msg)   { Write-Host "[확인] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "[주의] $msg" -ForegroundColor Yellow }
function Step([string]$msg) { Write-Host ""; Write-Host "== $msg" -ForegroundColor Cyan }

function Find-Tailscale {
    $cmd = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $default = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
    if (Test-Path $default) { return $default }
    return $null
}

# 응답 코드만 돌려준다 (404 등도 예외 없이). 연결 자체가 안 되면 0.
function Get-HttpStatus([string]$method, [string]$url) {
    try {
        $r = Invoke-WebRequest -Uri $url -Method $method -UseBasicParsing -TimeoutSec 5
        return [int]$r.StatusCode
    } catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return 0
    }
}

function Get-DemoProcess {
    if (-not (Test-Path $PidFile)) { return $null }
    $id = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $id) { return $null }
    $p = Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue
    if (-not $p) { return $null }
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue
    if ($cim -and $cim.CommandLine -match 'app\.server:app') { return $p }
    return $null   # PID 가 재사용된 다른 프로그램이면 건드리지 않는다
}

$ts = Find-Tailscale

# ------------------------------------------------------------------ 끄기
if ($Stop) {
    Step '시연 서버 끄기'
    $p = Get-DemoProcess
    if ($p) { Stop-Process -Id $p.Id -Force; Ok "백엔드(PID $($p.Id))를 껐습니다." } else { Warn '이 스크립트가 켠 백엔드가 없습니다.' }
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
    if ($ts) {
        Warn 'tailscale serve(443) 설정을 해제합니다.'
        & $ts serve --https=443 off
    }
    exit 0
}

# ------------------------------------------------------------------ 1. 사전 점검
Step '1. 사전 점검'
$envFile = Join-Path $Backend '.env'
if (-not (Test-Path $envFile)) { Fail 'backend\.env 가 없습니다.' 'backend 폴더에서 .env.example 을 .env 로 복사하고 값을 채우세요.' }

$envValues = @{}
foreach ($line in (Get-Content $envFile -Encoding UTF8)) {
    $t = $line.Trim()
    if ($t -and -not $t.StartsWith('#') -and $t.Contains('=')) {
        $k, $v = $t.Split('=', 2)
        $envValues[$k.Trim().ToUpper()] = $v.Trim()
    }
}
if (-not $envValues['JWT_SECRET']) { Fail 'backend\.env 의 JWT_SECRET 이 비어 있습니다.' '.env.example 안내대로 긴 임의 문자열을 넣으세요. (값은 이 화면에 출력하지 않습니다)' }
if ($envValues.ContainsKey('DEV_TOOLS') -or $env:DEV_TOOLS) {
    Fail 'DEV_TOOLS 가 설정되어 있습니다 (backend\.env 또는 환경 변수). 시연 서버에서는 /dev/reset 등을 열면 안 됩니다.' '.env 에서 DEV_TOOLS 줄을 지우고, 이 창의 환경 변수는 Remove-Item Env:DEV_TOOLS 로 지운 뒤 다시 실행하세요.'
}
Ok '.env 확인 (JWT_SECRET 있음, DEV_TOOLS 없음)'

$py = Join-Path $Backend '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { Fail "$py 가 없습니다." 'README 대로 backend\.venv 를 먼저 만드세요.' }
Ok 'backend\.venv 확인'

if ($Build) {
    Warn 'frontend\dist 를 새로 빌드합니다 (기존 dist 는 덮어씁니다).'
    Push-Location $Frontend
    try { & npm run build; if ($LASTEXITCODE -ne 0) { Fail 'npm run build 가 실패했습니다.' '위 오류 메시지를 확인하세요.' } } finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $Frontend 'dist\index.html'))) {
    Fail 'frontend\dist\index.html 이 없습니다.' 'frontend 폴더에서 npm run build 를 하거나, 이 스크립트를 -Build 로 다시 실행하세요.'
}
Ok 'frontend\dist 확인'

# ------------------------------------------------------------------ 2. DB
Step '2. PostgreSQL'
$svc = @(Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue)
if ($svc.Count -eq 0) {
    Warn 'postgresql 로 시작하는 Windows 서비스를 찾지 못했습니다. 5432 포트로 대신 확인합니다.'
    $listening = Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue
    if (-not $listening) { Fail 'PostgreSQL 이 꺼져 있는 것 같습니다 (5432 포트).' 'services.msc 에서 PostgreSQL 을 시작하거나 설치를 확인하세요.' }
    Ok '5432 포트가 열려 있습니다.'
} else {
    foreach ($s in $svc) {
        if ($s.Status -ne 'Running') {
            Warn "$($s.Name) 서비스가 중지 상태입니다. 시작합니다."
            try { Start-Service -Name $s.Name; $s.WaitForStatus('Running', [TimeSpan]::FromSeconds(20)) }
            catch { Fail "$($s.Name) 서비스를 시작하지 못했습니다." '관리자 권한 PowerShell 로 다시 실행하거나 services.msc 에서 직접 시작하세요.' }
        }
        Ok "$($s.Name) 실행 중"
    }
}

# ------------------------------------------------------------------ 3. 포트
Step "3. $Port 포트"
$old = Get-DemoProcess
if ($old) { Warn "이전에 켠 시연 서버(PID $($old.Id))를 먼저 끕니다."; Stop-Process -Id $old.Id -Force; Start-Sleep -Seconds 1 }
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    $owner = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
    Warn "$Port 포트를 쓰는 프로그램이 있습니다: $($owner.ProcessName) (PID $($conn.OwningProcess))"
    if ($cim) { Write-Host "       명령: $($cim.CommandLine)" }
    $answer = Read-Host '이 프로그램을 종료하고 계속할까요? (y/N)'
    if ($answer -ne 'y') { Fail "$Port 포트가 사용 중입니다." '그 프로그램을 직접 끄고 다시 실행하세요.' }
    Stop-Process -Id $conn.OwningProcess -Force
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { Fail "$Port 포트가 아직 사용 중입니다." '관리자 권한으로 다시 시도하세요.' }
}
Ok "$Port 포트 비어 있음"

# ------------------------------------------------------------------ 4. 백엔드
Step '4. 백엔드 기동'
New-Item -ItemType Directory -Force $RunDir, $LogDir | Out-Null
$out = Join-Path $LogDir 'backend.out.log'
$err = Join-Path $LogDir 'backend.err.log'
$proc = Start-Process -FilePath $py `
    -ArgumentList '-m', 'uvicorn', 'app.server:app', '--host', '127.0.0.1', '--port', "$Port" `
    -WorkingDirectory $Backend -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $out -RedirectStandardError $err
Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII
Ok "백엔드 시작 (PID $($proc.Id), 로그: deploy\logs\)"

# ------------------------------------------------------------------ 5. 상태 대기
Step '5. 상태 확인 (최대 30초)'
$up = $false
for ($i = 0; $i -lt 30; $i++) {
    if ($proc.HasExited) { Fail '백엔드가 바로 종료되었습니다.' "deploy\logs\backend.err.log 의 마지막 줄을 확인하세요." }
    if ((Get-HttpStatus 'GET' "$Base/api/health") -eq 200) { $up = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $up) { Fail '30초 안에 /api/health 가 200 을 돌려주지 않았습니다.' 'deploy\logs\backend.err.log 를 확인하세요 (DB 연결 문제가 가장 흔합니다).' }
Ok '/api/health 200'

# ------------------------------------------------------------------ 6. Tailscale Serve
Step '6. Tailscale Serve (https 443 -> 127.0.0.1:8000)'
if (-not $ts) { Fail 'tailscale 명령을 찾지 못했습니다.' 'Tailscale 을 설치하고 로그인하세요. (deploy\README.md 1번)' }
$help = & { $ErrorActionPreference = 'Continue'; & $ts serve --help 2>&1 | Out-String }
if ($help -notmatch '--bg' -or $help -notmatch '--https') {
    Fail '설치된 Tailscale 의 serve 문법이 예상과 다릅니다 (--bg / --https 옵션 없음).' 'tailscale serve --help 를 확인하고 이 스크립트의 6단계 명령을 맞추세요.'
}
$status = & { $ErrorActionPreference = 'Continue'; & $ts serve status 2>&1 | Out-String }
$rootMap = $status -split "`r?`n" | Where-Object { $_ -match '^\s*\|--\s+/\s' } | Select-Object -First 1
$target = "127.0.0.1:$Port"
if ($rootMap -and $rootMap -notmatch [regex]::Escape($target)) {
    Warn "기존 Serve 매핑이 다른 곳을 가리킵니다 (이전 시험용일 수 있음): $($rootMap.Trim())"
    $answer = Read-Host '이 매핑을 해제하고 새로 설정할까요? (y/N)'
    if ($answer -ne 'y') { Fail '기존 Serve 매핑이 남아 있습니다.' 'tailscale serve status 로 확인한 뒤 직접 정리하고 다시 실행하세요.' }
    & $ts serve --https=443 off
}
& $ts serve --bg --https=443 "http://$target"
if ($LASTEXITCODE -ne 0) { Fail 'tailscale serve 설정에 실패했습니다.' 'tailscale status 로 로그인 상태를, 관리 콘솔에서 MagicDNS / HTTPS Certificates 가 켜져 있는지 확인하세요.' }
Ok 'tailscale serve 설정 완료'

# ------------------------------------------------------------------ 7. 자체 점검
Step '7. 자체 점검'
$dev = Get-HttpStatus 'POST' "$Base/api/dev/reset"
if ($dev -ne 404) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Warn 'tailscale serve 를 해제합니다 (안전하지 않은 상태).'
    & $ts serve --https=443 off
    Fail "/api/dev/reset 이 404 가 아니라 $dev 를 돌려주었습니다. 서버를 껐습니다." 'DEV_TOOLS 설정이 남아 있지 않은지 확인하세요.'
}
Ok '/api/dev/reset 404 (차단됨)'
if ((Get-HttpStatus 'GET' "$Base/api/health") -ne 200) { Fail '/api/health 가 200 이 아닙니다.' '로그를 확인하세요.' }
Ok '/api/health 200'
$final = & { $ErrorActionPreference = 'Continue'; & $ts serve status 2>&1 | Out-String }
Write-Host $final

# ------------------------------------------------------------------ 8. 안내
Step '8. 완료'
$url = [regex]::Match($final, 'https://[A-Za-z0-9.\-]+\.ts\.net').Value
if ($url) { Write-Host "폰에서 열 주소: $url" -ForegroundColor Green } else { Warn '주소를 상태 출력에서 찾지 못했습니다. 위 tailscale serve status 를 보세요.' }
Write-Host '폰은 Tailscale 앱이 켜져 있어야 접속됩니다. 설치(홈 화면 추가) 방법은 deploy\README.md 6번.'
Write-Host '끄기: powershell -ExecutionPolicy Bypass -File deploy\start-demo.ps1 -Stop'

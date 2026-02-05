---
name: kis-health
description: KIS API 연결 상태, 토큰 유효성, 계좌 접근 가능 여부 확인
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
---

# KIS API 헬스체크 스킬

**사용법:** `/kis-health` 또는 `kis-health`를 입력하면 실행됩니다.

## 검증 항목

### 1. 환경 설정 확인
- Excel B12-B14 값 읽기
- APP KEY, APP SECRET 존재 확인

### 2. API 연결 테스트
- **토큰 발급**: `/oauth2/tokenP` 엔드포인트 호출
- **응답 시간**: 1초 이내 (정상), 3초 이상 (경고)
- **인증 상태**: 200 OK / 401 Unauthorized

### 3. 계좌 조회 테스트
- 계좌 잔고 조회 API 호출
- 응답 JSON 파싱
- 계좌 유효성 확인

### 4. 실시간 시세 WebSocket (선택)
- WebSocket 연결 가능 여부
- Ping/Pong 응답

## 실행 단계

### 1단계: Python 헬스체크 스크립트 실행
```bash
python .claude/scripts/kis_health_check.py
```

### 2단계: 결과 분석
- ✅ 모든 연결 정상
- ⚠️ 토큰 발급 실패 (APP KEY/SECRET 확인)
- ❌ 네트워크 오류 (방화벽, VPN 확인)

### 3단계: 리포트 생성
검증 결과를 `.claude/logs/KIS-Health-Report.md`에 저장합니다.

## 성공 조건
- [ ] 토큰 발급 성공 (200 OK)
- [ ] 계좌 조회 성공
- [ ] 응답 시간 < 2초
- [ ] API Rate Limit 확인

## 주의사항
- 실제 계좌 정보가 노출되지 않도록 로그에서 마스킹 처리
- API Key는 절대 로그에 출력하지 않음

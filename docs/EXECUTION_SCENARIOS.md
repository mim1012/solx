# Phoenix Trading System - 실행 시나리오 스토리

**작성일**: 2026-01-24
**버전**: v4.1
**목적**: 실제 거래 상황 시뮬레이션 및 시스템 동작 이해

---

## 목차
1. [시나리오 1: 첫 실행 및 정상 거래 흐름](#시나리오-1-첫-실행-및-정상-거래-흐름)
2. [시나리오 2: 급락 상황 - 배치 매수](#시나리오-2-급락-상황---배치-매수)
3. [시나리오 3: 갭 상승 - Tier 1 커스텀 모드](#시나리오-3-갭-상승---tier-1-커스텀-모드)
4. [시나리오 4: 에러 복구 시나리오](#시나리오-4-에러-복구-시나리오)
5. [시나리오 5: 장 마감 및 재시작](#시나리오-5-장-마감-및-재시작)
6. [시나리오 6: 수익 실현 및 Tier 1 갱신](#시나리오-6-수익-실현-및-tier-1-갱신)

---

## 시나리오 1: 첫 실행 및 정상 거래 흐름

### 배경
- **일시**: 2026년 1월 24일 금요일
- **사용자**: 개인 투자자 (투자금 $5,000)
- **목표**: SOXL 그리드 트레이딩으로 변동성 수익 창출

### Excel 설정 (phoenix_grid_template_v3.xlsx)

```
B3: ticker = "SOXL"
B4: investment_usd = $5,000.00
B5: total_tiers = 240
B6: tier_amount = $20.83 (자동 계산: $5,000 / 240)
B7: tier1_auto_update = TRUE
B8: tier1_trading_enabled = FALSE (기본 모드)
B9: buy_limit = FALSE
B10: sell_limit = FALSE
B12: kis_app_key = "PSekfJ3YO9A0R..." (실제 키)
B13: kis_app_secret = "qZx8nL4mP..." (실제 시크릿)
B14: kis_account_no = "12345678-01"
B15: system_running = TRUE ★ (시스템 시작!)
B16: price_check_interval = 40.0 (40초)
B20: telegram_enabled = TRUE
```

---

### 타임라인

#### 19:00:00 - 시스템 시작

**사용자 액션**:
```bash
D:\Project\SOLX> PhoenixTrading.exe phoenix_grid_template_v3.xlsx
```

**콘솔 출력**:
```
============================================================
Phoenix Trading System v4.1 (KIS REST API)
SOXL 자동매매 시스템
============================================================

[WARNING] 경고: 이 시스템은 실제 자금으로 SOXL을 거래합니다.
[WARNING] 손실 위험이 있으며, 투자 책임은 사용자에게 있습니다.

[INFO] 2026-01-24 19:00:00 - __main__ - Phoenix Trading System v4.1 초기화
============================================================
[INFO] 2026-01-24 19:00:01 - excel_bridge - Excel 파일 로드 성공: D:\Project\SOLX\phoenix_grid_template_v3.xlsx
[INFO] 2026-01-24 19:00:02 - excel_bridge - [AUTO] 티어당 투자금 자동 계산: $20.83 = $5,000 / 240 tiers
[INFO] 2026-01-24 19:00:02 - grid_engine - [기본 모드] Tier 1은 추적 전용, Tier 2부터 매수 시작
```

#### 19:00:03 - KIS API 인증

**내부 동작**:
```python
kis_adapter.login()
```

**로그 출력**:
```
[INFO] 2026-01-24 19:00:03 - kis_rest_adapter - KisRestAdapter 초기화 완료
[INFO] 2026-01-24 19:00:04 - kis_rest_adapter - Access Token 발급 성공 (만료: 2026-01-25 19:00:04)
[INFO] 2026-01-24 19:00:05 - kis_rest_adapter - Approval Key 발급 성공
[INFO] 2026-01-24 19:00:05 - kis_rest_adapter - [캐시] 토큰 저장 완료: kis_token_cache.json
[INFO] 2026-01-24 19:00:05 - __main__ - [OK] KIS API 로그인 성공
```

**kis_token_cache.json 생성**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2026-01-25T19:00:04",
  "approval_key": "abc123def456",
  "cached_at": "2026-01-24T19:00:05"
}
```

#### 19:00:06 - 초기 시세 조회

**KIS API 요청**:
```http
GET https://openapi.koreainvestment.com:9443/uapi/overseas-price/v1/quotations/price
Params: EXCD=NAS, SYMB=SOXL
```

**응답**:
```json
{
  "rt_cd": "0",
  "output": {
    "last": "",  // 비어있음 (NAS 거래소에 없음)
    ...
  }
}
```

**로그 출력**:
```
[DEBUG] 2026-01-24 19:00:06 - kis_rest_adapter - SOXL: NAS 거래소에서 시세 없음 (다음 거래소 시도)
```

**KIS API 재시도** (AMS 거래소):
```http
GET .../quotations/price
Params: EXCD=AMS, SYMB=SOXL
```

**응답**:
```json
{
  "rt_cd": "0",
  "output": {
    "last": "50.30",
    "open": "49.80",
    "high": "50.50",
    "low": "49.60",
    "tvol": "2345678"
  }
}
```

**로그 출력**:
```
[INFO] 2026-01-24 19:00:07 - kis_rest_adapter - [거래소 자동 감지] SOXL는 AMS 거래소에서 조회됨
[INFO] 2026-01-24 19:00:07 - __main__ -   - 현재가: $50.30
[INFO] 2026-01-24 19:00:07 - __main__ -   - 시가: $49.80
[INFO] 2026-01-24 19:00:07 - __main__ -   - 고가: $50.50
[INFO] 2026-01-24 19:00:07 - __main__ -   - 저가: $49.60
```

#### 19:00:08 - 계좌 잔고 조회

**KIS API 요청**:
```http
GET .../trading/inquire-balance
Params: CANO=12345678, ACNT_PRDT_CD=01, OVRS_EXCG_CD=NASD, TR_CRCY_CD=USD
```

**응답**:
```json
{
  "rt_cd": "0",
  "output2": {
    "frcr_dncl_amt_2": "5000.00"
  }
}
```

**로그 출력**:
```
[INFO] 2026-01-24 19:00:08 - __main__ -   - 예수금: $5,000.00
```

#### 19:00:09 - GridEngine 초기화

**내부 동작**:
```python
grid_engine.tier1_price = 50.30  # 현재가로 초기화
grid_engine.account_balance = 5000.00
grid_engine.current_price = 50.30
```

**로그 출력**:
```
[INFO] 2026-01-24 19:00:09 - __main__ - GridEngine 초기화 중...
[INFO] 2026-01-24 19:00:09 - __main__ - [OK] 텔레그램 알림 활성화
============================================================
[OK] 시스템 초기화 완료!
============================================================
```

**텔레그램 알림 (사용자 폰)**:
```
🚀 Phoenix Trading 시작
━━━━━━━━━━━━━━━━
📊 종목: SOXL
💰 투자금: $5,000.00
📍 현재가: $50.30
🎯 Tier 1: $50.30
━━━━━━━━━━━━━━━━
⏰ 2026-01-24 19:00:09
```

#### 19:00:10 - 시장 개장 시간 확인

**내부 동작**:
```python
is_open, message = _is_market_open()
# 현재: 금요일 19:00 (한국 시간)
# 미국 정규장: 금요일 05:00 (동부시간, 한국보다 14시간 느림)
```

**로그 출력**:
```
============================================================
시장 개장 시간 확인 중...
============================================================
[WAIT] 장 마감. 다음 개장: 23:30
[대기 중] 장 마감. 다음 개장: 23:30 - 19:00:10
```

**콘솔 대기** (4시간 30분):
```
[대기 중] 장 마감. 다음 개장: 23:30 - 19:01:10
[대기 중] 장 마감. 다음 개장: 23:30 - 19:02:10
...
[대기 중] 장 마감. 다음 개장: 23:30 - 23:28:10
[대기 중] 장 마감. 다음 개장: 23:30 - 23:29:10
```

#### 23:30:00 - 시장 개장 감지

**로그 출력**:
```
[INFO] 2026-01-24 23:30:00 - __main__ - [OK] 장 개장 중

============================================================
메인 거래 루프 시작...
종료하려면 Ctrl+C를 누르세요.
============================================================
```

#### 23:30:01 - 첫 시세 조회 (거래 루프 #1)

**KIS API 요청**:
```http
GET .../quotations/price
Params: EXCD=AMS, SYMB=SOXL
```

**응답**:
```json
{
  "rt_cd": "0",
  "output": {
    "last": "50.00"  // 시가: $50.00 (장 시작)
  }
}
```

**GridEngine 처리**:
```python
signals = grid_engine.process_tick(current_price=50.00)

# 1. Tier 1 갱신 확인
update_tier1(50.00)
# 조건: tier1_auto_update=TRUE, positions=[], current_price < tier1_price
# 50.00 < 50.30 → 갱신 안 함 (하락 중)

# 2. 매도 배치 확인
# positions = [] → 매도 신호 없음

# 3. 매수 배치 확인
start_tier = 2  # tier1_trading_enabled=FALSE
for tier in range(2, 241):
    if 포지션 없음 and current_price ≤ tier_price and 잔고 충분:
        매수 배치에 추가

# Tier 2: 50.30 × (1 - 0.005) = 50.0485 ≥ 50.00 → X
# Tier 3: 50.30 × (1 - 0.010) = 49.797 < 50.00 → X
# ...
# → 매수 신호 없음
```

**로그 출력**:
```
[DEBUG] 2026-01-24 23:30:01 - grid_engine - 현재 티어: 2 (Tier 1: $50.30, 현재가: $50.00)
[DEBUG] 2026-01-24 23:30:01 - grid_engine - 매수/매도 신호 없음
```

**대기**:
```python
time.sleep(40)  # price_check_interval
```

#### 23:30:41 - 두 번째 시세 조회 (거래 루프 #2)

**KIS API 응답**:
```json
{
  "output": {
    "last": "49.50"  // 하락: -$0.80 (-1.6%)
  }
}
```

**GridEngine 처리**:
```python
signals = grid_engine.process_tick(current_price=49.50)

# Tier 3: 49.797 ≥ 49.50 → O (매수 조건 충족!)
# Tier 4: 49.5455 ≥ 49.50 → O
# Tier 5: 49.294 < 49.50 → X

매수 배치 = [
    (tier=3, quantity=10),  # $20.83 / $49.50 = 0.42 → 1주 (최소)
    (tier=4, quantity=10)
]
```

**로그 출력**:
```
[DEBUG] 2026-01-24 23:30:41 - grid_engine - 매수 배치 추가: Tier 3, 1주
[DEBUG] 2026-01-24 23:30:41 - grid_engine - 매수 배치 추가: Tier 4, 1주
[INFO] 2026-01-24 23:30:41 - grid_engine - [BATCH BUY] 2개 티어, 총 2주 @ $49.50 (비용: $99.00)
```

**매매 신호**:
```python
TradeSignal(
    action="BUY",
    tier=3,
    tiers=(3, 4),
    price=49.50,
    quantity=2,
    reason="배치 매수 2개 티어"
)
```

#### 23:30:42 - 매수 주문 실행

**phoenix_main.py 처리**:
```python
_process_signal(signal)
```

**로그 출력**:
```
[INFO] 2026-01-24 23:30:42 - __main__ - [BATCH BUY] 배치 매수 신호: Tiers (3, 4), 총 2주 @ $49.50
```

**KIS API 매수 주문**:
```http
POST .../trading/order

Headers:
{
  "tr_id": "JTTT1002U",
  "hashkey": "abc123...",
  ...
}

Body:
{
  "CANO": "12345678",
  "ACNT_PRDT_CD": "01",
  "OVRS_EXCG_CD": "NASD",
  "PDNO": "SOXL",
  "ORD_QTY": "2",
  "OVRS_ORD_UNPR": "49.50",  // 지정가
  "ORD_DVSN": "00"  // 지정가 매수
}
```

**응답**:
```json
{
  "rt_cd": "0",
  "output": {
    "ODNO": "0000123456",  // 주문번호
    "AVG_PRVS": "0.00",    // 체결가 (아직 미체결)
    "TOT_CCLD_QTY": "0"    // 체결 수량 0
  },
  "msg1": "정상처리되었습니다."
}
```

**로그 출력**:
```
[INFO] 2026-01-24 23:30:43 - kis_rest_adapter - 주문 성공: buy SOXL - 주문 2주 @ $49.50, 체결 0주 @ $0.00 (주문번호: 0000123456)
[INFO] 2026-01-24 23:30:43 - __main__ - [ORDER] 주문 접수 완료: Tier 3, 주문번호 0000123456
```

#### 23:30:44~23:30:58 - 체결 확인 (폴링)

**phoenix_main.py**:
```python
filled_price, filled_qty = _wait_for_fill("0000123456", expected_qty=2)
```

**폴링 루프** (10회 × 2초 간격):

**시도 #1** (23:30:44):
```http
GET .../trading/inquire-ccnl
Params: ODNO=0000123456, ORD_STRT_DT=20260124
```

**응답**:
```json
{
  "output": [
    {
      "odno": "0000123456",
      "prcs_stat_name": "접수",  // 접수 상태
      "ft_ccld_qty": "0",
      "ft_ccld_unpr3": "0.00",
      "nccs_qty": "2",
      "rjct_rson_name": ""
    }
  ]
}
```

**로그**:
```
[DEBUG] 2026-01-24 23:30:44 - __main__ - [FILL CHECK 1/10] 주문번호 0000123456: 접수, 체결 0/2주 @ $0.00
```

**시도 #2** (23:30:46):
```
[DEBUG] 2026-01-24 23:30:46 - __main__ - [FILL CHECK 2/10] 주문번호 0000123456: 접수, 체결 0/2주 @ $0.00
```

**시도 #3** (23:30:48):
```json
{
  "output": [
    {
      "odno": "0000123456",
      "prcs_stat_name": "완료",  // 체결 완료!
      "ft_ccld_qty": "2",
      "ft_ccld_unpr3": "49.48",  // 실제 체결가: $49.48
      "nccs_qty": "0"
    }
  ]
}
```

**로그**:
```
[DEBUG] 2026-01-24 23:30:48 - __main__ - [FILL CHECK 3/10] 주문번호 0000123456: 완료, 체결 2/2주 @ $49.48
[INFO] 2026-01-24 23:30:48 - __main__ - [FILL] 체결 확인: 2주 @ $49.48 (상태: 완료)
```

#### 23:30:49 - 포지션 생성 (GridEngine)

**내부 동작**:
```python
grid_engine.execute_buy(
    signal=signal,
    actual_filled_price=49.48,
    actual_filled_qty=2
)

# 배치 처리
qty_per_tier = 2 // 2 = 1
remainder = 2 % 2 = 0

# Tier 3 포지션 생성
Position(
    tier=3,
    quantity=1,
    avg_price=49.48,
    invested_amount=49.48,
    opened_at=datetime(2026, 1, 24, 23, 30, 49)
)

# Tier 4 포지션 생성
Position(
    tier=4,
    quantity=1,
    avg_price=49.48,
    invested_amount=49.48,
    opened_at=datetime(2026, 1, 24, 23, 30, 49)
)

# 잔고 차감
account_balance = 5000.00 - (49.48 × 2) = 4901.04
```

**로그 출력**:
```
[INFO] 2026-01-24 23:30:49 - grid_engine - 배치 매수 체결: Tiers (3, 4), 총 2주 @ $49.48, 티어당 1주 분배
[INFO] 2026-01-24 23:30:49 - __main__ - [OK] 매수 체결: Tier 3 - 체결 2주 @ $49.48 (주문번호: 0000123456)
```

**텔레그램 알림**:
```
✅ 매수 체결
━━━━━━━━━━━━━━━━
🔢 Tier: 3, 4 (배치)
💰 체결가: $49.48
📊 수량: 2주
💵 투자금: $98.96
━━━━━━━━━━━━━━━━
💼 잔고: $4,901.04
⏰ 2026-01-24 23:30:49
```

#### 23:30:50~23:31:28 - Excel 업데이트 대기

**대기 중** (excel_update_interval = 1초마다 체크):
```python
while True:
    now = datetime.now()
    if (now - last_update_time).total_seconds() >= 1.0:
        _update_system_state(current_price)
        break
    time.sleep(0.1)
```

**23:31:29** - Excel 업데이트:
```python
state = grid_engine.get_system_state(current_price=49.50)
```

**SystemState 계산**:
```python
current_price = 49.50
tier1_price = 50.30
current_tier = 4  # (50.30 - 49.50) / 50.30 / 0.005 + 1
account_balance = 4901.04
total_quantity = 2
total_invested = 98.96
stock_value = 2 × 49.50 = 99.00
total_profit = 4901.04 + 99.00 - 5000.00 = 0.04
profit_rate = 0.04 / 5000.00 = 0.0008% (0.0008%)
```

**Excel 업데이트** (시트 1):

**영역 B** (D1:E10):
```
E2: 2026-01-24 23:31:29
E3: 4 (현재 티어)
E4: $49.50 (현재가)
E5: $4,901.04 (잔고)
E6: 2 (총 보유 수량)
E7: 대기 (매수 상태)
E8: 대기 (매도 상태)
```

**영역 D** (G17:N257) - Tier 3, 4 행만 표시:

| G (티어) | H (잔고량) | I (투자금) | J (티어평단) | K (매수가) | L (매수량) | M (매도가) | N (매도량) |
|---------|----------|----------|-----------|----------|----------|----------|----------|
| 3 | 1 | $49.48 | $49.48 | | | $51.17 | 1 |
| 4 | 1 | $49.48 | $49.48 | | | $51.01 | 1 |

**M (매도가) 계산**:
```
Tier 3 매도가 = 49.797 × 1.03 = 51.29 (티어 기준가 × 1.03)
Tier 4 매도가 = 49.5455 × 1.03 = 51.03
```

**히스토리 로그 추가** (시트 2):

| A (업데이트) | B (날짜) | C (시트) | D (종목) | E (티어) | F (총티어) | G (수량차) | H (투자금) | ... | P (매수) | Q (매도) |
|------------|---------|---------|---------|---------|----------|----------|----------|-----|---------|---------|
| 2026-01-24 23:31:29 | 2026-01-24 | Main | SOXL | 4 | 240 | 2 | $98.96 | ... | 2 | 0 |

**로그**:
```
[DEBUG] 2026-01-24 23:31:29 - excel_bridge - 프로그램 정보 업데이트: Tier 4, $49.50
[DEBUG] 2026-01-24 23:31:29 - excel_bridge - 프로그램 영역 업데이트 완료: 2개 포지션
[INFO] 2026-01-24 23:31:29 - excel_bridge - 히스토리 로그 추가: 행 3, Tier 4
[INFO] 2026-01-24 23:31:29 - excel_bridge - Excel 파일 저장 완료: D:\Project\SOLX\phoenix_grid_template_v3.xlsx
[DEBUG] 2026-01-24 23:31:29 - __main__ - [SAVE] Excel 업데이트: 가격 $49.50, 포지션 2개
```

#### 23:31:30 - 다음 시세 조회 대기

**대기**:
```python
time.sleep(40)  # price_check_interval
```

---

### 요약: 첫 거래 사이클 완료

**결과**:
- ✅ Tier 3, 4에 각 1주씩 매수 (총 2주)
- ✅ 평균 체결가: $49.48
- ✅ 투자금: $98.96
- ✅ 잔고: $4,901.04
- ✅ 미실현 손익: +$0.04 (+0.0008%)

**다음 예상**:
- 가격이 $51.29 이상 상승 시 → Tier 3 매도 신호
- 가격이 $49.29 이하 하락 시 → Tier 5 매수 신호

---

## 시나리오 2: 급락 상황 - 배치 매수

### 배경
- **시간**: 23:45:00 (첫 거래 후 13분 경과)
- **현재 포지션**: Tier 3, 4 보유 (각 1주)
- **잔고**: $4,901.04

### 타임라인

#### 23:45:00 - 급락 시세 조회

**KIS API 응답**:
```json
{
  "output": {
    "last": "47.50"  // 급락: -$2.00 (-4.0%)
  }
}
```

**로그**:
```
[INFO] 2026-01-24 23:45:00 - __main__ - 시세 조회: SOXL = $47.50 (Tier 1: $50.30)
```

#### 23:45:01 - 배치 매수 신호 생성

**GridEngine 처리**:
```python
signals = grid_engine.process_tick(current_price=47.50)

# 매수 배치 확인
매수 가능 티어:
- Tier 5: 49.294 ≥ 47.50 → O
- Tier 6: 49.0425 ≥ 47.50 → O
- Tier 7: 48.791 ≥ 47.50 → O
- Tier 8: 48.5395 ≥ 47.50 → O
- Tier 9: 48.288 ≥ 47.50 → O
- Tier 10: 48.0365 ≥ 47.50 → O
- Tier 11: 47.785 ≥ 47.50 → O
- Tier 12: 47.5335 ≥ 47.50 → O
- Tier 13: 47.282 < 47.50 → X

총 8개 티어 (Tier 5~12)
```

**수량 계산**:
```python
for tier in [5, 6, 7, 8, 9, 10, 11, 12]:
    quantity = floor($20.83 / $47.50) = floor(0.438) = 0 → 1주 (최소값)

총 수량 = 8주
총 비용 = 8 × $47.50 = $380.00
잔고 확인: $4,901.04 ≥ $380.00 → O
```

**로그**:
```
[DEBUG] 2026-01-24 23:45:01 - grid_engine - 매수 배치 추가: Tier 5, 1주
[DEBUG] 2026-01-24 23:45:01 - grid_engine - 매수 배치 추가: Tier 6, 1주
[DEBUG] 2026-01-24 23:45:01 - grid_engine - 매수 배치 추가: Tier 7, 1주
[DEBUG] 2026-01-24 23:45:01 - grid_engine - 매수 배치 추가: Tier 8, 1주
[DEBUG] 2026-01-24 23:45:01 - grid_engine - 매수 배치 추가: Tier 9, 1주
[DEBUG] 2026-01-24 23:45:01 - grid_engine - 매수 배치 추가: Tier 10, 1주
[DEBUG] 2026-01-24 23:45:01 - grid_engine - 매수 배치 추가: Tier 11, 1주
[DEBUG] 2026-01-24 23:45:01 - grid_engine - 매수 배치 추가: Tier 12, 1주
[INFO] 2026-01-24 23:45:01 - grid_engine - [BATCH BUY] 8개 티어, 총 8주 @ $47.50 (비용: $380.00)
```

**매매 신호**:
```python
TradeSignal(
    action="BUY",
    tier=5,
    tiers=(5, 6, 7, 8, 9, 10, 11, 12),
    price=47.50,
    quantity=8,
    reason="배치 매수 8개 티어"
)
```

#### 23:45:02 - 매수 주문 실행

**KIS API 주문**:
```http
POST .../trading/order
Body: ORD_QTY=8, OVRS_ORD_UNPR=47.50
```

**응답**:
```json
{
  "output": {
    "ODNO": "0000123457"
  }
}
```

**로그**:
```
[INFO] 2026-01-24 23:45:02 - __main__ - [BATCH BUY] 배치 매수 신호: Tiers (5, 6, 7, 8, 9, 10, 11, 12), 총 8주 @ $47.50
[INFO] 2026-01-24 23:45:03 - __main__ - [ORDER] 주문 접수 완료: Tier 5, 주문번호 0000123457
```

#### 23:45:04~23:45:14 - 체결 확인

**시도 #1~#5**: 접수 상태

**시도 #6** (23:45:14):
```json
{
  "output": [
    {
      "prcs_stat_name": "완료",
      "ft_ccld_qty": "6",  // 부분 체결! (8주 중 6주)
      "ft_ccld_unpr3": "47.48"
    }
  ]
}
```

**로그**:
```
[DEBUG] 2026-01-24 23:45:14 - __main__ - [FILL CHECK 6/10] 주문번호 0000123457: 완료, 체결 6/8주 @ $47.48
[INFO] 2026-01-24 23:45:14 - __main__ - [FILL] 체결 확인: 6주 @ $47.48 (상태: 완료)
```

#### 23:45:15 - 포지션 생성 (부분 체결 처리)

**GridEngine 처리**:
```python
grid_engine.execute_buy(
    signal=signal,  # tiers=(5, 6, 7, 8, 9, 10, 11, 12)
    actual_filled_price=47.48,
    actual_filled_qty=6  # 8주 주문, 6주 체결
)

# 부분 체결 처리
qty_per_tier = 6 // 8 = 0
remainder = 6 % 8 = 6

# 첫 번째 티어(Tier 5)에 전량 할당
Position(
    tier=5,
    quantity=6,
    avg_price=47.48,
    invested_amount=284.88,
    opened_at=datetime.now()
)

# 나머지 티어(6~12)는 수량 0이므로 생성 안 함
```

**로그**:
```
[WARNING] 2026-01-24 23:45:15 - grid_engine - [PARTIAL FILL] 배치 매수 부분체결! 체결: 6주 < 티어 수: 8
[INFO] 2026-01-24 23:45:15 - grid_engine - 배치 매수 부분체결 완료: Tier 5에 6주 @ $47.48 할당
[INFO] 2026-01-24 23:45:15 - __main__ - [OK] 매수 체결: Tier 5 - 체결 6주 @ $47.48 (주문번호: 0000123457)
```

**잔고 업데이트**:
```python
account_balance = 4901.04 - (47.48 × 6) = 4616.16
```

**텔레그램 알림**:
```
⚠️ 매수 체결 (부분체결)
━━━━━━━━━━━━━━━━
🔢 Tier: 5 (8개 티어 중 1개만)
💰 체결가: $47.48
📊 수량: 6주 (주문 8주)
💵 투자금: $284.88
━━━━━━━━━━━━━━━━
⚠️ 부분체결 발생
💼 잔고: $4,616.16
⏰ 2026-01-24 23:45:15
```

### 요약: 급락 대응

**결과**:
- ✅ Tier 5에 6주 매수 (부분 체결)
- ⚠️ Tier 6~12는 미체결 (주문 실패)
- ✅ 현재 포지션: Tier 3 (1주), Tier 4 (1주), Tier 5 (6주)
- ✅ 총 보유: 8주
- ✅ 잔고: $4,616.16

**부분 체결 원인 (추정)**:
- 유동성 부족 (시장가 급락 시)
- 호가창 부족 (지정가 $47.50에 매도 물량 부족)

---

## 시나리오 3: 갭 상승 - Tier 1 커스텀 모드

### 배경
- **시간**: 다음날 월요일 23:30 (장 시작)
- **전날 종료 상태**: Tier 1 = $50.30, 포지션 청산 완료
- **뉴스**: SOXL 호재 발표 (반도체 ETF 긍정 전망)

### Excel 설정 변경

사용자가 Tier 1 거래 모드를 활성화:
```
B8: tier1_trading_enabled = TRUE (변경!)
C18: tier1_buy_percent = 0.0 (Tier 1 가격에 매수)
```

### 타임라인

#### 23:30:00 - 갭 상승 시가

**KIS API 응답**:
```json
{
  "output": {
    "last": "52.00",  // 갭 상승: +$1.70 (+3.5%)
    "open": "52.00"
  }
}
```

**로그**:
```
[INFO] 2026-01-27 23:30:00 - __main__ - 시세 조회: SOXL = $52.00 (Tier 1: $50.30)
```

#### 23:30:01 - Tier 1 자동 갱신

**GridEngine 처리**:
```python
# 1. Tier 1 갱신 확인
update_tier1(current_price=52.00)

조건 확인:
- tier1_auto_update: TRUE ✓
- total_quantity: 0 (전날 모두 청산) ✓
- current_price > tier1_price: 52.00 > 50.30 ✓

→ Tier 1 갱신!
```

**로그**:
```
[INFO] 2026-01-27 23:30:01 - grid_engine - Tier 1 갱신: $50.30 → $52.00
```

**새로운 티어 구조**:
```
Tier 1:   $52.00  (갱신!)
Tier 2:   $51.74  (-0.5%)
Tier 3:   $51.48  (-1.0%)
...
```

#### 23:30:02 - Tier 1 매수 신호 생성

**GridEngine 처리**:
```python
# 3. 매수 배치 확인
start_tier = 1  # tier1_trading_enabled=TRUE

# Tier 1 확인
tier1_buy_price = 52.00 × (1 + 0.0) = 52.00
if current_price (52.00) ≤ tier1_buy_price (52.00):
    매수 신호 생성!
```

**로그**:
```
[INFO] 2026-01-27 23:30:02 - grid_engine - [CUSTOM] Tier 1 매수 조건 충족: $52.00 ≤ $52.00
[INFO] 2026-01-27 23:30:02 - grid_engine - [BATCH BUY] 1개 티어, 총 1주 @ $52.00 (비용: $52.00)
```

**매매 신호**:
```python
TradeSignal(
    action="BUY",
    tier=1,
    tiers=(1,),
    price=52.00,
    quantity=1,  # floor($20.83 / $52.00) = 0 → 1주 (최소)
    reason="[CUSTOM] Tier 1 진입 (매수%: 0.00%)"
)
```

#### 23:30:03 - 매수 주문 및 체결

**KIS API 주문**:
```http
POST .../trading/order
Body: ORD_QTY=1, OVRS_ORD_UNPR=52.00
```

**체결 확인** (23:30:05):
```json
{
  "output": [
    {
      "prcs_stat_name": "완료",
      "ft_ccld_qty": "1",
      "ft_ccld_unpr3": "51.98"  // 실제 체결가
    }
  ]
}
```

**포지션 생성**:
```python
Position(
    tier=1,
    quantity=1,
    avg_price=51.98,
    invested_amount=51.98,
    opened_at=datetime.now()
)

account_balance = 5000.00 - 51.98 = 4948.02
```

**로그**:
```
[INFO] 2026-01-27 23:30:06 - __main__ - [OK] 매수 체결: Tier 1 - 체결 1주 @ $51.98 (주문번호: 0000123458)
```

**텔레그램 알림**:
```
✅ 매수 체결 (Tier 1 진입!)
━━━━━━━━━━━━━━━━
🔢 Tier: 1 (최고가 갱신)
💰 체결가: $51.98
📊 수량: 1주
💵 투자금: $51.98
━━━━━━━━━━━━━━━━
🎯 갭 상승 이득 확보!
💼 잔고: $4,948.02
⏰ 2026-01-27 23:30:06
```

#### 23:35:00 - 가격 상승 시 매도

**시세 조회**:
```json
{
  "output": {
    "last": "53.60"  // +3% 상승
  }
}
```

**GridEngine 처리**:
```python
# 매도 조건 확인
position = Position(tier=1, avg_price=51.98)
tier_buy_price = 52.00  # Tier 1 기준가
tier_sell_price = 52.00 × 1.03 = 53.56

if 53.60 ≥ 53.56:
    매도 신호 생성!
```

**로그**:
```
[INFO] 2026-01-27 23:35:01 - grid_engine - Tier 1 매도 조건 충족: 현재가 $53.60 ≥ 티어매도가 $53.56 (실제수익률: 3.12%)
[INFO] 2026-01-27 23:35:01 - grid_engine - [BATCH SELL] 1개 티어, 총 1주 @ $53.60
```

**매도 체결** (23:35:04):
```json
{
  "ft_ccld_qty": "1",
  "ft_ccld_unpr3": "53.58"
}
```

**수익 계산**:
```python
sell_amount = 53.58 × 1 = 53.58
profit = 53.58 - 51.98 = 1.60
profit_rate = 1.60 / 51.98 = 3.08%

account_balance = 4948.02 + 53.58 = 5001.60
```

**로그**:
```
[INFO] 2026-01-27 23:35:05 - __main__ - [OK] 매도 체결: Tier 1 - 체결 1주 @ $53.58, 수익 $1.60 (3.08%) (주문번호: 0000123459)
```

**텔레그램 알림**:
```
💰 매도 체결 (익절)
━━━━━━━━━━━━━━━━
🔢 Tier: 1
💰 체결가: $53.58
📊 수량: 1주
━━━━━━━━━━━━━━━━
📈 수익: +$1.60 (+3.08%)
💼 잔고: $5,001.60
⏰ 2026-01-27 23:35:05
```

### 요약: 갭 상승 대응

**Tier 1 커스텀 모드 효과**:
- ✅ 갭 상승 이득 확보 ($52.00에 매수)
- ✅ 3% 목표 달성 ($53.58에 매도)
- ✅ 실현 수익: +$1.60 (+3.08%)
- ✅ 총 자산: $5,001.60 (+0.032%)

**기본 모드였다면?**:
- ❌ Tier 1 갱신 후 매수 안 함 (Tier 2부터 시작)
- ❌ 갭 상승 이득 상실
- ❌ 수익 기회 놓침

---

## 시나리오 4: 에러 복구 시나리오

### 4-1. Excel 파일 잠금 에러

#### 상황
- **시간**: 00:15:00
- **사용자 실수**: Excel 파일을 수동으로 열어둠

#### 타임라인

**00:15:00** - Excel 업데이트 시도:
```python
excel_bridge.save_workbook()
```

**에러 발생**:
```
[WARNING] 2026-01-25 00:15:00 - excel_bridge - Excel 파일 잠금 감지, 1.0초 후 재시도 (1/3): [Errno 13] Permission denied: 'D:\\Project\\SOLX\\phoenix_grid_template_v3.xlsx'
```

**재시도 #1** (00:15:01):
```
[WARNING] 2026-01-25 00:15:01 - excel_bridge - Excel 파일 잠금 감지, 1.0초 후 재시도 (2/3): [Errno 13] Permission denied
```

**사용자 조치**: Excel 파일 닫음

**재시도 #2** (00:15:02):
```
[INFO] 2026-01-25 00:15:02 - excel_bridge - Excel 파일 저장 성공 (재시도 2회 후): D:\Project\SOLX\phoenix_grid_template_v3.xlsx
```

**결과**: ✅ 복구 성공 (데이터 손실 없음)

---

### 4-2. KIS API 토큰 만료

#### 상황
- **시간**: 19:00:00 (다음날, 첫 실행 후 24시간)
- **토큰 만료**: Access Token 유효기간 24시간

#### 타임라인

**19:00:00** - 시세 조회 시도:
```python
kis_adapter.get_overseas_price("SOXL")
```

**내부 동작**:
```python
_refresh_token_if_needed()

# 토큰 만료 확인
token_expires_at = datetime(2026, 1, 25, 19, 0, 4)
now = datetime(2026, 1, 25, 18, 55, 0)

if now >= token_expires_at - timedelta(minutes=5):  # 5분 전 갱신
    logger.info("토큰 갱신 중...")
    self.login()
```

**로그**:
```
[INFO] 2026-01-25 18:55:00 - kis_rest_adapter - 토큰 갱신 중...
[INFO] 2026-01-25 18:55:01 - kis_rest_adapter - Access Token 발급 성공 (만료: 2026-01-26 18:55:01)
[INFO] 2026-01-25 18:55:01 - kis_rest_adapter - [캐시] 토큰 저장 완료: kis_token_cache.json
```

**결과**: ✅ 자동 갱신 성공 (거래 중단 없음)

---

### 4-3. API Rate Limiting

#### 상황
- **시간**: 01:30:00
- **원인**: 빠른 연속 API 호출 (버그)

#### 타임라인

**01:30:00** - 연속 API 호출:
```python
for i in range(10):
    kis_adapter.get_overseas_price("SOXL")
```

**Rate Limiting 동작**:
```python
_apply_rate_limit()

elapsed = time.time() - last_request_time
# Call #1: elapsed=0 → sleep(0.2)
# Call #2: elapsed=0.2 → sleep(0)
# Call #3: elapsed=0.2 → sleep(0)
# ...
```

**로그**:
```
[DEBUG] 2026-01-25 01:30:00.000 - kis_rest_adapter - Rate limit: sleep 0.200초
[DEBUG] 2026-01-25 01:30:00.200 - kis_rest_adapter - Rate limit: sleep 0.000초
[DEBUG] 2026-01-25 01:30:00.400 - kis_rest_adapter - Rate limit: sleep 0.000초
...
```

**결과**: ✅ 초당 5회 제한 준수 (API 차단 방지)

---

### 4-4. 주문 체결 타임아웃

#### 상황
- **시간**: 02:00:00
- **원인**: 시장 유동성 부족 (새벽 시간)

#### 타임라인

**02:00:00** - 매수 주문:
```python
result = kis_adapter.send_order(side="BUY", ticker="SOXL", quantity=1, price=48.00)
order_id = "0000123460"
```

**체결 확인** (폴링):
```
[DEBUG] 2026-01-25 02:00:02 - __main__ - [FILL CHECK 1/10] 주문번호 0000123460: 접수, 체결 0/1주
[DEBUG] 2026-01-25 02:00:04 - __main__ - [FILL CHECK 2/10] 주문번호 0000123460: 접수, 체결 0/1주
...
[DEBUG] 2026-01-25 02:00:20 - __main__ - [FILL CHECK 10/10] 주문번호 0000123460: 접수, 체결 0/1주
[WARNING] 2026-01-25 02:00:20 - __main__ - [TIMEOUT] 체결 확인 타임아웃: 주문번호 0000123460, 20초 경과
```

**결과**:
```python
filled_price, filled_qty = 0.0, 0  # 타임아웃

if filled_qty <= 0:
    logger.warning("매수 실행 거부: 체결 수량 0")
    return None  # 포지션 생성 안 함
```

**로그**:
```
[WARNING] 2026-01-25 02:00:21 - grid_engine - 매수 실행 거부: Tier 10 - 체결 수량이 0 이하입니다 (filled_qty=0). 포지션을 생성하지 않습니다.
```

**텔레그램 알림**:
```
⚠️ 주문 체결 타임아웃
━━━━━━━━━━━━━━━━
🔢 주문번호: 0000123460
📊 주문: Tier 10, 1주 @ $48.00
━━━━━━━━━━━━━━━━
⏰ 20초 경과 (체결 확인 실패)
📋 수동 확인 필요
⏰ 2026-01-25 02:00:21
```

**권장 조치**:
1. KIS HTS에서 주문 내역 확인
2. 실제 체결 여부 확인
3. 체결된 경우: Excel 수동 수정 필요

**결과**: ⚠️ 잠재적 위험 (실제 체결 시 시스템 불일치)

---

### 4-5. 시세 조회 실패 (네트워크 에러)

#### 상황
- **시간**: 03:00:00
- **원인**: 일시적 네트워크 단절

#### 타임라인

**03:00:00** - 시세 조회 시도:
```python
price_data = kis_adapter.get_overseas_price("SOXL")
```

**네트워크 에러**:
```python
try:
    response = requests.get(url, headers=headers, params=params, timeout=10)
except requests.exceptions.Timeout as e:
    logger.warning(f"SOXL: AMS 거래소 조회 중 예외: {e}")
    return None
```

**로그**:
```
[WARNING] 2026-01-25 03:00:10 - kis_rest_adapter - SOXL: AMS 거래소 조회 중 예외: HTTPConnectionPool(host='openapi.koreainvestment.com', port=9443): Read timed out. (read timeout=10)
[ERROR] 2026-01-25 03:00:10 - kis_rest_adapter - SOXL: 모든 거래소(NAS, AMS, NYS)에서 시세 조회 실패
[WARNING] 2026-01-25 03:00:10 - __main__ - SOXL 시세 조회 실패. 재시도...
```

**대기 및 재시도**:
```python
if not price_data:
    logger.warning(f"{self.settings.ticker} 시세 조회 실패. 재시도...")
    time.sleep(5)
    continue  # 다음 루프로
```

**5초 후 재시도** (03:00:15):
```
[INFO] 2026-01-25 03:00:15 - kis_rest_adapter - [거래소 자동 감지] SOXL는 AMS 거래소에서 조회됨
[INFO] 2026-01-25 03:00:15 - __main__ - 시세 조회: SOXL = $48.20
```

**결과**: ✅ 자동 복구 성공 (5초 지연)

---

## 시나리오 5: 장 마감 및 재시작

### 5-1. 장 마감 감지

#### 상황
- **시간**: 06:00:00 (토요일, 미국 금요일 마감)

#### 타임라인

**05:59:40** - 마지막 정상 시세:
```
[INFO] 2026-01-25 05:59:40 - __main__ - 시세 조회: SOXL = $49.80
```

**06:00:00** - 장 마감 시세:
```json
{
  "output": {
    "last": "0.00"  // 시세 $0.00 (장 마감)
  }
}
```

**장 마감 감지**:
```python
if current_price <= 0:
    is_open, message = _is_market_open()
    # weekday=5 (토요일), hour=6
    # → 주말 확인
```

**로그**:
```
[WARNING] 2026-01-25 06:00:00 - __main__ - 시세 $0.00 감지 - 주말입니다. 다음 개장: 2026-01-27 23:30 (월요일 밤)
[INFO] 2026-01-25 06:00:00 - __main__ - 시장 개장 시간까지 대기합니다...
```

**대기 모드 진입**:
```
[대기 중] 주말입니다. 다음 개장: 2026-01-27 23:30 (월요일 밤) - 06:01:00
[대기 중] 주말입니다. 다음 개장: 2026-01-27 23:30 (월요일 밤) - 06:02:00
...
```

**결과**: ⏸️ 시스템 대기 중 (65시간 30분, 월요일 23:30까지)

---

### 5-2. 사용자 수동 종료

#### 상황
- **시간**: 06:05:00 (토요일, 대기 중)
- **사용자**: 주말 동안 PC 끄기 위해 종료

#### 타임라인

**사용자 액션**: Ctrl+C 입력

**시그널 핸들러 동작**:
```python
def _signal_handler(self, signum, frame):
    logger.info(f"\n종료 시그널 수신 ({signum}). 안전하게 종료 중...")
    self.stop_requested = True
```

**로그**:
```
^C
[INFO] 2026-01-25 06:05:00 - __main__ -
종료 시그널 수신 (2). 안전하게 종료 중...
[INFO] 2026-01-25 06:05:00 - __main__ - 사용자에 의해 대기 중 종료됨
```

**종료 프로세스**:
```python
shutdown()
```

**최종 상태 저장**:
```
[INFO] 2026-01-25 06:05:01 - __main__ - ============================================================
[INFO] 2026-01-25 06:05:01 - __main__ - 시스템 종료 중...
[INFO] 2026-01-25 06:05:01 - __main__ - ============================================================
[INFO] 2026-01-25 06:05:02 - excel_bridge - Excel 파일 저장 완료: D:\Project\SOLX\phoenix_grid_template_v3.xlsx
[INFO] 2026-01-25 06:05:02 - __main__ - [OK] 최종 상태 저장 완료
[INFO] 2026-01-25 06:05:02 - kis_rest_adapter - REST API 연결 해제
[INFO] 2026-01-25 06:05:02 - __main__ - [OK] KIS API 연결 해제
[INFO] 2026-01-25 06:05:02 - __main__ - ============================================================
[INFO] 2026-01-25 06:05:02 - __main__ - [OK] Phoenix Trading System 정상 종료
[INFO] 2026-01-25 06:05:02 - __main__ - ============================================================

============================================================
[정상 종료] 프로그램이 성공적으로 종료되었습니다.
============================================================

Press Enter to exit...
```

**텔레그램 알림**:
```
⏹️ Phoenix Trading 종료
━━━━━━━━━━━━━━━━
📊 종목: SOXL
💼 최종 잔고: $4,856.32
📈 총 수익: +$12.45 (+0.25%)
━━━━━━━━━━━━━━━━
📦 보유 포지션: 3개
  - Tier 3: 1주
  - Tier 4: 1주
  - Tier 5: 6주
━━━━━━━━━━━━━━━━
⏰ 2026-01-25 06:05:02
```

**결과**: ✅ 안전 종료 (모든 데이터 저장)

---

### 5-3. 시스템 재시작 (월요일 밤)

#### 상황
- **시간**: 2026-01-27 22:00 (월요일, 장 시작 1.5시간 전)

#### 타임라인

**사용자 액션**:
```bash
D:\Project\SOLX> PhoenixTrading.exe phoenix_grid_template_v3.xlsx
```

**초기화**:
```
[INFO] 2026-01-27 22:00:01 - excel_bridge - Excel 파일 로드 성공
[INFO] 2026-01-27 22:00:02 - kis_rest_adapter - [캐시] Access Token 재사용 (만료: 2026-01-28 18:55:01)
[INFO] 2026-01-27 22:00:03 - __main__ - GridEngine 초기화 중...
```

**기존 포지션 복원** (Excel에서):
```python
# Excel 영역 D에서 보유 포지션 읽기
# (실제로는 GridEngine이 Excel에서 직접 읽지 않음, phoenix_main이 초기화 시 복원 필요)

# 현재 구현: 포지션 복원 안 됨!
# → 개선 필요: load_positions_from_excel() 메서드 추가
```

**⚠️ 현재 한계**:
- Excel에 포지션 정보가 저장되어 있지만
- 재시작 시 자동 복원 로직 없음
- 사용자가 수동으로 확인 필요

**권장 개선**:
```python
# excel_bridge.py에 추가
def load_positions_from_excel(self) -> List[Position]:
    """영역 D에서 보유 포지션 로드"""
    positions = []
    for tier in range(1, 241):
        row_idx = 17 + tier
        quantity = ws[row_idx, 8].value  # 잔고량
        if quantity and quantity > 0:
            avg_price = ws[row_idx, 10].value
            invested = ws[row_idx, 9].value
            positions.append(Position(
                tier=tier,
                quantity=quantity,
                avg_price=avg_price,
                invested_amount=invested,
                opened_at=datetime.now()  # 원본 시각 손실
            ))
    return positions
```

---

## 시나리오 6: 수익 실현 및 Tier 1 갱신

### 배경
- **시간**: 2026-01-28 00:30 (화요일)
- **현재 포지션**: Tier 8, 10, 12 보유 (각 2주)
- **현재가**: $51.00 (상승 추세)

### 타임라인

#### 00:30:00 - 상승 시세

**시세 조회**:
```json
{
  "output": {
    "last": "51.00"
  }
}
```

#### 00:30:01 - 배치 매도 신호

**GridEngine 처리**:
```python
signals = grid_engine.process_tick(current_price=51.00)

# 매도 배치 확인
for pos in sorted(positions, key=lambda p: p.tier, reverse=True):
    # Tier 12 (최고 티어부터)
    tier_buy_price = calculate_tier_price(12) = 47.5335
    tier_sell_price = 47.5335 × 1.03 = 48.9595
    if 51.00 ≥ 48.9595: → O

    # Tier 10
    tier_sell_price = 48.0365 × 1.03 = 49.4776
    if 51.00 ≥ 49.4776: → O

    # Tier 8
    tier_sell_price = 48.5395 × 1.03 = 50.0157
    if 51.00 ≥ 50.0157: → O

매도 배치 = [Tier 8, 10, 12]
```

**로그**:
```
[DEBUG] 2026-01-28 00:30:01 - grid_engine - 매도 배치 추가: Tier 12, 2주 (실제수익률: 7.29%)
[DEBUG] 2026-01-28 00:30:01 - grid_engine - 매도 배치 추가: Tier 10, 2주 (실제수익률: 6.17%)
[DEBUG] 2026-01-28 00:30:01 - grid_engine - 매도 배치 추가: Tier 8, 2주 (실제수익률: 5.10%)
[INFO] 2026-01-28 00:30:01 - grid_engine - [BATCH SELL] 3개 티어, 총 6주 @ $51.00
```

#### 00:30:02 - 배치 매도 체결

**주문 및 체결**:
```
[INFO] 2026-01-28 00:30:02 - __main__ - [BATCH SELL] 배치 매도 신호: Tiers (12, 10, 8), 총 6주 @ $51.00
[INFO] 2026-01-28 00:30:03 - __main__ - [ORDER] 주문 접수 완료: Tier 12, 주문번호 0000123461
[INFO] 2026-01-28 00:30:07 - __main__ - [FILL] 체결 확인: 6주 @ $50.98 (상태: 완료)
```

**수익 계산**:
```python
# Tier 12: 2주 @ $47.00 (평균 매수가)
# Tier 10: 2주 @ $48.00
# Tier 8: 2주 @ $48.50

total_invested = (47.00 × 2) + (48.00 × 2) + (48.50 × 2) = 287.00
sell_amount = 50.98 × 6 = 305.88
total_profit = 305.88 - 287.00 = 18.88
profit_rate = 18.88 / 287.00 = 6.58%

account_balance += 305.88
```

**로그**:
```
[INFO] 2026-01-28 00:30:08 - grid_engine - 배치 매도 체결: Tiers (12, 10, 8), 총 6주 @ $50.98, 수익: $18.88
[INFO] 2026-01-28 00:30:08 - __main__ - [OK] 매도 체결: Tier 12 - 체결 6주 @ $50.98, 수익 $18.88 (6.58%) (주문번호: 0000123461)
```

**텔레그램 알림**:
```
💰 매도 체결 (배치 익절)
━━━━━━━━━━━━━━━━
🔢 Tier: 12, 10, 8 (3개)
💰 체결가: $50.98
📊 수량: 6주
━━━━━━━━━━━━━━━━
📈 수익: +$18.88 (+6.58%)
💼 잔고: $5,162.20
⏰ 2026-01-28 00:30:08
```

#### 00:30:09 - 포지션 전체 청산 확인

**현재 상태**:
```python
positions = []  # 모든 포지션 청산
account_balance = 5162.20
tier1_price = 50.30 (기존)
```

#### 00:35:00 - 추가 상승 및 Tier 1 갱신

**시세 조회**:
```json
{
  "output": {
    "last": "52.50"  // 추가 상승
  }
}
```

**GridEngine 처리**:
```python
# 1. Tier 1 갱신 확인
update_tier1(52.50)

조건 확인:
- tier1_auto_update: TRUE ✓
- total_quantity: 0 ✓
- current_price > tier1_price: 52.50 > 50.30 ✓

→ Tier 1 갱신!
```

**로그**:
```
[INFO] 2026-01-28 00:35:01 - grid_engine - Tier 1 갱신: $50.30 → $52.50
```

**새로운 그리드 구조**:
```
Tier 1:   $52.50  (신규 High Water Mark)
Tier 2:   $52.24  (-0.5%)
Tier 3:   $51.98  (-1.0%)
...
Tier 240: $10.63  (-119.5%)
```

**텔레그램 알림**:
```
🎯 Tier 1 갱신!
━━━━━━━━━━━━━━━━
📊 신규 기준가: $52.50
📈 상승폭: +$2.20 (+4.38%)
━━━━━━━━━━━━━━━━
💼 현재 잔고: $5,162.20
📦 보유 포지션: 0개
⏰ 2026-01-28 00:35:01
```

### 요약: 완전한 사이클

**전체 수익**:
```
초기 투자금: $5,000.00
최종 잔고: $5,162.20
실현 수익: +$162.20 (+3.24%)

거래 횟수:
- 매수: 12회 (총 20주)
- 매도: 8회 (총 20주)

평균 보유 기간: 약 1.5일
평균 수익률: 약 5% (매도 건당)
```

**시스템 성과**:
- ✅ 변동성 활용 (하락 시 매수, 상승 시 매도)
- ✅ Tier 1 갱신 (High Water Mark 추적)
- ✅ 배치 주문으로 효율성 극대화
- ✅ 지정가 주문으로 슬리피지 최소화

---

## 전체 시나리오 요약

### 시나리오별 핵심 교훈

| 시나리오 | 상황 | 시스템 대응 | 결과 |
|---------|------|-----------|------|
| 1. 정상 거래 | 일반적인 매수/매도 | 배치 주문, 체결 확인 폴링 | ✅ 정상 작동 |
| 2. 급락 상황 | -4% 급락 | 8개 티어 동시 매수 (부분 체결) | ⚠️ 부분 체결 처리 |
| 3. 갭 상승 | +3.5% 갭 상승 | Tier 1 커스텀 모드로 이득 확보 | ✅ 갭 이득 획득 |
| 4. 에러 복구 | Excel 잠금, 토큰 만료, 네트워크 단절 | 재시도 로직, 자동 갱신 | ✅ 자동 복구 |
| 5. 장 마감 | 주말 마감 | 자동 대기, 안전 종료 | ✅ 데이터 보존 |
| 6. 수익 실현 | 전체 청산 + 상승 | 배치 매도, Tier 1 갱신 | ✅ 수익 실현 |

### 시스템 안정성 평가

**장점**:
- ✅ 자동 에러 복구 (토큰, 네트워크)
- ✅ 데이터 무결성 보장 (Excel 저장, 재시도)
- ✅ 실시간 알림 (텔레그램)
- ✅ 배치 처리 효율성

**개선 필요**:
- ⚠️ 재시작 시 포지션 복원 로직 없음
- ⚠️ 체결 타임아웃 시 수동 확인 필요
- ⚠️ 부분 체결 시 나머지 티어 재주문 로직 없음

---

**문서 작성**: AI Agent (Claude Code)
**시뮬레이션 기간**: 2026-01-24 ~ 2026-01-28 (4일)
**총 시나리오**: 6개
**최종 수정**: 2026-01-24


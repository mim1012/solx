# Phoenix Trading System v4.1 - 납품 체크리스트

**납품 대상**: SOXL 자동매매 시스템 (KIS REST API)
**검증일**: 2026-01-22
**검증자**: Claude Code Agent

---

## 📋 체크리스트 요약

| 구분 | 항목 | 상태 | 비고 |
|------|------|------|------|
| **1. 파일 구성** | Excel 템플릿 존재 확인 | ⏳ 대기 | phoenix_grid_template_v3.xlsx |
| | EXE 파일 존재 확인 | ⏳ 대기 | PhoenixTrading.exe |
| | 로그 폴더 생성 확인 | ⏳ 대기 | logs/ 자동 생성 |
| **2. Excel 설정 로드** | API 키 로드 (B12~B14) | ⏳ 대기 | kis_app_key, kis_app_secret, kis_account_no |
| | 기본 설정 로드 (B2~B10) | ⏳ 대기 | ticker, investment_usd, tier_amount 등 |
| | 시스템 실행 플래그 (B15) | ⏳ 대기 | system_running |
| | 시간 간격 설정 (B16, B21) | ⏳ 대기 | price_check_interval, excel_update_interval |
| | Tier 1 거래 설정 (B8, C18) | ⏳ 대기 | tier1_trading_enabled, tier1_buy_percent |
| **3. 자동 시작** | B15=TRUE 시 자동 시작 | ⏳ 대기 | InitStatus.SUCCESS 확인 |
| | B15=FALSE 시 중지 | ⏳ 대기 | InitStatus.STOPPED 확인 |
| | API 키 누락 시 에러 | ⏳ 대기 | InitStatus.ERROR_API_KEY 확인 |
| **4. KIS API 연동** | OAuth2 로그인 | ⏳ 대기 | Access Token 발급 |
| | Approval Key 발급 | ⏳ 대기 | WebSocket용 |
| | 시세 조회 (SOXL) | ⏳ 대기 | get_overseas_price() |
| | 잔고 조회 | ⏳ 대기 | get_balance() |
| **5. Tier 1 갱신** | 초기 Tier 1 설정 | ⏳ 대기 | current_price로 초기화 |
| | 보유=0일 때 자동 갱신 | ⏳ 대기 | update_tier1() |
| | 보유>0일 때 갱신 안함 | ⏳ 대기 | 안전성 검증 |
| **6. 매매 로직** | 시간 간격 준수 (40초) | ⏳ 대기 | price_check_interval |
| | 매수 조건 확인 | ⏳ 대기 | check_buy_condition() |
| | 매도 조건 확인 | ⏳ 대기 | check_sell_condition() |
| | process_tick() 실행 | ⏳ 대기 | 매 주기마다 |
| **7. Excel 업데이트** | 프로그램 정보 업데이트 (E2~E8) | ⏳ 대기 | update_program_info() |
| | 프로그램 영역 업데이트 (G17:N257) | ⏳ 대기 | update_program_area() |
| | 히스토리 로그 추가 | ⏳ 대기 | append_history_log() |
| | Excel 파일 저장 | ⏳ 대기 | save_workbook() |
| **8. 안전성** | Ctrl+C 종료 처리 | ⏳ 대기 | signal_handler |
| | 최종 상태 저장 | ⏳ 대기 | shutdown() |
| | 에러 로깅 | ⏳ 대기 | logs/ 폴더에 기록 |

---

## 🔍 상세 테스트 시나리오

### 테스트 1: Excel 설정 로드 검증

**목적**: Excel 파일에서 API 키 및 모든 설정이 올바르게 로드되는지 확인

**전제 조건**:
- `phoenix_grid_template_v3.xlsx` 파일 존재
- 시트 "01_매매전략_기준설정" 존재

**테스트 단계**:
1. Excel 파일 열기
2. B12~B14 셀에 KIS API 키 입력 확인
   - B12: kis_app_key (36자 이상)
   - B13: kis_app_secret (36자 이상)
   - B14: kis_account_no (10자리 형식: 12345678-01)
3. B2~B10 기본 설정 확인
   - B3: SOXL (고정)
   - B4: investment_usd > 0
   - B5: total_tiers = 240
   - B6: tier_amount > 0
   - B7: tier1_auto_update = TRUE
   - B8: tier1_trading_enabled = TRUE/FALSE
   - B9: buy_limit = FALSE (거래 활성화)
   - B10: sell_limit = FALSE (거래 활성화)
4. B15: system_running = TRUE (자동 시작)
5. B16: price_check_interval = 40.0 (초)
6. B21: excel_update_interval = 1.0 (초)
7. C18: tier1_buy_percent = -0.005 (-0.5%)

**예상 결과**:
```
Excel 설정 로드 중...
  - 계좌번호: 12345678-01
  - 종목: SOXL
  - 투자금: $10,000.00
  - 시스템 실행: ON
```

**검증 방법**:
```python
from src.excel_bridge import ExcelBridge

bridge = ExcelBridge("phoenix_grid_template_v3.xlsx")
settings = bridge.load_settings()

assert settings.kis_app_key != ""
assert settings.kis_app_secret != ""
assert settings.kis_account_no != ""
assert settings.ticker == "SOXL"
assert settings.system_running == True
assert settings.price_check_interval == 40.0
```

---

### 테스트 2: 자동 시작 기능 검증

**목적**: EXE 실행 시 B15 설정에 따라 자동으로 프로그램이 시작/중지되는지 확인

**테스트 케이스 2-1: B15 = TRUE (자동 시작)**

**전제 조건**:
- Excel B15 = TRUE
- API 키 정상 입력

**실행**:
```bash
PhoenixTrading.exe phoenix_grid_template_v3.xlsx
```

**예상 결과**:
```
[OK] 시스템 초기화 완료!
메인 거래 루프 시작...
종료하려면 Ctrl+C를 누르세요.
```

**검증 코드**:
- `initialize()` 리턴값 = `InitStatus.SUCCESS` (0)
- `is_running` = True
- 거래 루프 진입

---

**테스트 케이스 2-2: B15 = FALSE (중지)**

**전제 조건**:
- Excel B15 = FALSE

**실행**:
```bash
PhoenixTrading.exe phoenix_grid_template_v3.xlsx
```

**예상 결과**:
```
[STOP] 시스템이 중지 상태입니다 (Excel B15=FALSE)
자동 거래를 시작하려면:
  1. Excel 파일 열기
  2. 시트 '01_매매전략_기준설정'
  3. B15 셀을 TRUE로 변경
  4. 저장 후 프로그램 재시작
[OK] 시스템이 중지 상태로 설정되어 있습니다.
```

**검증 코드**:
- `initialize()` 리턴값 = `InitStatus.STOPPED` (10)
- 프로그램 종료 코드 = 10

---

**테스트 케이스 2-3: API 키 누락**

**전제 조건**:
- Excel B12 또는 B13 비어 있음

**예상 결과**:
```
[FAIL] KIS API 키가 설정되지 않았습니다!
Excel 파일에서 다음 항목을 입력하세요:
  - B12: KIS APP KEY
  - B13: KIS APP SECRET
  - B14: KIS 계좌번호 (예: 12345678-01)
```

**검증 코드**:
- `initialize()` 리턴값 = `InitStatus.ERROR_API_KEY` (21)

---

### 테스트 3: KIS API 연동 검증

**목적**: KIS REST API 로그인 및 기본 기능 확인

**테스트 단계**:
1. OAuth2 로그인
2. Approval Key 발급
3. SOXL 시세 조회
4. 계좌 잔고 조회

**예상 결과**:
```
KIS REST API 연결 중...
[OK] KIS API 로그인 성공
SOXL 초기 시세 조회 중...
  - 현재가: $45.30
  - 시가: $44.80
  - 고가: $45.50
  - 저가: $44.50
계좌 잔고 조회 중...
  - 예수금: $10,000.00
```

**검증 방법**:
```python
adapter = KisRestAdapter(app_key, app_secret, account_no)
assert adapter.login() == True
assert adapter.access_token is not None

price = adapter.get_overseas_price("SOXL")
assert price is not None
assert price["price"] > 0

balance = adapter.get_balance()
assert balance >= 0
```

---

### 테스트 4: Tier 1 갱신 로직 검증

**목적**: 설정한 시간 간격(40초)마다 Tier 1이 올바르게 갱신되는지 확인

**테스트 케이스 4-1: 초기 Tier 1 설정**

**전제 조건**:
- 보유 포지션 = 0
- 현재가 = $45.30

**예상 결과**:
```python
grid_engine.tier1_price = 45.30  # 초기값 = 현재가
```

**검증 코드**:
```python
# phoenix_main.py:205
grid_engine.tier1_price = current_price
assert grid_engine.tier1_price == 45.30
```

---

**테스트 케이스 4-2: 보유=0, 상승 → 갱신됨**

**시나리오**:
1. 초기: Tier 1 = $45.30, 보유 = 0
2. 40초 후: 현재가 = $46.00 (상승)
3. `process_tick($46.00)` 호출

**예상 결과**:
```
Tier 1 갱신: $45.30 → $46.00
```

**검증 코드**:
```python
# grid_engine.py:120-123
updated, new_tier1 = grid_engine.update_tier1(46.00)
assert updated == True
assert new_tier1 == 46.00
assert grid_engine.tier1_price == 46.00
```

---

**테스트 케이스 4-3: 보유>0 → 갱신 안됨**

**시나리오**:
1. Tier 1 = $45.30
2. Tier 2에서 매수 (보유 100주)
3. 현재가 = $46.00 (상승)

**예상 결과**:
```
(로그 없음, Tier 1 갱신 안됨)
```

**검증 코드**:
```python
# grid_engine.py:115-117
total_quantity = sum(pos.quantity for pos in grid_engine.positions)
assert total_quantity > 0

updated, _ = grid_engine.update_tier1(46.00)
assert updated == False
assert grid_engine.tier1_price == 45.30  # 변경 안됨
```

---

### 테스트 5: 매매 로직 검증

**목적**: 설정한 시간 간격(40초)마다 매수/매도 조건을 확인하고 신호를 생성하는지 검증

**테스트 케이스 5-1: 시간 간격 준수**

**전제 조건**:
- Excel B16 = 40.0 (price_check_interval)

**예상 동작**:
```python
# phoenix_main.py:285
time.sleep(self.settings.price_check_interval)  # 40초 대기
```

**검증 방법**:
- 로그 타임스탬프 확인
- 연속된 시세 조회 간격 = 40초 ± 2초

---

**테스트 케이스 5-2: process_tick() 주기적 실행**

**예상 동작**:
```python
# phoenix_main.py:260-285 (메인 루프)
while is_running:
    # 1. 시세 조회
    price_data = kis_adapter.get_overseas_price("SOXL")
    current_price = price_data['price']

    # 2. 매매 신호 확인
    signals = grid_engine.process_tick(current_price)

    # 3. 신호 처리
    for signal in signals:
        _process_signal(signal)

    # 4. Excel 업데이트
    if (now - last_update_time).seconds >= excel_update_interval:
        _update_system_state(current_price)

    # 5. 40초 대기
    time.sleep(price_check_interval)
```

**검증 로그**:
```
[2026-01-22 10:00:00] SOXL 시세 조회: $45.30
[2026-01-22 10:00:00] process_tick() 실행
[2026-01-22 10:00:40] SOXL 시세 조회: $45.28
[2026-01-22 10:00:40] process_tick() 실행
[2026-01-22 10:01:20] SOXL 시세 조회: $45.25
```

---

**테스트 케이스 5-3: Tier 1 갱신 확인 (process_tick 내부)**

**코드 위치**: grid_engine.py:474-475

```python
def process_tick(self, current_price: float) -> List[TradeSignal]:
    # 1. Tier 1 갱신 확인
    self.update_tier1(current_price)

    # 2. 매도 조건 확인
    # 3. 매수 조건 확인
```

**검증**:
- 매 tick마다 `update_tier1()` 호출됨
- 보유=0이고 상승 시에만 갱신됨

---

### 테스트 6: Excel 업데이트 검증

**목적**: 설정한 간격(1초)마다 Excel 파일이 올바르게 업데이트되는지 확인

**테스트 케이스 6-1: 프로그램 정보 업데이트 (E2~E8)**

**전제 조건**:
- excel_update_interval = 1.0초

**예상 결과**:
- E2: 업데이트 시간 (1초마다 갱신)
- E3: 현재 티어
- E4: 현재가
- E5: 잔고
- E6: 총 보유 수량

**검증 방법**:
```python
# phoenix_main.py:478
excel_bridge.update_program_info(state)

# Excel E2 셀 값이 1초마다 변경되는지 확인
```

---

**테스트 케이스 6-2: 히스토리 로그 추가**

**예상 결과**:
- 시트 "02_운용로그_히스토리"에 1초마다 새 행 추가
- 컬럼: 업데이트 시간, 날짜, 종목, 티어, 잔고, 수익률 등

**검증 방법**:
```python
# phoenix_main.py:486-492
log_entry = excel_bridge.create_history_log_entry(state, settings)
excel_bridge.append_history_log(log_entry)
```

---

## 🧪 통합 테스트 시나리오

### 시나리오 1: 정상 시작 → Tier 1 갱신 → 종료

**단계**:
1. Excel B15 = TRUE, API 키 정상 입력
2. EXE 실행
3. 초기 Tier 1 = 현재가로 설정 확인
4. 40초 대기
5. 현재가 상승 시 Tier 1 갱신 확인
6. Ctrl+C로 종료
7. Excel 최종 상태 저장 확인

**예상 로그**:
```
[OK] 시스템 초기화 완료!
GridEngine 초기화: Tier 1 = $45.30
메인 거래 루프 시작...

(40초 대기)

SOXL 시세 조회: $45.50
Tier 1 갱신: $45.30 → $45.50

(Ctrl+C)

시스템 종료 중...
[OK] 최종 상태 저장 완료
[OK] Phoenix Trading System 정상 종료
```

---

### 시나리오 2: 매수 → 보유 중 → Tier 1 갱신 안됨

**단계**:
1. Tier 1 = $45.00
2. 현재가 = $44.78 (Tier 2 진입, -0.5%)
3. 매수 신호 생성 → 매수 체결
4. 현재가 = $45.50 (상승)
5. **Tier 1 갱신 안됨** (보유 > 0)

**예상 로그**:
```
[BUY] 매수 신호: Tier 2, 100주 @ $44.78
[OK] 매수 체결: Tier 2 - 체결 100주 @ $44.78

(40초 대기, 현재가 $45.50)

SOXL 시세 조회: $45.50
(Tier 1 갱신 로그 없음) ← 보유 중이므로 갱신 안됨
```

---

### 시나리오 3: 매도 → 전량 매도 → Tier 1 갱신 재개

**단계**:
1. Tier 2 보유 중 (100주 @ $44.78)
2. 현재가 = $46.12 (+3% 달성)
3. 매도 신호 생성 → 전량 매도
4. 보유 = 0
5. 현재가 = $46.50 (상승)
6. **Tier 1 갱신됨** (보유 = 0)

**예상 로그**:
```
[SELL] 매도 신호: Tier 2, 100주 @ $46.12
[OK] 매도 체결: Tier 2 - 체결 100주 @ $46.12, 수익 $134.00

(40초 대기, 현재가 $46.50)

SOXL 시세 조회: $46.50
Tier 1 갱신: $45.00 → $46.50 ← 보유 0이므로 갱신됨
```

---

## ✅ 체크리스트 검증 기준

### PASS 조건
- [ ] Excel 파일에서 모든 설정이 올바르게 로드됨
- [ ] B15=TRUE 시 자동으로 거래 루프 시작
- [ ] B15=FALSE 시 중지 메시지 출력 후 종료
- [ ] API 키 누락 시 명확한 에러 메시지
- [ ] KIS API 로그인 성공
- [ ] SOXL 시세 조회 성공
- [ ] 초기 Tier 1 = 현재가로 설정
- [ ] 보유=0일 때 Tier 1 자동 갱신
- [ ] 보유>0일 때 Tier 1 갱신 안됨
- [ ] 40초 간격으로 process_tick() 실행
- [ ] Excel 1초 간격으로 업데이트
- [ ] Ctrl+C로 안전하게 종료
- [ ] 최종 상태 Excel에 저장

### FAIL 조건
- [ ] 설정 로드 실패 또는 잘못된 값
- [ ] B15=TRUE인데 시작 안됨
- [ ] API 키 있는데 로그인 실패
- [ ] 시세 조회 실패
- [ ] Tier 1 갱신 로직 오작동
- [ ] 시간 간격 무시 (즉시 반복 실행)
- [ ] Excel 업데이트 안됨
- [ ] 종료 시 상태 저장 안됨

---

## 📝 테스트 실행 기록

### 실행 1: [대기]
- 실행 시간:
- Excel 파일:
- 결과:
- 비고:

---

## 🔧 문제 발견 시 조치

### 문제 1: Excel 설정 로드 실패
**원인**: 파일 경로 잘못됨, 시트 이름 불일치
**조치**:
- 파일 경로 확인
- 시트 "01_매매전략_기준설정" 존재 확인

### 문제 2: API 로그인 실패
**원인**: API 키 잘못됨, 네트워크 오류
**조치**:
- KIS 개발자 센터에서 API 키 재발급
- 인터넷 연결 확인

### 문제 3: Tier 1 갱신 안됨
**원인**: tier1_auto_update = FALSE
**조치**:
- Excel B7 셀을 TRUE로 변경

### 문제 4: 시간 간격 안 지켜짐
**원인**: price_check_interval 설정 오류
**조치**:
- Excel B16 셀 값 확인 (40.0)

---

## 📌 납품 전 최종 확인 사항

- [ ] 모든 체크리스트 항목 PASS
- [ ] 로그 파일 정상 생성 (logs/ 폴더)
- [ ] Excel 파일 정상 업데이트
- [ ] 히스토리 로그 정상 추가
- [ ] 텔레그램 알림 정상 작동 (옵션)
- [ ] 에러 발생 시 명확한 메시지
- [ ] 사용자 매뉴얼 작성 완료
- [ ] 실거래 경고 메시지 표시

---

**검증 완료 서명**: _______________
**날짜**: _______________

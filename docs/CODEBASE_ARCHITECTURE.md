# Phoenix Trading System - 코드베이스 아키텍처 문서

**작성일**: 2026-01-24
**버전**: v4.1
**목적**: SOXL 그리드 자동매매 시스템

---

## 목차
1. [시스템 개요](#시스템-개요)
2. [프로젝트 구조](#프로젝트-구조)
3. [핵심 컴포넌트](#핵심-컴포넌트)
4. [거래 전략 알고리즘](#거래-전략-알고리즘)
5. [데이터 흐름](#데이터-흐름)
6. [주요 기술 스택](#주요-기술-스택)
7. [보안 및 에러 처리](#보안-및-에러-처리)

---

## 시스템 개요

### 핵심 목적
Phoenix Trading System은 **SOXL (Direxion Daily Semiconductor Bull 3X Shares ETF)** 종목에 대해 그리드 트레이딩 전략을 자동으로 실행하는 시스템입니다.

### 주요 특징
- **240단계 그리드 매매**: Tier 1부터 Tier 240까지 계단식 매수/매도
- **Excel 기반 설정 관리**: 코드 수정 없이 Excel에서 파라미터 조정
- **KIS REST API 통합**: 한국투자증권 REST API를 통한 실시간 거래
- **배치 주문 최적화**: 1회 시세 조회로 여러 티어 동시 주문
- **지정가 주문**: Slippage 방지 (현재가 이하 매수, 현재가 이상 매도)
- **Tier 1 거래 옵션**: 사용자 설정에 따라 최고가 갱신 시 Tier 1 진입 가능

### 거래 로직 핵심
1. **매수**: 현재가가 티어 기준가 이하로 하락 시 지정가 매수
2. **매도**: 티어별 목표가(+3%) 도달 시 지정가 매도
3. **Tier 1 갱신**: 모든 포지션 청산 상태에서 신고가 갱신 시 기준가 갱신

---

## 프로젝트 구조

```
SOLX/
├── phoenix_main.py              # 메인 시스템 진입점
├── src/
│   ├── grid_engine.py           # 그리드 거래 엔진 (핵심 로직)
│   ├── excel_bridge.py          # Excel 파일 I/O 인터페이스
│   ├── kis_rest_adapter.py      # KIS REST API 어댑터
│   ├── models.py                # 데이터 모델 (Position, TradeSignal, GridSettings)
│   └── telegram_notifier.py     # 텔레그램 알림
├── config.py                    # 시스템 설정 상수
├── phoenix_grid_template_v3.xlsx # Excel 설정 템플릿
├── tests/                       # 단위/통합 테스트
├── docs/                        # 문서
└── logs/                        # 실행 로그
```

---

## 핵심 컴포넌트

### 1. PhoenixTradingSystem (phoenix_main.py)

**역할**: 시스템 오케스트레이터 - 모든 컴포넌트 통합 및 거래 루프 실행

#### 주요 메서드

##### `initialize() -> InitStatus`
시스템 초기화 프로세스:
1. Excel 파일 존재 확인
2. Excel 설정 로드 (ExcelBridge)
3. 시스템 실행 여부 확인 (B15 셀)
4. KIS API 키 검증
5. GridEngine 초기화
6. KIS API 로그인 및 토큰 발급
7. 초기 시세 조회
8. 계좌 잔고 조회
9. 텔레그램 알림 초기화

**반환 코드**:
- `0`: 정상
- `10`: 중지 (B15=FALSE)
- `20-24`: 에러 (Excel 누락, API 키 누락, 로그인 실패 등)

##### `run() -> int`
메인 거래 루프:
```python
while 거래 중:
    1. 시세 조회 (KisRestAdapter)
    2. 매매 신호 생성 (GridEngine.process_tick)
    3. 매매 신호 처리 (_process_signal)
    4. Excel 상태 업데이트 (주기적)
    5. 대기 (price_check_interval, 기본 40초)
```

##### `_process_signal(signal: TradeSignal)`
매매 신호 실행:
- **매수 신호**:
  1. KIS API 매수 주문 (지정가)
  2. 체결 확인 대기 (`_wait_for_fill`)
  3. GridEngine 상태 업데이트 (`execute_buy`)
  4. 텔레그램 알림 발송

- **매도 신호**:
  1. KIS API 매도 주문 (지정가)
  2. 체결 확인 대기
  3. GridEngine 상태 업데이트 (`execute_sell`)
  4. 수익 계산 및 텔레그램 알림

##### `_wait_for_fill(order_id: str, expected_qty: int) -> (float, int)`
주문 체결 확인 폴링:
- 최대 재시도: `fill_check_max_retries` (기본 10회)
- 재시도 간격: `fill_check_interval` (기본 2초)
- 반환: (체결가, 체결 수량)

#### 시장 개장 시간 관리
`_is_market_open() -> (bool, str)`:
- 미국 정규장: 월~금 09:30~16:00 (동부시간)
- 한국 시간: 23:30 ~ 06:00 (다음날)
- 주말 처리: 토요일 06:00 ~ 월요일 23:30 = 거래 불가

---

### 2. GridEngine (src/grid_engine.py)

**역할**: 그리드 거래 전략 핵심 로직 - 매수/매도 신호 생성 및 포지션 관리

#### 핵심 속성
```python
positions: List[Position]       # 보유 포지션 리스트
tier1_price: float              # High Water Mark (최고가 기준)
current_price: float            # 현재 시세
account_balance: float          # 계좌 잔고
settings: GridSettings          # 그리드 설정
```

#### 주요 메서드

##### `calculate_tier_price(tier: int) -> float`
티어별 기준가 계산:
```
Tier 1: tier1_price (그대로)
Tier 2: tier1_price × (1 - 0.5%)
Tier 3: tier1_price × (1 - 1.0%)
...
Tier N: tier1_price × (1 - (N-1) × 0.5%)
```

**예시**:
- Tier 1 = $50.00
- Tier 2 = $49.75 (-0.5%)
- Tier 3 = $49.50 (-1.0%)
- Tier 240 = $10.25 (-119.5%)

##### `update_tier1(current_price: float) -> (bool, float)`
Tier 1 (High Water Mark) 자동 갱신 로직:

**조건**:
1. `tier1_auto_update` = TRUE (Excel B7)
2. 총 보유 수량 = 0 (모든 포지션 청산 상태)
3. 현재가 > 현재 Tier 1 가격

**동작**:
```python
if 조건 충족:
    tier1_price = current_price
    logger.info(f"Tier 1 갱신: ${old_tier1:.2f} → ${current_price:.2f}")
```

##### `process_tick(current_price: float) -> List[TradeSignal]`
**배치 주문 방식** - 1회 시세 조회로 모든 거래 결정:

```python
signals = []

# 1. Tier 1 갱신 확인
update_tier1(current_price)

# 2. 매도 배치 생성
for pos in positions:
    tier_sell_price = calculate_tier_price(pos.tier) × 1.03  # +3%
    if current_price ≥ tier_sell_price:
        매도 배치에 추가

if 매도 배치:
    signals.append(TradeSignal(
        action="SELL",
        tiers=(2, 3, 5),  # 여러 티어 동시 매도
        quantity=총 수량,
        price=current_price
    ))

# 3. 매수 배치 생성
for tier in range(start_tier, 240):
    if 이미 보유:
        continue
    tier_price = calculate_tier_price(tier)
    if current_price ≤ tier_price and 잔고 충분:
        매수 배치에 추가

if 매수 배치:
    signals.append(TradeSignal(
        action="BUY",
        tiers=(6, 7, 8),  # 여러 티어 동시 매수
        quantity=총 수량,
        price=current_price
    ))

return signals  # 최대 2개 (매도 1개, 매수 1개)
```

##### `execute_buy(signal, actual_filled_price, actual_filled_qty) -> Position`
매수 체결 처리:

**단일 티어**:
```python
position = Position(
    tier=signal.tier,
    quantity=filled_qty,
    avg_price=filled_price,
    invested_amount=filled_price × filled_qty,
    opened_at=datetime.now()
)
positions.append(position)
account_balance -= invested_amount
```

**배치 티어** (signal.tiers 존재 시):
```python
qty_per_tier = filled_qty // len(signal.tiers)
remainder = filled_qty % len(signal.tiers)

for i, tier in enumerate(signal.tiers):
    tier_qty = qty_per_tier + (remainder if i == 0 else 0)
    positions.append(Position(tier, tier_qty, filled_price, ...))
```

**부분체결 처리**: 체결 수량이 티어 수보다 적으면 첫 번째 티어에 전량 할당

##### `execute_sell(signal, actual_filled_price, actual_filled_qty) -> float`
매도 체결 처리 및 수익 계산:

**단일 티어 전량 매도**:
```python
position = find_position(tier)
sell_amount = filled_price × filled_qty
profit = sell_amount - position.invested_amount
positions.remove(position)
account_balance += sell_amount
return profit
```

**배치 티어 매도** (높은 티어부터 순차 제거):
```python
for position in sorted(positions, reverse=True):  # Tier 높은 순
    if filled_qty 남음:
        qty_to_remove = min(position.quantity, filled_qty)
        제거 또는 부분 제거
        filled_qty -= qty_to_remove
```

#### Tier 1 거래 커스텀 모드 (v3.1)

**설정** (Excel):
- B8: `tier1_trading_enabled` (TRUE/FALSE)
- C18: `tier1_buy_percent` (예: 0.0, -0.005, +0.005)

**매수 조건**:
```python
if tier == 1 and tier1_trading_enabled:
    tier1_buy_price = tier1_price × (1 + tier1_buy_percent)
    if current_price ≤ tier1_buy_price:
        매수 신호 생성
```

**예시**:
- `tier1_buy_percent = 0.0`: Tier 1 = $50.00일 때 $50.00 이하면 매수
- `tier1_buy_percent = -0.005`: $49.75 이하면 매수 (0.5% 하락 시)
- `tier1_buy_percent = +0.005`: $50.25 이하면 매수 (0.5% 상승까지 허용)

---

### 3. ExcelBridge (src/excel_bridge.py)

**역할**: Excel 파일과 시스템 간 데이터 인터페이스

#### Excel 구조

**시트 1: "01_매매전략_기준설정"**

| 영역 | 범위 | 용도 | 읽기/쓰기 |
|------|------|------|-----------|
| A | A1:B16 | 기본 설정 | 읽기 |
| B | D1:E10 | 프로그램 매매 정보 | 쓰기 |
| C | A17:E257 | 240개 티어 테이블 | 읽기 전용 |
| D | G17:N257 | 프로그램 시뮬레이션 영역 | 쓰기 |

**영역 A 주요 설정 필드**:
```
B2: account_no (계좌번호)
B3: ticker (종목, "SOXL" 고정)
B4: investment_usd (총 투자금)
B5: total_tiers (티어 수, 240 고정)
B6: tier_amount (티어당 금액, 자동 계산 가능)
B7: tier1_auto_update (Tier 1 자동 갱신)
B8: tier1_trading_enabled (Tier 1 거래 활성화)
B9: buy_limit (매수 제한)
B10: sell_limit (매도 제한)
B12: kis_app_key (KIS APP KEY)
B13: kis_app_secret (KIS APP SECRET)
B14: kis_account_no (KIS 계좌번호)
B15: system_running (시스템 실행, TRUE/FALSE) ★
B16: price_check_interval (시세 조회 주기, 기본 40초)
B18: telegram_id (텔레그램 ID)
B19: telegram_token (텔레그램 토큰)
B20: telegram_enabled (텔레그램 활성화)
B21: excel_update_interval (Excel 업데이트 주기)
C18: tier1_buy_percent (Tier 1 매수%, 기본 0.0)
```

**영역 D 컬럼 구조** (G17:N257):
```
G: 티어 번호 (1~240)
H: 잔고량 (보유 수량)
I: 투자금 (실제 투자 금액)
J: 티어평단 (평균 매수가)
K: 매수(가) (예상 매수가)
L: 매수(량) (예상 매수 수량)
M: 매도(가) (목표 매도가)
N: 매도(량) (예상 매도 수량)
```

**시트 2: "02_운용로그_히스토리"**
- 시간 순 누적 로그 (append-only)
- 매 업데이트 주기마다 상태 스냅샷 저장

#### 주요 메서드

##### `load_settings() -> GridSettings`
Excel 영역 A 읽기 및 검증:
```python
# 자동 계산 로직 (B6)
if B6 == 수식 or None or 0:
    tier_amount = investment_usd / total_tiers
else:
    tier_amount = float(B6)

# Boolean 안전 읽기
tier1_auto_update = _read_bool(B7)  # 1, "true", "yes" 등 처리

# 검증
if ticker != "SOXL":
    raise ValueError("SOXL만 지원")
```

##### `update_program_info(state: SystemState)`
영역 B 업데이트 (D1:E10):
```python
E2: 최근 업데이트 시간
E3: 현재 티어
E4: 현재가
E5: 잔고
E6: 총 보유 수량
E7: 매수 상태
E8: 매도 상태
```

##### `update_program_area(positions, tier1_price, buy_interval)`
영역 D 업데이트 (G17:N257) - 240개 행 순회:
```python
for tier in range(1, 241):
    row_idx = 17 + tier

    position = find_position(tier)

    if position:
        # 보유 중
        ws[row_idx, 8] = position.quantity  # 잔고량
        ws[row_idx, 10] = position.avg_price  # 티어평단
        ws[row_idx, 13] = position.avg_price × 1.03  # 매도가
    else:
        # 미보유
        buy_price = calculate_tier_price(tier)
        ws[row_idx, 11] = buy_price  # 매수 예상가
```

##### `append_history_log(log_entry: Dict)`
시트 2에 로그 추가 (17개 컬럼):
```python
next_row = ws_history.max_row + 1

ws[next_row, 1] = update_time
ws[next_row, 2] = date
ws[next_row, 3] = sheet
ws[next_row, 4] = ticker
ws[next_row, 5] = tier
...
ws[next_row, 16] = buy_qty
ws[next_row, 17] = sell_qty
```

##### `save_workbook(max_retries=3, retry_delay=1.0) -> bool`
Excel 파일 저장 (재시도 로직):
```python
for attempt in range(max_retries):
    try:
        wb.save(file_path)
        return True
    except PermissionError:
        # Excel 파일이 열려 있는 경우
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
        else:
            logger.error("최대 재시도 초과")
            return False
```

---

### 4. KisRestAdapter (src/kis_rest_adapter.py)

**역할**: 한국투자증권(Korea Investment & Securities) REST API 연동

#### 마이그레이션 배경
| 항목 | 기존 (OpenAPI+) | 신규 (REST API) |
|------|-----------------|-----------------|
| 통신 방식 | COM (ActiveX) | HTTP/WebSocket |
| Python 버전 | 32비트 전용 | 64비트 지원 |
| 플랫폼 | Windows 전용 | 크로스 플랫폼 |
| 해외주식 | 미지원 | 지원 |
| 설치 | OCX 설치 필요 | 설치 불필요 |

#### 인증 프로세스

##### `login() -> bool`
OAuth2 + Approval Key 발급:

**1단계: Access Token 발급**
```python
POST https://openapi.koreainvestment.com:9443/oauth2/tokenP

Request:
{
  "grant_type": "client_credentials",
  "appkey": "...",
  "appsecret": "..."
}

Response:
{
  "access_token": "eyJ...",
  "expires_in": 86400  # 24시간
}
```

**2단계: Approval Key 발급 (WebSocket용)**
```python
POST /oauth2/Approval

Request:
{
  "grant_type": "client_credentials",
  "appkey": "...",
  "secretkey": "..."
}

Response:
{
  "approval_key": "abc123..."
}
```

**3단계: 토큰 캐싱**
```python
kis_token_cache.json 생성:
{
  "access_token": "...",
  "expires_at": "2026-01-25T19:00:00",
  "approval_key": "...",
  "cached_at": "2026-01-24T19:00:00"
}

# 5분 여유를 두고 재발급
if datetime.now() >= expires_at - timedelta(minutes=5):
    재발급
```

#### 주요 API 엔드포인트

##### `get_overseas_price(ticker: str) -> Optional[Dict]`
미국 주식 현재가 조회 (자동 거래소 감지):

**거래소 우선순위**: NAS → AMS → NYS
```python
exchanges_to_try = ["NAS", "AMS", "NYS"]

for excd in exchanges_to_try:
    GET /uapi/overseas-price/v1/quotations/price

    Params:
    {
      "EXCD": "NAS",  # 나스닥
      "SYMB": "SOXL"
    }

    Headers:
    {
      "authorization": "Bearer {access_token}",
      "appkey": "...",
      "appsecret": "...",
      "tr_id": "HHDFS00000300",
      "custtype": "P"
    }

    Response:
    {
      "rt_cd": "0",  # 성공
      "output": {
        "last": "45.30",    # 현재가
        "open": "44.80",
        "high": "45.50",
        "low": "44.50",
        "tvol": "1234567"
      }
    }
```

**SOXL 거래소**: 대부분 AMS (아멕스)에서 조회됨

##### `send_order(side, ticker, quantity, price) -> dict`
주문 실행 (지정가):

```python
POST /uapi/overseas-stock/v1/trading/order

# 1. Hashkey 생성
hashkey = _get_hashkey(payload)

# 2. 계좌번호 파싱
cano, acnt_prdt_cd = _parse_account_no(account_no)
# "12345678-01" → CANO="12345678", ACNT_PRDT_CD="01"

# 3. Payload 구성
{
  "CANO": "12345678",
  "ACNT_PRDT_CD": "01",
  "OVRS_EXCG_CD": "NASD",      # 나스닥
  "PDNO": "SOXL",
  "ORD_QTY": "10",
  "OVRS_ORD_UNPR": "45.30",    # 지정가
  "ORD_SVR_DVSN_CD": "0",
  "ORD_DVSN": "00"              # 00=지정가, 01=시장가
}

# 4. Headers
{
  "authorization": "Bearer ...",
  "tr_id": "JTTT1002U",
  "hashkey": "...",
  ...
}

# 5. Response
{
  "rt_cd": "0",
  "output": {
    "ODNO": "0000123456",       # 주문번호
    "AVG_PRVS": "45.28",        # 평균 체결가
    "TOT_CCLD_QTY": "10"        # 총 체결 수량
  },
  "msg1": "정상처리되었습니다."
}

# 6. 반환값
{
  "status": "SUCCESS",
  "order_id": "0000123456",
  "filled_price": 45.28,
  "filled_qty": 10,
  "message": "정상처리되었습니다."
}
```

##### `get_order_fill_status(order_no: str) -> dict`
주문 체결 상태 조회 (폴링용):

```python
GET /uapi/overseas-stock/v1/trading/inquire-ccnl

Params:
{
  "CANO": "12345678",
  "ACNT_PRDT_CD": "01",
  "ODNO": "0000123456",  # 주문번호
  "ORD_STRT_DT": "20260124",
  "ORD_END_DT": "20260124",
  ...
}

Headers:
{
  "tr_id": "TTTS3035R",  # 실계좌
  ...
}

Response:
{
  "rt_cd": "0",
  "output": [
    {
      "odno": "0000123456",
      "prcs_stat_name": "완료",  # "접수", "거부", "완료"
      "ft_ccld_qty": "10",       # 체결 수량
      "ft_ccld_unpr3": "45.28",  # 체결 단가
      "nccs_qty": "0",           # 미체결 수량
      "rjct_rson_name": ""       # 거부 사유
    }
  ]
}

# 반환값
{
  "status": "완료",
  "filled_qty": 10,
  "filled_price": 45.28,
  "unfilled_qty": 0,
  "reject_reason": ""
}
```

##### `get_balance() -> float`
계좌 잔고 조회:

```python
GET /uapi/overseas-stock/v1/trading/inquire-balance

Params:
{
  "CANO": "12345678",
  "ACNT_PRDT_CD": "01",
  "OVRS_EXCG_CD": "NASD",
  "TR_CRCY_CD": "USD"
}

Response:
{
  "rt_cd": "0",
  "output2": {
    "frcr_dncl_amt_2": "5000.00"  # 외화예수금 (USD)
  }
}

return 5000.00
```

#### Rate Limiting

```python
_apply_rate_limit():
    elapsed = time.time() - last_request_time
    if elapsed < 0.2:  # 초당 5회 (200ms 간격)
        time.sleep(0.2 - elapsed)
    last_request_time = time.time()
```

#### WebSocket 실시간 시세 (미사용)
현재 시스템은 **폴링 방식**을 사용하며 WebSocket은 구현되어 있지만 미활성화:
- `subscribe_realtime_price()`: WebSocket 구독 (비동기)
- `unsubscribe_realtime_price()`: 구독 해제

---

### 5. Models (src/models.py)

#### Position (불변 dataclass)
```python
@dataclass(frozen=True)
class Position:
    tier: int                    # 티어 번호 (1~240)
    quantity: int                # 보유 수량 (주)
    avg_price: float             # 평균 매수가 (USD)
    invested_amount: float       # 투자금 (USD)
    opened_at: datetime          # 포지션 오픈 시각

    def current_value(self, current_price: float) -> float:
        """현재 평가금액"""
        return self.quantity * current_price

    def unrealized_profit(self, current_price: float) -> float:
        """미실현 손익"""
        return (current_price - self.avg_price) * self.quantity
```

#### TradeSignal (불변 dataclass)
```python
@dataclass(frozen=True)
class TradeSignal:
    action: str                  # "BUY" 또는 "SELL"
    tier: int                    # 대표 티어
    price: float                 # 거래 예상 가격 (USD)
    quantity: int                # 거래 수량 (주)
    reason: str                  # 거래 사유
    tiers: Optional[Tuple[int, ...]] = None  # 배치 주문 시 티어들
    timestamp: datetime = None   # 신호 생성 시각
```

**배치 주문 예시**:
```python
TradeSignal(
    action="BUY",
    tier=6,              # 대표 티어 (가장 낮은 티어)
    tiers=(6, 7, 8),     # 실제 매수할 티어들
    price=45.30,
    quantity=30,         # 총 수량 (티어당 10주씩)
    reason="배치 매수 3개 티어"
)
```

#### GridSettings (불변 dataclass)
```python
@dataclass(frozen=True)
class GridSettings:
    # 기본 설정
    account_no: str
    ticker: str                  # "SOXL" 고정
    investment_usd: float        # 총 투자금
    total_tiers: int             # 240 고정
    tier_amount: float           # 티어당 금액
    tier1_auto_update: bool      # Tier 1 자동 갱신

    # Tier 1 거래 설정
    tier1_trading_enabled: bool  # Tier 1 거래 활성화
    tier1_buy_percent: float     # Tier 1 매수% (0.0, -0.005 등)

    # 제한 스위치
    buy_limit: bool              # 매수 제한
    sell_limit: bool             # 매도 제한

    # KIS API 설정
    kis_app_key: str
    kis_app_secret: str
    kis_account_no: str
    system_running: bool         # TRUE=시작, FALSE=중지

    # 텔레그램 알림
    telegram_id: Optional[str]
    telegram_token: Optional[str]
    telegram_enabled: bool

    # 시스템 설정
    excel_update_interval: float = 1.0      # Excel 업데이트 주기 (초)
    price_check_interval: float = 40.0      # 시세 조회 주기 (초)

    # 체결 확인 설정
    fill_check_enabled: bool = True
    fill_check_max_retries: int = 10
    fill_check_interval: float = 2.0

    # 그리드 파라미터
    seed_ratio: float = 0.05     # 시드 비율 (5%)
    buy_interval: float = 0.005  # 매수 간격 (0.5%)
    sell_target: float = 0.03    # 매도 목표 (3%)
```

#### SystemState (가변 dataclass)
```python
@dataclass
class SystemState:
    current_price: float         # 현재가
    tier1_price: float           # Tier 1 기준가
    current_tier: int            # 현재 티어
    account_balance: float       # 계좌 잔고
    total_quantity: int          # 총 보유 수량
    total_invested: float        # 총 투자금
    stock_value: float           # 주식 평가금
    total_profit: float          # 잔고 수익
    profit_rate: float           # 수익률

    buy_status: str = "대기"      # 매수 상태
    sell_status: str = "대기"     # 매도 상태
    last_update: datetime = None # 최근 업데이트 시간
```

---

## 거래 전략 알고리즘

### 그리드 트레이딩 핵심 원리

**기본 개념**: 가격이 하락하면 분할 매수, 상승하면 분할 매도하여 변동성에서 수익 창출

#### 티어 구조 (240단계)
```
Tier 1:   $50.00  (기준가, High Water Mark)
Tier 2:   $49.75  (-0.5%)
Tier 3:   $49.50  (-1.0%)
Tier 4:   $49.25  (-1.5%)
...
Tier 240: $10.25  (-119.5%)
```

### 매수 로직

#### 조건
```python
매수 가능 조건:
1. buy_limit = FALSE (매수 제한 없음)
2. account_balance ≥ tier_amount (잔고 충분)
3. 해당 티어 미보유
4. current_price ≤ tier_price (티어 기준가 이하)
```

#### 예시 시나리오

**초기 상태**:
- Tier 1 = $50.00
- 현재가 = $49.50
- 잔고 = $5,000
- tier_amount = $20.83 (≈ $5,000 / 240)

**현재가 $49.50 시**:
```python
current_tier = 3  # (50.00 - 49.50) / 50.00 / 0.005 + 1

매수 가능 티어 확인:
- Tier 1: $50.00 > $49.50 → X
- Tier 2: $49.75 > $49.50 → X
- Tier 3: $49.50 ≥ $49.50 → O (매수 신호!)
```

**배치 매수** (같은 시세 조회에서):
```python
현재가 = $48.00

매수 가능:
- Tier 5: $48.75 ≥ $48.00 → O
- Tier 6: $48.50 ≥ $48.00 → O
- Tier 7: $48.25 ≥ $48.00 → O
- Tier 8: $48.00 ≥ $48.00 → O

→ TradeSignal(
    action="BUY",
    tiers=(5, 6, 7, 8),
    quantity=40주,  # 4개 티어 × 10주
    price=$48.00    # 지정가 (현재가)
)
```

### 매도 로직

#### 조건
```python
매도 가능 조건:
1. sell_limit = FALSE (매도 제한 없음)
2. 해당 티어 보유 중
3. current_price ≥ tier_sell_price (티어 매도가 이상)

tier_sell_price = tier_buy_price × 1.03  # +3% 목표
```

**중요**: 매도가는 **실제 매수가가 아닌** 티어 지정 매수가 기준으로 계산!

#### 예시

**보유 포지션**:
```python
Position(
    tier=10,
    quantity=10,
    avg_price=$47.30,        # 실제 체결가
    invested_amount=$473.00
)

Tier 10 기준가 = $47.75
Tier 10 매도가 = $47.75 × 1.03 = $49.18
```

**현재가 $49.20 시**:
```python
if $49.20 ≥ $49.18:
    매도 신호 생성!

실제 수익률:
($49.20 - $47.30) / $47.30 = 4.02%  # 티어 기준 3%보다 높을 수 있음
```

**배치 매도** (높은 티어부터):
```python
보유 포지션:
- Tier 8: 10주 @ $48.50
- Tier 10: 10주 @ $47.30
- Tier 12: 10주 @ $46.80

현재가 = $49.50

매도 가능:
- Tier 8: $49.18 ≥ $49.50 → O
- Tier 10: $49.18 ≥ $49.50 → O
- Tier 12: $48.66 < $49.50 → X

→ TradeSignal(
    action="SELL",
    tiers=(8, 10),         # Tier 12는 제외
    quantity=20주,
    price=$49.50           # 지정가 (현재가)
)
```

### Tier 1 갱신 (High Water Mark)

#### 동작 조건
```python
갱신 조건:
1. tier1_auto_update = TRUE (Excel B7)
2. total_quantity = 0 (모든 포지션 청산)
3. current_price > tier1_price (신고가 갱신)
```

#### 시나리오 예시

**초기**:
- Tier 1 = $50.00
- 포지션: Tier 10 보유 중

**Step 1**: 가격 상승 → $52.00
```python
조건 확인:
- tier1_auto_update: TRUE ✓
- total_quantity: 10 (보유 중) X
- current_price > tier1_price: TRUE ✓

→ 갱신 안 함 (포지션 보유 중)
```

**Step 2**: Tier 10 매도 체결 → 포지션 0
```python
조건 확인:
- tier1_auto_update: TRUE ✓
- total_quantity: 0 ✓
- current_price ($52.00) > tier1_price ($50.00) ✓

→ Tier 1 갱신: $50.00 → $52.00

새로운 티어 구조:
Tier 1:   $52.00
Tier 2:   $51.74  (-0.5%)
Tier 3:   $51.48  (-1.0%)
...
```

### 배치 주문의 장점

**기존 방식** (1회 시세당 1개 티어):
```
시세 조회 #1 → Tier 5 매수 신호 → 주문 1
시세 조회 #2 → Tier 6 매수 신호 → 주문 2
시세 조회 #3 → Tier 7 매수 신호 → 주문 3
```
- API 호출 3회
- 슬리피지 위험 (가격 변동)

**배치 방식** (1회 시세당 여러 티어):
```
시세 조회 #1 → Tier 5, 6, 7 매수 신호 → 주문 1 (30주)
```
- API 호출 1회
- 가격 일관성 (같은 시세로 모든 티어 처리)
- 거래 비용 절감

### Tier 1 거래 커스텀 모드 상세

#### 모드 비교

| 모드 | tier1_trading_enabled | tier1_buy_percent | 동작 |
|------|----------------------|-------------------|------|
| 기본 | FALSE | (무시) | Tier 1은 추적 전용, Tier 2부터 매수 |
| 커스텀 | TRUE | 0.0 | Tier 1 ≤ 현재가 시 매수 |
| 커스텀 | TRUE | -0.005 | Tier 1 × 0.995 ≤ 현재가 시 매수 (0.5% 하락 필요) |
| 커스텀 | TRUE | +0.005 | Tier 1 × 1.005 ≤ 현재가 시 매수 (0.5% 상승까지 허용) |

#### 갭 상승 시나리오

**상황**: 장 마감 후 호재로 갭 상승
- 전일 종가: $50.00 (Tier 1)
- 당일 시가: $52.00 (+4%)

**기본 모드 (tier1_trading_enabled = FALSE)**:
```python
Tier 1 자동 갱신:
- 포지션 0개 → tier1_price = $52.00

매수 조건:
- Tier 1: $52.00 > $52.00 → X (매수 안 함)
- Tier 2: $51.74 < $52.00 → X (매수 안 함)

→ 갭 상승 이득 상실!
```

**커스텀 모드 (tier1_trading_enabled = TRUE, tier1_buy_percent = 0.0)**:
```python
Tier 1 자동 갱신:
- tier1_price = $52.00

매수 조건:
- Tier 1: $52.00 × (1 + 0.0) = $52.00 ≤ $52.00 → O (매수!)

→ 갭 상승 이득 확보 ($52.00에 매수 → 추후 $53.56에 매도 시 3% 수익)
```

---

## 데이터 흐름

### 시스템 시작 흐름

```
[사용자] Excel 파일 설정 (B15=TRUE)
    ↓
[main()] PhoenixTradingSystem 생성
    ↓
[initialize()]
    ├─ [ExcelBridge] Excel 파일 로드
    │   └→ GridSettings 객체 생성
    ├─ [GridEngine] 초기화 (settings 전달)
    ├─ [KisRestAdapter] 로그인
    │   ├→ Access Token 발급 (24시간)
    │   └→ Approval Key 발급 (WebSocket용)
    ├─ [KisRestAdapter] 초기 시세 조회
    │   └→ tier1_price 설정
    ├─ [KisRestAdapter] 계좌 잔고 조회
    │   └→ account_balance 설정
    └─ [TelegramNotifier] 초기화 (선택)
    ↓
[_wait_for_market_open()] 시장 개장 대기
    ↓
[run()] 메인 거래 루프 시작
```

### 거래 루프 흐름 (1사이클)

```
[PhoenixTradingSystem.run()]
    ↓
1. [KisRestAdapter] 시세 조회 (폴링)
    └→ price_data = get_overseas_price("SOXL")
    ↓
2. [GridEngine] 매매 신호 생성
    └→ signals = process_tick(current_price)
        ├─ update_tier1() - Tier 1 갱신 확인
        ├─ 매도 배치 확인 (보유 포지션 순회)
        └─ 매수 배치 확인 (티어 1~240 순회)
    ↓
3. [PhoenixTradingSystem] 신호 처리
    for signal in signals:
        _process_signal(signal)
            ↓
        if signal.action == "BUY":
            ├─ [KisRestAdapter] 매수 주문 (지정가)
            │   └→ result = send_order(side="BUY", ...)
            ├─ [PhoenixTradingSystem] 체결 확인
            │   └→ _wait_for_fill(order_id, quantity)
            │       └─ [KisRestAdapter] get_order_fill_status() 폴링
            ├─ [GridEngine] 포지션 생성
            │   └→ execute_buy(signal, filled_price, filled_qty)
            │       └→ positions.append(Position(...))
            └─ [TelegramNotifier] 매수 알림 (선택)

        else if signal.action == "SELL":
            ├─ [KisRestAdapter] 매도 주문 (지정가)
            ├─ [PhoenixTradingSystem] 체결 확인
            ├─ [GridEngine] 포지션 제거 및 수익 계산
            │   └→ profit = execute_sell(signal, ...)
            │       └→ positions.remove(position)
            └─ [TelegramNotifier] 매도 알림 (선택)
    ↓
4. [PhoenixTradingSystem] Excel 업데이트 (주기적)
    if (now - last_update) ≥ excel_update_interval:
        ├─ [GridEngine] 현재 상태 조회
        │   └→ state = get_system_state(current_price)
        ├─ [ExcelBridge] 프로그램 정보 업데이트
        │   ├→ update_program_info(state)
        │   └→ update_program_area(positions, tier1_price)
        ├─ [ExcelBridge] 히스토리 로그 추가
        │   └→ append_history_log(log_entry)
        └─ [ExcelBridge] 파일 저장
            └→ save_workbook()
    ↓
5. [PhoenixTradingSystem] 대기
    └→ time.sleep(price_check_interval)  # 기본 40초
    ↓
6. 루프 반복 (Ctrl+C 또는 에러 시 종료)
```

### 데이터 변환 흐름

```
Excel 파일 (phoenix_grid_template_v3.xlsx)
    ↓ [ExcelBridge.load_settings()]
GridSettings (dataclass, 불변)
    ↓ [GridEngine.__init__()]
GridEngine (positions: List[Position])
    ↓ [GridEngine.process_tick()]
List[TradeSignal] (매수/매도 신호)
    ↓ [PhoenixTradingSystem._process_signal()]
KIS API 주문 (JSON)
    ↓ [KisRestAdapter.send_order()]
OrderResult (order_id, filled_price, filled_qty)
    ↓ [GridEngine.execute_buy/sell()]
Position (tier, quantity, avg_price, invested_amount)
    ↓ [GridEngine.get_system_state()]
SystemState (current_price, total_profit, profit_rate, ...)
    ↓ [ExcelBridge.update_program_info/area()]
Excel 파일 업데이트 (영역 B, D) + 히스토리 로그 (시트 2)
```

---

## 주요 기술 스택

### Python 라이브러리

| 라이브러리 | 용도 | 버전 |
|----------|------|------|
| openpyxl | Excel 파일 읽기/쓰기 | 3.1+ |
| requests | HTTP 요청 (KIS REST API) | 2.31+ |
| websockets | WebSocket 통신 (실시간 시세, 미사용) | 12.0+ |
| logging | 로깅 시스템 | 표준 라이브러리 |
| dataclasses | 데이터 모델 | 표준 라이브러리 (Python 3.7+) |
| datetime | 날짜/시간 처리 | 표준 라이브러리 |
| pathlib | 파일 경로 처리 | 표준 라이브러리 |

### API

| API | 제공자 | 용도 |
|-----|--------|------|
| KIS REST API | 한국투자증권 | 시세 조회, 주문 실행, 잔고 조회 |
| Telegram Bot API | Telegram | 거래 알림 (선택) |

### 파일 포맷

| 포맷 | 파일명 | 용도 |
|------|--------|------|
| .xlsx | phoenix_grid_template_v3.xlsx | 시스템 설정 및 상태 저장 |
| .json | kis_token_cache.json | KIS API 토큰 캐싱 |
| .log | logs/phoenix_YYYYMMDD_HHMMSS.log | 실행 로그 |
| .env | .env | 환경 변수 (미사용, 하드코딩 대신 사용 가능) |

---

## 보안 및 에러 처리

### API 키 관리

**현재 방식**: Excel 파일에 평문 저장
```
B12: KIS APP KEY
B13: KIS APP SECRET
B14: KIS 계좌번호
```

**보안 취약점**:
- Excel 파일이 노출되면 API 키 유출
- Git에 실수로 커밋 시 공개될 위험

**권장 개선**:
1. `.env` 파일 사용 (python-dotenv)
2. 환경 변수 사용
3. 키 관리 서비스 (AWS Secrets Manager 등)

### 에러 처리 전략

#### 1. 초기화 에러

```python
InitStatus (Enum):
    SUCCESS = 0           # 정상
    STOPPED = 10          # 사용자 중지 (B15=FALSE)
    ERROR_EXCEL = 20      # Excel 파일 없음
    ERROR_API_KEY = 21    # KIS API 키 누락
    ERROR_LOGIN = 22      # KIS 로그인 실패
    ERROR_PRICE = 23      # 시세 조회 실패
    ERROR_BALANCE = 24    # 잔고 조회 실패
```

**처리**:
```python
status = system.initialize()

if status == InitStatus.STOPPED:
    logger.warning("시스템 중지 상태 (B15=FALSE)")
    return 10  # 에러 아님, 정상 종료

elif status != InitStatus.SUCCESS:
    logger.error(f"초기화 실패 (코드: {status.value})")
    return status.value  # 20-24
```

#### 2. API 에러

**인증 에러**:
```python
class AuthenticationError(Exception):
    pass

try:
    kis_adapter.login()
except AuthenticationError as e:
    logger.error(f"KIS 로그인 실패: {e}")
    telegram.notify_error("로그인 실패", str(e))
    sys.exit(22)
```

**Rate Limiting**:
```python
_apply_rate_limit():
    # 초당 5회 제한 (200ms 간격)
    elapsed = time.time() - last_request_time
    if elapsed < 0.2:
        time.sleep(0.2 - elapsed)
```

**토큰 만료**:
```python
_refresh_token_if_needed():
    # 만료 5분 전 자동 갱신
    if datetime.now() >= token_expires_at - timedelta(minutes=5):
        logger.info("토큰 갱신 중...")
        self.login()
```

#### 3. Excel 파일 잠금

```python
save_workbook(max_retries=3, retry_delay=1.0):
    for attempt in range(max_retries):
        try:
            wb.save(file_path)
            return True
        except PermissionError:
            # Excel 파일이 열려 있는 경우
            if attempt < max_retries - 1:
                logger.warning(f"Excel 잠금, {retry_delay}초 후 재시도")
                time.sleep(retry_delay)
            else:
                logger.error("최대 재시도 초과")
                return False
```

#### 4. 체결 확인 타임아웃

```python
_wait_for_fill(order_id, expected_qty):
    max_retries = 10  # 20초 (2초 × 10회)

    for attempt in range(1, max_retries + 1):
        time.sleep(2)

        fill_status = kis_adapter.get_order_fill_status(order_id)

        if fill_status["filled_qty"] > 0:
            return fill_status["filled_price"], fill_status["filled_qty"]
        elif fill_status["status"] == "거부":
            logger.error(f"주문 거부: {fill_status['reject_reason']}")
            return 0.0, 0

    # 타임아웃
    logger.warning(f"체결 확인 타임아웃: {order_id}")
    return 0.0, 0
```

**위험**: 체결 확인 타임아웃 시 실제 체결 여부 불확실
- **현재 처리**: 체결 수량 0으로 반환 → 포지션 생성 안 함
- **잠재 위험**: 실제로는 체결되었지만 시스템이 인지 못함
- **권장 개선**: 타임아웃 시 별도 로그 기록 + 수동 확인 필요

#### 5. 0수량 포지션 방지

```python
execute_buy(signal, filled_price, filled_qty):
    # [P0 FIX] 0수량 포지션 방지
    if filled_qty <= 0:
        logger.warning(
            f"매수 실행 거부: Tier {signal.tier} - "
            f"체결 수량이 0 이하입니다 (filled_qty={filled_qty}). "
            f"포지션을 생성하지 않습니다."
        )
        return None
```

#### 6. 시장 마감 감지

```python
if current_price <= 0:
    is_open, message = _is_market_open()
    if not is_open:
        logger.warning(f"시세 $0.00 감지 - {message}")
        logger.info("시장 개장 시간까지 대기합니다...")
        _wait_for_market_open()
        continue
```

### 로깅 전략

**로그 레벨**:
```python
logging.INFO:    # 주요 거래 이벤트 (매수/매도, Tier 1 갱신)
logging.DEBUG:   # 상세 디버깅 정보 (시세 조회, Excel 업데이트)
logging.WARNING: # 경고 (체결 타임아웃, Excel 잠금)
logging.ERROR:   # 에러 (API 실패, 인증 실패)
```

**로그 포맷**:
```python
LOG_FORMAT = "[%(levelname)s] %(asctime)s - %(name)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 출력 예시
[INFO] 2026-01-24 19:30:15 - __main__ - [OK] KIS API 로그인 성공
[INFO] 2026-01-24 19:30:20 - grid_engine - [BATCH BUY] 3개 티어, 총 30주 @ $48.00
[INFO] 2026-01-24 19:30:25 - kis_rest_adapter - 주문 성공: BUY SOXL - 체결 30주 @ $47.98 (주문번호: 0000123456)
```

**로그 파일**:
```
logs/phoenix_20260124_193000.log
```

### 거래 안전장치

#### 1. 시스템 실행 스위치 (B15)
```python
if not settings.system_running:
    logger.warning("[STOP] 시스템이 중지 상태입니다 (Excel B15=FALSE)")
    return InitStatus.STOPPED  # 정상 종료
```

#### 2. 매수/매도 제한 스위치 (B9, B10)
```python
if settings.buy_limit:
    logger.debug("매수 제한 활성화됨")
    return None  # 매수 신호 생성 안 함

if settings.sell_limit:
    logger.debug("매도 제한 활성화됨")
    return None  # 매도 신호 생성 안 함
```

#### 3. 지정가 주문 (Slippage 방지)
```python
# 매수: 현재가 이하 보장
send_order(side="BUY", price=current_price)

# 매도: 현재가 이상 보장
send_order(side="SELL", price=current_price)
```

#### 4. 잔고 확인
```python
if account_balance < tier_amount:
    logger.debug(f"잔고 부족: ${account_balance:.2f} < ${tier_amount:.2f}")
    return None  # 매수 신호 생성 안 함
```

#### 5. 종목 제한
```python
if ticker != "SOXL":
    raise ValueError(f"지원하지 않는 종목: {ticker}. SOXL만 지원합니다.")
```

---

## 종합 평가

### 장점
1. **모듈화된 설계**: 각 컴포넌트가 명확히 분리되어 유지보수 용이
2. **Excel 기반 설정**: 비개발자도 파라미터 조정 가능
3. **배치 주문 최적화**: API 호출 최소화로 효율성 향상
4. **지정가 주문**: Slippage 방지로 거래 안정성 확보
5. **종합 로깅**: 모든 거래 이벤트 추적 가능
6. **에러 복구**: 재시도 로직, 토큰 자동 갱신 등

### 개선 권장 사항

#### 1. 보안
- [ ] API 키를 `.env` 파일 또는 환경 변수로 이동
- [ ] Excel 파일 암호화 (openpyxl.load_workbook(password=...))
- [ ] Git에 `.gitignore` 추가 (*.xlsx, .env, kis_token_cache.json)

#### 2. 안정성
- [ ] 체결 확인 타임아웃 시 수동 확인 프로세스 추가
- [ ] WebSocket 실시간 시세로 전환 (폴링 대체)
- [ ] 중복 주문 방지 로직 (주문 ID 추적)
- [ ] 데이터베이스 도입 (Excel 대체, 히스토리 로그 영구 저장)

#### 3. 모니터링
- [ ] 텔레그램 알림 활성화 권장
- [ ] 웹 대시보드 추가 (실시간 포지션 확인)
- [ ] Prometheus/Grafana 연동 (메트릭 수집)

#### 4. 테스트
- [ ] 단위 테스트 커버리지 확대 (현재 tests/ 폴더 존재)
- [ ] 통합 테스트 자동화 (CI/CD)
- [ ] 모의 거래 모드 추가 (KIS API 모의투자 환경 활용)

#### 5. 성능
- [ ] 비동기 I/O (asyncio) 도입 (KIS API 병렬 호출)
- [ ] Excel 업데이트 주기 최적화 (현재 1초는 과도)
- [ ] 메모리 사용량 모니터링 (장시간 실행 시)

---

## 부록: 주요 설정값 참조

### Excel 템플릿 (phoenix_grid_template_v3.xlsx)

**시트 1: "01_매매전략_기준설정"**

| 셀 위치 | 필드명 | 기본값 | 설명 |
|---------|--------|--------|------|
| B2 | account_no | - | 계좌번호 (레거시, 미사용) |
| B3 | ticker | SOXL | 종목코드 (변경 불가) |
| B4 | investment_usd | 5000.00 | 총 투자금 (USD) |
| B5 | total_tiers | 240 | 티어 분할 수 (변경 불가) |
| B6 | tier_amount | =B4/B5 | 티어당 금액 (자동 계산) |
| B7 | tier1_auto_update | TRUE | Tier 1 자동 갱신 |
| B8 | tier1_trading_enabled | FALSE | Tier 1 거래 활성화 |
| B9 | buy_limit | FALSE | 매수 제한 (긴급 중지용) |
| B10 | sell_limit | FALSE | 매도 제한 (긴급 중지용) |
| B12 | kis_app_key | (입력 필요) | KIS APP KEY |
| B13 | kis_app_secret | (입력 필요) | KIS APP SECRET |
| B14 | kis_account_no | (입력 필요) | KIS 계좌번호 (12345678-01) |
| B15 | system_running | FALSE | 시스템 실행 (TRUE=시작) ★ |
| B16 | price_check_interval | 40.0 | 시세 조회 주기 (초) |
| B18 | telegram_id | - | 텔레그램 Chat ID |
| B19 | telegram_token | - | 텔레그램 Bot Token |
| B20 | telegram_enabled | FALSE | 텔레그램 알림 활성화 |
| B21 | excel_update_interval | 1.0 | Excel 업데이트 주기 (초) |
| C18 | tier1_buy_percent | 0.0 | Tier 1 매수% (0.0, -0.005 등) |

### 하드코딩된 상수 (config.py 또는 코드 내)

```python
# 그리드 파라미터
BUY_INTERVAL = 0.005  # 0.5% (티어 간 하락 간격)
SELL_TARGET = 0.03    # 3% (매도 목표)
SEED_RATIO = 0.05     # 5% (시드 비율, 미사용)

# 체결 확인
FILL_CHECK_ENABLED = True          # 체결 확인 활성화
FILL_CHECK_MAX_RETRIES = 10        # 최대 10회 재시도
FILL_CHECK_INTERVAL = 2.0          # 2초 간격

# KIS API
KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_WS_URL = "ws://ops.koreainvestment.com:21000"
RATE_LIMIT_INTERVAL = 0.2          # 초당 5회 (200ms)

# 시장 개장 시간 (한국 시간 기준)
MARKET_OPEN_HOUR = 23              # 23:30
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 6              # 06:00
MARKET_CLOSE_MINUTE = 0
```

---

**문서 작성**: AI Agent (Claude Code)
**검토 필요**: 사용자 확인
**최종 수정**: 2026-01-24


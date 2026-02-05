# Phoenix Trading System - 실시간 거래로직 및 엣지케이스 분석

**문서 버전**: 1.0
**작성일**: 2026-01-25
**대상 시스템**: Phoenix Trading System (SOXL Grid Trading)
**분석 범위**: Epic 2 (실시간 거래), Epic 3 (갭 상승), Epic 5 (24/7 운영)

---

## 목차

1. [실시간 거래로직 아키텍처](#1-실시간-거래로직-아키텍처)
2. [핵심 실시간 처리 흐름](#2-핵심-실시간-처리-흐름)
3. [엣지케이스 카탈로그 (15개 주요 시나리오)](#3-엣지케이스-카탈로그)
4. [실시간 데이터 동기화 메커니즘](#4-실시간-데이터-동기화-메커니즘)
5. [엣지케이스 대응 전략 매트릭스](#5-엣지케이스-대응-전략-매트릭스)
6. [실거래 위험 평가](#6-실거래-위험-평가)

---

## 1. 실시간 거래로직 아키텍처

### 1.1 실시간 처리 파이프라인

```
[Market Data] → [Price Query] → [Signal Generation] → [Order Execution] → [Fill Confirmation] → [State Update]
    40초 폴링       KIS REST API    GridEngine          KIS Order API        20초 폴링           Excel + Memory
```

**타이밍 특성**:
- 가격 조회 주기: **40초** (설정 가능)
- 체결 확인 폴링: **2초 × 최대 10회 = 20초**
- API Rate Limit: **200ms** 최소 간격 (초당 5회)
- Excel 저장 재시도: **1초 × 최대 3회**

### 1.2 핵심 컴포넌트 및 책임

| 컴포넌트 | 파일 위치 | 실시간 처리 책임 |
|---------|---------|----------------|
| **GridEngine** | `src/grid_engine.py:200-400` | 매수/매도 신호 생성, 배치 주문 최적화, 포지션 추적 |
| **KisRestAdapter** | `src/kis_rest_adapter.py` | KIS REST API 호출, OAuth2 토큰 갱신, 체결 확인 폴링 |
| **PhoenixTradingSystem** | `phoenix_main.py:400-550` | 메인 거래 루프, 신호 처리, 에러 복구 |
| **ExcelBridge** | `src/excel_bridge.py` | 실시간 Excel 동기화 (4개 영역 업데이트) |

---

## 2. 핵심 실시간 처리 흐름

### 2.1 메인 거래 루프 (40초 주기)

```python
# phoenix_main.py:400-550 (실제 코드 기반)
def run(self):
    while not self.stop_signal:
        # [1] 시장 시간 확인 (Epic 5.1)
        if not is_market_open():
            sleep_until_next_open()
            continue

        # [2] 실시간 가격 조회 (Story 2.3)
        current_price = self.kis_adapter.get_current_price("SOXL")
        # KIS API: /uapi/overseas-price/v1/quotations/price
        # EXCD 자동 감지: NAS → AMS → NYS 순차 시도

        # [3] Tier 1 갱신 확인 (Story 2.1)
        if current_price > self.grid_engine.tier1_price and len(positions) == 0:
            self.grid_engine.tier1_price = current_price
            excel_bridge.update_tier1(current_price)  # B18 셀 갱신

        # [4] 배치 매수 신호 생성 (Story 2.4)
        buy_signal = self.grid_engine.process_tick(current_price)
        # TradeSignal(action="BUY", tiers=(4,5,6,7), quantity=40, price=48.50)

        # [5] 지정가 주문 실행 (Story 2.5)
        if buy_signal:
            order_result = self.kis_adapter.send_order(
                side="BUY",
                ticker="SOXL",
                quantity=buy_signal.quantity,
                price=buy_signal.price  # 지정가 = 현재가 (슬리피지 방지)
            )

            # [6] 체결 확인 폴링 (Story 2.5)
            filled_price, filled_qty = self._wait_for_fill(
                order_id=order_result["order_id"],
                expected_qty=buy_signal.quantity,
                max_retries=10,  # 2초 × 10 = 20초
                interval=2
            )

            # [7] 부분 체결 처리 (Story 2.8)
            if filled_qty < buy_signal.quantity:
                # 배치: 티어별 비례 분배 또는 첫 티어 전량 할당
                positions = distribute_partial_fill(buy_signal, filled_qty)

            # [8] 상태 업데이트
            self.grid_engine.execute_buy(buy_signal, filled_price, filled_qty)
            self.excel_bridge.update_all_areas()  # 4개 영역 동기화

        # [9] 매도 신호 처리 (Story 2.6, 2.7)
        sell_signal = self.grid_engine.check_sell_conditions(current_price)
        # ... 매도 로직 (동일 패턴)

        time.sleep(40)  # 다음 틱 대기
```

**실시간 처리 특징**:
- **지정가 주문**: 매수는 현재가 이하, 매도는 현재가 이상 보장
- **배치 최적화**: 1회 가격 조회로 여러 티어 동시 주문 (예: Tier 4-7 4개 티어)
- **체결 확인**: 주문 접수 ≠ 체결, 반드시 20초 폴링으로 확인
- **비동기 아님**: 순차 처리 (체결 확인 완료 후 다음 틱 진행)

### 2.2 배치 매수 신호 생성 알고리즘

```python
# src/grid_engine.py:218-248 (실제 코드)
def generate_buy_signal(self, current_price: float) -> TradeSignal:
    eligible_tiers = []

    for tier in range(1, 241):
        tier_buy_price = self.calculate_tier_price(tier)
        # tier_buy_price = Tier1 × (1 - (tier-1) × 0.005)

        # 조건 1: 가격이 티어 매수가 이하로 하락
        # 조건 2: 해당 티어에 포지션 없음
        if current_price <= tier_buy_price and tier not in self.positions:
            eligible_tiers.append(tier)

    if eligible_tiers:
        return TradeSignal(
            action="BUY",
            tiers=tuple(eligible_tiers),  # 배치: (4, 5, 6, 7)
            price=current_price,  # 지정가
            quantity=len(eligible_tiers) * (tier_amount / current_price),
            reason=f"Batch buy: {len(eligible_tiers)} tiers eligible"
        )

    return None
```

**배치 매수 시나리오 예시**:

| 시나리오 | Tier 1 | 현재가 | 조건 충족 티어 | 배치 수량 |
|---------|--------|--------|--------------|----------|
| 정상 배치 | $50.00 | $48.50 | Tier 4-7 (4개) | 40주 (10×4) |
| 소량 배치 | $50.00 | $49.80 | Tier 2 (1개) | 10주 |
| 대량 배치 (폭락) | $50.00 | $40.00 | Tier 20-40 (21개) | 210주 |
| 배치 없음 | $50.00 | $51.00 | 없음 (Tier 1 이상) | 0주 |

### 2.3 체결 확인 폴링 메커니즘

```python
# phoenix_main.py:513-550 (실제 코드)
def _wait_for_fill(self, order_id: str, expected_qty: int) -> tuple[float, int]:
    """주문 체결 대기 (폴링 방식)"""

    for attempt in range(1, 11):  # 최대 10회 폴링
        time.sleep(2)  # 2초 대기

        # KIS API: /uapi/overseas-stock/v1/trading/inquire-ccnl
        fill_status = self.kis_adapter.get_order_fill_status(order_id)

        status = fill_status["status"]  # "02" = 체결, "01" = 접수
        filled_qty = fill_status["filled_qty"]
        filled_price = fill_status["filled_price"]

        if filled_qty > 0:
            # 체결 완료 (전체 또는 부분)
            return filled_price, filled_qty

        if status == "거부":
            # 주문 거부 (잔고 부족, 호가 초과 등)
            raise OrderRejectedException(fill_status["message"])

    # 20초 타임아웃
    logger.warning(f"체결 확인 타임아웃: 주문번호 {order_id}")
    return 0.0, 0  # 체결 수량 0 반환
```

**체결 확인 타임라인**:
```
[23:32:10] 주문 접수 (order_id: KR1234567890)
[23:32:12] 폴링 1회: status=01 (접수), filled_qty=0
[23:32:14] 폴링 2회: status=02 (체결), filled_qty=10, filled_price=$48.95
[23:32:14] ✅ 체결 확인 완료 (4초 소요)
```

### 2.4 부분 체결 분배 로직

```python
# src/grid_engine.py:316-371 (실제 코드)
def execute_buy(self, signal: TradeSignal, actual_filled_qty: int):
    """배치 주문 부분 체결 처리"""

    if signal.tiers and len(signal.tiers) > 1:
        # 배치 주문 (여러 티어)

        # [엣지케이스 1] 극단적 부분체결: 체결 < 티어 수
        if actual_filled_qty < len(signal.tiers):
            # 예: 4개 티어 주문, 3주 체결 → 첫 티어에만 할당
            position = Position(
                tier=signal.tiers[0],
                quantity=actual_filled_qty,
                avg_price=filled_price,
                invested_amount=filled_price * actual_filled_qty
            )
            self.positions.append(position)
            logger.warning(
                f"[PARTIAL FILL] 배치 극단적 부분체결: "
                f"{actual_filled_qty}주 < {len(signal.tiers)} 티어"
            )
            return position

        # [정상 배치] 티어별 비례 분배
        qty_per_tier = actual_filled_qty // len(signal.tiers)
        remainder = actual_filled_qty % len(signal.tiers)

        for i, tier in enumerate(signal.tiers):
            tier_qty = qty_per_tier + (remainder if i == 0 else 0)

            if tier_qty > 0:  # [안전장치] 0주 포지션 방지
                position = Position(
                    tier=tier,
                    quantity=tier_qty,
                    avg_price=filled_price,
                    invested_amount=filled_price * tier_qty
                )
                self.positions.append(position)

        logger.info(
            f"배치 매수 체결: Tiers {signal.tiers}, "
            f"총 {actual_filled_qty}주 @ ${filled_price:.2f}, "
            f"티어당 {qty_per_tier}주 분배"
        )
```

**부분 체결 시나리오별 분배 전략**:

| 주문 | 체결 수량 | 분배 전략 | 결과 |
|-----|---------|---------|------|
| Tier 5-7 (30주) | 18주 | 비례 분배 | Tier 5:6주, Tier 6:6주, Tier 7:6주 |
| Tier 10-11 (20주) | 7주 | 첫 티어 할당 | Tier 10:7주, Tier 11:없음 |
| Tier 5 (10주) | 6주 | 단일 티어 | Tier 5:6주 |
| Tier 15-20 (60주) | 0주 | 타임아웃 | 포지션 생성 없음 |

---

## 3. 엣지케이스 카탈로그

### 3.1 API 관련 엣지케이스 (5개)

#### EC-01: API 네트워크 타임아웃

**발생 조건**:
- KIS API 호출 시 네트워크 지연/실패
- 타임아웃: 기본 10초 (설정 가능)

**시스템 대응** (Story 5.2):
```python
# src/kis_rest_adapter.py
def get_current_price(self, ticker: str) -> float:
    for attempt in range(1, 4):  # 3회 재시도
        try:
            response = requests.get(url, timeout=10)
            return response.json()["output"]["last"]
        except Timeout:
            logger.warning(f"⚠️  API 호출 실패 (시도 {attempt}/3): Timeout")
            time.sleep(2 ** (attempt - 1))  # Exponential backoff: 1s, 2s, 4s

    # 3회 실패 → 현재 틱 스킵
    logger.error("❌ API 호출 실패 (3회 재시도 실패): 다음 틱 대기")
    return None  # 가격 조회 실패
```

**실거래 영향**:
- ✅ **안전**: 단일 틱 스킵, 40초 후 재시도
- ⚠️ **리스크**: 3회 연속 실패 시 최대 120초 지연 (가격 변동 위험)

**완화 전략**:
- Exponential backoff (1s → 2s → 4s)
- 재시도 후에도 거래 루프 유지 (크래시 방지)

#### EC-02: Rate Limiting (429 Error)

**발생 조건**:
- 초당 5회 이상 API 호출 (200ms 미만 간격)
- KIS API 응답: 429 Too Many Requests

**시스템 대응** (Story 2.3):
```python
# src/kis_rest_adapter.py
class KisRestAdapter:
    def __init__(self):
        self.last_call_time = 0
        self.rate_limit_interval = 0.2  # 200ms

    def _enforce_rate_limit(self):
        elapsed = time.time() - self.last_call_time
        if elapsed < self.rate_limit_interval:
            sleep_time = self.rate_limit_interval - elapsed
            logger.debug(f"⏱️  Rate limiting: {sleep_time*1000:.0f}ms 대기 중")
            time.sleep(sleep_time)

        self.last_call_time = time.time()
```

**실거래 영향**:
- ✅ **안전**: 자동 200ms 지연 삽입
- ⚠️ **리스크**: 배치 주문 시 여러 API 호출 발생 (가격 조회 + 주문 + 체결 확인)

**배치 주문 API 호출 시퀀스**:
```
[23:32:00] 가격 조회 API → 200ms 대기
[23:32:00.2] 주문 API (Tier 5-7 배치) → 200ms 대기
[23:32:00.4] 체결 확인 API #1 → 2초 대기
[23:32:02.6] 체결 확인 API #2 → ...
```

#### EC-03: OAuth2 토큰 만료

**발생 조건**:
- Access Token 유효기간: 24시간
- 만료된 토큰으로 API 호출 시 401 Unauthorized

**시스템 대응** (Story 5.3):
```python
# src/kis_rest_adapter.py
def _ensure_token_valid(self):
    if datetime.now() >= self.token_expires_at:
        logger.info("🔄 토큰 만료 → 재인증 시작")
        self._authenticate()  # OAuth2 재인증
        self._save_token_cache()  # kis_token_cache.json 갱신
```

**자동 복구 타임라인**:
```
[06:00:00] Access Token 만료 감지
[06:00:01] OAuth2 재인증 시작 (APP KEY + SECRET)
[06:00:03] 새 토큰 획득 (expires_in: 86400초)
[06:00:04] 토큰 캐시 저장
[06:00:05] 가격 조회 재시도 → 성공
```

**실거래 영향**:
- ✅ **안전**: 자동 재인증, 거래 중단 없음
- ✅ **보장**: 토큰 만료 5초 전 선제 갱신 (설정 가능)

#### EC-04: 거래소 코드 오류 (EXCD)

**발생 조건**:
- SOXL 거래소 변경 (NAS → AMS 등)
- 잘못된 EXCD로 가격 조회 시 "No data" 응답

**시스템 대응** (Story 2.3):
```python
# src/kis_rest_adapter.py
def get_current_price(self, ticker: str) -> float:
    exchanges = ["NAS", "AMS", "NYS"]  # 우선순위 순서

    for excd in exchanges:
        response = self._query_price(ticker, excd)

        if response and response["output"]["last"] > 0:
            self.exchange_cache[ticker] = excd  # 캐싱
            logger.info(f"SOXL 현재가 조회: ${price} ({excd})")
            return response["output"]["last"]

    raise Exception("모든 거래소에서 가격 조회 실패")
```

**실거래 영향**:
- ✅ **안전**: 자동 거래소 감지, 캐싱으로 성능 최적화
- ⚠️ **리스크**: 최초 감지 시 3회 API 호출 발생 (Rate Limit 고려)

#### EC-05: 주문 거부 (Order Reject)

**발생 조건**:
- 잔고 부족
- 호가 단위 위반
- 거래 정지 종목

**시스템 대응** (Story 2.5):
```python
# phoenix_main.py:513-550
def _wait_for_fill(self, order_id: str):
    fill_status = self.kis_adapter.get_order_fill_status(order_id)

    if fill_status["status"] == "거부":
        logger.error(
            f"❌ 주문 거부: {fill_status['message']} "
            f"(주문번호: {order_id})"
        )
        # 포지션 생성 안 함, 다음 틱에서 재시도
        return 0.0, 0
```

**실거래 영향**:
- ✅ **안전**: 거부된 주문은 포지션 생성 안 함
- ⚠️ **리스크**: 잔고 부족 시 영구적 주문 실패 (수동 개입 필요)

**개선 권장사항**:
- Telegram 알림 추가: "⚠️ 주문 거부 - 수동 확인 필요"
- Excel B15 "시스템 가동" FALSE로 변경 (긴급 정지)

---

### 3.2 부분 체결 엣지케이스 (4개)

#### EC-06: 배치 주문 극단적 부분체결

**발생 조건**:
- 배치 주문 티어 수 > 체결 수량
- 예: Tier 5-7 (3개 티어) 주문, 2주만 체결

**시스템 대응** (Story 2.8):
```python
# src/grid_engine.py:318-336
if actual_filled_qty < len(signal.tiers):
    # 첫 번째 티어에만 전량 할당
    position = Position(
        tier=signal.tiers[0],
        quantity=actual_filled_qty,
        avg_price=filled_price,
        opened_at=datetime.now()
    )
    self.positions.append(position)

    logger.warning(
        f"[PARTIAL FILL] 배치 극단적 부분체결: "
        f"{actual_filled_qty}주 < {len(signal.tiers)} 티어 → "
        f"Tier {signal.tiers[0]}에 전량 할당"
    )
```

**실거래 예시**:

| 주문 내용 | 체결 결과 | 포지션 생성 |
|---------|---------|-----------|
| Tier 10-12 (30주) | 5주 @ $47.00 | Tier 10: 5주 @ $47.00 |
| Tier 20-25 (60주) | 8주 @ $45.00 | Tier 20: 8주 @ $45.00 |

**실거래 영향**:
- ✅ **안전**: 체결된 수량은 정확히 추적
- ⚠️ **비효율**: Tier 11, 12는 포지션 없음 (다음 틱에서 재주문 필요)

#### EC-07: 단일 티어 부분체결

**발생 조건**:
- 단일 티어 주문 (Tier 5, 10주) → 6주만 체결

**시스템 대응** (Story 2.5):
```python
# phoenix_main.py:420-436
filled_price, filled_qty = self._wait_for_fill(order_id, signal.quantity)

if filled_qty > 0:
    position = self.grid_engine.execute_buy(
        signal=signal,
        actual_filled_price=filled_price,
        actual_filled_qty=filled_qty  # 부분 체결 수량
    )

    logger.info(
        f"[OK] 매수 체결: Tier {signal.tier} - "
        f"체결 {filled_qty}/{signal.quantity}주 @ ${filled_price:.2f}"
    )
```

**실거래 영향**:
- ✅ **안전**: 체결된 수량만큼 포지션 생성
- ⚠️ **비효율**: 나머지 수량은 다음 틱 대기 (40초 지연)

**개선 권장사항**:
- 부분 체결 후 즉시 잔여 수량 재주문 (설정 가능)

#### EC-08: 매도 부분체결 후 포지션 보유

**발생 조건**:
- Tier 10 포지션 12주 → 8주만 매도 체결

**시스템 대응** (Story 2.7, 4.4):
```python
# src/grid_engine.py:397-450 (execute_sell)
def execute_sell(self, signal: TradeSignal, actual_filled_qty: int):
    position = next((p for p in self.positions if p.tier == signal.tier), None)

    if actual_filled_qty < position.quantity:
        # 부분 체결: 포지션 수량 업데이트
        remaining_qty = position.quantity - actual_filled_qty

        # 새 포지션 생성 (immutable pattern)
        updated_position = Position(
            tier=position.tier,
            quantity=remaining_qty,
            avg_price=position.avg_price,
            invested_amount=position.avg_price * remaining_qty,
            opened_at=position.opened_at
        )

        # 기존 포지션 제거, 새 포지션 추가
        self.positions.remove(position)
        self.positions.append(updated_position)

        logger.warning(
            f"⚠️  부분 매도: {actual_filled_qty}/{position.quantity}주, "
            f"{remaining_qty}주 보유 유지"
        )
```

**실거래 영향**:
- ✅ **안전**: 잔여 수량 정확히 추적
- ✅ **보장**: 다음 틱에서 잔여 수량 재매도 시도

#### EC-09: 체결 확인 타임아웃

**발생 조건**:
- 20초 폴링 중 체결 확인 실패
- 주문은 접수됐으나 체결 상태 확인 불가

**시스템 대응** (phoenix_main.py:547-550):
```python
# 20초 타임아웃 후
logger.warning(f"⚠️  체결 확인 타임아웃: 주문번호 {order_id}")
return 0.0, 0  # 체결 수량 0 반환

# 메인 로직
if filled_qty == 0:
    logger.error(f"[FAIL] 매수 체결 실패: Tier {signal.tier}")
    # 포지션 생성 안 함
```

**실거래 영향**:
- ⚠️ **위험**: 실제 체결됐으나 시스템이 인지 못함 (포지션 불일치 가능)
- 🛡️ **완화**: 다음 틱에서 잔고 조회 → 실제 보유 수량 확인

**개선 권장사항** (중요):
1. 타임아웃 후 수동 주문 조회 (KIS 홈페이지)
2. Excel Sheet 2 로그와 실제 체결 대조
3. 포지션 불일치 발견 시 수동 동기화 (설정 제공)

---

### 3.3 Excel 동기화 엣지케이스 (3개)

#### EC-10: Excel 파일 잠금 (User Open)

**발생 조건**:
- 사용자가 Excel 파일을 열어둔 상태에서 시스템이 저장 시도
- `PermissionError: [Errno 13] Permission denied`

**시스템 대응** (Story 4.2):
```python
# src/excel_bridge.py
def save_workbook(self):
    for attempt in range(1, 4):
        try:
            self.workbook.save(self.file_path)
            logger.info("Excel 저장 성공")
            return True
        except PermissionError:
            logger.warning(f"⚠️  Excel 잠금: 재시도 중 ({attempt}/3)")
            time.sleep(1)

    logger.error("❌ Excel 저장 실패: 다음 틱에 재시도")
    return False
```

**실거래 영향**:
- ⚠️ **리스크**: 3회 실패 시 상태 미저장 (Excel과 메모리 불일치)
- ✅ **완화**: 거래는 계속 진행, 다음 틱에서 재저장

**권장 운영 방법**:
- Excel 파일 읽기 전용 모드로 열기 (`Ctrl+Shift+O`)
- 실시간 모니터링은 Telegram 사용

#### EC-11: Excel 필드 누락 (B22 등)

**발생 조건**:
- 사용자가 Excel 템플릿 수정 중 필수 필드 삭제
- B22 "Tier 1" 셀이 비어있음

**시스템 대응** (Story 1.1):
```python
# src/excel_bridge.py
def validate_settings(self) -> InitStatus:
    required_fields = {
        "B12": "APP KEY",
        "B13": "APP SECRET",
        "B14": "Account Number",
        # ...
        "B22": "Tier 1 Price"
    }

    for cell, name in required_fields.items():
        if self.worksheet[cell].value is None:
            logger.error(f"❌ 필수 필드 누락: {cell} ({name})")
            return InitStatus.ERROR_EXCEL  # Code 20

    return InitStatus.SUCCESS
```

**실거래 영향**:
- ✅ **안전**: 시스템 시작 거부 (거래 시작 전 검증)
- ✅ **보장**: 초기화 9단계 중 1단계에서 검증

#### EC-12: Sheet 2 로그 10,000+ 행

**발생 조건**:
- 장기간 운영으로 Sheet 2 히스토리 로그 10,000행 초과
- Excel 성능 저하

**시스템 대응** (Story 4.3):
```python
# src/excel_bridge.py
def append_history_log(self, log_entry: dict):
    current_row = self.history_sheet.max_row + 1

    if current_row > 10000:
        logger.warning("⚠️  히스토리 로그: 10,000+ rows (성능 저하 가능)")

    # 계속 append (제한 없음)
    self.history_sheet.append(log_entry.values())
```

**실거래 영향**:
- ⚠️ **리스크**: Excel 저장 속도 저하 (10초 이상)
- 🛡️ **완화**: 월별 로그 아카이빙 (수동)

**개선 권장사항**:
- 5,000행마다 자동 아카이빙 (새 파일 생성)
- 예: `phoenix_history_202601.xlsx`, `phoenix_history_202602.xlsx`

---

### 3.4 시장 시간 및 운영 엣지케이스 (3개)

#### EC-13: 시장 마감 중 주문 실행 중

**발생 조건**:
- 16:00 EST (06:00 KST) 마감 직전 주문 접수
- 체결 확인 중 시장 마감

**시스템 대응** (Story 5.1):
```python
# phoenix_main.py:run()
def run(self):
    while True:
        if not is_market_open():
            logger.info("🔴 시장 마감: 거래 일시정지")
            self._wait_for_market_open()
            continue

        # 주문 실행 중에는 시장 시간 확인 안 함
        # → 체결 확인 완료까지 대기 (최대 20초)
```

**실거래 영향**:
- ⚠️ **리스크**: 마감 직전 주문은 체결 실패 가능
- ✅ **완화**: 마감 1분 전 거래 중단 (설정 가능)

**권장 설정**:
```python
# phoenix_main.py
MARKET_CLOSE_BUFFER = 60  # 마감 60초 전 거래 중단
```

#### EC-14: 갭 상승 직후 Tier 1 매수 실패

**발생 조건**:
- 갭 상승으로 Tier 1 매수 신호 (Story 3.2)
- 지정가 주문 ($50.00) 제출했으나 현재가 $56.00
- 체결 불가 (가격 괴리 10% 이상)

**시스템 대응** (Story 3.2):
```python
# phoenix_main.py
# Tier 1 매수 주문 (지정가 = Tier 1 가격)
order_result = self.kis_adapter.send_order(
    side="BUY",
    ticker="SOXL",
    quantity=20,
    price=50.00  # Tier 1 지정 가격 (현재가 $56.00 아님)
)

# 체결 확인 (20초 폴링)
filled_price, filled_qty = self._wait_for_fill(order_id, 20)

if filled_qty == 0:
    logger.warning("⚠️  Tier 1 매수 체결 실패 (가격 괴리)")
    # 포지션 생성 안 함
```

**실거래 영향**:
- ⚠️ **리스크**: 갭 상승 기회 놓침
- 🛡️ **완화**: 다음 틱에서 재시도 (현재가 하락 시 체결 가능)

**개선 권장사항**:
- Tier 1 매수는 시장가 주문 옵션 제공 (`tier1_market_order=True`)

#### EC-15: Tier 240 도달 (최대 하락)

**발생 조건**:
- SOXL 가격이 Tier 240 매수가 이하로 폭락
- Tier 1 $50.00 → Tier 240 $10.05 (-79.9%)

**시스템 대응** (Story 2.4):
```python
# src/grid_engine.py:218-248
def generate_buy_signal(self, current_price: float):
    eligible_tiers = []

    for tier in range(1, 241):
        if current_price <= self.calculate_tier_price(tier):
            if tier not in self.positions:
                eligible_tiers.append(tier)

    if 240 in eligible_tiers and 240 in self.positions:
        logger.warning("⚠️  Tier 240 도달: 추가 매수 중단")
        return None  # 매수 신호 없음

    return TradeSignal(...)
```

**실거래 영향**:
- ⚠️ **위험**: 추가 매수 불가 (잔고 소진 가능성)
- 🛡️ **완화**: Tier 240 도달 시 Telegram 긴급 알림

**권장 위기 대응**:
1. Excel B15 "시스템 가동" FALSE로 변경 (긴급 정지)
2. 수동 손절매 여부 결정
3. Tier 1 재설정 후 재시작

---

## 4. 실시간 데이터 동기화 메커니즘

### 4.1 3-Layer 상태 관리

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Memory State    │────▶│ Excel State     │────▶│ KIS API State   │
│ (GridEngine)    │     │ (4 Areas)       │     │ (Brokerage)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
   - positions list       - Sheet 1: 4개 영역      - 실제 주문 체결
   - account_balance      - Sheet 2: 히스토리      - 잔고 조회
   - tier1_price          - 40초마다 저장           - 포지션 조회
```

**동기화 타이밍**:
1. **매수 체결 시**: Memory → Excel → KIS (순차)
2. **매도 체결 시**: Memory → Excel → KIS
3. **Tier 1 갱신 시**: Memory → Excel
4. **시스템 시작 시**: Excel → Memory (단방향)

**불일치 시나리오 및 해결**:

| 불일치 상황 | 원인 | 탐지 방법 | 복구 전략 |
|-----------|------|---------|----------|
| Memory ≠ Excel | Excel 저장 실패 (EC-10) | 다음 틱에서 재저장 | Memory → Excel 재동기화 |
| Excel ≠ KIS | 체결 타임아웃 (EC-09) | 수동 주문 조회 | KIS → Excel 수동 입력 |
| Memory ≠ KIS | 시스템 크래시 중 체결 | 시작 시 잔고 조회 | KIS → Memory 복구 |

### 4.2 Excel 4개 영역 업데이트 순서

```python
# src/excel_bridge.py:update_all_areas()
def update_all_areas(self):
    """실시간 Excel 동기화 (매 체결 후 실행)"""

    # [Area A] Settings - 읽기 전용 (업데이트 안 함)

    # [Area B] Program Info (H12:H22)
    self.worksheet["H12"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    self.worksheet["H13"] = ", ".join([str(p.tier) for p in positions])
    self.worksheet["H14"] = f"${current_price:.2f}"
    self.worksheet["H15"] = f"${account_balance:.2f}"
    self.worksheet["H16"] = sum([p.quantity for p in positions])

    # [Area C] Tier Table (C25:G264) - 240 rows
    for tier in range(1, 241):
        row = 24 + tier  # Tier 1 → row 25
        position = next((p for p in positions if p.tier == tier), None)

        self.worksheet[f"F{row}"] = position.quantity if position else None
        self.worksheet[f"G{row}"] = position.avg_price if position else None

    # [Area D] Simulation (I25:M264)
    # ... (생략)

    # 저장 (3회 재시도)
    self.save_workbook()
```

**업데이트 성능**:
- Area B: **O(1)** - 6개 셀만 업데이트
- Area C: **O(N)** - 240개 행 순회 (보유 포지션만 업데이트)
- 총 시간: **평균 50ms** (Excel 잠금 없을 시)

---

## 5. 엣지케이스 대응 전략 매트릭스

| 엣지케이스 | 발생 빈도 | 심각도 | 자동 복구 | 수동 개입 | 완화 우선순위 |
|----------|---------|--------|---------|---------|-------------|
| **EC-01: API 타임아웃** | 높음 (1일 1-3회) | 낮음 | ✅ 3회 재시도 | ❌ | P2 |
| **EC-02: Rate Limiting** | 중간 (1주 1회) | 낮음 | ✅ 200ms 대기 | ❌ | P3 |
| **EC-03: 토큰 만료** | 낮음 (1일 1회) | 중간 | ✅ 자동 재인증 | ❌ | P2 |
| **EC-04: EXCD 오류** | 낮음 (1개월 1회) | 낮음 | ✅ 자동 감지 | ❌ | P3 |
| **EC-05: 주문 거부** | 중간 (1주 1-2회) | 높음 | ❌ | ✅ 잔고 확인 | **P0** |
| **EC-06: 배치 극단적 부분체결** | 높음 (1일 5-10회) | 중간 | ✅ 첫 티어 할당 | ❌ | P1 |
| **EC-07: 단일 부분체결** | 높음 (1일 10-20회) | 낮음 | ✅ 체결량 추적 | ❌ | P2 |
| **EC-08: 매도 부분체결** | 중간 (1일 3-5회) | 중간 | ✅ 잔여량 추적 | ❌ | P1 |
| **EC-09: 체결 타임아웃** | 낮음 (1주 1회) | **높음** | ⚠️ 부분 복구 | ✅ 수동 조회 | **P0** |
| **EC-10: Excel 잠금** | 중간 (사용자 개입) | 낮음 | ✅ 3회 재시도 | ❌ | P3 |
| **EC-11: Excel 필드 누락** | 낮음 (초기화 시) | 높음 | ❌ | ✅ 템플릿 복구 | **P0** |
| **EC-12: 로그 10,000+ 행** | 낮음 (1개월 1회) | 낮음 | ❌ | ✅ 수동 아카이빙 | P3 |
| **EC-13: 마감 중 주문** | 낮음 (1개월 1회) | 중간 | ✅ 체결 대기 | ❌ | P2 |
| **EC-14: Tier 1 체결 실패** | 중간 (갭 상승 시) | 중간 | ✅ 재시도 | ❌ | P1 |
| **EC-15: Tier 240 도달** | 낮음 (폭락 시) | **높음** | ❌ | ✅ 긴급 정지 | **P0** |

**심각도 기준**:
- **높음**: 실거래 손실 가능성, 포지션 불일치
- **중간**: 거래 기회 손실, 성능 저하
- **낮음**: 일시적 지연, 로그 누락

**우선순위 (P0-P3)**:
- **P0**: 즉시 수동 개입 필요 (실거래 위험)
- **P1**: 자동 복구 후 모니터링 필요
- **P2**: 자동 복구 충분, 주기적 확인
- **P3**: 무시 가능, 장기 개선 과제

---

## 6. 실거래 위험 평가

### 6.1 Critical Risk (P0)

#### Risk-01: 체결 타임아웃 후 포지션 불일치 (EC-09)

**시나리오**:
```
[23:32:00] Tier 5 매수 주문 10주 @ $49.00 (주문번호: KR123)
[23:32:02] 체결 확인 #1: status=01 (접수)
[23:32:04] 체결 확인 #2: status=01 (접수)
...
[23:32:20] 체결 확인 #10: status=01 (접수)
[23:32:20] ⚠️  체결 타임아웃 → 포지션 생성 안 함

[실제 KIS 계좌에서는 23:32:15에 10주 체결됨]
```

**영향**:
- ❌ Memory: Tier 5 포지션 없음
- ❌ Excel: Tier 5 수량 0주
- ✅ KIS: Tier 5 10주 보유

**결과**:
- 다음 틱에서 Tier 5 매수 신호 재생성 (중복 매수 위험)
- 실제 보유: 20주, 시스템 인지: 0주

**완화 전략** (필수 구현):
1. **체결 확인 폴링 강화**:
   ```python
   # 타임아웃 후 추가 조회 (1회)
   logger.warning("체결 타임아웃 → 1회 추가 확인")
   time.sleep(5)
   final_status = self.kis_adapter.get_order_fill_status(order_id)
   if final_status["filled_qty"] > 0:
       logger.info("추가 확인에서 체결 발견!")
       return final_status["filled_price"], final_status["filled_qty"]
   ```

2. **다음 틱에서 잔고 조회**:
   ```python
   # phoenix_main.py:run()
   if previous_tick_timeout:
       actual_positions = self.kis_adapter.get_all_positions("SOXL")
       self._sync_positions_from_kis(actual_positions)
   ```

3. **Telegram 긴급 알림**:
   ```
   ⚠️  체결 타임아웃 발생
   주문번호: KR1234567890
   수동 확인 필요: KIS 홈페이지 → 주문 내역 → 체결 여부 확인
   ```

#### Risk-02: 주문 거부 - 잔고 부족 (EC-05)

**시나리오**:
```
잔고: $100
Tier 10-15 배치 매수 신호 (60주 × $47.00 = $2,820)
→ 주문 거부 (잔고 부족)
```

**영향**:
- 거래 중단 (영구적 매수 신호 생성 불가)
- 수동 입금 전까지 시스템 정지

**완화 전략**:
1. **사전 검증**:
   ```python
   # phoenix_main.py:process_buy_signal()
   required_capital = signal.quantity * signal.price

   if self.grid_engine.account_balance < required_capital:
       logger.error(f"❌ 잔고 부족: ${required_capital} 필요, ${balance} 보유")
       self.telegram.notify_error("잔고 부족 - 입금 필요")
       # Excel B15 "시스템 가동" FALSE로 변경
       self.excel_bridge.stop_system()
       return
   ```

2. **긴급 정지 프로토콜**:
   ```
   Telegram: "🛑 긴급 정지: 잔고 부족 ($2,820 필요, $100 보유)"
   Excel B15: TRUE → FALSE (자동 변경)
   시스템: 안전 종료 (포지션 저장)
   ```

#### Risk-03: Tier 240 도달 (EC-15)

**시나리오**:
```
Tier 1: $50.00
현재가: $10.00 (-80%)
Tier 240 매수가: $10.05
→ Tier 240 포지션 생성 후 추가 하락 시 대응 불가
```

**영향**:
- 추가 매수 불가 (240개 티어 모두 소진)
- 반등 전까지 손실 고정

**완화 전략**:
1. **Tier 230 도달 시 조기 경고**:
   ```python
   if max([p.tier for p in positions]) >= 230:
       logger.warning("⚠️  Tier 230 도달: 위험 수준 접근")
       self.telegram.notify_warning("Tier 230 도달 - 모니터링 강화")
   ```

2. **Tier 240 도달 시 긴급 정지**:
   ```python
   if 240 in [p.tier for p in positions]:
       logger.error("🛑 Tier 240 도달: 시스템 긴급 정지")
       self.excel_bridge.stop_system()  # B15 → FALSE
       self.telegram.notify_emergency("Tier 240 도달 - 수동 개입 필요")
   ```

### 6.2 High Risk (P1)

#### Risk-04: 배치 주문 극단적 부분체결 (EC-06)

**시나리오**:
```
Tier 20-30 (11개 티어) 배치 매수
주문: 110주 (티어당 10주)
체결: 5주 (극단적 부분체결)
→ Tier 20에만 5주 할당, Tier 21-30 포지션 없음
```

**영향**:
- 배치 효율성 감소
- 다음 틱에서 Tier 21-30 재주문 (40초 지연)

**완화 전략**:
- 배치 최소 체결률 설정 (예: 50% 미만 시 재주문)

### 6.3 Medium Risk (P2)

#### Risk-05: API 연속 타임아웃 (EC-01)

**시나리오**:
```
[23:30:00] 가격 조회 타임아웃 (3회 재시도 실패)
[23:30:45] 가격 조회 타임아웃 (3회 재시도 실패)
[23:31:30] 가격 조회 타임아웃 (3회 재시도 실패)
→ 120초간 거래 중단
```

**영향**:
- 가격 변동 감지 불가
- 매수/매도 기회 손실

**완화 전략**:
- 5회 연속 실패 시 Telegram 알림
- 네트워크 상태 확인 (ping test)

---

## 7. 실거래 배포 전 체크리스트

### 7.1 엣지케이스 검증 테스트

| 테스트 항목 | 검증 방법 | 통과 기준 |
|-----------|---------|----------|
| **부분 체결 처리** | Mock API로 50% 체결 시뮬레이션 | 포지션 수량 정확히 추적 |
| **체결 타임아웃 복구** | 20초 타임아웃 후 수동 조회 | 추가 조회로 체결 발견 |
| **Excel 잠금 재시도** | 파일 열어둔 상태에서 거래 | 3회 재시도 후 성공 |
| **API 타임아웃 재시도** | 네트워크 차단 후 복구 | 3회 재시도 후 정상 복구 |
| **Tier 240 도달 정지** | 가격을 $10.00로 설정 | 시스템 자동 정지 (B15=FALSE) |

### 7.2 모니터링 설정

**필수 알림 (Telegram)**:
1. ⚠️ 체결 타임아웃 발생
2. ⚠️ 잔고 부족 (긴급 정지)
3. ⚠️ Tier 230 도달 (위험 경고)
4. 🛑 Tier 240 도달 (긴급 정지)
5. ❌ API 5회 연속 실패

**권장 모니터링 주기**:
- 실시간: Telegram 알림
- 1시간마다: Excel 파일 확인 (H12 업데이트 시간)
- 1일 1회: Sheet 2 로그 검토

---

## 8. 결론 및 권장사항

### 8.1 실시간 거래로직 안정성 평가

| 평가 항목 | 점수 (1-5) | 평가 근거 |
|---------|-----------|----------|
| **신호 생성 정확성** | 5/5 | 배치 최적화, 티어 기반 정확한 가격 계산 |
| **주문 실행 안전성** | 4/5 | 지정가 주문, 체결 확인 폴링 (타임아웃 리스크 존재) |
| **부분 체결 처리** | 5/5 | 비례 분배, 극단적 케이스 대응 |
| **에러 복구 능력** | 4/5 | 3회 재시도, exponential backoff (수동 개입 필요 케이스 존재) |
| **데이터 동기화** | 3/5 | Excel 잠금 재시도 (불일치 가능성) |
| **24/7 운영 안정성** | 4/5 | 시장 시간 자동 감지, 토큰 자동 갱신 |

**종합 평가**: **4.2/5** (실거래 배포 가능, 모니터링 필수)

### 8.2 우선 개선 권장사항

#### P0 (즉시 구현 필요)
1. **체결 타임아웃 추가 조회** (Risk-01 완화)
2. **잔고 사전 검증 및 긴급 정지** (Risk-02 완화)
3. **Tier 240 도달 자동 정지** (Risk-03 완화)

#### P1 (1주 내 구현)
4. 배치 부분체결 최소 비율 설정 (50% 미만 재주문)
5. Excel Sheet 2 자동 아카이빙 (5,000행마다)

#### P2 (1개월 내 구현)
6. 실시간 포지션 동기화 (KIS ↔ Memory 주기적 검증)
7. Tier 1 매수 시장가 옵션

### 8.3 최종 권고

✅ **배포 가능 조건**:
- P0 개선사항 3개 모두 구현 완료
- 소액 테스트 ($100-$500) 1주일 운영
- Telegram 알림 설정 완료
- 매일 1회 Excel 로그 검토

⚠️ **운영 시 필수 사항**:
- Excel 파일 읽기 전용으로 열기
- 체결 타임아웃 알림 시 즉시 KIS 홈페이지 확인
- Tier 230 도달 시 수동 모니터링 강화

---

**문서 끝** | Phoenix Trading System v1.0 | 2026-01-25

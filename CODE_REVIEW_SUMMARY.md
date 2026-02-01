# Phoenix Trading System - 코드 리뷰 종합 보고서

**검토일:** 2026-02-01
**검토자:** 3개 전문 에이전트 (KIS Adapter / Grid Engine / Phoenix Main)

---

## Executive Summary

총 **37개 이슈** 발견:
- **CRITICAL: 9개** - 실거래 전 필수 수정
- **HIGH: 10개** - 안정성 위험, 조속히 수정
- **MEDIUM: 12개** - 코드 품질 개선
- **LOW: 6개** - 유지보수성 향상

**핵심 위험:** 동시성 제어 부재로 인한 중복 주문, 보안 취약점

---

## CRITICAL Issues (실거래 전 필수 수정)

### 1. KIS REST Adapter - 보안 취약점

#### C1. 토큰 파일 평문 저장
- **위치:** `src/kis_rest_adapter.py:240-252`
- **문제:** `kis_token_cache.json` 파일에 OAuth 토큰을 평문으로 저장
- **위험:** 로컬 사용자/악성코드가 토큰을 탈취하여 계좌 조작 가능
- **수정:**
```python
import os, stat

def _save_token_cache(self):
    # ... 기존 코드 ...
    with open(self.token_cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
    # 파일 권한을 소유자만 읽기/쓰기로 제한
    os.chmod(self.token_cache_file, stat.S_IRUSR | stat.S_IWUSR)
```

#### C2. 토큰 갱신 Race Condition
- **위치:** `src/kis_rest_adapter.py:263-278`
- **문제:** 여러 스레드가 동시에 토큰 갱신 시도 가능
- **위험:** KIS API Rate Limit 초과로 계정 잠금
- **수정:**
```python
import threading

class KisRestAdapter:
    def __init__(self, ...):
        self._token_lock = threading.Lock()

    def _refresh_token_if_needed(self):
        if not self._is_token_valid():
            with self._token_lock:
                # Double-check after acquiring lock
                if not self._is_token_valid():
                    self.login()
```

### 2. Grid Engine - 거래 로직 결함

#### C3. Tier 상태 Race Condition (💰 금전적 손실 위험)
- **위치:** `src/grid_engine.py:450-490`
- **문제:** 시세 콜백 스레드가 동시에 같은 Tier 읽고 주문 실행
- **위험:** **동일 Tier에 중복 매수 주문** → 의도하지 않은 2배 포지션
- **수정:**
```python
import threading

class GridEngine:
    def __init__(self, ...):
        self._order_lock = threading.Lock()

    def process_tick(self, current_price: float):
        with self._order_lock:
            # 상태 읽기 → 판단 → 주문 → 상태 쓰기 (원자적 실행)
            ...
```

#### C4. 주문 수량 검증 없음
- **위치:** `src/grid_engine.py:520-545`
- **문제:** `quantity = int(amount / price)` 계산 결과를 검증 없이 주문
- **위험:**
  - `price = 0` → Division by Zero
  - `price = 0.0001` → 수백만 주 주문
  - `quantity = 0` → 무효 주문
- **수정:**
```python
def _calculate_quantity(self, investment_amount: float, price: float) -> int:
    if price <= 0:
        logger.error(f"Invalid price: {price}")
        return 0
    qty = int(investment_amount / price)
    if qty <= 0:
        logger.warning(f"Quantity is 0 for amount={investment_amount}, price={price}")
        return 0
    MAX_QTY = 10000  # 안전 상한선
    if qty > MAX_QTY:
        logger.error(f"Quantity {qty} exceeds safety cap {MAX_QTY}")
        return 0
    return qty
```

#### C5. Gap Trading 무제한 주문
- **위치:** `src/grid_engine.py:680-740`
- **문제:** 가격 갭 발생 시 건너뛴 모든 Tier에 주문 (10개, 20개 무제한)
- **위험:** **플래시 크래시 시 전체 잔고 소진**
- **수정:**
```python
MAX_BATCH_ORDERS = 3  # Excel에서 설정 가능하도록

def _process_gap_scenario(self, crossed_tiers: list, ...):
    if len(crossed_tiers) > MAX_BATCH_ORDERS:
        logger.warning(f"Gap crossed {len(crossed_tiers)} tiers, limiting to {MAX_BATCH_ORDERS}")
        crossed_tiers = crossed_tiers[:MAX_BATCH_ORDERS]
    for tier in crossed_tiers:
        self._execute_buy_order(tier, ...)
```

### 3. Phoenix Main - 시스템 안정성

#### C6. 토큰 갱신 중 주문 실행
- **위치:** `phoenix_main.py:92-103`, `120-148`
- **문제:** 토큰 갱신과 주문 실행 사이에 동기화 없음
- **위험:** 만료된 토큰으로 주문 → 실패 → 주문 누락
- **수정:**
```python
class PhoenixTradingSystem:
    def __init__(self):
        self._token_lock = threading.RLock()

    def _refresh_token(self):
        with self._token_lock:
            self.api.login()

    def _execute_order(self, ticker, order):
        with self._token_lock:
            return self.api.send_order(order)
```

#### C7. Excel 동시 접근 미보호
- **위치:** `phoenix_main.py:160-175`
- **문제:** 시세 콜백 스레드와 메인 루프가 동시에 Excel 읽기/쓰기
- **위험:** 파일 손상, PermissionError, 데이터 불일치
- **수정:**
```python
class PhoenixTradingSystem:
    def __init__(self):
        self._excel_lock = threading.Lock()

    def _update_excel(self, ticker, price, status):
        with self._excel_lock:
            self.excel_bridge.update_price(ticker, price)
            self.excel_bridge.update_status(ticker, status)
```

#### C8. 예외 삼킴으로 인한 중복 주문
- **위치:** `phoenix_main.py:144-147`
- **문제:** 주문 실행 중 예외를 로그만 남기고 계속 진행
- **위험:** 부분 체결 후 예외 발생 → 다음 사이클에 중복 주문
- **수정:**
```python
def _check_and_execute(self, ticker, price):
    try:
        signal = self.grid_engine.process_tick(price)
        if signal:
            result = self.api.send_order(signal)
            if not result.success:
                if "잔고부족" in result.message:
                    self._disable_ticker(ticker)
                elif "토큰만료" in result.message:
                    self._refresh_token()
                    # 재시도
                    result = self.api.send_order(signal)
    except requests.exceptions.Timeout:
        logger.warning(f"주문 타임아웃 (재시도 가능): {ticker}")
    except Exception as e:
        logger.critical(f"주문 실행 중 예상치 못한 오류: {ticker}", exc_info=True)
        self._disable_ticker(ticker)  # 안전을 위해 해당 종목 거래 중단
```

---

## HIGH Issues (조속히 수정 권장)

### KIS REST Adapter
- **H1.** 예외 타입 구분 없음 (네트워크 오류 vs 버그)
- **H2.** Retry에 Exponential Backoff 없음
- **H3.** HTTP 429/401/503 응답 처리 없음

### Grid Engine
- **H4.** 부분 체결 시 상태 불일치
- **H5.** Tier 가격 계산 부동소수점 오차
- **H6.** Excel 데이터 staleness 체크 없음
- **H7.** 예외 무시로 인한 상태 손상

### Phoenix Main
- **H8.** 시세 콜백에서 블로킹 주문 실행 (다른 종목 지연)
- **H9.** Graceful Shutdown 미흡 (진행 중 주문 미완료)
- **H10.** 텔레그램 알림 타임아웃 없음 (무한 블로킹)

---

## 우선순위별 수정 로드맵

### Phase 1: 긴급 (실거래 전 필수) - 1일
1. `.gitignore`에 `kis_token_cache.json` 추가 (1분)
2. 토큰 파일 권한 제한 (15분)
3. 주문 수량 검증 로직 추가 (30분)
4. Gap Trading 배치 제한 추가 (30분)
5. Excel/토큰 Lock 추가 (1시간)

### Phase 2: 고위험 수정 - 2일
6. Tier 상태 Race Condition 수정 (2시간)
7. 예외 처리 세분화 (3시간)
8. 시세 콜백 비동기화 (4시간)
9. Graceful Shutdown 구현 (2시간)

### Phase 3: 품질 개선 - 1주
10. Retry Exponential Backoff
11. HTTP 상태 코드 처리
12. 타입 힌트 추가
13. 매직 넘버 제거

---

## 긍정적 측면

- ✅ 토큰 캐싱으로 불필요한 재인증 방지
- ✅ Retry 로직 존재 (개선 필요하지만 기본 구조는 있음)
- ✅ Paper/Live 모드 분리
- ✅ Excel 기반 설정으로 비개발자 사용 가능
- ✅ 로깅 체계 존재
- ✅ 텔레그램 알림 통합

---

## 결론

**현재 상태:** 기본 기능은 구현되었으나, **동시성 제어 부재**와 **보안 취약점**으로 인해 **실거래에 즉시 투입 시 위험**

**권장 사항:**
1. **Phase 1 (긴급 수정) 완료 후 소액 Paper Trading 테스트**
2. **Phase 2 완료 후 실거래 전환**
3. Phase 3는 운영 중 점진적 개선

**예상 총 작업 시간:** 약 20시간 (1주일)

---

**검토 완료일:** 2026-02-01
**다음 검토 예정일:** Phase 2 완료 후

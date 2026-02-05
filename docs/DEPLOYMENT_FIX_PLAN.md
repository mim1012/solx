# Phoenix Trading System - 실거래 배포 수정 계획

**작성일**: 2026-01-21
**버전**: v4.2 (배포 준비)
**상태**: 🔴 현재 배포 불가 → 🟢 배포 가능 목표

---

## 📋 Executive Summary

### 현재 상태
- **배포 가능성**: ❌ **불가** (CRITICAL)
- **치명적 버그**: 3개 (주문 실행 차단, 계좌번호 형식 오류, 상태 동기화 부재)
- **고위험 이슈**: 4개 (엑셀 파싱, 다중 주문, 에러 핸들링, 중복 주문)

### 목표
모든 P0~P2 이슈를 해결하여 **실거래 환경에서 안전하게 주문을 실행하고, 실계좌와 시스템 상태를 동기화**하는 안정적인 시스템 구축

---

## 🎯 Priority 0 (P0) - 주문 실행 차단 해결 [CRITICAL]

### ✅ 작업 1: `send_order()` 시그니처 통일
**파일**: `kis_rest_adapter.py`, `phoenix_main.py`
**예상 시간**: 1-2시간

#### 현재 문제
```python
# phoenix_main.py:305-335 (호출부)
self.kis_adapter.send_order(
    side="BUY",          # ❌ 잘못된 파라미터
    ticker=signal.ticker,
    quantity=signal.quantity,
    price=signal.price
)

# kis_rest_adapter.py:759-783 (정의)
def send_order(self, order_type, ticker, quantity, price):
    # side 파라미터 없음
    ...
```

#### 수정 방안
**Option A (권장)**: 어댑터 시그니처를 호출부에 맞춤
```python
# kis_rest_adapter.py
def send_order(self, side: str, ticker: str, quantity: int, price: Optional[float] = None) -> dict:
    """
    주문 전송 (매수/매도 통합)

    Args:
        side: "BUY" or "SELL"
        ticker: 종목코드 (예: "SOXL")
        quantity: 주문 수량
        price: 지정가 (None이면 시장가)

    Returns:
        {
            "order_id": "주문번호",
            "filled_price": 체결가격,
            "filled_qty": 체결수량,
            "status": "SUCCESS" | "FAILED",
            "message": "상세 메시지"
        }
    """
    # side에 따라 tr_id 분기
    if side == "BUY":
        tr_id = "JTTT1002U"  # 해외주식 매수
        order_type = "00"     # 지정가
    elif side == "SELL":
        tr_id = "JTTT1006U"  # 해외주식 매도
        order_type = "00"
    else:
        raise ValueError(f"Invalid side: {side}. Must be 'BUY' or 'SELL'")

    # 시장가 처리
    if price is None:
        order_type = "01"  # 시장가
        price = 0

    # ... (기존 주문 로직)
```

**Option B**: 호출부를 어댑터에 맞춤 (비권장 - 호출부가 더 많음)

#### 구현 체크리스트
- [ ] `kis_rest_adapter.send_order()` 시그니처 변경
- [ ] `side` → `tr_id` 매핑 로직 추가
- [ ] 시장가/지정가 분기 처리
- [ ] 반환값을 구조화된 dict로 변경 (주문번호, 체결가, 체결수량 포함)
- [ ] `phoenix_main._process_signal()` 호출 코드 확인 (이미 올바름)
- [ ] 단위 테스트 작성 (`tests/test_kis_send_order.py`)

---

### ✅ 작업 2: 계좌번호/상품코드 분리
**파일**: `excel_bridge.py`, `kis_rest_adapter.py`
**예상 시간**: 1시간

#### 현재 문제
```python
# excel_bridge.py:193-197
account_no = str(self.ws_master["B14"].value or "")  # "12345-67"

# kis_rest_adapter.py:388-396 (주문 요청)
body = {
    "CANO": account_no,  # ❌ "12345-67" 그대로 전달
    "ACNT_PRDT_CD": "??",  # 누락
    ...
}
```

#### KIS REST API 사양
- `CANO`: 계좌번호 앞 8자리 (예: `12345678`)
- `ACNT_PRDT_CD`: 계좌상품코드 2자리 (예: `01`)
- Excel B14 형식: `12345678-01` 또는 `1234567801`

#### 수정 방안
```python
# excel_bridge.py
def _parse_account_no(self, raw_account: str) -> Tuple[str, str]:
    """
    계좌번호 파싱 (KIS REST API 사양)

    Input: "12345678-01" or "1234567801"
    Output: ("12345678", "01")
    """
    raw_account = raw_account.strip().replace("-", "")

    if len(raw_account) < 10:
        raise ValueError(f"계좌번호가 너무 짧습니다: {raw_account}")

    cano = raw_account[:8]
    acnt_prdt_cd = raw_account[8:10]

    return cano, acnt_prdt_cd

# GridSettings에 필드 추가
@dataclass
class GridSettings:
    account_no: str        # 원본 (예: "12345678-01")
    account_cano: str      # 계좌번호 (예: "12345678")
    account_prdt_cd: str   # 상품코드 (예: "01")
    ...

# kis_rest_adapter.send_order()에서 사용
body = {
    "CANO": self.settings.account_cano,
    "ACNT_PRDT_CD": self.settings.account_prdt_cd,
    ...
}
```

#### 구현 체크리스트
- [ ] `_parse_account_no()` 유틸리티 함수 추가
- [ ] `GridSettings`에 `account_cano`, `account_prdt_cd` 필드 추가
- [ ] `ExcelBridge.load_settings()`에서 파싱 호출
- [ ] `KisRestAdapter` 생성자에서 분리된 값 전달
- [ ] 주문 요청 body에 올바른 필드 사용
- [ ] 단위 테스트 작성 (정상 케이스, 잘못된 형식)

---

### ✅ 작업 3: 주문 응답 처리 및 체결 동기화
**파일**: `kis_rest_adapter.py`, `grid_engine.py`, `phoenix_main.py`, `models.py`
**예상 시간**: 3-4시간

#### 현재 문제
1. `send_order()` 반환값을 무시함 → 주문번호/체결가 저장 안 됨
2. `GridEngine`이 로컬 시뮬레이션으로만 포지션 관리 → 실계좌와 괴리
3. 부분 체결, 슬리피지 미반영

#### 목표 아키텍처
```
[KIS REST API]
      ↓
  체결 응답 (주문번호, 체결가, 체결수량)
      ↓
[KisRestAdapter] → dict 반환
      ↓
[phoenix_main._process_signal] → 응답 검증
      ↓
[GridEngine.execute_buy/sell] → 실제 체결가로 포지션 갱신
      ↓
[ExcelBridge] → 엑셀에 실제 체결 기록
```

#### 수정 방안

##### 3.1. KisRestAdapter 반환값 구조화
```python
# kis_rest_adapter.py
def send_order(self, side: str, ticker: str, quantity: int, price: Optional[float] = None) -> dict:
    """
    Returns:
        성공 시:
        {
            "status": "SUCCESS",
            "order_id": "US20260121000001",
            "filled_price": 45.23,
            "filled_qty": 10,
            "message": "주문 체결 완료"
        }

        실패 시:
        {
            "status": "FAILED",
            "order_id": None,
            "filled_price": 0.0,
            "filled_qty": 0,
            "error_code": "40310000",
            "message": "잔고 부족"
        }
    """
    try:
        # API 호출
        response = self._post(url, headers, body)

        # 응답 파싱
        if response.get("rt_cd") == "0":  # 성공
            output = response.get("output", {})
            return {
                "status": "SUCCESS",
                "order_id": output.get("ODNO"),        # 주문번호
                "filled_price": float(output.get("AVG_PRVS", price)),  # 체결가
                "filled_qty": int(output.get("TOT_CCLD_QTY", quantity)),  # 체결수량
                "message": response.get("msg1", "주문 성공")
            }
        else:  # 실패
            return {
                "status": "FAILED",
                "order_id": None,
                "filled_price": 0.0,
                "filled_qty": 0,
                "error_code": response.get("rt_cd"),
                "message": response.get("msg1", "주문 실패")
            }

    except Exception as e:
        logger.error(f"주문 전송 예외: {e}")
        return {
            "status": "FAILED",
            "order_id": None,
            "filled_price": 0.0,
            "filled_qty": 0,
            "message": str(e)
        }
```

##### 3.2. GridEngine 체결 동기화
```python
# grid_engine.py
def execute_buy(self, signal: TradeSignal, actual_filled_price: float, actual_filled_qty: int) -> Position:
    """
    매수 체결 실행 (실제 체결가 반영)

    Args:
        signal: 원래 시그널
        actual_filled_price: KIS API에서 받은 실제 체결가
        actual_filled_qty: 실제 체결 수량
    """
    # 실제 체결가로 포지션 생성
    invested = actual_filled_price * actual_filled_qty
    position = Position(
        tier=signal.tier,
        quantity=actual_filled_qty,
        avg_price=actual_filled_price,
        invested_amount=invested,
        opened_at=datetime.now()
    )

    # 포지션 추가
    self.positions.append(position)

    # 잔고 차감 (실제 체결금액)
    self.cash_balance -= invested

    logger.info(f"매수 체결: Tier {signal.tier}, 수량 {actual_filled_qty}, 가격 ${actual_filled_price:.2f}")
    return position

def execute_sell(self, current_price: float, tier: int, actual_filled_price: float, actual_filled_qty: int) -> float:
    """
    매도 체결 실행 (실제 체결가 반영)

    Returns:
        realized_profit: 실현 수익 (USD)
    """
    # ... (기존 로직과 유사하지만 actual_filled_price 사용)
```

##### 3.3. phoenix_main 응답 처리
```python
# phoenix_main.py
def _process_signal(self, signal: TradeSignal):
    """매매 신호 처리 (응답 검증 추가)"""
    try:
        if signal.action == "BUY":
            # 주문 전송
            result = self.kis_adapter.send_order(
                side="BUY",
                ticker=signal.ticker,
                quantity=signal.quantity,
                price=signal.price
            )

            # 응답 검증
            if result["status"] == "SUCCESS":
                # 실제 체결가로 포지션 갱신
                position = self.grid_engine.execute_buy(
                    signal=signal,
                    actual_filled_price=result["filled_price"],
                    actual_filled_qty=result["filled_qty"]
                )

                # 텔레그램 알림 (실제 체결가 포함)
                self.telegram.send_message(
                    f"✅ 매수 체결\n"
                    f"종목: {signal.ticker}\n"
                    f"Tier: {signal.tier}\n"
                    f"주문 수량: {signal.quantity}\n"
                    f"실제 체결: {result['filled_qty']}주 @ ${result['filled_price']:.2f}\n"
                    f"주문번호: {result['order_id']}"
                )

                # Excel 기록
                self._log_trade_history(signal, result)

            else:  # 주문 실패
                logger.error(f"주문 실패: {result['message']}")
                self.telegram.send_message(
                    f"❌ 주문 실패\n"
                    f"{result['message']}\n"
                    f"에러 코드: {result.get('error_code', 'N/A')}"
                )

        elif signal.action == "SELL":
            # ... (매도도 동일하게 처리)

    except Exception as e:
        logger.error(f"신호 처리 예외: {e}")
        self.telegram.send_message(f"⚠️ 시스템 에러: {e}")
```

#### 구현 체크리스트
- [ ] `KisRestAdapter.send_order()` 반환값 구조화
- [ ] KIS REST API 응답 필드 매핑 (`ODNO`, `AVG_PRVS`, `TOT_CCLD_QTY`)
- [ ] `GridEngine.execute_buy/sell()` 시그니처 변경 (체결가/수량 파라미터 추가)
- [ ] `phoenix_main._process_signal()` 응답 검증 로직
- [ ] 주문 실패 시 텔레그램 알림
- [ ] Excel 히스토리에 주문번호, 체결가 기록
- [ ] 통합 테스트 (`tests/test_order_execution_flow.py`)
- [ ] Mock KIS API로 성공/실패/부분체결 시나리오 검증

---

## ⚠️ Priority 1 (P1) - 고위험 해결 [HIGH RISK]

### ✅ 작업 4: 엑셀 파싱 검증 강화
**파일**: `excel_bridge.py`
**예상 시간**: 2시간

#### 현재 문제
```python
# excel_bridge.py:178-243
investment_usd = float(self.ws_master["B4"].value)  # ❌ "10,000" → ValueError
tier_amount = float(self.ws_master["B6"].value)     # ❌ "500" (텍스트) → ValueError
```

#### 수정 방안
```python
def _read_float(self, cell, field_name: str) -> float:
    """
    Excel 셀에서 float를 안전하게 읽음

    지원 형식:
    - 숫자: 1000, 1000.5
    - 문자열: "1000", "1,000", "1,000.50"
    - 퍼센트: "3%", "0.03"
    """
    value = cell.value

    if value is None or value == "":
        raise ValueError(f"{field_name} 필수 입력 (셀이 비어 있음)")

    # 이미 숫자면 반환
    if isinstance(value, (int, float)):
        return float(value)

    # 문자열 전처리
    value_str = str(value).strip()

    # 퍼센트 처리
    if "%" in value_str:
        value_str = value_str.replace("%", "")
        return float(value_str) / 100.0

    # 콤마 제거
    value_str = value_str.replace(",", "")

    try:
        return float(value_str)
    except ValueError:
        raise ValueError(f"{field_name} 숫자 변환 실패: '{value}'")

# 사용 예
investment_usd = self._read_float(self.ws_master["B4"], "총 투자금")
tier_amount = self._read_float(self.ws_master["B6"], "티어당 금액")

# 값 검증
if investment_usd <= 0:
    raise ValueError(f"총 투자금은 0보다 커야 합니다: {investment_usd}")
if tier_amount <= 0:
    raise ValueError(f"티어당 금액은 0보다 커야 합니다: {tier_amount}")
```

#### 구현 체크리스트
- [ ] `_read_float()` 유틸리티 함수 추가
- [ ] 모든 숫자 셀 읽기를 `_read_float()`로 대체
- [ ] 필수 필드 빈 값 검증
- [ ] 값 범위 검증 (예: 투자금 > 0, 티어 수 1~240)
- [ ] 단위 테스트 (정상, 콤마, 퍼센트, 빈 값, 잘못된 형식)

---

### ✅ 작업 5: 에러 핸들링 개선
**파일**: `kis_rest_adapter.py`, `excel_bridge.py`, `phoenix_main.py`
**예상 시간**: 3시간

#### 5.1. REST API 재시도 + 백오프
```python
# kis_rest_adapter.py
import time
from typing import Optional

def _post_with_retry(self, url: str, headers: dict, body: dict, max_retries: int = 3) -> Optional[dict]:
    """
    재시도 로직이 포함된 POST 요청

    지수 백오프: 1초 → 2초 → 4초
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            logger.warning(f"타임아웃 ({attempt}/{max_retries})")
            if attempt < max_retries:
                wait_time = 2 ** (attempt - 1)
                time.sleep(wait_time)

        except requests.exceptions.RequestException as e:
            logger.error(f"네트워크 에러 ({attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))

    logger.error(f"최대 재시도 {max_retries}회 초과")
    return None
```

#### 5.2. Excel 파일 잠금 재시도
```python
# excel_bridge.py
def save_workbook_with_retry(self, max_retries: int = 5, retry_delay: float = 1.0) -> bool:
    """
    Excel 파일 저장 (파일 잠금 재시도)
    """
    for attempt in range(1, max_retries + 1):
        try:
            self.wb.save(self.excel_path)
            logger.debug(f"Excel 저장 성공 (시도 {attempt})")
            return True

        except PermissionError as e:
            logger.warning(f"Excel 파일 잠금 ({attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                logger.error(f"Excel 저장 실패: 파일이 잠겨 있음")
                # 텔레그램 알림
                if hasattr(self, 'telegram'):
                    self.telegram.send_message("⚠️ Excel 저장 실패: 파일을 닫아주세요")
                return False

        except Exception as e:
            logger.error(f"Excel 저장 예외: {e}")
            return False

    return False
```

#### 5.3. AuthenticationError 재로그인
```python
# phoenix_main.py
def _handle_authentication_error(self):
    """인증 에러 처리 (재로그인)"""
    logger.warning("인증 토큰 만료 - 재로그인 시도")
    try:
        self.kis_adapter.authenticate()
        logger.info("재로그인 성공")
        self.telegram.send_message("🔄 인증 갱신 완료")
    except Exception as e:
        logger.error(f"재로그인 실패: {e}")
        self.telegram.send_message(f"❌ 인증 실패: {e}\n시스템 중단")
        self.stop()

# 메인 루프에서 사용
try:
    price_data = self.kis_adapter.get_overseas_price(self.settings.ticker)
except AuthenticationError:
    self._handle_authentication_error()
    continue  # 다음 루프에서 재시도
```

#### 구현 체크리스트
- [ ] `_post_with_retry()` 구현 및 모든 API 호출에 적용
- [ ] `save_workbook_with_retry()` 구현
- [ ] `_handle_authentication_error()` 추가
- [ ] 메인 루프에 예외 처리 추가
- [ ] 중요 에러는 텔레그램으로 실시간 알림
- [ ] 단위 테스트 (타임아웃, 네트워크 에러, 파일 잠금)

---

### ✅ 작업 6: 다중 주문 체결 확인
**파일**: `grid_engine.py`, `phoenix_main.py`
**예상 시간**: 2시간

#### 현재 문제
```python
# grid_engine.py:401-466
# 급락 시 한 틱에서 5건 연속 발행
for tier in range(1, 6):
    signals.append(self.generate_buy_signal(current_price, tier))
# → 체결 확인 없이 모두 전송됨
```

#### 수정 방안
```python
# phoenix_main.py
def _process_signal(self, signal: TradeSignal):
    """매매 신호 처리 (체결 확인 후 다음 주문)"""
    result = self.kis_adapter.send_order(...)

    if result["status"] == "SUCCESS":
        # 체결 확인될 때까지 대기 (최대 5초)
        for _ in range(5):
            time.sleep(1)
            order_status = self.kis_adapter.check_order_status(result["order_id"])
            if order_status["filled_qty"] > 0:
                logger.info(f"주문 {result['order_id']} 체결 확인")
                break

        # 체결된 수량으로 포지션 갱신
        self.grid_engine.execute_buy(
            signal=signal,
            actual_filled_price=order_status["filled_price"],
            actual_filled_qty=order_status["filled_qty"]
        )
    else:
        logger.error(f"주문 실패: {result['message']}")
        # 실패 시 다음 주문 진행 안 함
        return

# kis_rest_adapter.py
def check_order_status(self, order_id: str) -> dict:
    """
    주문 상태 조회

    Returns:
        {
            "order_id": "US20260121000001",
            "status": "FILLED" | "PARTIAL" | "PENDING" | "REJECTED",
            "filled_price": 45.23,
            "filled_qty": 10,
            "total_qty": 10
        }
    """
    # KIS REST API 주문 조회 (TR_ID: JTTT3001R)
    # ...
```

#### 구현 체크리스트
- [ ] `KisRestAdapter.check_order_status()` 구현
- [ ] `_process_signal()`에 체결 확인 로직 추가
- [ ] 부분 체결 시 재주문 로직
- [ ] 주문 실패 시 다음 신호 처리 안 함
- [ ] 통합 테스트 (다중 주문 시나리오)

---

## 🔧 Priority 2 (P2) - 안정성 강화 [MEDIUM RISK]

### ✅ 작업 7: 중복 주문 방지
**파일**: `grid_engine.py`, `phoenix_main.py`
**예상 시간**: 2시간

#### 목표
- 같은 티어에 중복 매수 방지
- 주문 대기 중인 티어는 재주문 안 함

#### 수정 방안
```python
# grid_engine.py
@dataclass
class GridEngine:
    pending_orders: Dict[int, str] = field(default_factory=dict)  # {tier: order_id}

    def can_place_order(self, tier: int) -> bool:
        """주문 가능 여부 확인"""
        # 이미 포지션 보유 중
        if any(pos.tier == tier for pos in self.positions):
            return False

        # 주문 대기 중
        if tier in self.pending_orders:
            return False

        return True

    def mark_order_pending(self, tier: int, order_id: str):
        """주문 대기 상태로 표시"""
        self.pending_orders[tier] = order_id

    def mark_order_filled(self, tier: int):
        """주문 체결 완료"""
        if tier in self.pending_orders:
            del self.pending_orders[tier]

# phoenix_main.py
def _process_signal(self, signal: TradeSignal):
    # 중복 체크
    if not self.grid_engine.can_place_order(signal.tier):
        logger.debug(f"Tier {signal.tier} 주문 불가 (중복/대기 중)")
        return

    # 주문 전송
    result = self.kis_adapter.send_order(...)

    if result["status"] == "SUCCESS":
        # 대기 상태로 표시
        self.grid_engine.mark_order_pending(signal.tier, result["order_id"])

        # 체결 확인 후 포지션 생성
        # ... (작업 6 로직)

        # 체결 완료 표시
        self.grid_engine.mark_order_filled(signal.tier)
```

#### 구현 체크리스트
- [ ] `pending_orders` 상태 관리
- [ ] `can_place_order()` 중복 체크
- [ ] 체결 완료 시 대기 상태 해제
- [ ] 타임아웃 시 대기 상태 해제 (5분 후 자동)
- [ ] 단위 테스트

---

### ✅ 작업 8: 실계좌 잔고 동기화
**파일**: `phoenix_main.py`, `kis_rest_adapter.py`
**예상 시간**: 1시간

#### 목표
주기적으로 KIS API에서 실제 잔고 조회 → 로컬 시뮬레이션과 비교

#### 수정 방안
```python
# phoenix_main.py
def _sync_balance_with_kis(self):
    """실계좌 잔고 동기화 (5분마다)"""
    kis_balance = self.kis_adapter.get_balance()
    local_balance = self.grid_engine.cash_balance

    diff = abs(kis_balance["cash_usd"] - local_balance)

    if diff > 1.0:  # $1 이상 차이
        logger.warning(f"잔고 불일치: KIS ${kis_balance['cash_usd']:.2f} vs Local ${local_balance:.2f}")
        self.telegram.send_message(
            f"⚠️ 잔고 불일치 감지\n"
            f"실계좌: ${kis_balance['cash_usd']:.2f}\n"
            f"로컬: ${local_balance:.2f}\n"
            f"차이: ${diff:.2f}"
        )

        # 로컬 잔고를 실계좌에 맞춤
        self.grid_engine.cash_balance = kis_balance["cash_usd"]

# 메인 루프에서 5분마다 호출
if (datetime.now() - self.last_balance_sync).seconds > 300:
    self._sync_balance_with_kis()
    self.last_balance_sync = datetime.now()
```

#### 구현 체크리스트
- [ ] `_sync_balance_with_kis()` 구현
- [ ] 메인 루프에 주기적 호출 추가
- [ ] 차이 임계값 설정 ($1)
- [ ] 불일치 시 텔레그램 알림
- [ ] 로컬 잔고 강제 동기화 옵션

---

## 🧪 작업 9: 통합 테스트 작성
**파일**: `tests/test_deployment_readiness.py`
**예상 시간**: 3시간

### 테스트 시나리오
```python
import pytest
from unittest.mock import Mock, patch

class TestDeploymentReadiness:
    """실거래 배포 준비 검증 테스트"""

    def test_order_execution_flow_success(self):
        """정상 주문 실행 플로우"""
        # Given: 매수 신호 발생
        signal = TradeSignal(action="BUY", tier=1, price=45.0, quantity=10)

        # Mock: KIS API 성공 응답
        mock_response = {
            "status": "SUCCESS",
            "order_id": "TEST123",
            "filled_price": 45.0,
            "filled_qty": 10
        }

        # When: 주문 전송
        with patch.object(kis_adapter, 'send_order', return_value=mock_response):
            phoenix_main._process_signal(signal)

        # Then: 포지션 생성 확인
        assert len(grid_engine.positions) == 1
        assert grid_engine.positions[0].tier == 1
        assert grid_engine.positions[0].quantity == 10
        assert grid_engine.positions[0].avg_price == 45.0

    def test_order_execution_flow_partial_fill(self):
        """부분 체결 처리"""
        # Given: 10주 주문
        signal = TradeSignal(action="BUY", tier=1, price=45.0, quantity=10)

        # Mock: 5주만 체결
        mock_response = {
            "status": "SUCCESS",
            "order_id": "TEST123",
            "filled_price": 45.0,
            "filled_qty": 5  # 부분 체결
        }

        # When
        with patch.object(kis_adapter, 'send_order', return_value=mock_response):
            phoenix_main._process_signal(signal)

        # Then: 실제 체결 수량만 포지션에 반영
        assert grid_engine.positions[0].quantity == 5

    def test_order_execution_flow_failure(self):
        """주문 실패 처리"""
        # Given
        signal = TradeSignal(action="BUY", tier=1, price=45.0, quantity=10)

        # Mock: 주문 실패 (잔고 부족)
        mock_response = {
            "status": "FAILED",
            "message": "잔고 부족",
            "error_code": "40310000"
        }

        # When
        with patch.object(kis_adapter, 'send_order', return_value=mock_response):
            phoenix_main._process_signal(signal)

        # Then: 포지션 생성 안 됨
        assert len(grid_engine.positions) == 0

    def test_duplicate_order_prevention(self):
        """중복 주문 방지"""
        # Given: Tier 1 포지션 보유 중
        grid_engine.positions.append(
            Position(tier=1, quantity=10, avg_price=45.0, invested_amount=450.0, opened_at=datetime.now())
        )

        # When: 같은 티어 매수 신호 발생
        signal = TradeSignal(action="BUY", tier=1, price=44.0, quantity=10)
        phoenix_main._process_signal(signal)

        # Then: 주문 전송 안 됨
        assert kis_adapter.send_order.call_count == 0

    def test_excel_parsing_various_formats(self):
        """엑셀 다양한 형식 파싱"""
        test_cases = [
            ("10000", 10000.0),      # 숫자
            ("10,000", 10000.0),     # 콤마
            ("10,000.50", 10000.5),  # 콤마 + 소수점
            ("3%", 0.03),            # 퍼센트
            ("0.03", 0.03),          # 소수
        ]

        for input_val, expected in test_cases:
            # Mock: Excel 셀
            mock_cell = Mock()
            mock_cell.value = input_val

            # When
            result = excel_bridge._read_float(mock_cell, "test_field")

            # Then
            assert result == expected

    def test_account_number_parsing(self):
        """계좌번호 파싱"""
        test_cases = [
            ("12345678-01", ("12345678", "01")),
            ("1234567801", ("12345678", "01")),
            ("12345678 01", ("12345678", "01")),  # 공백
        ]

        for input_val, expected in test_cases:
            cano, prdt_cd = excel_bridge._parse_account_no(input_val)
            assert (cano, prdt_cd) == expected

    def test_balance_sync_mismatch_alert(self):
        """잔고 불일치 알림"""
        # Given: 로컬 잔고 $10,000
        grid_engine.cash_balance = 10000.0

        # Mock: KIS API에서 $9,950 조회 (차이 $50)
        mock_balance = {"cash_usd": 9950.0}

        # When
        with patch.object(kis_adapter, 'get_balance', return_value=mock_balance):
            phoenix_main._sync_balance_with_kis()

        # Then: 텔레그램 알림 발송 확인
        assert telegram.send_message.called
        assert "잔고 불일치" in telegram.send_message.call_args[0][0]

    def test_retry_on_timeout(self):
        """타임아웃 시 재시도"""
        # Given: 첫 2번 타임아웃, 3번째 성공
        mock_adapter = Mock()
        mock_adapter._post_with_retry.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            {"rt_cd": "0", "output": {...}}
        ]

        # When
        result = mock_adapter.send_order(...)

        # Then: 3번 시도 후 성공
        assert mock_adapter._post_with_retry.call_count == 3
        assert result["status"] == "SUCCESS"
```

---

## 📅 실행 일정 (Estimated Timeline)

| Priority | 작업 | 예상 시간 | 담당 | 상태 |
|---------|------|---------|-----|------|
| P0 | 작업 1: `send_order()` 시그니처 통일 | 1-2h | Dev | 🔲 대기 |
| P0 | 작업 2: 계좌번호/상품코드 분리 | 1h | Dev | 🔲 대기 |
| P0 | 작업 3: 주문 응답 처리 및 체결 동기화 | 3-4h | Dev | 🔲 대기 |
| P1 | 작업 4: 엑셀 파싱 검증 강화 | 2h | Dev | 🔲 대기 |
| P1 | 작업 5: 에러 핸들링 개선 | 3h | Dev | 🔲 대기 |
| P1 | 작업 6: 다중 주문 체결 확인 | 2h | Dev | 🔲 대기 |
| P2 | 작업 7: 중복 주문 방지 | 2h | Dev | 🔲 대기 |
| P2 | 작업 8: 실계좌 잔고 동기화 | 1h | Dev | 🔲 대기 |
| - | 작업 9: 통합 테스트 작성 | 3h | QA | 🔲 대기 |
| - | **총 예상 시간** | **18-20h** | | |

---

## ✅ 배포 전 체크리스트

### Phase 1: P0 완료 (주문 실행 가능)
- [ ] `send_order()` 시그니처 통일 완료
- [ ] 계좌번호 파싱 완료
- [ ] 주문 응답 처리 및 체결 동기화 완료
- [ ] 단위 테스트 통과 (P0)
- [ ] **검증**: Mock API로 정상 주문 → 체결 → 포지션 생성 확인

### Phase 2: P1 완료 (고위험 해결)
- [ ] 엑셀 파싱 검증 완료
- [ ] 에러 핸들링 (재시도, 재로그인) 완료
- [ ] 다중 주문 체결 확인 완료
- [ ] 단위 테스트 통과 (P1)
- [ ] **검증**: 급락 시나리오에서 다중 주문 순차 체결 확인

### Phase 3: P2 완료 (안정성 강화)
- [ ] 중복 주문 방지 완료
- [ ] 실계좌 잔고 동기화 완료
- [ ] 통합 테스트 통과 (작업 9)
- [ ] **검증**: 1시간 모의 거래 (Paper Trading) 무장애 운영

### Phase 4: 실거래 배포
- [ ] 모든 P0~P2 작업 완료
- [ ] 통합 테스트 100% 통과
- [ ] 텔레그램 알림 동작 확인
- [ ] Excel 히스토리 기록 확인
- [ ] **최소 투자금으로 실거래 1일 모니터링**
- [ ] 문제 없으면 정식 투자금 투입

---

## 📊 성공 지표 (Success Metrics)

| 지표 | 배포 전 목표 | 측정 방법 |
|-----|-----------|----------|
| 주문 성공률 | 99% 이상 | (성공 주문 / 전체 주문) × 100 |
| 체결가 정확도 | ±0.1% 이내 | abs(체결가 - 예상가) / 예상가 |
| 잔고 동기화 | ±$1 이내 | abs(KIS 잔고 - 로컬 잔고) |
| 시스템 가동률 | 99.9% | (정상 운영 시간 / 전체 시간) × 100 |
| 중복 주문 발생 | 0건 | 수동 확인 |
| Excel 저장 실패율 | < 0.1% | (실패 횟수 / 전체 시도) × 100 |

---

## 🚨 롤백 계획 (Rollback Plan)

### 긴급 중단 조건
다음 중 하나라도 발생 시 즉시 시스템 중단:
1. 중복 주문 2건 이상 발생
2. 잔고 불일치 $100 이상
3. 주문 실패율 10% 초과
4. 시스템 크래시 3회 이상

### 롤백 절차
1. `Ctrl+C`로 시스템 즉시 중단
2. Excel 파일 백업 (`phoenix_grid_template_v3_backup_{timestamp}.xlsx`)
3. KIS API에서 실계좌 상태 확인 (잔고, 포지션)
4. 로그 파일 분석 (`logs/phoenix_*.log`)
5. 텔레그램으로 상황 보고
6. 문제 원인 파악 후 재배포 or 긴급 패치

---

## 📝 버전 관리

### v4.2-alpha (Phase 1 완료)
- P0 작업 완료
- 주문 실행 가능
- Mock API 테스트 통과

### v4.2-beta (Phase 2 완료)
- P1 작업 완료
- 고위험 이슈 해결
- 모의 거래 1시간 무장애

### v4.2-rc (Phase 3 완료)
- P2 작업 완료
- 통합 테스트 통과
- 실거래 준비 완료

### v4.2-stable (Phase 4 완료)
- 실거래 1일 모니터링 완료
- 모든 성공 지표 달성
- **정식 배포 승인**

---

## 📞 지원 및 문의

- **긴급 버그 리포트**: Telegram 채널
- **로그 위치**: `D:\Project\SOLX\logs\`
- **백업 위치**: `D:\Project\SOLX\backup\`
- **테스트 명령어**: `pytest tests/test_deployment_readiness.py -v`

---

**문서 작성자**: Claude Code
**마지막 업데이트**: 2026-01-21
**다음 리뷰**: Phase 1 완료 시

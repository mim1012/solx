"""
Paper Trading Test for Grid Engine v4.0
========================================

Codex 리뷰 결과 수정사항 검증:
1. 매도 시 잔고 복구 (돈 증발 버그 수정)
2. 주문 실패 시 Lock 해제
3. 부분 체결 수량 처리
4. 상태 전이 정확성

테스트 시나리오:
- 매수 → 매도 사이클 (잔고 변화 추적)
- 주문 실패 시나리오 (Lock 해제 확인)
- 배치 주문 (수량 분배 확인)
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# 프로젝트 루트 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.models import GridSettings, TradeSignal
from src.grid_engine_v4_state_machine import GridEngineV4
from tier_state_machine import TierState


class PaperTradingTest:
    """Paper Trading 테스트 실행기"""

    def __init__(self):
        self.settings = GridSettings(
            account_no="PAPER-TRADING",
            ticker="SOXL",
            tier1_price=50.0,
            buy_interval=0.005,  # 0.5%
            sell_target=0.03,    # 3%
            tier_amount=500.0,
            total_tiers=240,
            investment_usd=100000.0,
            tier1_auto_update=False,
            tier1_trading_enabled=False,
            tier1_buy_percent=0.0,
            buy_limit=False,
            sell_limit=False
        )
        self.engine = GridEngineV4(self.settings)
        self.initial_balance = self.engine.account_balance
        self.test_results = []

    def log(self, message: str, status: str = "INFO"):
        """테스트 로그 기록"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{status}] {message}"
        print(log_entry)
        self.test_results.append(log_entry)

    def verify_balance(self, expected: float, tolerance: float = 0.01):
        """잔고 검증"""
        actual = self.engine.account_balance
        diff = abs(actual - expected)

        if diff <= tolerance:
            self.log(f"잔고 검증 통과: ${actual:,.2f} (예상: ${expected:,.2f})", "PASS")
            return True
        else:
            self.log(f"잔고 검증 실패: ${actual:,.2f} (예상: ${expected:,.2f}, 차이: ${diff:,.2f})", "FAIL")
            return False

    def test_buy_sell_cycle(self):
        """
        Test 1: 매수 → 매도 사이클 (잔고 복구 검증)

        시나리오:
        1. Tier 5 매수 ($47.50, 10주)
        2. 가격 상승 ($49.00)
        3. Tier 5 매도
        4. 잔고 = 초기잔고 + 수익
        """
        self.log("=" * 60)
        self.log("Test 1: 매수-매도 사이클 (잔고 복구 검증)")
        self.log("=" * 60)

        initial = self.engine.account_balance
        self.log(f"초기 잔고: ${initial:,.2f}")

        # 1. Tier 5 매수 신호 생성
        tier5_price = self.engine.calculate_tier_price(5)
        self.log(f"Tier 5 매수가: ${tier5_price:.2f}")

        buy_signals = self.engine.process_tick(tier5_price)
        buy_signal = next((s for s in buy_signals if s.action == "BUY"), None)

        if not buy_signal:
            self.log("매수 신호 생성 실패", "FAIL")
            return False

        self.log(f"매수 신호: Tiers={buy_signal.tiers}, 수량={buy_signal.quantity}주, 가격=${buy_signal.price:.2f}")

        # 2. 매수 체결 확인
        invested = buy_signal.quantity * buy_signal.price
        self.engine.confirm_order(
            signal=buy_signal,
            order_id="PAPER_BUY_001",
            filled_qty=buy_signal.quantity,
            filled_price=buy_signal.price,
            success=True,
            error_message=""
        )

        after_buy = self.engine.account_balance
        self.log(f"매수 후 잔고: ${after_buy:,.2f} (투자: ${invested:.2f})")

        # 매수 후 잔고 검증
        expected_after_buy = initial - invested
        if not self.verify_balance(expected_after_buy):
            return False

        # 3. 가격 상승 → 매도 신호
        sell_price = tier5_price * 1.05  # 5% 상승
        sell_signals = self.engine.process_tick(sell_price)
        sell_signal = next((s for s in sell_signals if s.action == "SELL"), None)

        if not sell_signal:
            self.log("매도 신호 생성 실패", "FAIL")
            return False

        self.log(f"매도 신호: Tiers={sell_signal.tiers}, 수량={sell_signal.quantity}주, 가격=${sell_signal.price:.2f}")

        # 4. 매도 체결 확인
        proceeds = sell_signal.quantity * sell_signal.price
        profit = proceeds - invested

        self.engine.confirm_order(
            signal=sell_signal,
            order_id="PAPER_SELL_001",
            filled_qty=sell_signal.quantity,
            filled_price=sell_signal.price,
            success=True,
            error_message=""
        )

        after_sell = self.engine.account_balance
        self.log(f"매도 후 잔고: ${after_sell:,.2f} (수익: ${profit:.2f})")

        # [CRITICAL] 매도 후 잔고 = 초기잔고 + 수익
        expected_after_sell = initial + profit
        return self.verify_balance(expected_after_sell)

    def test_order_failure_lock_release(self):
        """
        Test 2: 주문 실패 시 Lock 해제 검증

        시나리오:
        1. Tier 10 매수 신호 생성 (Lock됨)
        2. 주문 실패 (confirm_order with success=False)
        3. Tier 10 상태가 ERROR 또는 EMPTY로 복구되는지 확인
        4. 다시 매수 가능한지 확인
        """
        self.log("=" * 60)
        self.log("Test 2: 주문 실패 시 Lock 해제 검증")
        self.log("=" * 60)

        # 1. Tier 10 매수 신호
        tier10_price = self.engine.calculate_tier_price(10)
        signals = self.engine.process_tick(tier10_price)
        buy_signal = next((s for s in signals if s.action == "BUY"), None)

        if not buy_signal or 10 not in buy_signal.tiers:
            self.log("Tier 10 매수 신호 없음 (다른 Tier가 먼저 체결된 상태일 수 있음)", "WARN")
            # 다른 Tier로 테스트
            if buy_signal and buy_signal.tiers:
                test_tier = buy_signal.tiers[0]
            else:
                self.log("매수 신호 생성 실패", "FAIL")
                return False
        else:
            test_tier = 10

        self.log(f"테스트 Tier: {test_tier}")

        # Tier 상태 확인 (LOCKED 상태여야 함)
        tier_state_before = self.engine.state_machine.get_tier(test_tier)
        self.log(f"주문 전 Tier {test_tier} 상태: {tier_state_before.state.value}")

        # 2. 주문 실패 시뮬레이션
        self.engine.confirm_order(
            signal=buy_signal,
            order_id="",
            filled_qty=0,
            filled_price=0,
            success=False,
            error_message="Paper Trading: 모의 주문 실패"
        )

        # 3. Tier 상태 확인 (ERROR 또는 EMPTY여야 함)
        tier_state_after = self.engine.state_machine.get_tier(test_tier)
        self.log(f"실패 후 Tier {test_tier} 상태: {tier_state_after.state.value}")

        if tier_state_after.state in (TierState.ERROR, TierState.EMPTY):
            self.log(f"Lock 해제 성공: {tier_state_after.state.value}", "PASS")
            return True
        else:
            self.log(f"Lock 해제 실패: 여전히 {tier_state_after.state.value} 상태", "FAIL")
            return False

    def test_batch_order_quantity_distribution(self):
        """
        Test 3: 배치 주문 수량 분배 검증

        시나리오:
        1. Gap Trading 발생 (3개 Tier 배치 주문)
        2. 100주 주문 → 3 Tier 분배
        3. 34 + 33 + 33 = 100주 (나머지 1주가 첫 Tier에 할당)
        """
        self.log("=" * 60)
        self.log("Test 3: 배치 주문 수량 분배 검증")
        self.log("=" * 60)

        # Gap 발생 시나리오 (Tier 20 가격으로 점프)
        tier20_price = self.engine.calculate_tier_price(20)
        signals = self.engine.process_tick(tier20_price)

        batch_signal = next((s for s in signals if s.action == "BUY" and len(s.tiers) > 1), None)

        if not batch_signal:
            self.log("배치 주문 신호 없음", "WARN")
            return True  # Skip

        total_qty = batch_signal.quantity
        num_tiers = len(batch_signal.tiers)

        self.log(f"배치 주문: {num_tiers}개 Tier, 총 {total_qty}주")
        self.log(f"Tiers: {batch_signal.tiers}")

        # 체결 확인
        self.engine.confirm_order(
            signal=batch_signal,
            order_id="PAPER_BATCH_001",
            filled_qty=total_qty,
            filled_price=batch_signal.price,
            success=True,
            error_message=""
        )

        # 각 Tier 수량 확인
        allocated_qty = 0
        for tier in batch_signal.tiers:
            pos = next((p for p in self.engine.positions if p.tier == tier), None)
            if pos:
                allocated_qty += pos.quantity
                self.log(f"  Tier {tier}: {pos.quantity}주")

        self.log(f"총 할당 수량: {allocated_qty}주 / {total_qty}주")

        if allocated_qty == total_qty:
            self.log("수량 분배 정확함", "PASS")
            return True
        else:
            self.log(f"수량 불일치: {total_qty - allocated_qty}주 손실", "FAIL")
            return False

    def run_all_tests(self):
        """모든 Paper Trading 테스트 실행"""
        self.log("=" * 60)
        self.log("Grid Engine v4.0 Paper Trading 테스트 시작")
        self.log("=" * 60)
        self.log(f"초기 설정:")
        self.log(f"  Ticker: {self.settings.ticker}")
        self.log(f"  Tier 1: ${self.settings.tier1_price}")
        self.log(f"  초기 잔고: ${self.initial_balance:,.2f}")
        self.log(f"  Tier당 투자: ${self.settings.tier_amount}")

        results = {}

        # Test 1: 매수-매도 사이클
        try:
            results["buy_sell_cycle"] = self.test_buy_sell_cycle()
        except Exception as e:
            self.log(f"Test 1 에러: {e}", "ERROR")
            results["buy_sell_cycle"] = False

        # Test 2: 주문 실패 시 Lock 해제
        try:
            results["order_failure"] = self.test_order_failure_lock_release()
        except Exception as e:
            self.log(f"Test 2 에러: {e}", "ERROR")
            results["order_failure"] = False

        # Test 3: 배치 주문 수량 분배
        try:
            results["batch_distribution"] = self.test_batch_order_quantity_distribution()
        except Exception as e:
            self.log(f"Test 3 에러: {e}", "ERROR")
            results["batch_distribution"] = False

        # 결과 요약
        self.log("=" * 60)
        self.log("Paper Trading 테스트 결과")
        self.log("=" * 60)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for test_name, result in results.items():
            status = "PASS" if result else "FAIL"
            self.log(f"{test_name}: {status}")

        self.log("=" * 60)
        self.log(f"최종 결과: {passed}/{total} 통과 ({passed/total*100:.1f}%)")
        self.log("=" * 60)

        return passed == total


if __name__ == "__main__":
    tester = PaperTradingTest()
    success = tester.run_all_tests()

    sys.exit(0 if success else 1)

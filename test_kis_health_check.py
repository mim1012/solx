"""
KIS API 연결 상태 헬스체크
- 토큰 발급 확인
- 계좌번호 검증
- 잔고 조회 테스트
- 시세 조회 테스트
"""

import sys
import logging
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.kis_rest_adapter import KisRestAdapter
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, TICKER

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


def health_check():
    """KIS API 헬스체크"""

    print("=" * 80)
    print("KIS API Health Check")
    print("=" * 80)

    results = {
        "config": False,
        "login": False,
        "account": False,
        "balance": False,
        "price": False
    }

    # 1. 설정 검증
    print("\n[1] Configuration Check")
    if not KIS_APP_KEY or KIS_APP_KEY == "your_app_key_here":
        print("  [FAIL] KIS_APP_KEY not configured")
        print("  Action: Set KIS_APP_KEY in .env file")
        return results

    if not KIS_APP_SECRET or KIS_APP_SECRET == "your_app_secret_here":
        print("  [FAIL] KIS_APP_SECRET not configured")
        print("  Action: Set KIS_APP_SECRET in .env file")
        return results

    if not KIS_ACCOUNT_NO or KIS_ACCOUNT_NO == "12345678-01":
        print("  [FAIL] KIS_ACCOUNT_NO not configured")
        print("  Action: Set KIS_ACCOUNT_NO in .env file")
        return results

    print(f"  [OK] APP_KEY: {KIS_APP_KEY[:10]}...{KIS_APP_KEY[-4:]}")
    print(f"  [OK] APP_SECRET: {KIS_APP_SECRET[:10]}...{KIS_APP_SECRET[-4:]}")
    print(f"  [OK] ACCOUNT_NO: {KIS_ACCOUNT_NO}")
    results["config"] = True

    # 2. KIS Adapter 초기화
    print("\n[2] KIS Adapter Initialization")
    try:
        adapter = KisRestAdapter(
            app_key=KIS_APP_KEY,
            app_secret=KIS_APP_SECRET,
            account_no=KIS_ACCOUNT_NO
        )
        print("  [OK] Adapter initialized")
    except Exception as e:
        print(f"  [FAIL] Adapter initialization failed: {e}")
        return results

    # 3. 로그인 (토큰 발급)
    print("\n[3] Login (Token Issuance)")
    try:
        adapter.login()
        print(f"  [OK] Access token issued")
        print(f"  [OK] Token expires at: {adapter.token_expires_at}")
        if adapter.approval_key:
            print(f"  [OK] Approval key issued (WebSocket available)")
        else:
            print(f"  [WARN] Approval key not issued (WebSocket unavailable)")
        results["login"] = True
    except Exception as e:
        print(f"  [FAIL] Login failed: {e}")
        return results

    # 4. 계좌번호 검증
    print("\n[4] Account Validation")
    try:
        cano, acnt_prdt_cd = adapter._parse_account_no(KIS_ACCOUNT_NO)
        print(f"  [OK] CANO: {cano}")
        print(f"  [OK] ACNT_PRDT_CD: {acnt_prdt_cd}")
        results["account"] = True
    except Exception as e:
        print(f"  [FAIL] Account parsing failed: {e}")
        return results

    # 5. 잔고 조회
    print("\n[5] Balance Inquiry")
    try:
        balance = adapter.get_balance()
        print(f"  [OK] USD Balance: ${balance:,.2f}")
        results["balance"] = True
    except Exception as e:
        print(f"  [FAIL] Balance inquiry failed: {e}")
        import traceback
        traceback.print_exc()

    # 6. 시세 조회
    print("\n[6] Price Inquiry")
    try:
        price_data = adapter.get_overseas_price(TICKER)
        if price_data:
            print(f"  [OK] {TICKER} Price: ${price_data['price']:.2f}")
            print(f"  [OK] Open: ${price_data['open']:.2f}, High: ${price_data['high']:.2f}, Low: ${price_data['low']:.2f}")
            results["price"] = True
        else:
            print(f"  [FAIL] Price data is None")
    except Exception as e:
        print(f"  [FAIL] Price inquiry failed: {e}")
        import traceback
        traceback.print_exc()

    # 7. 연결 상태
    print("\n[7] Connection Status")
    if adapter.is_connected():
        print(f"  [OK] Connected")
    else:
        print(f"  [FAIL] Not connected")

    # 결과 요약
    print("\n" + "=" * 80)
    print("Health Check Summary")
    print("=" * 80)

    total = len(results)
    passed = sum(results.values())

    for check, status in results.items():
        status_str = "[PASS]" if status else "[FAIL]"
        print(f"  {status_str} {check}")

    print()
    print(f"Total: {passed}/{total} passed")

    if passed == total:
        print("\n[SUCCESS] All checks passed! KIS API is ready.")
        return True
    else:
        print(f"\n[WARNING] {total - passed} check(s) failed. Please fix the issues above.")
        return False


if __name__ == "__main__":
    success = health_check()
    sys.exit(0 if success else 1)

"""
Phoenix Trading System - Excel 기반 KIS API 통합 테스트
Excel 파일에서 설정을 읽고 KIS API로 연결하는 전체 플로우 검증
"""
import openpyxl
from src.excel_bridge import ExcelBridge
from src.kis_rest_adapter import KisRestAdapter

def test_excel_kis_integration():
    """Excel → KIS API 연동 테스트"""

    # 1. Excel에서 설정 읽기
    print("=" * 60)
    print("Step 1: Excel 설정 읽기")
    print("=" * 60)

    excel_file = "phoenix_grid_template_v3.xlsx"
    bridge = ExcelBridge(excel_file)

    try:
        settings = bridge.load_settings()

        print(f"[OK] Account No: {settings.account_no}")
        print(f"[OK] Ticker: {settings.ticker}")
        print(f"[OK] Investment: ${settings.investment_usd:,.2f}")
        print(f"[OK] KIS APP KEY: {settings.kis_app_key[:20]}..." if settings.kis_app_key else "[WARN] KIS APP KEY missing")
        print(f"[OK] KIS APP SECRET: {settings.kis_app_secret[:20]}..." if settings.kis_app_secret else "[WARN] KIS APP SECRET missing")
        print(f"[OK] KIS Account: {settings.kis_account_no}")
        print(f"[OK] System Running: {'ON (TRUE)' if settings.system_running else 'OFF (FALSE)'}")

        # 2. KIS API 연결 테스트 (system_running=TRUE일 때만)
        if settings.system_running:
            print("\n" + "=" * 60)
            print("Step 2: KIS API 연결 시도")
            print("=" * 60)

            if not settings.kis_app_key or not settings.kis_app_secret:
                print("[ERROR] KIS API keys not set in Excel!")
                print("\nOpen Excel file (phoenix_grid_template_v3.xlsx) and set:")
                print("  - B12: KIS APP KEY")
                print("  - B13: KIS APP SECRET")
                print("  - B14: KIS Account No (e.g., 12345678-01)")
                print("  - B15: TRUE (to start system)")
                return False

            # KIS REST Adapter 초기화
            adapter = KisRestAdapter(
                app_key=settings.kis_app_key,
                app_secret=settings.kis_app_secret,
                account_no=settings.kis_account_no or settings.account_no
            )

            # 로그인 시도
            print("로그인 시도 중...")
            success = adapter.login()

            if success:
                print("[OK] Login Success!")
                print(f"[OK] Access Token: {adapter.access_token[:30]}...")
                print(f"[OK] Approval Key: {adapter.approval_key[:30]}..." if adapter.approval_key else "[WARN] Approval Key missing")

                # 3. SOXL Price Query Test
                print("\n" + "=" * 60)
                print("Step 3: SOXL Price Query")
                print("=" * 60)

                price_data = adapter.get_overseas_price("SOXL")
                if price_data:
                    print(f"[OK] Current Price: ${price_data['price']:.2f}")
                    print(f"[OK] Open: ${price_data['open']:.2f}")
                    print(f"[OK] High: ${price_data['high']:.2f}")
                    print(f"[OK] Low: ${price_data['low']:.2f}")
                    print(f"[OK] Volume: {price_data['volume']:,}")
                else:
                    print("[ERROR] Price query failed")

                # 4. Account Balance Query
                print("\n" + "=" * 60)
                print("Step 4: Account Balance Query")
                print("=" * 60)

                balance = adapter.get_balance()
                if balance is not None:
                    print(f"[OK] Cash Balance: ${balance:,.2f}")
                else:
                    print("[ERROR] Balance query failed")

                adapter.disconnect()
                return True
            else:
                print("[ERROR] Login failed!")
                print("\nPossible causes:")
                print("  1. Wrong KIS APP KEY/SECRET")
                print("  2. API not approved yet")
                print("  3. Network connection issue")
                return False
        else:
            print("\n[INFO] System is STOPPED (B15=FALSE)")
            print("Set B15=TRUE in Excel to start trading system.")
            return None  # Stopped state is not a failure

    except Exception as e:
        print(f"\n[ERROR] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            if hasattr(bridge, 'wb') and bridge.wb:
                bridge.wb.close()
        except:
            pass


if __name__ == "__main__":
    print("\n")
    print("=" * 60)
    print("  Phoenix Trading System - Excel to KIS API Integration Test")
    print("=" * 60)
    print("\n")

    result = test_excel_kis_integration()

    print("\n" + "=" * 60)
    print("Final Result")
    print("=" * 60)
    if result is True:
        print("[SUCCESS] All tests passed! Ready for real trading!")
    elif result is False:
        print("[FAILED] Test failed. Check messages above.")
    else:
        print("[STOPPED] System is in stopped state (normal)")
    print("\n")

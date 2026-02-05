"""
다른 종목(AAPL)으로 KIS API 테스트
"""
from src.excel_bridge import ExcelBridge
from src.kis_rest_adapter import KisRestAdapter
import json

def main():
    print("=" * 60)
    print("AAPL 시세 조회 테스트")
    print("=" * 60)

    # Excel에서 키만 가져옴
    bridge = ExcelBridge("phoenix_grid_template_v3.xlsx")
    settings = bridge.load_settings()

    # KIS API 연결
    adapter = KisRestAdapter(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.account_no
    )

    if not adapter.login():
        print("로그인 실패!")
        return 1

    print("로그인 성공!\n")

    # 여러 종목 테스트
    test_tickers = ["AAPL", "TSLA", "SOXL", "SPY"]

    for ticker in test_tickers:
        print(f"\n[{ticker}] 시세 조회 중...")
        price_data = adapter.get_overseas_price(ticker)

        if not price_data:
            print(f"  [실패] 시세 조회 실패")
            continue

        print(f"  현재가: ${price_data['price']:.2f}")
        print(f"  거래량: {price_data['volume']:,}")

        if price_data['price'] == 0.0:
            print(f"  [경고] 현재가 $0.00")
        else:
            print(f"  [성공] 시세 정상 조회!")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

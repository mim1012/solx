"""
ETF 시세 테스트
"""
from src.excel_bridge import ExcelBridge
from src.kis_rest_adapter import KisRestAdapter

def main():
    print("=" * 60)
    print("ETF 시세 조회 테스트")
    print("=" * 60)

    bridge = ExcelBridge("phoenix_grid_template_v3.xlsx")
    settings = bridge.load_settings()

    adapter = KisRestAdapter(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.account_no
    )

    if not adapter.login():
        print("로그인 실패!")
        return 1

    print("로그인 성공!\n")

    # ETF vs 일반 주식 비교
    test_cases = [
        ("일반 주식", ["AAPL", "MSFT", "GOOGL"]),
        ("ETF", ["SOXL", "SPY", "QQQ", "TQQQ", "SPXL"])
    ]

    for category, tickers in test_cases:
        print(f"\n{'=' * 60}")
        print(f"[{category}]")
        print('=' * 60)

        for ticker in tickers:
            price_data = adapter.get_overseas_price(ticker)

            if not price_data:
                print(f"  {ticker:8s}: [실패] None 반환")
                continue

            if price_data['price'] > 0:
                print(f"  {ticker:8s}: ${price_data['price']:>8.2f}  거래량: {price_data['volume']:>12,}  [OK]")
            else:
                print(f"  {ticker:8s}: $0.00 [실패]")

    print("\n" + "=" * 60)
    print("결론:")
    print("  - 일반 주식은 정상 작동")
    print("  - ETF는?")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

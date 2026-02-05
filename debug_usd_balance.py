"""
USD 예수금 조회 디버그 스크립트
실제 API 응답을 확인하여 문제를 진단합니다.
"""

import logging
import sys
from config import (
    KIS_APP_KEY,
    KIS_APP_SECRET,
    KIS_ACCOUNT_NO,
    TICKER
)
from src.kis_rest_adapter import KisRestAdapter

# 로깅 설정 (상세한 디버그 로그)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """USD 예수금 조회 디버그"""
    print("=" * 80)
    print("USD 예수금 조회 디버그 스크립트")
    print("=" * 80)

    # 1. KIS API 어댑터 초기화
    print("\n[1단계] KIS API 어댑터 초기화...")
    adapter = KisRestAdapter(
        app_key=KIS_APP_KEY,
        app_secret=KIS_APP_SECRET,
        account_no=KIS_ACCOUNT_NO
    )

    # 2. 로그인
    print("\n[2단계] KIS API 로그인...")
    try:
        adapter.login()
        print("✓ 로그인 성공")
    except Exception as e:
        print(f"✗ 로그인 실패: {e}")
        return

    # 3. 현재가 조회
    print(f"\n[3단계] {TICKER} 현재가 조회...")
    try:
        price_data = adapter.get_overseas_price(TICKER)
        if not price_data:
            print(f"✗ {TICKER} 시세 조회 실패")
            return

        current_price = price_data['price']
        print(f"✓ 현재가: ${current_price:.2f}")
    except Exception as e:
        print(f"✗ 시세 조회 실패: {e}")
        return

    # 4. USD 예수금 조회 (get_cash_balance)
    print(f"\n[4단계] USD 예수금 조회 (매수가능금액조회 API)...")
    print(f"   - 종목: {TICKER}")
    print(f"   - 가격: ${current_price:.2f}")
    print(f"   - 계좌: {KIS_ACCOUNT_NO[:4]}****{KIS_ACCOUNT_NO[-2:]}")

    try:
        cash_balance = adapter.get_cash_balance(ticker=TICKER, price=current_price)
        print(f"\n   결과: ${cash_balance:,.2f}")

        if cash_balance == 0.0:
            print("\n⚠ 경고: USD 예수금이 $0.00으로 반환되었습니다!")
            print("   위의 [DEBUG] 로그를 확인하여 API 응답을 분석하세요.")
        else:
            print(f"\n✓ USD 예수금: ${cash_balance:,.2f}")
    except Exception as e:
        print(f"\n✗ 예수금 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        return

    # 5. 계좌 잔고 조회 (get_balance) - 비교용
    print(f"\n[5단계] 계좌 잔고 조회 (참고용)...")
    try:
        balance = adapter.get_balance()
        print(f"   계좌 잔고 API 결과: ${balance:,.2f}")
    except Exception as e:
        print(f"   계좌 잔고 조회 실패: {e}")

    print("\n" + "=" * 80)
    print("디버그 완료")
    print("=" * 80)


if __name__ == "__main__":
    main()

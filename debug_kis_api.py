"""
KIS API 시세 조회 디버깅 스크립트
실제 API 응답을 확인하여 필드명이 올바른지 검증합니다.
"""

import sys
from src.excel_bridge import ExcelBridge
from src.kis_rest_adapter import KisRestAdapter
import logging
import json

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG 레벨로 상세 정보 출력
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def main():
    """메인 함수"""
    print("=" * 60)
    print("KIS API 시세 조회 디버깅")
    print("=" * 60)

    # 1. Excel 설정 로드
    excel_file = "phoenix_grid_template_v3.xlsx"
    print(f"\n1. Excel 파일 로드: {excel_file}")

    try:
        bridge = ExcelBridge(excel_file)
        settings = bridge.load_settings()

        print(f"   - 종목: {settings.ticker}")
        print(f"   - APP KEY: {settings.kis_app_key[:10]}...")
        print(f"   - APP SECRET: {settings.kis_app_secret[:10]}...")
        print(f"   - 계좌번호: {settings.account_no}")

    except Exception as e:
        print(f"❌ Excel 로드 실패: {e}")
        return 1

    # 2. KIS API 연결
    print(f"\n2. KIS API 연결 중...")

    try:
        adapter = KisRestAdapter(
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            account_no=settings.account_no
        )

        # 로그인
        if not adapter.login():
            print("❌ KIS API 로그인 실패!")
            return 1

        print("✅ KIS API 로그인 성공")

    except Exception as e:
        print(f"❌ KIS API 연결 실패: {e}")
        return 1

    # 3. 시세 조회 (상세 디버깅)
    print(f"\n3. {settings.ticker} 시세 조회 중...")
    print("=" * 60)

    try:
        # get_overseas_price 내부에서 logger.debug로 API 응답을 출력함
        price_data = adapter.get_overseas_price(settings.ticker)

        print("\n[API 응답 결과]")
        print(json.dumps(price_data, indent=2, ensure_ascii=False))

        if not price_data:
            print("\n❌ 시세 조회 실패: None 반환")
            print("\n가능한 원인:")
            print("1. 시장 폐장 시간 (미국 정규장: 한국시간 23:30~06:00, 겨울 00:30~07:00)")
            print("2. 종목 코드 오류")
            print("3. API 권한 문제")
            return 1

        print("\n[파싱된 데이터]")
        print(f"  - ticker: {price_data['ticker']}")
        print(f"  - price: ${price_data['price']:.2f}")
        print(f"  - open: ${price_data['open']:.2f}")
        print(f"  - high: ${price_data['high']:.2f}")
        print(f"  - low: ${price_data['low']:.2f}")
        print(f"  - volume: {price_data['volume']:,}")

        if price_data['price'] == 0.0:
            print("\n⚠️ 현재가가 $0.00입니다!")
            print("\n가능한 원인:")
            print("1. 시장 폐장 시간 (프리마켓 포함)")
            print("2. API 응답 필드명 변경 (디버그 로그의 'KIS API 시세 응답' 확인)")
            print("3. KIS API 서버 문제")
        else:
            print("\n✅ 정상적으로 시세 조회됨")

    except Exception as e:
        print(f"\n❌ 시세 조회 중 예외: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 4. 계좌 잔고 조회
    print("\n" + "=" * 60)
    print("4. 계좌 잔고 조회 중...")
    print("=" * 60)

    try:
        balance = adapter.get_balance()
        print(f"\n✅ 잔고: ${balance:,.2f}")

        if balance == 0.0:
            print("\n⚠️ 잔고가 $0.00입니다!")
            print("   Excel B14의 계좌번호를 확인하세요 (예: 12345678-01)")

    except Exception as e:
        print(f"\n❌ 잔고 조회 실패: {e}")
        print("\n계좌번호 형식을 확인하세요:")
        print("  - 올바른 형식: 12345678-01 (숫자 8자리 + '-' + 숫자 2자리)")
        print(f"  - 현재 설정: {settings.account_no}")

    print("\n" + "=" * 60)
    print("디버깅 완료")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    sys.exit(main())

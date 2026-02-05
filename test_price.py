"""
KIS API 시세 조회 간단 테스트
"""
import sys
import json
from src.excel_bridge import ExcelBridge
from src.kis_rest_adapter import KisRestAdapter
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("KIS API 시세 조회 테스트")
    print("=" * 60)

    # Excel 설정 로드
    try:
        bridge = ExcelBridge("phoenix_grid_template_v3.xlsx")
        settings = bridge.load_settings()
        print(f"\n종목: {settings.ticker}")
        print(f"계좌번호: {settings.account_no}")
    except Exception as e:
        print(f"Excel 로드 실패: {e}")
        return 1

    # KIS API 연결
    try:
        adapter = KisRestAdapter(
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            account_no=settings.account_no
        )

        if not adapter.login():
            print("로그인 실패!")
            return 1

        print("로그인 성공!")

    except Exception as e:
        print(f"연결 실패: {e}")
        return 1

    # 시세 조회
    print("\n" + "=" * 60)
    print(f"{settings.ticker} 시세 조회 중...")
    print("=" * 60)

    try:
        price_data = adapter.get_overseas_price(settings.ticker)

        if not price_data:
            print("\n[ERROR] 시세 조회 실패 (None 반환)")
            print("\n가능한 원인:")
            print("1. 시장 폐장 시간")
            print("2. 종목 코드 오류")
            print("3. API 권한 문제")
            return 1

        print("\n[API 응답 결과]")
        print(json.dumps(price_data, indent=2, ensure_ascii=False))

        print("\n[파싱된 데이터]")
        print(f"  ticker: {price_data['ticker']}")
        print(f"  price: ${price_data['price']:.2f}")
        print(f"  open: ${price_data['open']:.2f}")
        print(f"  high: ${price_data['high']:.2f}")
        print(f"  low: ${price_data['low']:.2f}")
        print(f"  volume: {price_data['volume']:,}")

        if price_data['price'] == 0.0:
            print("\n[경고] 현재가가 $0.00입니다!")
            print("원인:")
            print("  1. 시장 폐장 시간 (정규장: 한국시간 23:30~06:00, 겨울 00:30~07:00)")
            print("  2. 프리마켓/애프터마켓 시간 (시세 제공 안 될 수 있음)")
            print("  3. API 응답 필드명 문제")
        else:
            print("\n[성공] 시세 정상 조회됨!")

    except Exception as e:
        print(f"\n[ERROR] 시세 조회 중 예외: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    sys.exit(main())

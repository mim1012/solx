"""
장 마감 시 KIS API 시세 조회 테스트
"""
import sys
sys.path.insert(0, '.')
from src.kis_rest_adapter import KisRestAdapter
import config
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

# KIS API 연결
adapter = KisRestAdapter(
    app_key=config.KIS_APP_KEY,
    app_secret=config.KIS_APP_SECRET,
    account_no=config.KIS_ACCOUNT_NO
)

print("=" * 60)
print("장 마감 시 KIS API 시세 조회 테스트")
print("=" * 60)
print()

if adapter.login():
    print('[OK] KIS API 로그인 성공')
    print()

    # SOXL 시세 조회
    print("SOXL 시세 조회 중...")
    price_data = adapter.get_overseas_price('SOXL')

    if price_data:
        print(f'[OK] SOXL 시세 조회 성공')
        print(f'  - 현재가: ${price_data["price"]:.2f}')
        print(f'  - 시가: ${price_data["open"]:.2f}')
        print(f'  - 고가: ${price_data["high"]:.2f}')
        print(f'  - 저가: ${price_data["low"]:.2f}')
    else:
        print('[ERROR] SOXL 시세 조회 실패')
        print('  - 장 마감 시간에는 시세 조회가 불가능할 수 있습니다')
else:
    print('[ERROR] KIS API 로그인 실패')

print()
print("=" * 60)

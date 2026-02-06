"""
다른 종목으로 USD 조회 테스트 - 같은 금액이 나오는지 확인
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

print("\n" + "="*80)
print("여러 종목으로 USD 예수금 조회 테스트")
print("="*80 + "\n")

# Excel 설정 로드
excel_path = "release/phoenix_grid_template_v3.xlsx"
bridge = ExcelBridge(excel_path)
settings = bridge.load_settings()

# KIS API 초기화
kis = KisRestAdapter(
    app_key=settings.kis_app_key,
    app_secret=settings.kis_app_secret,
    account_no=settings.kis_account_no
)

# 로그인
if not kis.login():
    print("[ERROR] 로그인 실패!")
    sys.exit(1)

print("[OK] 로그인 성공\n")

# 여러 종목으로 테스트
test_cases = [
    ("SOXL", 50.0),  # AMEX
    ("AAPL", 180.0), # NASD (나스닥)
    ("IBM", 150.0),  # NYSE (뉴욕)
]

print("="*80)
print("가설: '종목과 무관하게 계좌 전체 USD가 조회된다'")
print("="*80 + "\n")

for ticker, price in test_cases:
    try:
        cash = kis.get_cash_balance(ticker=ticker, price=price)
        print(f"{ticker:6s} (가격 ${price:6.2f}) -> USD 예수금: ${cash:.2f}")
    except Exception as e:
        print(f"{ticker:6s} -> 조회 실패: {e}")

print("\n" + "="*80)
print("결론:")
print("  - 모두 같은 금액이면: '계좌 전체 USD' 조회")
print("  - 금액이 다르면: '종목별 예수금' 조회")
print("="*80)

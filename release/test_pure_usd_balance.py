"""
TTTS3012R API로 순수 USD 잔고만 조회 테스트
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

print("\n" + "="*80)
print("TTTS3012R (해외주식 잔고) API로 USD만 조회 테스트")
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
print("KIS API 로그인 중...")
if not kis.login():
    print("[ERROR] 로그인 실패!")
    sys.exit(1)

print("[OK] 로그인 성공\n")

# get_balance() 호출 (TTTS3012R 사용)
print("get_balance() 호출 (종목 보유 없이 USD만 조회)...")
balance = kis.get_balance()

print(f"\n{'='*80}")
print(f"결과: USD 잔고 = ${balance:.2f}")
print(f"{'='*80}\n")

if balance > 0:
    print("[OK] 이 API는 종목 보유 없이도 USD 잔고 조회 가능!")
else:
    print("[INFO] USD 잔고 $0 또는 조회 실패")

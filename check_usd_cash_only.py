"""
USD 현금 예수금만 빠르게 조회
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

def main():
    print("\n" + "="*80)
    print("USD 현금 예수금 조회")
    print("="*80 + "\n")

    # Excel 설정 로드
    excel_path = "release/phoenix_grid_template_v3.xlsx"
    bridge = ExcelBridge(excel_path)
    settings = bridge.load_settings()

    print(f"계좌번호: {settings.kis_account_no}")
    print(f"티커: {settings.ticker}")
    print()

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
        return

    print("[OK] 로그인 성공\n")

    # SOXL 현재가 조회
    print("SOXL 현재가 조회 중...")
    try:
        price = kis.get_overseas_price("SOXL")  # [FIX] 자동 거래소 감지 사용
        print(f"SOXL 현재가: ${price:.2f}\n")
    except:
        price = 50.0
        print(f"현재가 조회 실패, 기본값 사용: ${price:.2f}\n")

    # USD 현금 예수금 조회 (TTTS3007R API)
    print("="*80)
    print("USD 현금 예수금 조회 (매매가능금액조회 API - TTTS3007R)")
    print("="*80 + "\n")

    cash = kis.get_cash_balance(ticker="SOXL", price=price)

    print(f"\n{'='*80}")
    print(f"결과: USD 현금 예수금 = ${cash:.2f}")
    print(f"{'='*80}\n")

    if cash > 0:
        print(f"[OK] 성공! 현금 잔고가 조회되었습니다.")
    else:
        print(f"[WARNING] USD 현금 잔고가 $0입니다.")
        print(f"   계좌번호를 확인하세요: {settings.kis_account_no}")

if __name__ == "__main__":
    main()

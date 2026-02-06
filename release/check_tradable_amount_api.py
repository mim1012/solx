"""
TTTS3007R API를 각 종목의 올바른 거래소로 호출
"""
import sys
import requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

print("\n" + "="*80)
print("올바른 거래소 코드로 USD 예수금 조회")
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

# 계좌번호 파싱
cano = settings.kis_account_no.split('-')[0]
acnt_prdt_cd = settings.kis_account_no.split('-')[1]

# 종목별 올바른 거래소로 테스트
test_cases = [
    ("SOXL", "AMEX", 50.0),
    ("AAPL", "NASD", 180.0),  # 나스닥
    ("IBM", "NYSE", 150.0),   # 뉴욕증권거래소
]

print("="*80)
print("가설: 계좌 전체 USD는 거래소 무관하게 동일해야 함")
print("="*80 + "\n")

for ticker, exchange, price in test_cases:
    print(f"\n[{ticker} @ {exchange}]")
    
    url = f"{kis.BASE_URL}/uapi/overseas-stock/v1/trading/inquire-psamount"
    
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": exchange,
        "OVRS_ORD_UNPR": f"{price:.2f}",
        "ITEM_CD": ticker
    }
    
    headers = kis._get_headers(tr_id="TTTS3007R")
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("rt_cd") == "0":
                output = data.get("output", {})
                cash_balance = float(output.get("ord_psbl_frcr_amt", 0))
                print(f"  USD 예수금: ${cash_balance:.2f}")
            else:
                print(f"  실패: {data.get('msg1')}")
        else:
            print(f"  HTTP 오류: {response.status_code}")
    
    except Exception as e:
        print(f"  예외: {e}")

print("\n" + "="*80)
print("결론:")
print("  - 모두 같은 금액 -> 계좌 전체 USD (거래소 무관)")
print("  - 금액이 다름 -> 거래소별 예수금 (거래소별 관리)")
print("="*80)

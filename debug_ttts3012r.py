"""
TTTS3012R API 응답 직접 확인
"""
import sys
import json
import requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

print("\n" + "="*80)
print("TTTS3012R (해외주식 잔고) API 응답 디버그")
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

# 여러 거래소 코드로 시도
exchange_codes = ["AMEX", "NASD", "NYSE"]

for exchange_code in exchange_codes:
    print("\n" + "="*80)
    print(f"테스트: {exchange_code} 거래소")
    print("="*80 + "\n")

    url = f"{kis.BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": exchange_code,
        "TR_CRCY_CD": "USD",
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": ""
    }

    headers = kis._get_headers(tr_id="TTTS3012R")

    print(f"[요청]")
    print(f"URL: {url}")
    print(f"TR_ID: TTTS3012R")
    print(f"거래소: {exchange_code}")
    print()

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        print(f"[응답]")
        print(f"HTTP Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            print(f"rt_cd: {data.get('rt_cd')}")
            print(f"msg1: {data.get('msg1')}")
            print()

            # output1 (보유종목), output2 (예수금)
            output1 = data.get("output1", [])
            output2 = data.get("output2")

            print(f"output1 타입: {type(output1)}, 길이: {len(output1) if isinstance(output1, list) else 'N/A'}")
            print(f"output2 타입: {type(output2)}")
            print()

            if output2:
                print("[output2 내용 (USD 예수금)]")
                print(json.dumps(output2, indent=2, ensure_ascii=False))
                print()

                if isinstance(output2, dict):
                    usd_balance = output2.get("frcr_drwg_psbl_amt_1", "NOT_FOUND")
                    print(f"frcr_drwg_psbl_amt_1: {usd_balance}")
                    
                    if usd_balance != "NOT_FOUND":
                        try:
                            usd_value = float(usd_balance or 0)
                            if usd_value > 0:
                                print(f"\n[SUCCESS] USD 예수금 발견: ${usd_value:.2f} (거래소: {exchange_code})")
                                break
                        except:
                            print(f"[ERROR] 숫자 변환 실패: {usd_balance}")
                elif isinstance(output2, list) and len(output2) > 0:
                    print(f"output2는 list (길이: {len(output2)})")
                    if isinstance(output2[0], dict):
                        usd_balance = output2[0].get("frcr_drwg_psbl_amt_1", "NOT_FOUND")
                        print(f"frcr_drwg_psbl_amt_1: {usd_balance}")

        else:
            print(f"[ERROR] HTTP 오류: {response.status_code}")
            print(f"응답: {response.text}")

    except Exception as e:
        print(f"[ERROR] 예외 발생: {e}")

print("\n" + "="*80)
print("디버그 완료")
print("="*80)

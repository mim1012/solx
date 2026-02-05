"""
USD 예수금 API 응답 전체를 출력하는 디버그 스크립트
"""
import sys
import json
import requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

def main():
    print("\n" + "="*80)
    print("USD 예수금 API 응답 디버그")
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

    # 현재가 조회
    price = 50.0
    try:
        price = kis.get_overseas_price("SOXL")  # [FIX] 자동 거래소 감지 사용
        print(f"SOXL 현재가: ${price:.2f}\n")
    except:
        print(f"현재가 조회 실패, 기본값 사용: ${price:.2f}\n")

    # 계좌번호 파싱
    cano = settings.kis_account_no.split('-')[0]
    acnt_prdt_cd = settings.kis_account_no.split('-')[1]

    # 여러 거래소 코드로 시도 (AMEX가 SOXL의 올바른 거래소)
    exchange_codes = ["AMEX", "NASD", "NYSE"]  # [FIX] AMEX 우선, AMS 제거

    for exchange_code in exchange_codes:
        print("\n" + "="*80)
        print(f"테스트: {exchange_code} 거래소")
        print("="*80 + "\n")

        # API 직접 호출
        url = f"{kis.BASE_URL}/uapi/overseas-stock/v1/trading/inquire-psamount"

        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "OVRS_EXCG_CD": exchange_code,
            "OVRS_ORD_UNPR": str(price),
            "ITEM_CD": "SOXL"
        }

        headers = kis._get_headers(tr_id="TTTS3007R")

        print(f"[요청 정보]")
        print(f"URL: {url}")
        print(f"TR_ID: TTTS3007R")
        print(f"파라미터:")
        for key, value in params.items():
            print(f"  {key}: {value}")
        print()

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)

            print(f"[응답]")
            print(f"HTTP Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                print(f"rt_cd: {data.get('rt_cd')}")
                print(f"msg_cd: {data.get('msg_cd')}")
                print(f"msg1: {data.get('msg1')}")
                print()

                # 전체 응답 출력
                print("[전체 응답 JSON]")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                print()

                # output 필드 확인
                if "output" in data:
                    output = data["output"]
                    print("[output 필드 상세]")
                    print(f"타입: {type(output)}")
                    if isinstance(output, dict):
                        for key, value in output.items():
                            print(f"  {key}: {value}")

                        # USD 예수금 필드 확인
                        cash_field = output.get("ord_psbl_frcr_amt", "NOT_FOUND")
                        print()
                        print(f"[USD 예수금 필드]")
                        print(f"ord_psbl_frcr_amt: {cash_field}")

                        if cash_field != "NOT_FOUND":
                            try:
                                cash_value = float(cash_field or 0)
                                print(f"변환된 값: ${cash_value:.2f}")

                                if cash_value > 0:
                                    print(f"\n[SUCCESS] USD 예수금 발견: ${cash_value:.2f} (거래소: {exchange_code})")
                                    return  # 성공하면 종료
                            except:
                                print(f"[ERROR] 숫자 변환 실패: {cash_field}")

                if data.get("rt_cd") == "0":
                    print(f"[OK] API 호출 성공했지만 USD 예수금 없음")
                elif data.get("rt_cd") == "7":
                    print(f"[INFO] 상품이 없습니다 (거래 이력 없음)")
                else:
                    print(f"[ERROR] API 호출 실패: {data.get('msg1')}")

            else:
                print(f"[ERROR] HTTP 오류: {response.status_code}")
                print(f"응답 본문: {response.text}")

        except Exception as e:
            print(f"[ERROR] 예외 발생: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*80)
    print("디버그 완료")
    print("="*80)

if __name__ == "__main__":
    main()

"""
KIS API 원본 응답 확인 스크립트
"""
import requests
import json
from src.excel_bridge import ExcelBridge

def main():
    print("=" * 80)
    print("KIS API 원본 응답 확인")
    print("=" * 80)

    # Excel 설정 로드
    bridge = ExcelBridge("phoenix_grid_template_v3.xlsx")
    settings = bridge.load_settings()

    print(f"\n종목: {settings.ticker}")

    # 1. 토큰 발급
    print("\n[1단계] Access Token 발급...")

    token_url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"

    token_payload = {
        "grant_type": "client_credentials",
        "appkey": settings.kis_app_key,
        "appsecret": settings.kis_app_secret
    }

    token_headers = {
        "Content-Type": "application/json; charset=utf-8"
    }

    token_response = requests.post(token_url, json=token_payload, headers=token_headers, timeout=10)

    if token_response.status_code != 200:
        print(f"토큰 발급 실패: {token_response.status_code}")
        print(token_response.text)
        return 1

    token_data = token_response.json()
    access_token = token_data["access_token"]

    print("토큰 발급 성공!")

    # 2. 시세 조회
    print("\n[2단계] 시세 조회...")
    print(f"종목: {settings.ticker}")
    print(f"거래소: NASDAQ (NAS)")

    price_url = "https://openapi.koreainvestment.com:9443/uapi/overseas-price/v1/quotations/price"

    params = {
        "EXCD": "NAS",  # 나스닥
        "SYMB": settings.ticker
    }

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": settings.kis_app_key,
        "appsecret": settings.kis_app_secret,
        "tr_id": "HHDFS00000300",  # 해외주식 현재가
        "custtype": "P"
    }

    price_response = requests.get(price_url, headers=headers, params=params, timeout=10)

    print(f"\nHTTP 상태 코드: {price_response.status_code}")

    if price_response.status_code != 200:
        print(f"시세 조회 실패: {price_response.text}")
        return 1

    # 3. 원본 응답 출력
    print("\n" + "=" * 80)
    print("[원본 JSON 응답 전체]")
    print("=" * 80)

    response_json = price_response.json()
    print(json.dumps(response_json, indent=2, ensure_ascii=False))

    # 4. output 필드 상세 분석
    print("\n" + "=" * 80)
    print("[output 필드 상세 분석]")
    print("=" * 80)

    if "output" in response_json:
        output = response_json["output"]
        print(f"\noutput 필드 개수: {len(output)}")
        print("\n필드명과 값:")
        print("-" * 80)

        for key, value in output.items():
            value_display = f"'{value}'" if value == "" else value
            print(f"  {key:20s} = {value_display}")

        print("\n" + "-" * 80)
        print("\n[중요 필드 확인]")

        # 가능한 현재가 필드명들
        price_fields = ['last', 'LAST', 'curr_price', 'CURR_PRICE', 'price', 'PRICE',
                       'last_price', 'LAST_PRICE', 'current_price', 'CURRENT_PRICE',
                       'curr', 'CURR', 'stck_prpr', 'STCK_PRPR']

        print("\n현재가 관련 필드 검색:")
        found_price = False
        for field in price_fields:
            if field in output:
                print(f"  [발견] {field} = {output[field]}")
                found_price = True

        if not found_price:
            print("  [경고] 일반적인 현재가 필드명을 찾을 수 없습니다!")
            print("  위의 'output 필드' 목록에서 현재가로 보이는 필드를 찾아보세요.")
    else:
        print("[오류] 응답에 'output' 필드가 없습니다!")

    print("\n" + "=" * 80)
    print("완료")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

"""
SOXL을 다른 거래소 코드로 테스트
"""
import requests
from src.excel_bridge import ExcelBridge

def test_ticker_with_exchange(app_key, app_secret, access_token, ticker, exchange_code):
    """특정 거래소 코드로 시세 조회"""
    url = "https://openapi.koreainvestment.com:9443/uapi/overseas-price/v1/quotations/price"

    params = {
        "EXCD": exchange_code,
        "SYMB": ticker
    }

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "HHDFS00000300",
        "custtype": "P"
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)

    if response.status_code == 200:
        data = response.json()
        if data.get("rt_cd") == "0":
            output = data["output"]
            price = output.get("last", "")
            if price and price != "":
                try:
                    return float(price)
                except:
                    pass
    return 0.0

def main():
    print("=" * 60)
    print("SOXL 거래소별 시세 조회 테스트")
    print("=" * 60)

    bridge = ExcelBridge("phoenix_grid_template_v3.xlsx")
    settings = bridge.load_settings()

    # 토큰 발급
    token_url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    token_payload = {
        "grant_type": "client_credentials",
        "appkey": settings.kis_app_key,
        "appsecret": settings.kis_app_secret
    }
    token_response = requests.post(token_url, json=token_payload, timeout=10)

    if token_response.status_code != 200:
        print("토큰 발급 실패!")
        return 1

    access_token = token_response.json()["access_token"]
    print("토큰 발급 성공!\n")

    # 여러 거래소 코드로 테스트
    exchanges = {
        "NAS": "나스닥",
        "NYS": "뉴욕",
        "AMS": "아멕스"
    }

    ticker = "SOXL"

    print(f"[{ticker}] 거래소별 시세 조회:\n")

    for code, name in exchanges.items():
        price = test_ticker_with_exchange(
            settings.kis_app_key,
            settings.kis_app_secret,
            access_token,
            ticker,
            code
        )

        if price > 0:
            print(f"  {code} ({name:6s}): ${price:>8.2f}  [성공!]")
        else:
            print(f"  {code} ({name:6s}): $0.00       [실패]")

    print("\n" + "=" * 60)
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

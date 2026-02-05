"""
한국투자증권 USD 예수금 조회 스크립트 (독립 실행 버전)
파이썬 없이도 실행 가능 (EXE 빌드용)
"""
import sys
import io
import requests
import json
from datetime import datetime

# UTF-8 출력 설정 (한글 깨짐 방지)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def get_access_token(app_key, app_secret):
    """OAuth 토큰 발급"""
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"

    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"토큰 발급 실패: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"토큰 발급 중 오류: {e}")
        return None

def get_usd_balance(app_key, app_secret, account_no, access_token):
    """USD 예수금 조회"""
    # 계좌번호 파싱
    if '-' in account_no:
        cano, acnt_prdt_cd = account_no.split('-')
    else:
        cano = account_no[:8]
        acnt_prdt_cd = account_no[8:]

    url = "https://openapi.koreainvestment.com:9443/uapi/overseas-stock/v1/trading/inquire-psamount"

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "TTTS3007R",  # 실전투자
        "custtype": "P"
    }

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": "NASD",
        "OVRS_ORD_UNPR": "1.00",
        "ITEM_CD": "SOXL"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            rt_cd = data.get("rt_cd")

            if rt_cd == "0":
                output = data.get("output", {})
                usd_balance = float(output.get("ord_psbl_frcr_amt", 0))
                return usd_balance, data
            elif rt_cd == "7":
                return 0.0, data
            else:
                print(f"조회 실패: rt_cd={rt_cd}, msg={data.get('msg1')}")
                return None, data
        else:
            print(f"HTTP 오류: {response.status_code}")
            print(response.text)
            return None, None
    except Exception as e:
        print(f"잔고 조회 중 오류: {e}")
        return None, None

def main():
    print("=" * 60)
    print("한국투자증권 USD 예수금 조회")
    print("=" * 60)
    print(f"조회 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 사용자 입력 받기
    print("API 정보를 입력하세요:")
    print("(한국투자증권 API 포털: https://apiportal.koreainvestment.com)")
    print()

    try:
        app_key = input("APP KEY: ").strip()
        app_secret = input("APP SECRET: ").strip()
        account_no = input("계좌번호 (예: 12345678-01): ").strip()
    except EOFError:
        print("\n[ERROR] 입력을 받을 수 없습니다.")
        return

    print()
    print("-" * 60)

    if not app_key or not app_secret or not account_no:
        print("[ERROR] 모든 정보를 입력해야 합니다.")
        return

    print(f"계좌번호: {account_no}")
    print(f"APP KEY: {app_key[:20]}...")
    print()

    # 토큰 발급
    print("토큰 발급 중...")
    access_token = get_access_token(app_key, app_secret)

    if not access_token:
        print("[ERROR] OAuth 토큰 발급 실패")
        print()
        print("확인 사항:")
        print("  1. APP KEY와 APP SECRET이 올바른지 확인")
        print("  2. 실전투자 APP KEY인지 확인 (모의투자 키는 다름)")
        print("  3. https://apiportal.koreainvestment.com 에서 APP 상태 확인")
        return

    print("[OK] 토큰 발급 성공")
    print()

    # USD 예수금 조회
    print("USD 예수금 조회 중...")
    usd_balance, data = get_usd_balance(app_key, app_secret, account_no, access_token)

    print()
    print("=" * 60)

    if usd_balance is not None:
        print(f"[결과] USD 예수금: ${usd_balance:,.2f}")

        if usd_balance == 0:
            print()
            print("[주의] USD 예수금이 0원입니다.")
            print()
            print("가능한 원인:")
            print("  1. 원화를 USD로 환전하지 않았음")
            print("  2. 해외주식 거래 권한이 없음")
            print("  3. 실제로 USD 잔고가 0원")
            print()
            print("해결 방법:")
            print("  1. 한국투자증권 HTS 로그인")
            print("  2. [해외주식] -> [환전하기] 메뉴")
            print("  3. 원화 -> USD 환전 (최소 600달러 권장)")
            print()
            print("참고:")
            print("  - Phoenix Trading 실행을 위해서는 USD 잔고 필요")
            print("  - 환전 후 5~10분 뒤 다시 조회하세요")
        else:
            print()
            print("[성공] 거래 가능한 USD 잔고가 확인되었습니다.")
            print(f"Phoenix Trading을 실행할 수 있습니다.")

        # 상세 응답 출력
        if data:
            print()
            print("-" * 60)
            print("API 응답 상세:")
            print(f"  응답코드(rt_cd): {data.get('rt_cd')}")
            print(f"  메시지(msg1): {data.get('msg1', '').strip()}")
            if data.get('output'):
                output = data.get('output')
                print(f"  주문가능금액: ${output.get('ord_psbl_frcr_amt', 'N/A')}")
    else:
        print("[ERROR] USD 예수금 조회 실패")
        print()
        print("계좌번호가 올바른지 확인하세요.")

    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print()
    input("Enter 키를 누르면 종료됩니다...")

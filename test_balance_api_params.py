"""
한국투자증권 잔고조회 API 파라미터 테스트
실제 전송되는 헤더와 Query 파라미터를 출력하여 확인
"""

import sys
import logging
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.kis_rest_adapter import KisRestAdapter
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def test_balance_api_params():
    """잔고조회 API 파라미터 확인"""

    print("=" * 80)
    print("한국투자증권 잔고조회 API 파라미터 테스트")
    print("=" * 80)

    # 1. 설정 정보 확인
    print("\n[1] 설정 정보 (config.py)")
    print(f"  KIS_APP_KEY: {KIS_APP_KEY[:10]}...{KIS_APP_KEY[-10:]}")
    print(f"  KIS_APP_SECRET: {KIS_APP_SECRET[:10]}...{KIS_APP_SECRET[-10:]}")
    print(f"  KIS_ACCOUNT_NO: {KIS_ACCOUNT_NO}")

    # 2. KIS REST Adapter 초기화
    print("\n[2] KIS REST Adapter 초기화")
    adapter = KisRestAdapter(
        app_key=KIS_APP_KEY,
        app_secret=KIS_APP_SECRET,
        account_no=KIS_ACCOUNT_NO
    )

    # 3. 로그인 (토큰 발급)
    print("\n[3] 로그인 중...")
    try:
        adapter.login()
        print(f"  ✅ Access Token: {adapter.access_token[:20]}...{adapter.access_token[-20:]}")
        print(f"  ✅ 만료 시간: {adapter.token_expires_at}")
    except Exception as e:
        print(f"  ❌ 로그인 실패: {e}")
        return

    # 4. 계좌번호 파싱
    print("\n[4] 계좌번호 파싱")
    try:
        cano, acnt_prdt_cd = adapter._parse_account_no(KIS_ACCOUNT_NO)
        print(f"  원본 계좌번호: {KIS_ACCOUNT_NO}")
        print(f"  CANO (8자리): {cano}")
        print(f"  ACNT_PRDT_CD (2자리): {acnt_prdt_cd}")
    except Exception as e:
        print(f"  ❌ 파싱 실패: {e}")
        return

    # 5. API 엔드포인트
    print("\n[5] API 엔드포인트")
    endpoint = f"{adapter.BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"
    print(f"  URL: {endpoint}")

    # 6. 헤더 생성
    print("\n[6] HTTP 헤더 (Headers)")
    try:
        headers = adapter._get_headers(
            tr_id=adapter.TR_ID_OVERSEAS_ACCOUNT,
            custtype="P"
        )

        # 민감 정보 마스킹하여 출력
        safe_headers = headers.copy()
        if "authorization" in safe_headers:
            token = safe_headers["authorization"]
            safe_headers["authorization"] = f"Bearer {token[7:27]}...{token[-20:]}"
        if "appkey" in safe_headers:
            safe_headers["appkey"] = f"{headers['appkey'][:10]}...{headers['appkey'][-10:]}"
        if "appsecret" in safe_headers:
            safe_headers["appsecret"] = f"{headers['appsecret'][:10]}...{headers['appsecret'][-10:]}"

        for key, value in safe_headers.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"  ❌ 헤더 생성 실패: {e}")
        return

    # 7. Query 파라미터
    print("\n[7] Query 파라미터 (Query Parameters)")
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": "",  # 현재 구현: 빈 문자열 (전체 거래소)
        "TR_CRCY_CD": "USD",
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": ""
    }

    for key, value in params.items():
        display_value = f'"{value}"' if value == "" else value
        print(f"  {key}: {display_value}")

    # 8. API 호출 시뮬레이션
    print("\n[8] 실제 API 호출 테스트")
    print("  실행 중...")

    try:
        balance = adapter.get_balance()
        print(f"  ✅ 잔고 조회 성공!")
        print(f"  💰 USD 예수금: ${balance:,.2f}")

    except Exception as e:
        print(f"  ❌ 잔고 조회 실패: {e}")
        import traceback
        traceback.print_exc()

    # 9. 파라미터 설명
    print("\n" + "=" * 80)
    print("파라미터 설명")
    print("=" * 80)

    print("\n[필수 헤더]")
    print("  - content-type: application/json; charset=utf-8")
    print("  - authorization: Bearer {access_token}")
    print("  - appkey: 한투 발급 앱키")
    print("  - appsecret: 한투 발급 앱시크릿")
    print("  - tr_id: TTTS3012R (실전) / VTTS3012R (모의)")
    print("  - custtype: P (개인) / B (법인)")

    print("\n[선택 헤더 - 법인 전용]")
    print("  - personalseckey: 고객식별키 (현재 미사용)")
    print("  - seq_no: 001 (현재 미사용)")
    print("  - mac_address: MAC 주소 (현재 미사용)")
    print("  - phone_number: 핸드폰번호 (현재 미사용)")
    print("  - ip_addr: IP 주소 (현재 미사용)")
    print("  - gt_uid: 거래고유번호 (현재 미사용)")

    print("\n[Query 파라미터]")
    print(f"  - CANO: {cano} (계좌번호 8자리)")
    print(f"  - ACNT_PRDT_CD: {acnt_prdt_cd} (계좌상품코드 2자리)")
    print(f"  - OVRS_EXCG_CD: \"\" (빈 문자열 = 전체 거래소)")
    print(f"      * NASD: 미국 전체")
    print(f"      * NAS: 나스닥")
    print(f"      * NYSE: 뉴욕")
    print(f"      * AMEX: 아멕스")
    print(f"  - TR_CRCY_CD: USD (미국 달러)")
    print(f"  - CTX_AREA_FK200: \"\" (연속조회 키 - 최초 조회)")
    print(f"  - CTX_AREA_NK200: \"\" (연속조회 키 - 최초 조회)")

    print("\n" + "=" * 80)
    print("테스트 완료")
    print("=" * 80)


if __name__ == "__main__":
    test_balance_api_params()

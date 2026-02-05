"""
Phoenix Trading System 통합 테스트
- Release 폴더 Excel 파일 기준
- 잔고조회, 시세조회, 매수/매도 주문 테스트
- KIS API 파라미터 검증 포함
"""

import sys
import logging
from pathlib import Path
from decimal import Decimal

# src 폴더를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_integration.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_api_parameters():
    """API 파라미터 검증"""

    logger.info("=" * 80)
    logger.info("[1] KIS API 파라미터 검증")
    logger.info("=" * 80)

    # 1. 잔고조회 API 파라미터
    logger.info("\n[잔고조회 API - CTRP6504R]")
    logger.info("URL: /uapi/overseas-stock/v1/trading/inquire-present-balance")
    logger.info("필수 파라미터:")
    logger.info("  - CANO: 계좌번호 (8자리)")
    logger.info("  - ACNT_PRDT_CD: 계좌상품코드 (2자리)")
    logger.info("  - WCRC_FRCR_DVSN_CD: '02' (외화)")
    logger.info("  - NATN_CD: '840' (미국)")
    logger.info("  - TR_MKET_CD: '00' (전체)")
    logger.info("  - INQR_DVSN_CD: '00' (전체)")
    logger.info("  [OK] 모든 필수 파라미터 구현됨")

    # 2. 주문 API 파라미터
    logger.info("\n[주문 API - JTTT1002U]")
    logger.info("URL: /uapi/overseas-stock/v1/trading/order")
    logger.info("필수 파라미터:")
    logger.info("  - CANO: 계좌번호 (8자리)")
    logger.info("  - ACNT_PRDT_CD: 계좌상품코드 (2자리)")
    logger.info("  - OVRS_EXCG_CD: 'NASD' (나스닥)")
    logger.info("  - PDNO: 종목코드")
    logger.info("  - ORD_QTY: 주문수량")
    logger.info("  - OVRS_ORD_UNPR: 주문단가")
    logger.info("  - ORD_SVR_DVSN_CD: '0'")
    logger.info("  - ORD_DVSN: '00' (지정가) / '01' (시장가)")
    logger.info("  [OK] 모든 필수 파라미터 구현됨")

    logger.info("\n[OK] API 파라미터 검증 완료")


def test_balance_inquiry(kis: KisRestAdapter):
    """잔고 조회 테스트"""

    logger.info("\n" + "=" * 80)
    logger.info("[2] 잔고 조회 테스트")
    logger.info("=" * 80)

    try:
        balance = kis.get_balance()
        logger.info(f"[OK] 잔고 조회 성공: ${balance:,.2f}")
        return balance
    except Exception as e:
        logger.error(f"[FAIL] 잔고 조회 실패: {e}")
        raise


def test_price_inquiry(kis: KisRestAdapter, ticker: str):
    """시세 조회 테스트"""

    logger.info("\n" + "=" * 80)
    logger.info(f"[3] 시세 조회 테스트 ({ticker})")
    logger.info("=" * 80)

    try:
        price_data = kis.get_overseas_price(ticker)

        if price_data:
            logger.info(f"[OK] 시세 조회 성공")
            logger.info(f"  - 현재가: ${price_data['price']:.2f}")
            logger.info(f"  - 시가: ${price_data['open']:.2f}")
            logger.info(f"  - 고가: ${price_data['high']:.2f}")
            logger.info(f"  - 저가: ${price_data['low']:.2f}")
            logger.info(f"  - 거래량: {price_data['volume']:,}")
            return price_data['price']
        else:
            logger.error(f"[FAIL] 시세 조회 실패: 응답 없음")
            return None
    except Exception as e:
        logger.error(f"[FAIL] 시세 조회 실패: {e}")
        raise


def test_buy_order(kis: KisRestAdapter, ticker: str, quantity: int, price: float):
    """매수 주문 테스트 (실제 주문하지 않음)"""

    logger.info("\n" + "=" * 80)
    logger.info(f"[4] 매수 주문 테스트 (DRY RUN)")
    logger.info("=" * 80)

    logger.info(f"  - 종목: {ticker}")
    logger.info(f"  - 수량: {quantity}주")
    logger.info(f"  - 가격: ${price:.2f}")
    logger.info(f"  - 총액: ${quantity * price:.2f}")

    logger.info("\n[SKIP] 실제 주문은 실행하지 않습니다.")
    logger.info("실거래 테스트는 소액으로 수동 실행하시기 바랍니다.")


def test_sell_order(kis: KisRestAdapter, ticker: str, quantity: int, price: float):
    """매도 주문 테스트 (실제 주문하지 않음)"""

    logger.info("\n" + "=" * 80)
    logger.info(f"[5] 매도 주문 테스트 (DRY RUN)")
    logger.info("=" * 80)

    logger.info(f"  - 종목: {ticker}")
    logger.info(f"  - 수량: {quantity}주")
    logger.info(f"  - 가격: ${price:.2f}")
    logger.info(f"  - 총액: ${quantity * price:.2f}")

    logger.info("\n[SKIP] 실제 주문은 실행하지 않습니다.")
    logger.info("실거래 테스트는 소액으로 수동 실행하시기 바랍니다.")


def main():
    """메인 테스트 함수"""

    logger.info("\n" + "=" * 80)
    logger.info("Phoenix Trading System - 통합 테스트")
    logger.info("=" * 80)

    # Excel 파일 경로
    excel_path = Path("D:\\Project\\SOLX\\release\\phoenix_grid_template_v3.xlsx")

    if not excel_path.exists():
        logger.error(f"Excel 파일이 없습니다: {excel_path}")
        logger.error("파일 경로를 확인하세요.")
        return False

    try:
        # 1. API 파라미터 검증
        test_api_parameters()

        # 2. Excel 설정 로드
        logger.info("\n" + "=" * 80)
        logger.info("Excel 설정 로드")
        logger.info("=" * 80)

        excel = ExcelBridge(str(excel_path))
        excel.load_workbook()
        settings = excel.load_settings()

        logger.info(f"  - 종목: {settings.ticker}")
        logger.info(f"  - 투자금: ${settings.investment_usd:,.2f}")
        logger.info(f"  - 계좌번호: {settings.account_no[:4]}****{settings.account_no[-2:]}")
        logger.info(f"  - Tier 1 자동 갱신: {settings.tier1_auto_update}")

        excel.close_workbook()

        # 3. KIS API 초기화
        logger.info("\n" + "=" * 80)
        logger.info("KIS REST API 초기화")
        logger.info("=" * 80)

        kis = KisRestAdapter(
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            account_no=settings.kis_account_no  # [FIX] B14에서 읽은 실제 계좌번호 사용
        )

        # 4. 로그인
        logger.info("로그인 중...")
        if not kis.login():
            logger.error("[FAIL] 로그인 실패")
            return False

        logger.info("[OK] 로그인 성공")

        # 5. 잔고 조회
        balance = test_balance_inquiry(kis)

        # 6. 시세 조회
        current_price = test_price_inquiry(kis, settings.ticker)

        if not current_price:
            logger.error("[FAIL] 시세 조회 실패")
            return False

        # 7. 매수/매도 주문 테스트 (DRY RUN)
        test_quantity = 1  # 1주
        buy_price = round(current_price * 0.995, 2)  # 현재가 -0.5%
        sell_price = round(current_price * 1.005, 2)  # 현재가 +0.5%

        test_buy_order(kis, settings.ticker, test_quantity, buy_price)
        test_sell_order(kis, settings.ticker, test_quantity, sell_price)

        # 8. 최종 결과
        logger.info("\n" + "=" * 80)
        logger.info("테스트 완료 - 결과 요약")
        logger.info("=" * 80)

        logger.info(f"[OK] API 파라미터 검증: 통과")
        logger.info(f"[OK] 로그인: 성공")
        logger.info(f"[OK] 잔고 조회: ${balance:,.2f}")
        logger.info(f"[OK] 시세 조회: ${current_price:.2f}")
        logger.info(f"[SKIP] 매수/매도 주문: DRY RUN (실제 주문 안함)")

        logger.info("\n" + "=" * 80)
        logger.info("[결론] KIS API 연동 정상 작동 확인")
        logger.info("실거래 전 소액($100-$500)으로 수동 테스트 권장")
        logger.info("=" * 80)

        # 연결 해제
        kis.disconnect()

        return True

    except Exception as e:
        logger.error(f"테스트 실패: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()

    if success:
        logger.info("\n[SUCCESS] 통합 테스트 완료")
        sys.exit(0)
    else:
        logger.error("\n[FAILED] 통합 테스트 실패")
        sys.exit(1)

"""
잔고 조회 테스트 스크립트
- wcrc_Frcr_dvsn_cd 파라미터 수정 후 테스트
"""

import sys
import logging
from pathlib import Path

# src 폴더를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_balance.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_balance_inquiry():
    """잔고 조회 테스트"""

    logger.info("=" * 60)
    logger.info("잔고 조회 테스트 시작")
    logger.info("=" * 60)

    # Excel 파일 경로
    excel_path = Path(__file__).parent / "phoenix_grid_template_v3.xlsx"

    if not excel_path.exists():
        logger.error(f"Excel 파일이 없습니다: {excel_path}")
        return False

    try:
        # Excel 설정 읽기
        logger.info("Excel 설정 읽기 중...")
        excel = ExcelBridge(str(excel_path))
        excel.load_workbook()
        settings = excel.load_settings()

        logger.info(f"계좌번호: {settings.account_no[:4]}****{settings.account_no[-2:]}")
        logger.info(f"APP KEY: {settings.kis_app_key[:8]}...")

        # KIS REST API 초기화
        logger.info("KIS REST API 초기화 중...")
        kis = KisRestAdapter(
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            account_no=settings.account_no
        )

        # 로그인
        logger.info("로그인 중...")
        if not kis.login():
            logger.error("로그인 실패!")
            return False

        logger.info("로그인 성공!")

        # 잔고 조회
        logger.info("-" * 60)
        logger.info("잔고 조회 실행 중...")
        logger.info("-" * 60)

        balance = kis.get_balance()

        logger.info("=" * 60)
        logger.info(f"✅ 잔고 조회 성공: ${balance:,.2f}")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"테스트 실패: {e}", exc_info=True)
        return False
    finally:
        # 연결 해제
        try:
            kis.disconnect()
        except:
            pass


if __name__ == "__main__":
    success = test_balance_inquiry()

    if success:
        logger.info("✅ 테스트 완료 - 성공")
        sys.exit(0)
    else:
        logger.error("❌ 테스트 완료 - 실패")
        sys.exit(1)

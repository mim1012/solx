"""
Phoenix Trading System v3.1 (CUSTOM) - Configuration
시스템 설정 상수
"""
import os
from pathlib import Path

# .env 파일 로딩 (python-dotenv)
try:
    from dotenv import load_dotenv
    # .env 파일이 있으면 로드
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv가 없으면 경고만 출력
    import warnings
    warnings.warn("python-dotenv가 설치되지 않음. 환경 변수를 OS에서 직접 설정해야 합니다.")

# 프로젝트 경로
PROJECT_ROOT = Path(__file__).parent
DOCS_DIR = PROJECT_ROOT / "docs"
LOGS_DIR = PROJECT_ROOT / "logs"
SRC_DIR = PROJECT_ROOT / "src"

# Excel 템플릿
EXCEL_TEMPLATE_NAME = "phoenix_grid_template_v3.xlsx"
EXCEL_TEMPLATE_PATH = PROJECT_ROOT / EXCEL_TEMPLATE_NAME

# 거래 설정
TICKER = "SOXL"  # 고정 종목
MARKET = "US"    # 미국 주식

# 미국 시장 설정
US_MARKET_EXCHANGE = "AMS"  # SOXL 거래소: AMS (아멕스), 다른 종목: NAS (나스닥), NYS (뉴욕증권거래소)
US_MARKET_CURRENCY = "USD"  # 거래 통화
US_MARKET_TIMEZONE = "America/New_York"  # 미국 동부 시간대

# 그리드 파라미터 (기본값, Excel에서 오버라이드 가능)
DEFAULT_SEED_RATIO = 0.05      # 5% 시드 비율
DEFAULT_BUY_INTERVAL = 0.005   # 0.5% 매수 간격
DEFAULT_SELL_TARGET = 0.03     # 3% 매도 목표
DEFAULT_TOTAL_TIERS = 240      # 240개 티어

# [CUSTOM v3.1] Tier 1 거래 설정 기본값
DEFAULT_TIER1_TRADING_ENABLED = False  # Tier 1 거래 비활성화 (기본)
DEFAULT_TIER1_BUY_PERCENT = 0.0        # Tier 1 매수% (정확히 일치)

# ====== 미국 장시간 설정 (한국 시간 기준) ======
# 서머타임 (EDT, 3월~11월): 미국 동부시간 +13시간 = 한국 시간
MARKET_HOURS_EDT = {
    "regular_open": (22, 30),    # 정규장 개장 (한국 22:30 = 미국 09:30)
    "regular_close": (5, 0),     # 정규장 마감 (한국 05:00 = 미국 16:00)
    "premarket_start": 17,       # 프리마켓 시작 (한국 17:00 = 미국 04:00)
    "aftermarket_end": 7,        # 애프터마켓 종료 (한국 07:00 = 미국 18:00)
}
# 표준시 (EST, 11월~3월): 미국 동부시간 +14시간 = 한국 시간
MARKET_HOURS_EST = {
    "regular_open": (23, 30),    # 정규장 개장 (한국 23:30 = 미국 09:30)
    "regular_close": (6, 0),     # 정규장 마감 (한국 06:00 = 미국 16:00)
    "premarket_start": 18,       # 프리마켓 시작 (한국 18:00 = 미국 04:00)
    "aftermarket_end": 7,        # 애프터마켓 종료 (한국 07:00 = 미국 18:00)
}

# 프리마켓/애프터마켓 거래 허용 여부
ENABLE_PREMARKET = True   # True: 프리마켓 시간에도 거래
ENABLE_AFTERMARKET = True # True: 애프터마켓 시간에도 거래

# 시스템 설정
UPDATE_INTERVAL = 1.0          # 상태 업데이트 간격 (초)
DAILY_SUMMARY_INTERVAL = 3600  # 일일 요약 간격 (초, 1시간)

# 로깅 설정
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# API 설정
KIS_REQUEST_INTERVAL = 0.2  # 한국투자증권 API 요청 간격 (초)
TELEGRAM_TIMEOUT = 10       # 텔레그램 타임아웃 (초)

# [v4.1] 한국투자증권(KIS) REST API 설정 (64비트 Python 지원, 해외주식 지원)
# 환경 변수 우선, 없으면 빈 값
KIS_APP_KEY = os.getenv("KIS_APP_KEY", os.getenv("KIWOOM_APP_KEY", ""))        # KIS 개발자센터에서 발급받은 앱 키
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", os.getenv("KIWOOM_APP_SECRET", ""))  # KIS 개발자센터에서 발급받은 앱 시크릿
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", os.getenv("KIWOOM_ACCOUNT_NO", ""))  # 계좌번호 (예: 12345678-01)

# KIS API 모드 설정 (실전/모의투자)
KIS_API_MODE = os.getenv("KIS_API_MODE", "REAL")  # REAL: 실전, PAPER: 모의투자
KIS_API_BASE_URL = "https://openapi.koreainvestment.com:9443" if KIS_API_MODE == "REAL" else "https://openapivts.koreainvestment.com:29443"

# 경고 설정
WARNING_BALANCE_THRESHOLD = 100.0  # 잔고 경고 임계값 (USD)
WARNING_POSITION_COUNT = 200       # 포지션 수 경고 임계값

# 버전 정보
VERSION = "4.1.0"
VERSION_DATE = "2026-02-04"
DESCRIPTION = "Phoenix Grid Trading System v4.1 with US Market Config & Balance Fix"

# 개발 모드
DEBUG_MODE = False  # True로 설정 시 상세 로그 출력

# ====== 설정 검증 ======
def validate_config():
    """설정 검증"""
    errors = []

    # 필수 디렉토리 확인
    if not PROJECT_ROOT.exists():
        errors.append(f"프로젝트 루트를 찾을 수 없음: {PROJECT_ROOT}")

    if not SRC_DIR.exists():
        errors.append(f"소스 디렉토리를 찾을 수 없음: {SRC_DIR}")

    # Excel 템플릿 확인
    if not EXCEL_TEMPLATE_PATH.exists():
        errors.append(f"Excel 템플릿을 찾을 수 없음: {EXCEL_TEMPLATE_PATH}")
        errors.append("create_excel_template.py를 실행하여 템플릿을 생성하세요.")

    # 종목 코드 검증 (환경 변수 우선)
    ticker = os.getenv("US_MARKET_TICKER", TICKER)
    if ticker != "SOXL":
        errors.append(f"지원하지 않는 종목: {ticker}. SOXL만 지원합니다.")

    # KIS REST API 자격 증명 검증
    if not KIS_APP_KEY:
        errors.append("KIS_APP_KEY가 필요합니다. 환경 변수 또는 .env 파일에 설정하세요.")
    if not KIS_APP_SECRET:
        errors.append("KIS_APP_SECRET이 필요합니다. 환경 변수 또는 .env 파일에 설정하세요.")
    if not KIS_ACCOUNT_NO:
        errors.append("KIS_ACCOUNT_NO가 필요합니다. 환경 변수 또는 .env 파일에 설정하세요.")

    # 미국 시장 설정 검증
    exchange = os.getenv("US_MARKET_EXCHANGE", US_MARKET_EXCHANGE)
    if exchange not in ["AMS", "NAS", "NYS"]:
        errors.append(f"지원하지 않는 거래소 코드: {exchange}. AMS, NAS, NYS만 지원합니다.")

    if errors:
        return False, errors
    return True, []


if __name__ == "__main__":
    """설정 검증 테스트"""
    print("Phoenix Trading System v4.1 - 설정 검증")
    print("=" * 60)

    valid, errors = validate_config()

    if valid:
        print("[OK] 모든 설정이 정상입니다.")
        print()
        print(f"프로젝트 루트: {PROJECT_ROOT}")
        print(f"Excel 템플릿: {EXCEL_TEMPLATE_PATH}")
        print(f"종목: {os.getenv('US_MARKET_TICKER', TICKER)}")
        print(f"거래소: {os.getenv('US_MARKET_EXCHANGE', US_MARKET_EXCHANGE)}")
        print(f"통화: {os.getenv('US_MARKET_CURRENCY', US_MARKET_CURRENCY)}")
        print(f"API 모드: {KIS_API_MODE}")
        print(f"버전: {VERSION} ({VERSION_DATE})")
    else:
        print("[ERROR] 설정 오류 발견:")
        for error in errors:
            print(f"  - {error}")
        exit(1)

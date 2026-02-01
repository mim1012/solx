"""
Phoenix Trading System v4.1 - Main Entry Point
SOXL 자동매매 시스템 메인 실행 파일 (KIS REST API)

Excel + EXE 독립 실행 모드
"""
import os
import sys
import time
import signal
import logging
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트를 Python 경로에 추가 (PyInstaller 빌드 시에도 동작)
if getattr(sys, 'frozen', False):
    # PyInstaller로 빌드된 EXE 실행 시
    BASE_DIR = Path(sys.executable).parent
else:
    # 개발 모드 (python phoenix_main.py)
    BASE_DIR = Path(__file__).parent

sys.path.insert(0, str(BASE_DIR))

from src.excel_bridge import ExcelBridge
from src.grid_engine_v4_state_machine import GridEngineV4 as GridEngine
from src.kis_rest_adapter import KisRestAdapter
from src.telegram_notifier import TelegramNotifier
from src.models import GridSettings, SystemState
import config


class InitStatus(Enum):
    """초기화 결과 상태"""
    SUCCESS = 0           # 정상, 거래 시작 가능
    STOPPED = 10          # B15=FALSE (의도적 중지)
    ERROR_EXCEL = 20      # Excel 파일 없음
    ERROR_API_KEY = 21    # KIS API 키 누락
    ERROR_LOGIN = 22      # KIS 로그인 실패
    ERROR_PRICE = 23      # 시세 조회 실패
    ERROR_BALANCE = 24    # 잔고 조회 실패


# 로깅 설정
def setup_logging():
    """로그 설정 초기화"""
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"phoenix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


logger = setup_logging()


class PhoenixTradingSystem:
    """Phoenix 자동매매 시스템 메인 클래스 (KIS REST API)"""

    def __init__(self, excel_file: str = None):
        """
        초기화

        Args:
            excel_file: Excel 템플릿 경로 (기본: phoenix_grid_template_v3.xlsx)
        """
        self.excel_file = excel_file or str(BASE_DIR / config.EXCEL_TEMPLATE_NAME)
        self.is_running = False
        self.stop_requested = False

        # 구성 요소
        self.excel_bridge = None
        self.grid_engine = None
        self.kis_adapter = None
        self.telegram = None
        self.settings = None

        # 통계
        self.daily_buy_count = 0
        self.daily_sell_count = 0
        self.last_update_time = datetime.now()

        # 시그널 핸들러
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """종료 시그널 처리 (Ctrl+C)"""
        logger.info(f"\n종료 시그널 수신 ({signum}). 안전하게 종료 중...")
        self.stop_requested = True

    def _is_dst(self, date: datetime) -> bool:
        """
        미국 서머타임(Daylight Saving Time) 여부 확인

        서머타임 기간: 3월 두 번째 일요일 ~ 11월 첫 번째 일요일

        Args:
            date: 확인할 날짜

        Returns:
            bool: 서머타임이면 True
        """
        year = date.year

        # 3월 두 번째 일요일 계산
        march = datetime(year, 3, 1)
        days_until_sunday = (6 - march.weekday()) % 7
        first_sunday = march + timedelta(days=days_until_sunday)
        dst_start = first_sunday + timedelta(weeks=1)  # 두 번째 일요일

        # 11월 첫 번째 일요일 계산
        november = datetime(year, 11, 1)
        days_until_sunday = (6 - november.weekday()) % 7
        dst_end = november + timedelta(days=days_until_sunday)  # 첫 번째 일요일

        return dst_start <= date < dst_end

    def _is_market_open(self) -> tuple[bool, str]:
        """
        미국 주식 시장 개장 여부 확인 (한국 시간 기준, 서머타임 반영)

        [KIS API 공식 문서 기준]
        미국 정규장: 월~금 09:30~16:00 (미국 동부시간)

        한국 시간 변환:
        - 표준시 (EST, 11월~3월): 23:30 ~ 06:00 (시차 14시간)
        - 서머타임 (EDT, 3월~11월): 22:30 ~ 05:00 (시차 13시간)

        프리마켓/애프터마켓: 주문 불가
        - 프리마켓: 표준시 18:00~23:30, 서머타임 17:00~22:30
        - 애프터마켓: 표준시 06:00~07:00, 서머타임 05:00~07:00

        Returns:
            tuple[bool, str]: (개장 여부, 메시지)
        """
        now = datetime.now()
        is_dst = self._is_dst(now)
        weekday = now.weekday()  # 0=월요일, 6=일요일
        hour = now.hour
        minute = now.minute

        # 거래시간 설정 (서머타임 반영)
        if is_dst:
            # 서머타임: 22:30 ~ 05:00 (정규장)
            open_hour, open_minute = 22, 30
            close_hour, close_minute = 5, 0
            premarket_start = 17  # 프리마켓 시작
            aftermarket_end = 7   # 애프터마켓 종료
            season = "서머타임(EDT)"
        else:
            # 표준시: 23:30 ~ 06:00 (정규장)
            open_hour, open_minute = 23, 30
            close_hour, close_minute = 6, 0
            premarket_start = 18  # 프리마켓 시작
            aftermarket_end = 7   # 애프터마켓 종료
            season = "표준시(EST)"

        # 주말 체크 (미국 시간 기준)
        if weekday == 5 and (hour > close_hour or (hour == close_hour and minute > close_minute)):
            # 토요일 정규장 종료 이후
            next_monday = now + timedelta(days=2)
            next_open = next_monday.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
            return False, f"주말입니다. 다음 개장: {next_open.strftime('%Y-%m-%d %H:%M')} ({season})"
        elif weekday == 6:
            # 일요일 전체
            next_monday = now + timedelta(days=1)
            next_open = next_monday.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
            return False, f"주말입니다. 다음 개장: {next_open.strftime('%Y-%m-%d %H:%M')} ({season})"
        elif weekday == 0 and (hour < open_hour or (hour == open_hour and minute < open_minute)):
            # 월요일 정규장 개장 이전
            next_open = now.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
            return False, f"주말입니다. 다음 개장: {next_open.strftime('%H:%M')} ({season})"

        # 정규장 시간 체크 (서머타임 반영)
        if is_dst:
            # 서머타임: 22:30 ~ 05:00
            is_open = (
                (hour == 22 and minute >= 30) or
                (hour == 23) or
                (hour < 5) or
                (hour == 5 and minute == 0)
            )
        else:
            # 표준시: 23:30 ~ 06:00
            is_open = (
                (hour == 23 and minute >= 30) or
                (hour < 6) or
                (hour == 6 and minute == 0)
            )

        if is_open:
            return True, f"정규장 개장 중 ({season})"

        # KIS API 문서: 프리마켓/애프터마켓 시간대에도 주문 가능
        # 프리마켓 시간대 (주문 가능)
        if is_dst:
            # 서머타임: 17:00 ~ 22:29
            in_premarket = (
                (hour >= 17 and hour < 22) or
                (hour == 22 and minute < 30)
            )
        else:
            # 표준시: 18:00 ~ 23:29
            in_premarket = (
                (hour >= 18 and hour < 23) or
                (hour == 23 and minute < 30)
            )

        if in_premarket:
            return True, f"프리마켓 시간 (주문 가능) - 정규장: {open_hour:02d}:{open_minute:02d} ({season})"

        # 애프터마켓 시간대 (주문 가능)
        if is_dst:
            # 서머타임: 05:01 ~ 07:00
            in_aftermarket = (
                (hour == 5 and minute > 0) or
                (hour == 6)
            )
        else:
            # 표준시: 06:01 ~ 07:00
            in_aftermarket = (
                (hour == 6 and minute > 0)
            )

        if in_aftermarket:
            return True, f"애프터마켓 시간 (주문 가능) - 다음 정규장: {open_hour:02d}:{open_minute:02d} ({season})"

        # 기타 시간 (장 마감)
        next_open = now.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
        return False, f"장 마감 - 다음 개장: {next_open.strftime('%H:%M')} ({season})"

    def _wait_for_market_open(self):
        """시장 개장 시간까지 대기"""
        while not self.stop_requested:
            is_open, message = self._is_market_open()

            if is_open:
                logger.info(f"[OK] {message}")
                break

            logger.info(f"[WAIT] {message}")
            print(f"\r[대기 중] {message} - {datetime.now().strftime('%H:%M:%S')}", end="", flush=True)

            # 1분마다 체크
            time.sleep(60)

    def initialize(self) -> InitStatus:
        """
        시스템 초기화

        Returns:
            InitStatus: 초기화 결과 상태
        """
        logger.info("=" * 60)
        logger.info("Phoenix Trading System v4.1 초기화")
        logger.info("=" * 60)

        # 1. Excel 파일 확인
        if not Path(self.excel_file).exists():
            logger.error(f"Excel 파일을 찾을 수 없음: {self.excel_file}")
            logger.error("create_excel_template.py를 실행하여 템플릿을 생성하세요.")
            return InitStatus.ERROR_EXCEL

        logger.info(f"Excel 파일: {self.excel_file}")

        # 2. Excel 설정 로드
        try:
            logger.info("Excel 설정 로드 중...")
            self.excel_bridge = ExcelBridge(self.excel_file)
            self.settings = self.excel_bridge.load_settings()

            logger.info(f"  - 계좌번호: {self.settings.kis_account_no or self.settings.account_no}")
            logger.info(f"  - 종목: {self.settings.ticker}")
            logger.info(f"  - 투자금: ${self.settings.investment_usd:,.2f}")
            logger.info(f"  - 시스템 실행: {'ON' if self.settings.system_running else 'OFF'}")

            # 3. 시스템 실행 여부 확인 (B15 셀)
            if not self.settings.system_running:
                logger.warning("=" * 60)
                logger.warning("[STOP]  시스템이 중지 상태입니다 (Excel B15=FALSE)")
                logger.warning("=" * 60)
                logger.warning("[!] 이것은 에러가 아닙니다!")
                logger.warning("사용자가 Excel B15 셀을 FALSE로 설정하여 시스템이 중지된 상태입니다.")
                logger.warning("")
                logger.warning("자동 거래를 시작하려면:")
                logger.warning("  1. Excel 파일 열기")
                logger.warning("  2. 시트 '01_매매전략_기준설정'")
                logger.warning("  3. B15 셀을 TRUE로 변경")
                logger.warning("  4. 저장 후 프로그램 재시작")
                logger.warning("=" * 60)
                return InitStatus.STOPPED

            # 4. KIS API 키 확인
            if not self.settings.kis_app_key or not self.settings.kis_app_secret:
                logger.error("=" * 60)
                logger.error("[FAIL] KIS API 키가 설정되지 않았습니다!")
                logger.error("=" * 60)
                logger.error("Excel 파일에서 다음 항목을 입력하세요:")
                logger.error("  - B12: KIS APP KEY")
                logger.error("  - B13: KIS APP SECRET")
                logger.error("  - B14: KIS 계좌번호 (예: 12345678-01)")
                logger.error("=" * 60)
                return InitStatus.ERROR_API_KEY

            # 5. GridEngine 초기화
            logger.info("GridEngine 초기화 중...")
            self.grid_engine = GridEngine(self.settings)

            # [v4.0] 상태 머신 초기화 상태 확인
            status = self.grid_engine.get_status()
            state_summary = status.get('state_summary', {})
            logger.info(
                f"[OK] GridEngine v4.0 초기화 완료 | "
                f"상태머신[EMPTY:{state_summary.get('EMPTY',0)} "
                f"FILLED:{state_summary.get('FILLED',0)} "
                f"ORDERING:{state_summary.get('ORDERING',0)} "
                f"ERROR:{state_summary.get('ERROR',0)}]"
            )

            # 6. KIS API 연결
            logger.info("KIS REST API 연결 중...")
            self.kis_adapter = KisRestAdapter(
                app_key=self.settings.kis_app_key,
                app_secret=self.settings.kis_app_secret,
                account_no=self.settings.kis_account_no or self.settings.account_no
            )

            if not self.kis_adapter.login():
                logger.error("KIS API 로그인 실패!")
                return InitStatus.ERROR_LOGIN

            logger.info("[OK] KIS API 로그인 성공")

            # 7. 초기 시세 조회
            logger.info(f"{self.settings.ticker} 초기 시세 조회 중...")
            price_data = self.kis_adapter.get_overseas_price(self.settings.ticker)

            if not price_data:
                logger.error(f"{self.settings.ticker} 시세 조회 실패!")
                return InitStatus.ERROR_PRICE

            current_price = price_data['price']
            logger.info(f"  - 현재가: ${current_price:.2f}")
            logger.info(f"  - 시가: ${price_data['open']:.2f}")
            logger.info(f"  - 고가: ${price_data['high']:.2f}")
            logger.info(f"  - 저가: ${price_data['low']:.2f}")

            # 8. USD 예수금 조회 (매수가능금액조회 API)
            logger.info("USD 예수금 조회 중...")
            balance = self.kis_adapter.get_cash_balance(ticker=self.settings.ticker, price=current_price)

            if balance is None:
                logger.error("USD 예수금 조회 실패!")
                return InitStatus.ERROR_BALANCE

            logger.info(f"  - USD 예수금: ${balance:,.2f}")

            # 잔고 0 경고
            if balance == 0.0:
                logger.warning("=" * 60)
                logger.warning("[주의] USD 예수금이 $0.00 입니다!")
                logger.warning("=" * 60)
                logger.warning("이것은 다음 중 하나를 의미합니다:")
                logger.warning("  1. 계좌에 USD 잔고가 없음")
                logger.warning("  2. 해당 계좌에서 해외주식 거래 이력이 없음")
                logger.warning("")
                logger.warning("자동 거래를 시작하려면:")
                logger.warning("  1. 증권사 앱에서 USD 입금 (원화→달러 환전)")
                logger.warning("  2. 또는 해외주식을 1회 이상 거래하여 계좌 활성화")
                logger.warning("=" * 60)

            # 9. 보유 주식 정보 조회 (참고용)
            logger.info("보유 주식 조회 중...")
            self.kis_adapter.get_balance()

            # 10. GridEngine 초기값 설정
            self.grid_engine.tier1_price = current_price
            self.grid_engine.account_balance = balance
            self.grid_engine.current_price = current_price

            # 10. 텔레그램 알림 초기화
            logger.info("텔레그램 알림 초기화 중...")
            self.telegram = TelegramNotifier.from_settings(self.settings)

            if self.telegram and self.telegram.enabled:
                self.telegram.notify_system_start(self.settings)
                logger.info("[OK] 텔레그램 알림 활성화")
            else:
                logger.info("텔레그램 알림 비활성화")

            logger.info("=" * 60)
            logger.info("[OK] 시스템 초기화 완료!")
            logger.info("=" * 60)

            return InitStatus.SUCCESS

        except Exception as e:
            logger.error(f"초기화 중 예외 발생: {e}", exc_info=True)
            return InitStatus.ERROR_EXCEL  # 일반 에러

    def run(self) -> int:
        """
        메인 거래 루프

        Returns:
            int: 종료 코드 (0=정상, 10=중지, 20+=에러)
        """
        # 초기화
        status = self.initialize()

        # 초기화 결과에 따라 처리
        if status == InitStatus.STOPPED:
            logger.info("=" * 60)
            logger.info("[OK] 시스템이 중지 상태로 설정되어 있습니다.")
            logger.info("거래를 시작하려면 Excel B15를 TRUE로 변경하세요.")
            logger.info("=" * 60)
            return status.value  # 10

        elif status != InitStatus.SUCCESS:
            logger.error("=" * 60)
            logger.error(f"[FAIL] 초기화 실패 (코드: {status.value})")
            logger.error("=" * 60)
            return status.value  # 20-24

        # 정상 초기화 완료
        self.is_running = True

        # 시장 개장 시간 체크
        logger.info("=" * 60)
        logger.info("시장 개장 시간 확인 중...")
        logger.info("=" * 60)
        self._wait_for_market_open()

        if self.stop_requested:
            logger.info("사용자에 의해 대기 중 종료됨")
            return 0

        # 거래 시작
        logger.info("")
        logger.info("=" * 60)
        logger.info("메인 거래 루프 시작...")
        logger.info("종료하려면 Ctrl+C를 누르세요.")
        logger.info("=" * 60)
        logger.info("")

        try:
            while self.is_running and not self.stop_requested:
                # 1. 현재 시세 조회
                price_data = self.kis_adapter.get_overseas_price(self.settings.ticker)

                if not price_data:
                    logger.warning(f"{self.settings.ticker} 시세 조회 실패. 재시도...")
                    time.sleep(5)
                    continue

                current_price = price_data['price']

                # 시세가 0이면 시장 마감 체크
                if current_price <= 0:
                    is_open, message = self._is_market_open()
                    if not is_open:
                        logger.warning(f"시세 $0.00 감지 - {message}")
                        logger.info("시장 개장 시간까지 대기합니다...")
                        self._wait_for_market_open()
                        continue

                # 2. [P0 FIX] Tier 240 도달 긴급 정지 확인 (Risk-03 완화)
                if any(pos.tier == 240 for pos in self.grid_engine.positions):
                    logger.error("🛑 Tier 240 도달: 시스템 긴급 정지")

                    if self.telegram:
                        self.telegram.notify_emergency(
                            f"🛑 Tier 240 도달 - 긴급 정지\n"
                            f"현재가: ${current_price:.2f}\n"
                            f"Tier 1: ${self.grid_engine.tier1_price:.2f}\n"
                            f"하락률: {((current_price / self.grid_engine.tier1_price) - 1) * 100:.1f}%\n"
                            f"수동 개입 필요: 손절매 또는 Tier 1 재설정"
                        )

                    # Excel B15 "시스템 가동" FALSE로 변경
                    logger.warning("시스템 긴급 정지 (Excel B15 → FALSE)")
                    self.excel_bridge.update_cell("B15", False)
                    self.excel_bridge.save_workbook()
                    self.stop_signal = True
                    break

                # 3. 매매 신호 확인
                signals = self.grid_engine.process_tick(current_price)

                # 4. 매매 신호 처리
                for signal in signals:
                    self._process_signal(signal)

                # 4. Excel 업데이트 (주기적)
                now = datetime.now()
                if (now - self.last_update_time).total_seconds() >= self.settings.excel_update_interval:
                    self._update_system_state(current_price)
                    self.last_update_time = now

                # 5. 시세 조회 주기 대기 (Excel B22 설정값, 기본 40초)
                time.sleep(self.settings.price_check_interval)

        except KeyboardInterrupt:
            logger.info("\n사용자에 의한 종료 요청")
        except Exception as e:
            logger.error(f"거래 루프 중 에러: {e}", exc_info=True)
            if self.telegram:
                self.telegram.notify_error("시스템 에러", str(e))
        finally:
            self.shutdown()

        # 정상 종료
        return 0

    def _process_signal(self, signal):
        """매매 신호 처리 (배치 주문 지원)"""
        try:
            if signal.action == "BUY":
                if signal.tiers:
                    logger.info(f"[BATCH BUY] 배치 매수 신호: Tiers {signal.tiers}, 총 {signal.quantity}주 @ ${signal.price:.2f}")
                else:
                    logger.info(f"[BUY] 매수 신호: Tier {signal.tier}, {signal.quantity}주 @ ${signal.price:.2f}")

                # [P0 FIX] 잔고 사전 검증 (Risk-02 완화)
                required_capital = signal.quantity * signal.price

                if self.grid_engine.account_balance < required_capital:
                    logger.error(
                        f"❌ 잔고 부족: ${required_capital:.2f} 필요, "
                        f"${self.grid_engine.account_balance:.2f} 보유"
                    )

                    if self.telegram:
                        self.telegram.notify_error(
                            f"🛑 긴급 정지: 잔고 부족\n"
                            f"필요 금액: ${required_capital:.2f}\n"
                            f"보유 잔고: ${self.grid_engine.account_balance:.2f}\n"
                            f"입금 후 시스템 재시작 필요"
                        )

                    # 긴급 정지 (Excel B15 "시스템 가동" FALSE로 변경)
                    logger.warning("시스템 긴급 정지 (Excel B15 → FALSE)")
                    self.excel_bridge.update_cell("B15", False)
                    self.excel_bridge.save_workbook()
                    self.stop_signal = True
                    return

                # 매수 주문 (지정가 - 현재가 이하 보장)
                result = self.kis_adapter.send_order(
                    side="BUY",
                    ticker=self.settings.ticker,
                    quantity=signal.quantity,
                    price=signal.price  # 지정가 (현재가)
                )

                if result["status"] == "SUCCESS":
                    order_id = result["order_id"]
                    logger.info(f"[ORDER] 주문 접수 완료: Tier {signal.tier}, 주문번호 {order_id}")

                    # 체결 확인 (설정에 따라)
                    if self.settings.fill_check_enabled:
                        filled_price, filled_qty = self._wait_for_fill(order_id, signal.quantity)

                        if filled_qty > 0:
                            # 체결 완료 → GridEngine 상태 업데이트
                            position = self.grid_engine.execute_buy(
                                signal=signal,
                                actual_filled_price=filled_price,
                                actual_filled_qty=filled_qty
                            )

                            if position:  # 포지션이 실제로 생성된 경우에만
                                self.daily_buy_count += 1

                                logger.info(
                                    f"[OK] 매수 체결: Tier {signal.tier} - "
                                    f"체결 {filled_qty}주 @ ${filled_price:.2f} "
                                    f"(주문번호: {order_id})"
                                )

                                if self.telegram:
                                    is_tier1 = signal.tier == 1 and self.settings.tier1_trading_enabled
                                    self.telegram.notify_buy_executed(signal, is_tier1)
                        else:
                            logger.error(f"[FAIL] 매수 체결 실패: Tier {signal.tier}, 주문번호 {order_id} (체결 수량 0)")
                    else:
                        # 체결 확인 비활성화 (기존 동작: 즉시 처리, 위험)
                        logger.warning("[WARN] 체결 확인이 비활성화되어 있습니다. 주문 접수 = 체결로 간주합니다.")
                        position = self.grid_engine.execute_buy(
                            signal=signal,
                            actual_filled_price=result.get("filled_price", signal.price),
                            actual_filled_qty=result.get("filled_qty", signal.quantity)
                        )
                        self.daily_buy_count += 1
                else:
                    logger.error(f"[FAIL] 매수 주문 실패: Tier {signal.tier} - {result['message']}")
                    # [FIX] GridEngine에 실패 알림 → Lock 해제
                    self.grid_engine.confirm_order(
                        signal=signal,
                        order_id="",
                        filled_qty=0,
                        filled_price=0,
                        success=False,
                        error_message=result.get("message", "주문 실패")
                    )

            elif signal.action == "SELL":
                if signal.tiers:
                    logger.info(f"[BATCH SELL] 배치 매도 신호: Tiers {signal.tiers}, 총 {signal.quantity}주 @ ${signal.price:.2f}")
                else:
                    logger.info(f"[SELL] 매도 신호: Tier {signal.tier}, {signal.quantity}주 @ ${signal.price:.2f}")

                # 매도 주문 (지정가 - 현재가 이상 보장)
                result = self.kis_adapter.send_order(
                    side="SELL",
                    ticker=self.settings.ticker,
                    quantity=signal.quantity,
                    price=signal.price  # 지정가 (현재가)
                )

                if result["status"] == "SUCCESS":
                    order_id = result["order_id"]
                    logger.info(f"[ORDER] 주문 접수 완료: Tier {signal.tier}, 주문번호 {order_id}")

                    # 수익 계산용 포지션 (삭제 전)
                    position = next((p for p in self.grid_engine.positions if p.tier == signal.tier), None)

                    # 체결 확인 (설정에 따라)
                    if self.settings.fill_check_enabled:
                        filled_price, filled_qty = self._wait_for_fill(order_id, signal.quantity)

                        if filled_qty > 0:
                            # 체결 완료 → GridEngine 상태 업데이트
                            profit = self.grid_engine.execute_sell(
                                signal=signal,
                                actual_filled_price=filled_price,
                                actual_filled_qty=filled_qty
                            )
                            profit_rate = profit / position.invested_amount if position else 0.0
                            self.daily_sell_count += 1

                            logger.info(
                                f"[OK] 매도 체결: Tier {signal.tier} - "
                                f"체결 {filled_qty}주 @ ${filled_price:.2f}, "
                                f"수익 ${profit:.2f} ({profit_rate*100:.2f}%) "
                                f"(주문번호: {order_id})"
                            )

                            if self.telegram:
                                self.telegram.notify_sell_executed(signal, profit, profit_rate)
                        else:
                            logger.error(f"[FAIL] 매도 체결 실패: Tier {signal.tier}, 주문번호 {order_id} (체결 수량 0)")
                    else:
                        # 체결 확인 비활성화 (기존 동작: 즉시 처리, 위험)
                        logger.warning("[WARN] 체결 확인이 비활성화되어 있습니다. 주문 접수 = 체결로 간주합니다.")
                        profit = self.grid_engine.execute_sell(
                            signal=signal,
                            actual_filled_price=result.get("filled_price", signal.price),
                            actual_filled_qty=result.get("filled_qty", signal.quantity)
                        )
                        profit_rate = profit / position.invested_amount if position else 0.0
                        self.daily_sell_count += 1
                else:
                    logger.error(f"[FAIL] 매도 주문 실패: Tier {signal.tier} - {result['message']}")
                    # [FIX] GridEngine에 실패 알림 → 상태 복구
                    self.grid_engine.confirm_order(
                        signal=signal,
                        order_id="",
                        filled_qty=0,
                        filled_price=0,
                        success=False,
                        error_message=result.get("message", "주문 실패")
                    )

        except Exception as e:
            logger.error(f"매매 신호 처리 에러: {e}", exc_info=True)
            if self.telegram:
                self.telegram.notify_error("주문 처리 에러", str(e))

    def _wait_for_fill(self, order_id: str, expected_qty: int) -> tuple[float, int]:
        """
        주문 체결 대기 (폴링 방식)

        Args:
            order_id: 주문번호
            expected_qty: 예상 체결 수량

        Returns:
            tuple[float, int]: (체결가, 체결 수량)
        """
        max_retries = self.settings.fill_check_max_retries
        check_interval = self.settings.fill_check_interval

        for attempt in range(1, max_retries + 1):
            time.sleep(check_interval)

            fill_status = self.kis_adapter.get_order_fill_status(order_id)

            status = fill_status["status"]
            filled_qty = fill_status["filled_qty"]
            filled_price = fill_status["filled_price"]

            logger.debug(
                f"[FILL CHECK {attempt}/{max_retries}] "
                f"주문번호 {order_id}: {status}, "
                f"체결 {filled_qty}/{expected_qty}주 @ ${filled_price:.2f}"
            )

            if filled_qty > 0:
                # 체결 완료 또는 부분 체결
                logger.info(
                    f"[FILL] 체결 확인: {filled_qty}주 @ ${filled_price:.2f} "
                    f"(상태: {status})"
                )
                return filled_price, filled_qty
            elif status == "거부":
                # 주문 거부
                reject_reason = fill_status["reject_reason"]
                logger.error(f"[REJECT] 주문 거부: {reject_reason}")
                return 0.0, 0
            elif status == "오류":
                # API 오류
                logger.error(f"[ERROR] 체결 조회 오류: {fill_status['reject_reason']}")
                # 계속 재시도
                continue

            # 아직 체결 안됨 또는 부분 체결 → 재시도

        # 최대 재시도 초과 → [P0 FIX] 추가 조회 1회 (5초 대기)
        logger.warning(
            f"[TIMEOUT] 체결 확인 타임아웃: 주문번호 {order_id}, "
            f"{max_retries * check_interval}초 경과 → 5초 후 최종 확인"
        )

        # [P0 FIX] 타임아웃 후 추가 조회 (Risk-01 완화)
        time.sleep(5)
        final_status = self.kis_adapter.get_order_fill_status(order_id)

        if final_status["filled_qty"] > 0:
            logger.info(
                f"[FILL RECOVERED] 최종 확인에서 체결 발견! "
                f"{final_status['filled_qty']}주 @ ${final_status['filled_price']:.2f}"
            )

            if self.telegram:
                self.telegram.notify_warning(
                    f"체결 타임아웃 후 복구\n"
                    f"주문번호: {order_id}\n"
                    f"체결: {final_status['filled_qty']}주 @ ${final_status['filled_price']:.2f}"
                )

            return final_status["filled_price"], final_status["filled_qty"]

        # 최종 확인에서도 체결 없음 → 긴급 알림
        logger.error(f"[FAIL] 최종 확인 실패: 주문번호 {order_id} - 수동 확인 필요")

        if self.telegram:
            self.telegram.notify_error(
                f"⚠️ 체결 타임아웃 발생\n"
                f"주문번호: {order_id}\n"
                f"수동 확인 필요: KIS 홈페이지 → 주문 내역 → 체결 여부 확인"
            )

        return 0.0, 0

    def _update_system_state(self, current_price: float):
        """시스템 상태 업데이트 및 Excel 저장"""
        try:
            state = self.grid_engine.get_system_state(current_price)

            # Excel 업데이트
            self.excel_bridge.update_program_info(state)
            self.excel_bridge.update_program_area(
                self.grid_engine.positions,
                self.grid_engine.tier1_price,
                self.settings.buy_interval
            )

            # 로그 엔트리 추가
            log_entry = self.excel_bridge.create_history_log_entry(
                state,
                self.settings,
                buy_qty=self.daily_buy_count,
                sell_qty=self.daily_sell_count
            )
            self.excel_bridge.append_history_log(log_entry)

            # 저장
            self.excel_bridge.save_workbook()

            # [v4.0] 상태 머신 상태 로깅
            status = self.grid_engine.get_status()
            state_summary = status.get('state_summary', {})
            logger.debug(
                f"[SAVE] Excel 업데이트: 가격 ${current_price:.2f}, "
                f"포지션 {len(self.grid_engine.positions)}개 | "
                f"상태머신[EMPTY:{state_summary.get('EMPTY',0)} "
                f"FILLED:{state_summary.get('FILLED',0)} "
                f"ORDERING:{state_summary.get('ORDERING',0)} "
                f"PARTIAL:{state_summary.get('PARTIAL_FILLED',0)} "
                f"ERROR:{state_summary.get('ERROR',0)}]"
            )

        except Exception as e:
            logger.error(f"상태 업데이트 에러: {e}", exc_info=True)

    def shutdown(self):
        """시스템 종료"""
        logger.info("=" * 60)
        logger.info("시스템 종료 중...")
        logger.info("=" * 60)

        self.is_running = False

        try:
            # 최종 상태 저장
            if self.grid_engine and self.excel_bridge:
                final_state = self.grid_engine.get_system_state(self.grid_engine.current_price)

                self.excel_bridge.update_program_info(final_state)
                self.excel_bridge.update_program_area(
                    self.grid_engine.positions,
                    self.grid_engine.tier1_price,
                    self.settings.buy_interval
                )
                self.excel_bridge.save_workbook()
                self.excel_bridge.close_workbook()

                logger.info("[OK] 최종 상태 저장 완료")

                # 종료 알림
                if self.telegram:
                    self.telegram.notify_system_stop(final_state)

            # KIS API 연결 해제
            if self.kis_adapter:
                self.kis_adapter.disconnect()
                logger.info("[OK] KIS API 연결 해제")

            logger.info("=" * 60)
            logger.info("[OK] Phoenix Trading System 정상 종료")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"종료 중 에러: {e}", exc_info=True)


def main():
    """메인 함수"""
    exit_code = 1  # 기본값: 에러

    try:
        print("")
        print("=" * 60)
        print("Phoenix Trading System v4.1 (KIS REST API)")
        print("SOXL 자동매매 시스템")
        print("=" * 60)
        print("")

        # Excel 파일 경로 (인자로 받거나 기본값)
        excel_file = sys.argv[1] if len(sys.argv) > 1 else None

        # 실거래 경고
        print("[WARNING] 경고: 이 시스템은 실제 자금으로 SOXL을 거래합니다.")
        print("[WARNING] 손실 위험이 있으며, 투자 책임은 사용자에게 있습니다.")
        print("")

        # 시스템 시작
        system = PhoenixTradingSystem(excel_file)
        exit_code = system.run()

    except KeyboardInterrupt:
        print("\n\n[사용자 중단] Ctrl+C가 눌렸습니다.")
        exit_code = 130
    except Exception as e:
        print("\n\n" + "=" * 60)
        print("[치명적 에러] 예상치 못한 오류 발생!")
        print("=" * 60)
        print(f"에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {e}")
        print("\n상세 로그는 logs/ 폴더를 확인하세요.")
        print("=" * 60)
        exit_code = 1
    finally:
        # 무조건 실행: 창이 닫히지 않도록 대기
        print("")
        print("=" * 60)
        if exit_code == 0:
            print("[정상 종료] 프로그램이 성공적으로 종료되었습니다.")
        elif exit_code == 10:
            print("[시스템 중지] Excel B15가 FALSE로 설정되어 있습니다.")
            print("자동 거래를 시작하려면 Excel B15를 TRUE로 변경하세요.")
        else:
            print(f"[에러 종료] 프로그램이 에러로 종료되었습니다 (코드: {exit_code})")
            print("위 로그를 확인하여 문제를 파악하세요.")
        print("=" * 60)
        print("")
        input("Press Enter to exit...")

    # 종료 코드 반환
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

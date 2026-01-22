"""
Phoenix Grid System - 데이터 모델
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Position:
    """보유 포지션 정보 (불변)"""
    tier: int                    # 티어 번호 (1~240)
    quantity: int                # 보유 수량 (주)
    avg_price: float             # 평균 매수가 (USD)
    invested_amount: float       # 투자금 (USD)
    opened_at: datetime          # 포지션 오픈 시각

    def current_value(self, current_price: float) -> float:
        """
        현재 평가금액 (current_price 필수)

        Args:
            current_price: 현재 시세 (USD)

        Returns:
            평가금액 (USD)
        """
        return self.quantity * current_price

    def unrealized_profit(self, current_price: float) -> float:
        """
        미실현 손익

        Args:
            current_price: 현재 시세 (USD)

        Returns:
            미실현 손익 (USD)
        """
        return (current_price - self.avg_price) * self.quantity

    def calculate_profit(self, current_price: float) -> float:
        """현재가 기준 수익금 계산 (unrealized_profit과 동일, 하위 호환성)"""
        return self.unrealized_profit(current_price)


@dataclass(frozen=True)
class TradeSignal:
    """매매 신호 (불변)"""
    action: str                  # "BUY" 또는 "SELL"
    tier: int                    # 거래 대상 티어
    price: float                 # 거래 예상 가격 (USD)
    quantity: int                # 거래 수량 (주)
    reason: str                  # 거래 사유
    timestamp: datetime = None   # 신호 생성 시각

    def __post_init__(self):
        if self.timestamp is None:
            # frozen=True이므로 object.__setattr__ 사용
            object.__setattr__(self, 'timestamp', datetime.now())


@dataclass(frozen=True)
class GridSettings:
    """그리드 시스템 설정 (불변)"""
    # 기본 설정
    account_no: str
    ticker: str                  # "SOXL" 고정
    investment_usd: float        # 총 투자금 (USD)
    total_tiers: int             # 티어 분할 수 (240 고정)
    tier_amount: float           # 1티어당 금액 (USD)
    tier1_auto_update: bool      # Tier 1 자동 갱신 여부

    # [CUSTOM v3.1] Tier 1 거래 설정
    tier1_trading_enabled: bool  # Tier 1 매수/매도 활성화
    tier1_buy_percent: float     # Tier 1 매수% (예: 0.0, -0.005, +0.005)

    # 제한 스위치
    buy_limit: bool              # 매수 제한 (True=매수 중단)
    sell_limit: bool             # 매도 제한 (True=매도 중단)

    # [v4.1] KIS API 설정
    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_account_no: str = ""
    system_running: bool = False  # TRUE=시작, FALSE=중지

    # 텔레그램 알림
    telegram_id: Optional[str] = None
    telegram_token: Optional[str] = None
    telegram_enabled: bool = False

    # 시스템 설정
    excel_update_interval: float = 1.0      # Excel 업데이트 주기 (초)
    price_check_interval: float = 40.0      # 시세 조회 주기 (초) - 기본값 40초

    # 체결 확인 설정
    fill_check_enabled: bool = True         # 체결 확인 활성화
    fill_check_max_retries: int = 10        # 체결 확인 최대 재시도 (기본: 10회)
    fill_check_interval: float = 2.0        # 체결 확인 간격 (초, 기본: 2초)

    # 그리드 파라미터 (계산값)
    seed_ratio: float = 0.05     # 시드 비율 (5%)
    buy_interval: float = 0.005  # 매수 간격 (0.5%)
    sell_target: float = 0.03    # 매도 목표 (3%)

    # 테스트가 기대하는 파생 필드
    tier1_price: float = 10.0    # Tier 1 기준가 (USD)
    tier_interval: float = 0.05  # Tier 간 가격 간격 (USD, buy_interval과 다름)

    def __post_init__(self):
        """설정값 유효성 검증"""
        if self.total_tiers < 1 or self.total_tiers > 240:
            raise ValueError("total_tiers must be between 1 and 240")
        if self.investment_usd <= 0:
            raise ValueError("investment_usd must be positive")
        if self.tier1_price <= 0:
            raise ValueError("tier1_price must be positive")


@dataclass
class SystemState:
    """시스템 현재 상태"""
    current_price: float         # 현재가 (USD)
    tier1_price: float           # Tier 1 기준가 (High Water Mark)
    current_tier: int            # 현재 티어
    account_balance: float       # 계좌 잔고 (USD)
    total_quantity: int          # 총 보유 수량 (주)
    total_invested: float        # 총 투자금 (USD)
    stock_value: float           # 주식 평가금 (USD)
    total_profit: float          # 잔고 수익 (USD)
    profit_rate: float           # 수익률 (%)

    buy_status: str = "대기"      # 매수 상태
    sell_status: str = "대기"     # 매도 상태
    last_update: datetime = None # 최근 업데이트 시간

    def __post_init__(self):
        if self.last_update is None:
            self.last_update = datetime.now()

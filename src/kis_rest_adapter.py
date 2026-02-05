"""
Phoenix KIS REST API Adapter v4.1
한국투자증권(Korea Investment & Securities) REST API 연동 (64비트 Python 지원)

마이그레이션 이유:
- 기존 OpenAPI+ (COM): 32비트 Python 필수, 해외주식 미지원
- 신규 REST API: 64비트 Python 지원, 크로스 플랫폼, 해외주식 지원

변경 사항:
- OAuth2 인증 방식
- HTTP 요청 기반 (requests 라이브러리)
- WebSocket 실시간 시세
- 해외주식(미국주식) 거래 지원

v4.1 개선 사항:
- Approval key 발급 구현
- Hashkey signature 생성
- tr_id, custtype 헤더 추가
- 토큰 관리 강화
- WebSocket 재연결 로직
- Rate limiting 적용
"""

import requests
import logging
import asyncio
import websockets
import json
import time
import threading
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# config import
try:
    import config
except ImportError:
    # 상대 경로로 import 시도
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    import config


@dataclass
class OrderResult:
    """주문 결과"""
    order_no: str
    status: str  # "success", "failed"
    message: str = ""
    filled_price: float = 0.0  # 체결가 (USD)
    filled_qty: int = 0        # 체결 수량
    total_qty: int = 0         # 주문 총 수량


class AuthenticationError(Exception):
    """인증 오류"""
    pass


class KisRestAdapter:
    """
    한국투자증권(KIS) REST API 어댑터

    주요 기능:
    - OAuth2 인증 + Approval key
    - 미국 주식 실시간 시세 수신 (WebSocket)
    - 미국 주식 매수/매도 주문
    - 계좌 잔고 조회

    장점:
    - 64비트 Python 지원
    - Windows, Mac, Linux 지원
    - 설치 불필요 (HTTP 요청만)
    - 해외주식 거래 지원
    """

    # REST API 엔드포인트
    BASE_URL = "https://openapi.koreainvestment.com:9443"
    WS_URL = "ws://ops.koreainvestment.com:21000"  # 실계좌용 (모의투자: port 31000)

    # TR ID 정의
    TR_ID_OVERSEAS_PRICE = "HHDFS00000300"      # 해외주식 현재가
    TR_ID_OVERSEAS_BUY = "TTTT1002U"            # 해외주식 매수 (실전: TTTT1002U, 모의: VTTT1002U)
    TR_ID_OVERSEAS_SELL = "TTTT1006U"           # 해외주식 매도 (실전: TTTT1006U, 모의: VTTT1001U)
    TR_ID_OVERSEAS_BALANCE = "CTRP6548R"        # 해외주식 잔고
    TR_ID_OVERSEAS_ACCOUNT = "TTTS3012R"        # 해외주식 잔고 (실전: TTTS3012R, 모의: VTTS3012R)
    TR_ID_OVERSEAS_BUYABLE = "TTTS3007R"        # 해외주식 매수가능금액조회 (USD 예수금)
    TR_ID_WS_REALTIME = "HDFSCNT0"              # 실시간 체결가

    def __init__(self, app_key: str, app_secret: str, account_no: str = "", error_callback: Optional[Callable] = None):
        """
        REST API 어댑터 초기화

        Args:
            app_key: 앱 키 (키움 개발자센터에서 발급)
            app_secret: 앱 시크릿
            account_no: 계좌번호 (선택)
            error_callback: 치명적 오류 발생 시 호출할 콜백 함수 (title: str, message: str)
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no

        # 인증 토큰
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.approval_key: Optional[str] = None

        # WebSocket 연결
        self.ws_connection = None
        self.ws_running = False
        self.ws_ready_event = threading.Event()  # WebSocket 준비 완료 이벤트
        self.ws_reconnect_count = 0
        self.ws_max_reconnect = 5

        # 콜백
        self.price_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = error_callback  # [v4.1] 치명적 오류 콜백

        # Rate limiting
        self.last_request_time = 0
        self.request_interval = 0.2  # 초당 5회 (200ms 간격)

        logger.info("KisRestAdapter 초기화 완료 (한국투자증권 REST API)")

    def _parse_account_no(self, raw_account: str) -> tuple[str, str]:
        """
        계좌번호 파싱 (KIS REST API 사양)

        Args:
            raw_account: 원본 계좌번호 (예: "12345678-01" 또는 "1234567801")

        Returns:
            tuple: (CANO, ACNT_PRDT_CD)
                - CANO: 계좌번호 8자리
                - ACNT_PRDT_CD: 계좌상품코드 2자리

        Raises:
            ValueError: 계좌번호 형식이 잘못된 경우
        """
        if not raw_account:
            raise ValueError("계좌번호가 비어 있습니다")

        # 하이픈, 공백 제거
        raw_account = raw_account.strip().replace("-", "").replace(" ", "")

        # 최소 10자리 필요 (계좌번호 8 + 상품코드 2)
        if len(raw_account) < 10:
            raise ValueError(f"계좌번호가 너무 짧습니다: {raw_account} (최소 10자리 필요)")

        # CANO (앞 8자리), ACNT_PRDT_CD (다음 2자리)
        cano = raw_account[:8]
        acnt_prdt_cd = raw_account[8:10]

        logger.debug(f"계좌번호 파싱: {raw_account[:4]}****{raw_account[-2:]} → CANO={cano[:4]}****, ACNT_PRDT_CD={acnt_prdt_cd}")

        return cano, acnt_prdt_cd

    # =====================================
    # 1. 인증 (OAuth2 + Approval Key)
    # =====================================

    def login(self) -> bool:
        """
        OAuth2 토큰 + Approval key 발급 (토큰 캐싱 지원)

        Returns:
            bool: 로그인 성공 여부

        Raises:
            AuthenticationError: 인증 실패 시
        """
        try:
            # 토큰 캐시 파일 경로
            token_cache_file = Path("kis_token_cache.json")

            # 1. 캐시된 토큰 확인
            if token_cache_file.exists():
                try:
                    with open(token_cache_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)

                    # 만료 시간 확인 (5분 여유)
                    expires_at = datetime.fromisoformat(cache["expires_at"])
                    if datetime.now() < expires_at - timedelta(minutes=5):
                        # 유효한 토큰 재사용
                        self.access_token = cache["access_token"]
                        self.token_expires_at = expires_at
                        self.approval_key = cache.get("approval_key")

                        logger.info(f"[캐시] Access Token 재사용 (만료: {self.token_expires_at})")
                        return True
                    else:
                        logger.info("[캐시] 토큰 만료됨, 재발급 시도...")
                except Exception as e:
                    logger.warning(f"[캐시] 토큰 캐시 로드 실패: {e}, 재발급 시도...")

            # 2. Access Token 발급 (실계좌: /oauth2/tokenP, 모의: /oauth2/token)
            url = f"{self.BASE_URL}/oauth2/tokenP"

            payload = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret
            }

            headers = {
                "Content-Type": "application/json; charset=utf-8"
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                expires_in = data["expires_in"]  # 초 단위
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                logger.info(f"Access Token 발급 성공 (만료: {self.token_expires_at})")
            else:
                error_msg = f"Access Token 발급 실패: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise AuthenticationError(error_msg)

            # 2. Approval Key 발급 (WebSocket용)
            approval_url = f"{self.BASE_URL}/oauth2/Approval"

            approval_payload = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "secretkey": self.app_secret
            }

            approval_response = requests.post(approval_url, json=approval_payload, timeout=10)

            if approval_response.status_code == 200:
                approval_data = approval_response.json()
                self.approval_key = approval_data.get("approval_key")
                logger.info("Approval Key 발급 성공")
            else:
                logger.warning(f"Approval Key 발급 실패: {approval_response.status_code}")
                # Approval key 없어도 REST API는 사용 가능 (WebSocket만 불가)

            # 3. 토큰 캐시 저장
            try:
                cache_data = {
                    "access_token": self.access_token,
                    "expires_at": self.token_expires_at.isoformat(),
                    "approval_key": self.approval_key,
                    "cached_at": datetime.now().isoformat()
                }
                with open(token_cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
                logger.info(f"[캐시] 토큰 저장 완료: {token_cache_file}")
            except Exception as e:
                logger.warning(f"[캐시] 토큰 저장 실패: {e} (무시하고 계속)")

            return True

        except AuthenticationError:
            raise
        except Exception as e:
            error_msg = f"로그인 예외: {e}"
            logger.error(error_msg)
            raise AuthenticationError(error_msg)

    def _refresh_token_if_needed(self):
        """토큰 만료 확인 및 갱신

        Raises:
            AuthenticationError: 토큰이 없거나 갱신 실패 시
        """
        if not self.token_expires_at:
            raise AuthenticationError("토큰이 발급되지 않았습니다. login()을 먼저 호출하세요.")

        # 만료 5분 전에 갱신
        if datetime.now() >= self.token_expires_at - timedelta(minutes=5):
            logger.info("토큰 갱신 중...")
            success = self.login()
            if not success:
                raise AuthenticationError("토큰 갱신 실패")

    def _get_hashkey(self, body: dict) -> str:
        """
        POST 요청 Body의 Hashkey 생성

        Args:
            body: POST 요청 body (dict)

        Returns:
            str: hashkey 값
        """
        try:
            url = f"{self.BASE_URL}/uapi/hashkey"

            headers = {
                "Content-Type": "application/json",
                "appkey": self.app_key,
                "appsecret": self.app_secret
            }

            response = requests.post(url, headers=headers, json=body, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("HASH", "")
            else:
                logger.error(f"Hashkey 생성 실패: {response.status_code}")
                return ""

        except Exception as e:
            logger.error(f"Hashkey 생성 예외: {e}")
            return ""

    def _get_headers(self, tr_id: str, custtype: str = "P", hashkey: str = "") -> dict:
        """
        API 요청 헤더 생성

        Args:
            tr_id: 거래 ID (TR_ID)
            custtype: 고객 타입 (P: 개인, B: 법인)
            hashkey: POST 요청 시 hashkey (선택)

        Returns:
            dict: Authorization 헤더

        Raises:
            AuthenticationError: 토큰이 없는 경우
        """
        # 토큰 갱신 확인
        self._refresh_token_if_needed()

        if not self.access_token:
            raise AuthenticationError("Access Token이 없습니다. login()을 먼저 호출하세요.")

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": custtype
        }

        # POST 요청 시 hashkey 추가
        if hashkey:
            headers["hashkey"] = hashkey

        return headers

    def _apply_rate_limit(self):
        """Rate Limiting 적용 (초당 5회)"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_interval:
            sleep_time = self.request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    # =====================================
    # 2. 시세 조회
    # =====================================

    def get_overseas_price(self, ticker: str) -> Optional[Dict]:
        """
        미국 주식 현재가 조회 (자동 거래소 감지)

        Args:
            ticker: 종목코드 (예: SOXL)

        Returns:
            dict: 시세 정보 또는 None
            {
                "ticker": "SOXL",
                "price": 45.30,
                "open": 44.80,
                "high": 45.50,
                "low": 44.50,
                "volume": 1234567
            }
        """
        # 빈 문자열 처리 함수 (안전한 float 변환)
        def safe_float(value, default=0.0):
            """빈 문자열을 안전하게 float로 변환"""
            if value == "" or value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        # 거래소 코드 우선순위: NASD → AMEX → NYSE
        # 대부분 종목: NASD (나스닥)
        # 일부 ETF (SOXL, SPY, SPXL 등): AMEX (아멕스)
        exchanges_to_try = ["NASD", "AMEX", "NYSE"]

        for excd in exchanges_to_try:
            try:
                self._apply_rate_limit()

                url = f"{self.BASE_URL}/uapi/overseas-price/v1/quotations/price"

                params = {
                    "EXCD": excd,
                    "SYMB": ticker
                }

                headers = self._get_headers(tr_id=self.TR_ID_OVERSEAS_PRICE)

                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("rt_cd") == "0":  # 성공
                        output = data["output"]

                        # 디버깅: 실제 API 응답 확인
                        logger.debug(f"KIS API 시세 응답 ({excd}): {output}")

                        price = safe_float(output.get("last"))

                        # 가격이 0보다 크면 성공
                        if price > 0:
                            if excd != "NASD":
                                logger.info(f"[거래소 자동 감지] {ticker}는 {excd} 거래소에서 조회됨")

                            return {
                                "ticker": ticker,
                                "price": price,
                                "open": safe_float(output.get("open")),
                                "high": safe_float(output.get("high")),
                                "low": safe_float(output.get("low")),
                                "volume": int(output.get("tvol") or 0)
                            }
                        else:
                            # 가격이 0이면 다음 거래소 시도
                            logger.debug(f"{ticker}: {excd} 거래소에서 시세 없음 (다음 거래소 시도)")
                            continue

            except AuthenticationError:
                raise
            except Exception as e:
                logger.warning(f"{ticker}: {excd} 거래소 조회 중 예외: {e}")
                continue

        # 모든 거래소에서 실패
        logger.error(f"{ticker}: 모든 거래소(NASD, AMEX, NYSE)에서 시세 조회 실패")
        return None

    # =====================================
    # 3. 주문 실행
    # =====================================

    def _send_order_internal(
        self,
        ticker: str,
        order_type: str,  # "buy" or "sell"
        quantity: int,
        price: float,
        order_kind: str = "limit"  # "limit" or "market"
    ) -> Optional[OrderResult]:
        """
        미국 주식 주문 실행

        Args:
            ticker: 종목코드
            order_type: 주문 유형 ("buy" 또는 "sell")
            quantity: 주문 수량
            price: 주문 가격 (시장가 주문 시 0)
            order_kind: 주문 종류 ("limit": 지정가, "market": 시장가)

        Returns:
            OrderResult: 주문 결과 또는 None
        """
        try:
            self._apply_rate_limit()

            url = f"{self.BASE_URL}/uapi/overseas-stock/v1/trading/order"

            # 주문 구분 코드
            ord_dvsn_map = {
                "buy": {
                    "limit": "00",   # 지정가 매수
                    "market": "01"   # 시장가 매수
                },
                "sell": {
                    "limit": "00",   # 지정가 매도
                    "market": "01"   # 시장가 매도
                }
            }

            ord_dvsn = ord_dvsn_map.get(order_type, {}).get(order_kind, "00")

            # 계좌번호 파싱 (CANO, ACNT_PRDT_CD 분리)
            cano, acnt_prdt_cd = self._parse_account_no(self.account_no)

            # [FIX] 거래소 코드 자동 감지 (SOXL → AMEX)
            exchange_code = os.getenv("US_MARKET_EXCHANGE", config.US_MARKET_EXCHANGE)
            if ticker == "SOXL":
                exchange_code = "AMEX"
            elif exchange_code not in ["AMEX", "NASD", "NYSE"]:
                exchange_code = "NASD"  # 기본값

            payload = {
                "CANO": cano,                       # 계좌번호 (8자리)
                "ACNT_PRDT_CD": acnt_prdt_cd,       # 계좌상품코드 (2자리)
                "OVRS_EXCG_CD": exchange_code,      # [FIX] 거래소코드 (자동 감지)
                "PDNO": ticker,                      # 종목코드
                "ORD_QTY": str(quantity),            # 주문수량
                "OVRS_ORD_UNPR": str(price) if order_kind == "limit" else "0",  # 주문단가
                "ORD_SVR_DVSN_CD": "0",             # 주문서버구분코드
                "ORD_DVSN": ord_dvsn                # 주문구분
            }

            # Hashkey 생성
            hashkey = self._get_hashkey(payload)

            # TR_ID 선택 (매수/매도 구분)
            tr_id = self.TR_ID_OVERSEAS_BUY if order_type == "buy" else self.TR_ID_OVERSEAS_SELL

            # 헤더 생성
            headers = self._get_headers(
                tr_id=tr_id,
                custtype="P",
                hashkey=hashkey
            )

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("rt_cd") == "0":  # 성공
                    output = data.get("output", {})
                    order_no = output.get("ODNO", "")

                    # 체결 정보 추출 (KIS REST API 응답 필드)
                    filled_price = float(output.get("AVG_PRVS", price or 0))  # 평균 체결가 (없으면 주문가 사용)
                    filled_qty = int(output.get("TOT_CCLD_QTY", quantity))     # 총 체결 수량 (없으면 주문 수량 사용)

                    logger.info(
                        f"주문 성공: {order_type} {ticker} - "
                        f"주문 {quantity}주 @ ${price}, "
                        f"체결 {filled_qty}주 @ ${filled_price:.2f} "
                        f"(주문번호: {order_no})"
                    )

                    return OrderResult(
                        order_no=order_no,
                        status="success",
                        message=data.get("msg1", ""),
                        filled_price=filled_price,
                        filled_qty=filled_qty,
                        total_qty=quantity
                    )
                else:
                    error_msg = data.get("msg1", "Unknown error")
                    logger.error(f"주문 실패: {error_msg}")

                    return OrderResult(
                        order_no="",
                        status="failed",
                        message=error_msg,
                        filled_price=0.0,
                        filled_qty=0,
                        total_qty=quantity
                    )
            else:
                logger.error(f"주문 HTTP 오류: {response.status_code} - {response.text}")
                return None

        except AuthenticationError as e:
            logger.error(f"인증 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"주문 예외: {e}")
            return None

    def send_buy_order(self, ticker: str, quantity: int, price: float) -> Optional[OrderResult]:
        """매수 주문 (지정가)"""
        return self._send_order_internal(ticker, "buy", quantity, price, "limit")

    def send_sell_order(self, ticker: str, quantity: int, price: float) -> Optional[OrderResult]:
        """매도 주문 (지정가)"""
        return self._send_order_internal(ticker, "sell", quantity, price, "limit")

    # =====================================
    # 4. 계좌 조회
    # =====================================

    def get_balance(self, account_no: str = "") -> float:
        """
        계좌 잔고 조회

        Args:
            account_no: 계좌번호 (미지정 시 self.account_no 사용)

        Returns:
            float: 잔고 (USD)
        """
        try:
            self._apply_rate_limit()

            account = account_no or self.account_no
            # [P0 FIX] 계좌번호 파싱 사용
            cano, acnt_prdt_cd = self._parse_account_no(account)

            # 환경 변수에서 거래소 코드 가져오기
            exchange_code = os.getenv("US_MARKET_EXCHANGE", config.US_MARKET_EXCHANGE)
            logger.info(f"잔고 조회 거래소 코드: {exchange_code}")

            url = f"{self.BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"

            params = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "OVRS_EXCG_CD": exchange_code,     # 해외거래소코드 (환경 변수/설정에서 가져옴)
                "TR_CRCY_CD": "USD",        # 거래통화코드
                "CTX_AREA_FK200": "",       # 연속조회검색조건200 (최초 조회시 공란)
                "CTX_AREA_NK200": ""        # 연속조회키200 (최초 조회시 공란)
            }

            headers = self._get_headers(tr_id=self.TR_ID_OVERSEAS_ACCOUNT)

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("rt_cd") == "0":
                    output1 = data.get("output1", [])
                    output2 = data.get("output2")  # list 또는 dict 가능

                    # 디버그: API 응답 구조 확인
                    logger.info(f"KIS API 잔고조회 성공: output1 {len(output1)}건, output2 타입={type(output2)}")
                    logger.info(f"[DEBUG] output2 내용: {output2}")

                    # output2에서 예수금 조회 (list 또는 dict 처리)
                    cash = 0.0

                    if output2:
                        # output2가 dict인 경우 (잔고 없을 때)
                        if isinstance(output2, dict):
                            cash = float(output2.get("frcr_drwg_psbl_amt_1", 0) or 0)
                            logger.info(f"USD 예수금 (dict): ${cash:.2f}")

                        # output2가 list인 경우 (잔고 있을 때)
                        elif isinstance(output2, list) and len(output2) > 0:
                            if isinstance(output2[0], dict):
                                cash = float(output2[0].get("frcr_drwg_psbl_amt_1", 0) or 0)
                                logger.info(f"USD 예수금 (list): ${cash:.2f}")

                    # output1에서 보유 종목 확인
                    if len(output1) > 0:
                        for item in output1:
                            if item.get("ovrs_pdno"):  # 종목코드가 있으면 실제 보유
                                ticker = item.get("ovrs_pdno", "")
                                qty = item.get("ovrs_cblc_qty", "0")
                                logger.info(f"  보유종목: {ticker} {qty}주")
                    else:
                        logger.info("  보유종목: 없음")

                    return cash  # 예수금 반환
                else:
                    error_msg = data.get('msg1', 'Unknown error')
                    logger.error(f"잔고 조회 실패: rt_cd={data.get('rt_cd')}, msg1={error_msg}")
                    logger.error(f"전체 응답: {data}")
                    return 0.0
            else:
                logger.error(f"잔고 조회 HTTP 오류: {response.status_code}, 응답: {response.text}")
                return 0.0

        except AuthenticationError as e:
            logger.error(f"인증 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"잔고 조회 예외: {e}")
            return 0.0

    def get_cash_balance(self, ticker: str = "SOXL", price: float = 1.0, account_no: str = "") -> float:
        """
        USD 예수금 조회 (매수가능금액조회 API 사용)

        Args:
            ticker: 조회할 종목코드 (기본값: SOXL)
            price: 조회할 주문단가 (기본값: 1.0, 현재가 사용 권장)
            account_no: 계좌번호 (옵션, 미제공 시 기본 계좌 사용)

        Returns:
            float: USD 예수금 (주문가능외화금액)
        """
        try:
            account = account_no or self.account_no
            cano, acnt_prdt_cd = self._parse_account_no(account)

            # 환경 변수에서 거래소 코드 가져오기 (기본값: config.US_MARKET_EXCHANGE)
            exchange_code = os.getenv("US_MARKET_EXCHANGE", config.US_MARKET_EXCHANGE)
            
            # ticker 기반으로 거래소 자동 감지 (SOXL → AMEX)
            if ticker == "SOXL":
                exchange_code = "AMEX"
            elif exchange_code not in ["AMEX", "NASD", "NYSE"]:
                exchange_code = "NASD"  # 기본값: 나스닥
            
            logger.info(f"예수금 조회 거래소 코드: {exchange_code} (종목: {ticker})")

            url = f"{self.BASE_URL}/uapi/overseas-stock/v1/trading/inquire-psamount"

            params = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "OVRS_EXCG_CD": exchange_code,    # 거래소 코드 (환경 변수/설정에서 가져옴)
                "OVRS_ORD_UNPR": f"{price:.2f}",  # 주문단가 (소수점 2자리면 충분)
                "ITEM_CD": ticker                 # 종목코드
            }

            headers = self._get_headers(tr_id=self.TR_ID_OVERSEAS_BUYABLE)

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                logger.info(f"[DEBUG] 매수가능금액조회 응답 rt_cd: {data.get('rt_cd')}")
                logger.info(f"[DEBUG] 매수가능금액조회 응답 msg1: {data.get('msg1')}")

                if data.get("rt_cd") == "0":
                    output = data.get("output", {})

                    logger.info(f"[DEBUG] output 타입: {type(output)}")
                    logger.info(f"[DEBUG] output 내용: {output}")

                    # ord_psbl_frcr_amt: 주문가능외화금액 (USD 예수금)
                    cash_balance = float(output.get("ord_psbl_frcr_amt", 0))

                    logger.info(f"USD 예수금 조회 성공: ${cash_balance:.2f} (거래소: {exchange_code})")
                    return cash_balance
                elif data.get("rt_cd") == "7":
                    # rt_cd=7: "상품이 없습니다" → 거래 이력 없음 or 잔고 0
                    msg = data.get('msg1', '').strip()
                    logger.info(f"예수금 조회: {msg} → USD 잔고 $0.00으로 처리")
                    return 0.0
                else:
                    error_msg = data.get('msg1', 'Unknown error')
                    logger.error(f"예수금 조회 실패: rt_cd={data.get('rt_cd')}, msg1={error_msg}")
                    # 상세 디버그 정보 출력
                    logger.debug(f"요청 파라미터: {params}")
                    logger.debug(f"응답 전체: {data}")
                    return 0.0
            else:
                logger.error(f"예수금 조회 HTTP 오류: {response.status_code}, 응답: {response.text}")
                return 0.0

        except AuthenticationError as e:
            logger.error(f"인증 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"예수금 조회 예외: {e}")
            return 0.0

    def get_account_list(self) -> List[str]:
        """
        계좌 목록 조회

        Returns:
            list: 계좌번호 리스트
        """
        # REST API는 계좌 목록 조회 엔드포인트가 없을 수 있음
        # 계좌번호는 사전에 알고 있어야 함
        if self.account_no:
            return [self.account_no]
        else:
            logger.warning("계좌번호가 설정되지 않음")
            return []

    # =====================================
    # 5. 실시간 시세 (WebSocket)
    # =====================================

    async def subscribe_realtime_price(
        self,
        ticker: str,
        callback: Callable[[Dict], None]
    ):
        """
        실시간 시세 구독 (WebSocket)

        Args:
            ticker: 종목코드
            callback: 시세 수신 시 호출할 콜백 함수
        """
        if not self.approval_key:
            logger.error("Approval Key가 없습니다. WebSocket을 사용할 수 없습니다.")
            return

        self.price_callback = callback
        self.ws_running = True
        self.ws_reconnect_count = 0

        while self.ws_running and self.ws_reconnect_count < self.ws_max_reconnect:
            try:
                async with websockets.connect(self.WS_URL) as ws:
                    self.ws_connection = ws
                    logger.info(f"WebSocket 연결 성공: {self.WS_URL}")

                    # 인증 및 구독 메시지
                    subscribe_msg = {
                        "header": {
                            "approval_key": self.approval_key,
                            "custtype": "P",  # 개인
                            "tr_type": "1",   # 등록
                            "content-type": "utf-8"
                        },
                        "body": {
                            "input": {
                                "tr_id": self.TR_ID_WS_REALTIME,
                                "tr_key": ticker
                            }
                        }
                    }

                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"WebSocket 구독 시작: {ticker}")

                    # 준비 완료 이벤트 설정
                    self.ws_ready_event.set()

                    # [v4.1] 안정적인 연결 확인을 위한 플래그
                    stable_connection_confirmed = False

                    # 실시간 데이터 수신
                    while self.ws_running:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60)
                            data = json.loads(message)

                            # [v4.1] 첫 메시지 수신 = 안정적 연결 확인
                            if not stable_connection_confirmed:
                                self.ws_reconnect_count = 0
                                stable_connection_confirmed = True
                                logger.info("WebSocket 안정적 연결 확인 - 재연결 카운터 리셋")

                            # 시세 데이터 파싱
                            if "body" in data and "output" in data["body"]:
                                output = data["body"]["output"]

                                price_data = {
                                    "ticker": ticker,
                                    "price": float(output.get("last", 0)),
                                    "timestamp": datetime.now().isoformat()
                                }

                                # 콜백 호출
                                if self.price_callback:
                                    self.price_callback(price_data)

                        except asyncio.TimeoutError:
                            # 핑 전송 (연결 유지)
                            await ws.send(json.dumps({"header": {"tr_type": "3"}}))
                            logger.debug("WebSocket ping 전송")

                        except Exception as e:
                            logger.error(f"WebSocket 수신 오류: {e}")
                            break

                    # 구독 해제 메시지 전송 (정상 종료 시에만)
                    if self.ws_connection and not self.ws_running:
                        try:
                            unsubscribe_msg = {
                                "header": {
                                    "approval_key": self.approval_key,
                                    "custtype": "P",
                                    "tr_type": "2",  # 해제
                                    "content-type": "utf-8"
                                },
                                "body": {
                                    "input": {
                                        "tr_id": self.TR_ID_WS_REALTIME,
                                        "tr_key": ticker
                                    }
                                }
                            }
                            await ws.send(json.dumps(unsubscribe_msg))
                            logger.info("WebSocket 구독 해제 메시지 전송")
                        except Exception as e:
                            logger.warning(f"구독 해제 메시지 전송 실패: {e}")

                    # unsubscribe 요청이면 루프 탈출
                    if not self.ws_running:
                        logger.info("WebSocket 정상 종료 (사용자 요청)")
                        break

            except Exception as e:
                logger.error(f"WebSocket 연결 오류: {e}")

                # unsubscribe 요청이면 재연결 안 함
                if not self.ws_running:
                    logger.info("WebSocket 종료 요청 확인 - 재연결 안 함")
                    break

                self.ws_reconnect_count += 1

                if self.ws_reconnect_count < self.ws_max_reconnect and self.ws_running:
                    backoff_time = min(2 ** self.ws_reconnect_count, 30)
                    logger.info(f"WebSocket 재연결 시도 {self.ws_reconnect_count}/{self.ws_max_reconnect} ({backoff_time}초 후)")
                    await asyncio.sleep(backoff_time)
                else:
                    error_msg = f"WebSocket 최대 재연결 횟수({self.ws_max_reconnect}) 초과"
                    logger.error(error_msg)

                    # [v4.1] 치명적 오류 콜백 호출
                    if self.error_callback and self.ws_running:
                        try:
                            self.error_callback("실시간 시세 연결 종료", error_msg + " - 실거래 중단됨")
                        except Exception as callback_error:
                            logger.error(f"오류 콜백 실행 실패: {callback_error}")
                    break

        self.ws_running = False
        self.ws_connection = None
        self.ws_ready_event.clear()
        logger.info("WebSocket 연결 종료")

    def unsubscribe_realtime_price(self):
        """실시간 시세 구독 해제"""
        self.ws_running = False
        logger.info("WebSocket 구독 해제 요청")

    # =====================================
    # 6. 유틸리티
    # =====================================

    def is_connected(self) -> bool:
        """연결 상태 확인"""
        if not self.access_token or not self.token_expires_at:
            return False
        return datetime.now() < self.token_expires_at

    def disconnect(self):
        """연결 해제"""
        self.unsubscribe_realtime_price()
        self.access_token = None
        self.token_expires_at = None
        self.approval_key = None
        logger.info("REST API 연결 해제")

    # =====================================
    # 7. 호환성 메서드 (기존 OpenAPI 인터페이스와 동일)
    # =====================================

    def get_us_stock_price(self, ticker: str) -> float:
        """
        미국 주식 현재가 조회 (호환성 메서드)

        Args:
            ticker: 종목코드

        Returns:
            float: 현재가 (USD) 또는 0.0 (실패 시)
        """
        data = self.get_overseas_price(ticker)
        return data["price"] if data else 0.0

    def subscribe_real_price(self, ticker: str, callback: Callable[[float], None]):
        """
        실시간 시세 구독 (호환성 메서드, 동기 인터페이스)

        Args:
            ticker: 종목코드
            callback: 가격 수신 시 호출할 콜백 함수 (인자: price)
        """
        # 콜백 래퍼 (Dict -> float 변환)
        def wrapped_callback(data: Dict):
            callback(data["price"])

        # 비동기 구독을 백그라운드 스레드에서 실행
        def run_async_subscription():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.subscribe_realtime_price(ticker, wrapped_callback))
            except Exception as e:
                logger.error(f"실시간 시세 구독 에러: {e}")
            finally:
                loop.close()

        thread = threading.Thread(target=run_async_subscription, daemon=True)
        thread.start()
        logger.info(f"실시간 시세 구독 시작 (백그라운드): {ticker}")

        # WebSocket 준비 완료 대기 (최대 5초)
        if not self.ws_ready_event.wait(timeout=5.0):
            logger.warning("WebSocket 준비 시간 초과")

    def get_account_balance(self) -> float:
        """
        계좌 잔고 조회 (호환성 메서드)

        Returns:
            float: 잔고 (USD)
        """
        return self.get_balance()

    def send_order(
        self,
        side: str = None,      # phoenix_main.py에서 side="BUY" 형태로 호출
        order_type: str = None,  # 호환성 유지 (side 우선)
        ticker: str = "",
        quantity: int = 0,
        price: float = 0
    ) -> dict:
        """
        주문 실행 (통합 메서드)

        Args:
            side: "BUY" 또는 "SELL" (권장)
            order_type: "BUY" 또는 "SELL" (호환성, side 우선)
            ticker: 종목코드
            quantity: 수량
            price: 가격 (0이면 시장가)

        Returns:
            dict: {
                "status": "SUCCESS" | "FAILED",
                "order_id": "주문번호",
                "filled_price": 체결가 (float),
                "filled_qty": 체결 수량 (int),
                "message": "상세 메시지"
            }
        """
        # side 우선, 없으면 order_type 사용
        order_direction = (side or order_type or "").upper()

        if order_direction not in ["BUY", "SELL"]:
            return {
                "status": "FAILED",
                "order_id": "",
                "filled_price": 0.0,
                "filled_qty": 0,
                "message": f"Invalid order direction: {order_direction}. Must be 'BUY' or 'SELL'"
            }

        order_kind = "market" if price == 0 else "limit"
        result = self._send_order_internal(ticker, order_direction.lower(), quantity, price, order_kind)

        # OrderResult를 dict로 변환
        if result:
            return {
                "status": "SUCCESS" if result.status == "success" else "FAILED",
                "order_id": result.order_no,
                "filled_price": result.filled_price,
                "filled_qty": result.filled_qty,
                "message": result.message
            }
        else:
            return {
                "status": "FAILED",
                "order_id": "",
                "filled_price": 0.0,
                "filled_qty": 0,
                "message": "Order failed (internal error)"
            }

    def get_order_fill_status(self, order_no: str, order_date: str = None) -> dict:
        """
        주문 체결 상태 조회 (v1_해외주식-007)

        Args:
            order_no: 주문번호 (ODNO)
            order_date: 주문일자 YYYYMMDD (None이면 오늘)

        Returns:
            dict: {
                "status": "완료" | "접수" | "거부",
                "filled_qty": 체결 수량 (int),
                "filled_price": 체결 단가 (float),
                "unfilled_qty": 미체결 수량 (int),
                "reject_reason": 거부 사유 (str)
            }
        """
        if not order_date:
            from datetime import datetime
            order_date = datetime.now().strftime("%Y%m%d")

        # 모의투자 여부 확인 (app_key 길이로 판단, 실전=36자, 모의=다를 수 있음)
        is_mock = len(self.app_key) != 36
        base_url = "https://openapivts.koreainvestment.com:29443" if is_mock else self.BASE_URL

        url = f"{base_url}/uapi/overseas-stock/v1/trading/inquire-ccnl"

        # 계좌번호 파싱
        cano, acnt_prdt_cd = self._parse_account_no(self.account_no)

        # [FIX] 거래소 코드 설정
        exchange_code = os.getenv("US_MARKET_EXCHANGE", config.US_MARKET_EXCHANGE)

        # 요청 파라미터
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": "%",  # 전체 종목
            "ORD_STRT_DT": order_date,
            "ORD_END_DT": order_date,
            "SLL_BUY_DVSN": "00",  # 전체 (매도/매수)
            "CCLD_NCCS_DVSN": "00",  # 전체 (체결/미체결)
            "OVRS_EXCG_CD": exchange_code,  # [FIX] 거래소 코드 (config에서 가져옴)
            "SORT_SQN": "DS",  # 내림차순
            "ORD_DT": "",
            "ORD_GNO_BRNO": "",
            "ODNO": order_no,  # [FIX] 주문번호 직접 전달
            "CTX_AREA_NK200": "",
            "CTX_AREA_FK200": ""
        }

        headers = self._get_headers(
            tr_id="TTTS3035R" if not is_mock else "VTTS3035R",
            custtype="P"
        )

        try:
            # [FIX] Rate limit 보호
            self._apply_rate_limit()

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("rt_cd") == "0":
                output_list = data.get("output", [])

                # 주문번호로 필터링
                for item in output_list:
                    if item.get("odno") == order_no:
                        status = item.get("prcs_stat_name", "")
                        filled_qty = int(item.get("ft_ccld_qty", "0"))
                        filled_price = float(item.get("ft_ccld_unpr3", "0"))
                        unfilled_qty = int(item.get("nccs_qty", "0"))
                        reject_reason = item.get("rjct_rson_name", "")

                        return {
                            "status": status,
                            "filled_qty": filled_qty,
                            "filled_price": filled_price,
                            "unfilled_qty": unfilled_qty,
                            "reject_reason": reject_reason
                        }

                # 주문번호 못 찾음
                logger.warning(f"주문번호 {order_no}를 찾을 수 없음 (조회된 주문 {len(output_list)}건)")
                return {
                    "status": "접수",
                    "filled_qty": 0,
                    "filled_price": 0.0,
                    "unfilled_qty": 0,
                    "reject_reason": "주문번호를 찾을 수 없음"
                }
            else:
                error_msg = data.get("msg1", "Unknown error")
                logger.error(f"체결 조회 실패: {error_msg}")
                return {
                    "status": "오류",
                    "filled_qty": 0,
                    "filled_price": 0.0,
                    "unfilled_qty": 0,
                    "reject_reason": error_msg
                }

        except Exception as e:
            logger.error(f"체결 조회 예외: {e}", exc_info=True)
            return {
                "status": "오류",
                "filled_qty": 0,
                "filled_price": 0.0,
                "unfilled_qty": 0,
                "reject_reason": str(e)
            }

    @property
    def account_list(self) -> List[str]:
        """
        계좌 목록 조회 (호환성 속성)

        Returns:
            list: 계좌번호 리스트
        """
        return self.get_account_list()

    def set_account(self, account_no: str):
        """
        계좌 설정 (호환성 메서드)

        Args:
            account_no: 계좌번호
        """
        self.account_no = account_no
        logger.info(f"계좌 설정: {account_no}")

    def run(self):
        """
        메인 이벤트 루프 실행 (호환성 메서드)

        REST API는 WebSocket이 백그라운드 스레드에서 실행되므로
        메인 스레드는 ws_running이 True인 동안 대기
        """
        logger.info("REST API 메인 루프 시작 (대기 모드)")

        # WebSocket 준비 대기
        if not self.ws_ready_event.wait(timeout=10.0):
            logger.error("WebSocket 준비 실패 - 시간 초과")
            return

        logger.info("WebSocket 준비 완료 - 메인 루프 실행")

        try:
            while self.ws_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("사용자 인터럽트")
        finally:
            self.disconnect()

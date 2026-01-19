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
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    """주문 결과"""
    order_no: str
    status: str  # "success", "failed"
    message: str = ""


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
    TR_ID_OVERSEAS_ORDER = "JTTT1002U"          # 해외주식 주문
    TR_ID_OVERSEAS_BALANCE = "CTRP6548R"        # 해외주식 잔고
    TR_ID_OVERSEAS_ACCOUNT = "CTRP6504R"        # 해외주식 계좌잔고
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

    # =====================================
    # 1. 인증 (OAuth2 + Approval Key)
    # =====================================

    def login(self) -> bool:
        """
        OAuth2 토큰 + Approval key 발급

        Returns:
            bool: 로그인 성공 여부

        Raises:
            AuthenticationError: 인증 실패 시
        """
        try:
            # 1. Access Token 발급
            url = f"{self.BASE_URL}/oauth2/token"

            payload = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret
            }

            response = requests.post(url, json=payload, timeout=10)

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
        미국 주식 현재가 조회

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
        try:
            self._apply_rate_limit()

            url = f"{self.BASE_URL}/uapi/overseas-price/v1/quotations/price"

            params = {
                "EXCD": "NAS",  # 나스닥
                "SYMB": ticker   # 종목코드
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

                    return {
                        "ticker": ticker,
                        "price": float(output.get("last", 0)),
                        "open": float(output.get("open", 0)),
                        "high": float(output.get("high", 0)),
                        "low": float(output.get("low", 0)),
                        "volume": int(output.get("tvol", 0))
                    }
                else:
                    logger.error(f"시세 조회 실패: {data.get('msg1')}")
                    return None
            else:
                logger.error(f"시세 조회 HTTP 오류: {response.status_code} - {response.text}")
                return None

        except AuthenticationError as e:
            logger.error(f"인증 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"시세 조회 예외: {e}")
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

            payload = {
                "CANO": self.account_no,           # 계좌번호
                "ACNT_PRDT_CD": "01",              # 계좌상품코드
                "OVRS_EXCG_CD": "NASD",            # 거래소코드 (나스닥)
                "PDNO": ticker,                     # 종목코드
                "ORD_QTY": str(quantity),           # 주문수량
                "OVRS_ORD_UNPR": str(price) if order_kind == "limit" else "0",  # 주문단가
                "ORD_SVR_DVSN_CD": "0",            # 주문서버구분코드
                "ORD_DVSN": ord_dvsn               # 주문구분
            }

            # Hashkey 생성
            hashkey = self._get_hashkey(payload)

            # 헤더 생성
            headers = self._get_headers(
                tr_id=self.TR_ID_OVERSEAS_ORDER,
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

                    logger.info(f"주문 성공: {order_type} {ticker} {quantity}주 @ ${price} (주문번호: {order_no})")

                    return OrderResult(
                        order_no=order_no,
                        status="success",
                        message=data.get("msg1", "")
                    )
                else:
                    error_msg = data.get("msg1", "Unknown error")
                    logger.error(f"주문 실패: {error_msg}")

                    return OrderResult(
                        order_no="",
                        status="failed",
                        message=error_msg
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
            url = f"{self.BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"

            params = {
                "CANO": account,
                "ACNT_PRDT_CD": "01",
                "OVRS_EXCG_CD": "NASD",
                "TR_CRCY_CD": "USD"
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
                    output = data.get("output2", {})
                    balance = float(output.get("frcr_dncl_amt_2", 0))  # 외화예수금

                    logger.debug(f"계좌 잔고: ${balance:.2f}")
                    return balance
                else:
                    logger.error(f"잔고 조회 실패: {data.get('msg1')}")
                    return 0.0
            else:
                logger.error(f"잔고 조회 HTTP 오류: {response.status_code}")
                return 0.0

        except AuthenticationError as e:
            logger.error(f"인증 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"잔고 조회 예외: {e}")
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
        order_type: str,
        ticker: str,
        quantity: int,
        price: float
    ) -> bool:
        """
        주문 실행 (호환성 메서드)

        Args:
            order_type: "BUY" 또는 "SELL"
            ticker: 종목코드
            quantity: 수량
            price: 가격 (0이면 시장가)

        Returns:
            bool: 성공 여부
        """
        order_kind = "market" if price == 0 else "limit"
        result = self._send_order_internal(ticker, order_type.lower(), quantity, price, order_kind)

        if result:
            return result.status == "success"
        return False

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

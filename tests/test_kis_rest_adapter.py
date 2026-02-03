"""
Phoenix Trading System - KisRestAdapter 테스트

한국투자증권(KIS) REST API 어댑터 단위 테스트 (Mock 기반)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import jsonschema
from src.kis_rest_adapter import KisRestAdapter, OrderResult


# =============================================================================
# KIS API 응답 JSON Schema 정의 (실제 API 스펙 기반)
# =============================================================================

# 로그인 응답 스키마
LOGIN_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["access_token", "expires_in"],
    "properties": {
        "access_token": {"type": "string", "minLength": 1},
        "expires_in": {"type": "integer", "minimum": 0},
        "token_type": {"type": "string"}
    }
}

# Approval Key 응답 스키마
APPROVAL_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["approval_key"],
    "properties": {
        "approval_key": {"type": "string", "minLength": 1}
    }
}

# 주문 응답 스키마
ORDER_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["rt_cd", "msg1"],
    "properties": {
        "rt_cd": {"type": "string", "enum": ["0", "1"]},  # 0=성공, 1=실패
        "msg_cd": {"type": "string"},
        "msg1": {"type": "string"},
        "output": {
            "type": "object",
            "required": ["ODNO"],  # 주문번호 필수
            "properties": {
                "ODNO": {"type": "string"},
                "ORD_TMD": {"type": "string"}  # 주문 시각
            }
        }
    }
}

# Hashkey 응답 스키마
HASHKEY_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["HASH"],
    "properties": {
        "HASH": {"type": "string", "minLength": 1}
    }
}

# 시세 응답 스키마
PRICE_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["rt_cd"],
    "properties": {
        "rt_cd": {"type": "string", "enum": ["0", "1"]},
        "msg_cd": {"type": "string"},
        "msg1": {"type": "string"},
        "output": {
            "type": "object",
            "properties": {
                "last": {"type": "string"},  # 현재가
                "open": {"type": "string"},
                "high": {"type": "string"},
                "low": {"type": "string"},
                "volume": {"type": "string"}
            }
        }
    }
}


class TestKisRestAdapter:
    """KisRestAdapter 클래스 테스트"""

    @pytest.fixture
    def adapter(self):
        """테스트용 어댑터 생성"""
        return KisRestAdapter(
            app_key="test_app_key",
            app_secret="test_app_secret",
            account_no="12345678-01"
        )

    # =====================
    # 1. 인증 테스트
    # =====================

    @patch('src.kis_rest_adapter.Path.exists')
    @patch('src.kis_rest_adapter.requests.post')
    def test_login_success(self, mock_post, mock_path_exists, adapter):
        """로그인 성공 테스트 - Token + Approval Key 발급"""
        # 토큰 캐시 파일 없음
        mock_path_exists.return_value = False

        # Mock 응답 설정: login()은 2번의 POST 호출
        # 1) /oauth2/tokenP - 토큰 발급
        token_resp = Mock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "test_token_12345",
            "expires_in": 86400
        }

        # 2) /oauth2/Approval - 승인키 발급 (WebSocket용)
        approval_resp = Mock()
        approval_resp.status_code = 200
        approval_resp.json.return_value = {
            "approval_key": "test_approval_abc123"
        }

        mock_post.side_effect = [token_resp, approval_resp]

        # 로그인 실행 (토큰 캐시 저장 mock)
        with patch('builtins.open', MagicMock()):
            result = adapter.login()

        # 검증
        assert result is True
        assert adapter.access_token == "test_token_12345"
        assert adapter.token_expires_at is not None
        assert isinstance(adapter.token_expires_at, datetime)

        # 🔥 Approval Key 검증 (WebSocket 필수)
        assert adapter.approval_key == "test_approval_abc123"

        # Request Body 검증
        assert mock_post.call_count == 2
        # 1번째 호출: grant_type="client_credentials"
        assert mock_post.call_args_list[0][1]["json"]["grant_type"] == "client_credentials"
        # 2번째 호출: secretkey 포함
        assert "secretkey" in mock_post.call_args_list[1][1]["json"]

    @patch('src.kis_rest_adapter.Path.exists')
    @patch('src.kis_rest_adapter.requests.post')
    def test_login_failure(self, mock_post, mock_path_exists, adapter):
        """로그인 실패 테스트"""
        # 토큰 캐시 파일 없음
        mock_path_exists.return_value = False

        # Mock 응답 설정 (401 Unauthorized)
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Invalid credentials"
        mock_post.return_value = mock_response

        # 로그인 실행 - AuthenticationError 예외 발생 예상
        from src.kis_rest_adapter import AuthenticationError
        with pytest.raises(AuthenticationError):
            adapter.login()

    # =====================
    # 2. 시세 조회 테스트
    # =====================

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_overseas_price_success(self, mock_get, adapter):
        """시세 조회 성공 테스트"""
        # 토큰 설정 (인증 통과)
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": {
                "last": "45.30",
                "open": "44.80",
                "high": "45.50",
                "low": "44.50",
                "tvol": "1234567"
            }
        }
        mock_get.return_value = mock_response

        # 시세 조회 실행
        result = adapter.get_overseas_price("SOXL")

        # 검증
        assert result is not None
        assert result["ticker"] == "SOXL"
        assert result["price"] == 45.30
        assert result["open"] == 44.80
        assert result["high"] == 45.50
        assert result["low"] == 44.50
        assert result["volume"] == 1234567

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_overseas_price_failure(self, mock_get, adapter):
        """시세 조회 실패 테스트 - HTTP 에러"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정 (에러)
        mock_response = Mock()
        mock_response.status_code = 400
        mock_get.return_value = mock_response

        # 시세 조회 실행
        result = adapter.get_overseas_price("INVALID")

        # 검증
        assert result is None

    @patch('src.kis_rest_adapter.requests.get')
    def test_price_query_business_error(self, mock_get, adapter):
        """🔥 실제 KIS API 에러 형식 - HTTP 200 + rt_cd='1'"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답: 실제 KIS API는 HTTP 200을 반환하지만 rt_cd="1"로 실패 표현
        mock_response = Mock()
        mock_response.status_code = 200  # ✅ HTTP는 성공
        mock_response.json.return_value = {
            "rt_cd": "1",  # ❌ 비즈니스 로직 실패
            "msg_cd": "EGW00123",  # 에러 코드
            "msg1": "조회 불가 종목입니다"  # 에러 메시지
        }
        mock_get.return_value = mock_response

        # 시세 조회 실행
        result = adapter.get_overseas_price("INVALID_SYMBOL")

        # 검증: rt_cd="1"일 때 None 반환
        assert result is None

    # =====================
    # 3. 주문 실행 테스트
    # =====================

    @patch('src.kis_rest_adapter.requests.post')
    def test_send_buy_order_success(self, mock_post, adapter):
        """매수 주문 성공 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": {
                "ODNO": "ORDER123456"
            },
            "msg1": "주문 접수 완료"
        }
        mock_post.return_value = mock_response

        # 매수 주문 실행
        result = adapter.send_buy_order("SOXL", 10, 45.0)

        # 검증
        assert result is not None
        assert result.order_no == "ORDER123456"
        assert result.status == "success"

    @patch('src.kis_rest_adapter.requests.post')
    def test_send_sell_order_success(self, mock_post, adapter):
        """매도 주문 성공 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": {
                "ODNO": "ORDER789012"
            },
            "msg1": "주문 접수 완료"
        }
        mock_post.return_value = mock_response

        # 매도 주문 실행
        result = adapter.send_sell_order("SOXL", 5, 48.0)

        # 검증
        assert result is not None
        assert result.order_no == "ORDER789012"
        assert result.status == "success"

    @patch('src.kis_rest_adapter.requests.post')
    def test_send_order_failure(self, mock_post, adapter):
        """주문 실패 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정 (주문 거부)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "1",
            "msg1": "잔고 부족"
        }
        mock_post.return_value = mock_response

        # 매수 주문 실행
        result = adapter.send_buy_order("SOXL", 1000, 45.0)

        # 검증
        assert result is not None
        assert result.status == "failed"
        assert "잔고 부족" in result.message

    @patch('src.kis_rest_adapter.requests.post')
    def test_order_requires_hashkey(self, mock_post, adapter):
        """🔥 Hashkey 강제 검증 - 실거래 필수 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정: send_buy_order()는 2번의 POST 호출
        # 1) POST /uapi/hashkey - 해시키 발급
        hashkey_resp = Mock()
        hashkey_resp.status_code = 200
        hashkey_resp.json.return_value = {
            "HASH": "deadbeef123456"  # 실제 API에서 받는 hashkey
        }

        # 2) POST /uapi/overseas-stock/v1/trading/order - 실제 주문
        order_resp = Mock()
        order_resp.status_code = 200
        order_resp.json.return_value = {
            "rt_cd": "0",
            "output": {"ODNO": "ORDER999999"},
            "msg1": "주문 전송 완료"
        }

        mock_post.side_effect = [hashkey_resp, order_resp]

        # 매수 주문 실행
        result = adapter.send_buy_order("SOXL", 10, 25.50)

        # 검증
        assert result is not None
        assert result.order_no == "ORDER999999"

        # 🔥 CRITICAL: hashkey가 헤더에 포함되었는지 검증
        assert mock_post.call_count == 2
        order_call = mock_post.call_args_list[1]  # 2번째 호출 (실제 주문)
        assert "headers" in order_call[1]
        assert "hashkey" in order_call[1]["headers"]
        assert order_call[1]["headers"]["hashkey"] == "deadbeef123456"

    @patch('src.kis_rest_adapter.requests.post')
    def test_order_business_error_with_msg_cd(self, mock_post, adapter):
        """🔥 주문 비즈니스 에러 - rt_cd='1' + msg_cd 검증"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정
        # 1) Hashkey 발급 성공
        hashkey_resp = Mock()
        hashkey_resp.status_code = 200
        hashkey_resp.json.return_value = {"HASH": "test_hash"}

        # 2) 주문 비즈니스 에러 (실제 KIS API 형식)
        order_resp = Mock()
        order_resp.status_code = 200  # ✅ HTTP는 성공
        order_resp.json.return_value = {
            "rt_cd": "1",  # ❌ 비즈니스 실패
            "msg_cd": "APBK0919",  # 실제 KIS 에러 코드
            "msg1": "주문가능수량을 초과하였습니다"
        }

        mock_post.side_effect = [hashkey_resp, order_resp]

        # 주문 실행
        result = adapter.send_buy_order("SOXL", 9999, 50.0)

        # 검증
        assert result is not None
        assert result.status == "failed"
        assert "주문가능수량" in result.message
        # msg_cd가 로그에 기록되는지는 로그 확인 필요 (현재 코드는 msg1만 사용)

    # =====================
    # 4. 계좌 조회 테스트
    # =====================

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_balance_success(self, mock_get, adapter):
        """계좌 잔고 조회 성공 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정 (실제 API 응답 형식: output2가 dict)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output1": [],
            "output2": {
                "frcr_drwg_psbl_amt_1": "5000.50"  # 실제 필드명
            }
        }
        mock_get.return_value = mock_response

        # 잔고 조회 실행
        balance = adapter.get_balance()

        # 검증
        assert balance == 5000.50

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_balance_failure(self, mock_get, adapter):
        """계좌 잔고 조회 실패 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정 (에러)
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        # 잔고 조회 실행
        balance = adapter.get_balance()

        # 검증
        assert balance == 0.0

    # =====================
    # 5. 호환성 메서드 테스트
    # =====================

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_us_stock_price_compatibility(self, mock_get, adapter):
        """get_us_stock_price 호환성 메서드 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": {
                "last": "50.25",
                "open": "50.00",
                "high": "51.00",
                "low": "49.50",
                "tvol": "2000000"
            }
        }
        mock_get.return_value = mock_response

        # 시세 조회 실행 (호환성 메서드)
        price = adapter.get_us_stock_price("SOXL")

        # 검증
        assert price == 50.25

    @patch('src.kis_rest_adapter.requests.get')
    def test_get_account_balance_compatibility(self, mock_get, adapter):
        """get_account_balance 호환성 메서드 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정 (실제 API 응답 형식)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output1": [],
            "output2": {
                "frcr_drwg_psbl_amt_1": "10000.00"  # 실제 필드명
            }
        }
        mock_get.return_value = mock_response

        # 잔고 조회 실행 (호환성 메서드)
        balance = adapter.get_account_balance()

        # 검증
        assert balance == 10000.00

    @patch('src.kis_rest_adapter.requests.post')
    def test_send_order_compatibility(self, mock_post, adapter):
        """send_order 호환성 메서드 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rt_cd": "0",
            "output": {
                "ODNO": "ORDER999999"
            },
            "msg1": "주문 접수 완료"
        }
        mock_post.return_value = mock_response

        # 주문 실행 (키워드 인자 사용)
        result = adapter.send_order(side="BUY", ticker="SOXL", quantity=20, price=45.5)

        # 검증 (dict 반환값)
        assert isinstance(result, dict)
        assert result["status"] == "SUCCESS"
        assert result["order_id"] == "ORDER999999"
        assert result["message"] == "주문 접수 완료"
        assert result["filled_qty"] == 20  # 주문 수량과 동일 (응답에 TOT_CCLD_QTY 없으면 quantity 사용)

    def test_account_list_property(self, adapter):
        """account_list 속성 테스트"""
        # 계좌번호가 설정된 경우
        result = adapter.account_list

        # 검증
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == "12345678-01"

    def test_set_account(self, adapter):
        """set_account 메서드 테스트"""
        # 계좌 설정
        adapter.set_account("99999999-01")

        # 검증
        assert adapter.account_no == "99999999-01"

    # =====================
    # 6. 토큰 갱신 테스트
    # =====================

    @patch('src.kis_rest_adapter.Path.exists')
    @patch('src.kis_rest_adapter.requests.post')
    def test_token_refresh(self, mock_post, mock_path_exists, adapter):
        """🔥 토큰 자동 갱신 테스트 - Token + Approval Key 모두 갱신"""
        # 토큰 캐시 파일 없음
        mock_path_exists.return_value = False

        # 만료 임박 토큰 설정 (4분 후 만료)
        adapter.access_token = "old_token"
        adapter.approval_key = "old_approval"
        adapter.token_expires_at = datetime.now() + timedelta(minutes=4)

        # Mock 응답 설정: login()은 2번의 POST 호출
        # 1) /oauth2/tokenP - 새 토큰 발급
        token_resp = Mock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "new_token_67890",
            "expires_in": 86400
        }

        # 2) /oauth2/Approval - 새 승인키 발급
        approval_resp = Mock()
        approval_resp.status_code = 200
        approval_resp.json.return_value = {
            "approval_key": "new_approval_xyz"
        }

        mock_post.side_effect = [token_resp, approval_resp]

        # _get_headers 호출 (내부에서 토큰 갱신 트리거)
        with patch('builtins.open', MagicMock()):  # 토큰 캐시 저장 mock
            headers = adapter._get_headers(tr_id="TEST_TR_ID")

        # 검증
        assert adapter.access_token == "new_token_67890"
        assert adapter.approval_key == "new_approval_xyz"  # 🔥 Approval Key도 갱신됨
        assert "Bearer new_token_67890" in headers["authorization"]

    @patch('src.kis_rest_adapter.Path.exists')
    @patch('src.kis_rest_adapter.requests.get')
    @patch('src.kis_rest_adapter.requests.post')
    def test_api_call_with_expired_token(self, mock_post, mock_get, mock_path_exists, adapter):
        """🔥 만료 토큰 자동 갱신 후 API 호출 성공 시나리오"""
        # 토큰 캐시 파일 없음
        mock_path_exists.return_value = False

        # 만료 임박 토큰 설정 (3분 후 만료 - 5분 임계값 이하)
        adapter.access_token = "expired_token"
        adapter.token_expires_at = datetime.now() + timedelta(minutes=3)

        # Mock 응답 설정
        # 1) Token 갱신
        token_resp = Mock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "refreshed_token", "expires_in": 86400}

        # 2) Approval Key 갱신
        approval_resp = Mock()
        approval_resp.status_code = 200
        approval_resp.json.return_value = {"approval_key": "refreshed_approval"}

        mock_post.side_effect = [token_resp, approval_resp]

        # 3) 실제 API 호출 (시세 조회)
        price_resp = Mock()
        price_resp.status_code = 200
        price_resp.json.return_value = {
            "rt_cd": "0",
            "output": {"last": "30.50"}
        }
        mock_get.return_value = price_resp

        # 시세 조회 실행 (내부에서 자동 토큰 갱신 발생)
        with patch('builtins.open', MagicMock()):  # 토큰 캐시 저장 mock
            result = adapter.get_overseas_price("SOXL")

        # 검증
        assert result is not None
        assert result["price"] == 30.50  # get_overseas_price는 dict 반환
        assert adapter.access_token == "refreshed_token"
        assert adapter.approval_key == "refreshed_approval"
        # 갱신 후 API 호출 성공
        assert mock_post.call_count == 2  # token + approval
        assert mock_get.call_count == 1  # price query

    # =====================
    # 7. 연결 상태 테스트
    # =====================

    def test_is_connected_true(self, adapter):
        """연결 상태 확인 (연결됨)"""
        # 유효한 토큰 설정
        adapter.access_token = "valid_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # 검증
        assert adapter.is_connected() is True

    def test_is_connected_false_no_token(self, adapter):
        """연결 상태 확인 (토큰 없음)"""
        # 토큰 없음
        adapter.access_token = None

        # 검증
        assert adapter.is_connected() is False

    def test_is_connected_false_expired(self, adapter):
        """연결 상태 확인 (토큰 만료)"""
        # 만료된 토큰
        adapter.access_token = "expired_token"
        adapter.token_expires_at = datetime.now() - timedelta(hours=1)

        # 검증
        assert adapter.is_connected() is False

    def test_disconnect(self, adapter):
        """연결 해제 테스트"""
        # 토큰 설정
        adapter.access_token = "test_token"
        adapter.token_expires_at = datetime.now() + timedelta(hours=1)

        # 연결 해제
        adapter.disconnect()

        # 검증
        assert adapter.access_token is None
        assert adapter.token_expires_at is None

    # =====================
    # 8. JSON Schema 검증 테스트 (실제 API 스펙 준수 확인)
    # =====================

    def test_login_response_schema_validation(self):
        """🔥 로그인 응답 스키마 검증"""
        # 실제 KIS API 응답 형식
        valid_response = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "expires_in": 86400,
            "token_type": "Bearer"
        }

        # Schema 검증 - 실패 시 ValidationError 발생
        jsonschema.validate(instance=valid_response, schema=LOGIN_RESPONSE_SCHEMA)

        # 잘못된 응답 (expires_in이 문자열)
        invalid_response = {
            "access_token": "token",
            "expires_in": "86400"  # ❌ 정수여야 함
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_response, schema=LOGIN_RESPONSE_SCHEMA)

    def test_approval_key_response_schema_validation(self):
        """🔥 Approval Key 응답 스키마 검증"""
        valid_response = {
            "approval_key": "12345678-abcd-efgh-ijkl-1234567890ab"
        }

        jsonschema.validate(instance=valid_response, schema=APPROVAL_RESPONSE_SCHEMA)

        # 잘못된 응답 (approval_key 누락)
        invalid_response = {}

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_response, schema=APPROVAL_RESPONSE_SCHEMA)

    def test_order_response_schema_validation(self):
        """🔥 주문 응답 스키마 검증 (Mock이 실제 스펙 준수)"""
        # 성공 응답
        valid_success = {
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "주문 전송 완료 되었습니다.",
            "output": {
                "ODNO": "0000004336",
                "ORD_TMD": "160524"
            }
        }

        jsonschema.validate(instance=valid_success, schema=ORDER_RESPONSE_SCHEMA)

        # 실패 응답
        valid_failure = {
            "rt_cd": "1",
            "msg_cd": "APBK0919",
            "msg1": "주문가능수량을 초과하였습니다"
        }

        jsonschema.validate(instance=valid_failure, schema=ORDER_RESPONSE_SCHEMA)

        # 잘못된 응답 (rt_cd가 숫자)
        invalid_response = {
            "rt_cd": 0,  # ❌ 문자열이어야 함
            "msg1": "message"
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_response, schema=ORDER_RESPONSE_SCHEMA)

    def test_hashkey_response_schema_validation(self):
        """🔥 Hashkey 응답 스키마 검증"""
        valid_response = {
            "HASH": "a1b2c3d4e5f6g7h8i9j0"
        }

        jsonschema.validate(instance=valid_response, schema=HASHKEY_RESPONSE_SCHEMA)

        # 잘못된 응답 (HASH 누락)
        invalid_response = {
            "hash": "lowercase_field"  # ❌ 대소문자 틀림
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_response, schema=HASHKEY_RESPONSE_SCHEMA)

    def test_price_response_schema_validation(self):
        """🔥 시세 응답 스키마 검증"""
        valid_response = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output": {
                "last": "30.50",
                "open": "29.80",
                "high": "31.20",
                "low": "29.50",
                "volume": "5432100"
            }
        }

        jsonschema.validate(instance=valid_response, schema=PRICE_RESPONSE_SCHEMA)

        # rt_cd="1" 에러 응답도 스키마 준수해야 함
        error_response = {
            "rt_cd": "1",
            "msg_cd": "EGW00123",
            "msg1": "조회 불가 종목입니다"
        }

        jsonschema.validate(instance=error_response, schema=PRICE_RESPONSE_SCHEMA)

    @patch('src.kis_rest_adapter.requests.post')
    def test_mock_responses_follow_schema(self, mock_post, adapter):
        """🔥 Mock 응답이 실제 스키마를 준수하는지 검증 (통합 테스트)"""
        # Token 응답 Mock
        token_resp = Mock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "test_token",
            "expires_in": 86400
        }

        # Approval 응답 Mock
        approval_resp = Mock()
        approval_resp.status_code = 200
        approval_resp.json.return_value = {
            "approval_key": "test_approval"
        }

        mock_post.side_effect = [token_resp, approval_resp]

        # 로그인 실행
        adapter.login()

        # Mock 응답들이 스키마를 준수하는지 검증
        jsonschema.validate(
            instance=token_resp.json.return_value,
            schema=LOGIN_RESPONSE_SCHEMA
        )

        jsonschema.validate(
            instance=approval_resp.json.return_value,
            schema=APPROVAL_RESPONSE_SCHEMA
        )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KIS API Validator MCP Server
실시간으로 KIS API 문서를 참조하여 파라미터 검증

사용법:
  claude mcp add --transport stdio kis-api \
    --env API_DOC_URL="https://apiportal.koreainvestment.com" \
    -- python .claude/mcp-servers/kis_api_validator.py
"""

import json
import sys
import logging
from typing import Dict, List, Optional

# MCP Server Protocol (간단한 구현)
# 실제로는 FastMCP나 MCP SDK를 사용하는 것을 권장

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# KIS API 스펙 (하드코딩 - 실제로는 웹에서 동적으로 가져와야 함)
KIS_API_SPECS = {
    "order_stock": {
        "method": "POST",
        "endpoint": "/uapi/overseas-stock/v1/trading/order",
        "tr_id": "JTTT1002U",  # 매수
        "required_params": {
            "CANO": {"type": "string", "description": "계좌번호 (8자리)", "pattern": r"^\d{8}$"},
            "ACNT_PRDT_CD": {"type": "string", "description": "계좌상품코드 (2자리)", "pattern": r"^\d{2}$"},
            "OVRS_EXCG_CD": {"type": "string", "description": "해외거래소코드", "enum": ["NASD", "NYSE", "AMEX"]},
            "PDNO": {"type": "string", "description": "종목코드 (티커)", "example": "SOXL"},
            "ORD_QTY": {"type": "string", "description": "주문수량", "pattern": r"^\d+$"},
            "OVRS_ORD_UNPR": {"type": "string", "description": "주문단가 (USD)", "pattern": r"^\d+(\.\d{1,2})?$"},
            "ORD_SVR_DVSN_CD": {"type": "string", "description": "주문서버구분코드", "enum": ["0"]},
            "ORD_DVSN": {"type": "string", "description": "주문구분", "enum": ["00", "32", "34"]},
        },
        "optional_params": {
            "CTAC_TLNO": {"type": "string", "description": "연락전화번호"},
        }
    },
    "get_balance": {
        "method": "GET",
        "endpoint": "/uapi/overseas-stock/v1/trading/inquire-balance",
        "tr_id": "CTRP6548R",
        "required_params": {
            "CANO": {"type": "string", "description": "계좌번호 (8자리)"},
            "ACNT_PRDT_CD": {"type": "string", "description": "계좌상품코드 (2자리)"},
            "OVRS_EXCG_CD": {"type": "string", "description": "해외거래소코드"},
            "TR_CRCY_CD": {"type": "string", "description": "거래통화코드", "enum": ["USD"]},
        }
    },
    "get_token": {
        "method": "POST",
        "endpoint": "/oauth2/tokenP",
        "required_params": {
            "grant_type": {"type": "string", "description": "인증타입", "enum": ["client_credentials"]},
            "appkey": {"type": "string", "description": "앱키"},
            "appsecret": {"type": "string", "description": "앱시크릿"},
        }
    }
}


class KISAPIValidator:
    """KIS API 파라미터 검증기"""

    def __init__(self):
        self.specs = KIS_API_SPECS

    def validate_params(self, api_name: str, params: Dict) -> Dict:
        """
        API 파라미터 검증

        Args:
            api_name: API 이름 (예: "order_stock")
            params: 검증할 파라미터 딕셔너리

        Returns:
            검증 결과 딕셔너리
        """
        if api_name not in self.specs:
            return {
                "valid": False,
                "errors": [f"Unknown API: {api_name}"],
                "warnings": []
            }

        spec = self.specs[api_name]
        errors = []
        warnings = []

        # 필수 파라미터 확인
        for param_name, param_spec in spec["required_params"].items():
            if param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
            else:
                # 타입 검증
                value = params[param_name]
                expected_type = param_spec["type"]

                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"{param_name}: Expected string, got {type(value).__name__}")

                # Enum 검증
                if "enum" in param_spec and value not in param_spec["enum"]:
                    errors.append(f"{param_name}: Invalid value '{value}'. Allowed: {param_spec['enum']}")

                # Pattern 검증 (정규표현식)
                if "pattern" in param_spec:
                    import re
                    if not re.match(param_spec["pattern"], str(value)):
                        errors.append(f"{param_name}: Invalid format. Pattern: {param_spec['pattern']}")

        # 불필요한 파라미터 경고
        optional_params = spec.get("optional_params", {})
        all_valid_params = set(spec["required_params"].keys()) | set(optional_params.keys())

        for param_name in params.keys():
            if param_name not in all_valid_params:
                warnings.append(f"Unknown parameter: {param_name} (will be ignored by API)")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "api_spec": {
                "method": spec["method"],
                "endpoint": spec["endpoint"],
                "tr_id": spec.get("tr_id", "N/A")
            }
        }

    def get_api_list(self) -> List[str]:
        """지원하는 API 목록 반환"""
        return list(self.specs.keys())

    def get_api_doc(self, api_name: str) -> Optional[Dict]:
        """API 문서 반환"""
        if api_name not in self.specs:
            return None

        spec = self.specs[api_name]
        return {
            "name": api_name,
            "method": spec["method"],
            "endpoint": spec["endpoint"],
            "tr_id": spec.get("tr_id"),
            "required_params": spec["required_params"],
            "optional_params": spec.get("optional_params", {})
        }


def main():
    """MCP Server 메인 루프"""
    validator = KISAPIValidator()

    logger.info("KIS API Validator MCP Server started")

    # MCP Protocol: stdin/stdout로 JSON-RPC 통신
    # 간단한 예제 구현 (실제로는 MCP SDK 사용 권장)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line)
            method = request.get("method")
            params = request.get("params", {})

            response = {"jsonrpc": "2.0", "id": request.get("id")}

            if method == "validate_params":
                api_name = params.get("api_name")
                api_params = params.get("params", {})
                result = validator.validate_params(api_name, api_params)
                response["result"] = result

            elif method == "get_api_list":
                response["result"] = validator.get_api_list()

            elif method == "get_api_doc":
                api_name = params.get("api_name")
                result = validator.get_api_doc(api_name)
                response["result"] = result

            else:
                response["error"] = {"code": -32601, "message": "Method not found"}

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

        except Exception as e:
            logger.error(f"Error: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)}
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == '__main__':
    main()

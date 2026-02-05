# KIS API Validator MCP Server

## 설치 방법

### 1. MCP 서버 추가
```bash
claude mcp add --transport stdio kis-api \
  --env API_DOC_URL="https://apiportal.koreainvestment.com" \
  -- python D:\Project\SOLX\.claude\mcp-servers\kis_api_validator.py
```

### 2. 연결 확인
```bash
claude mcp list
```

출력:
```
kis-api (stdio) - Running
```

## 사용 방법

### Claude Code에서 자동 검증

코드를 작성할 때 자동으로 KIS API 파라미터를 검증합니다:

```python
# 코드 작성 시
adapter.order_stock(
    account_no="12345678-01",
    symbol="SOXL",
    qty=10,
    price=35.50,
    order_type="LIMIT"  # ❌ 잘못된 파라미터!
)
```

Claude가 자동으로 감지:
```
⚠️ KIS API 검증 실패:
- order_type: Unknown parameter (API에서 지원하지 않음)
- 올바른 파라미터: ORD_DVSN (주문구분)
```

### 수동 검증

```bash
# API 목록 확인
echo '{"jsonrpc":"2.0","method":"get_api_list","id":1}' | python kis_api_validator.py

# API 문서 조회
echo '{"jsonrpc":"2.0","method":"get_api_doc","params":{"api_name":"order_stock"},"id":1}' | python kis_api_validator.py

# 파라미터 검증
echo '{"jsonrpc":"2.0","method":"validate_params","params":{"api_name":"order_stock","params":{"CANO":"12345678"}},"id":1}' | python kis_api_validator.py
```

## 지원 API

- `order_stock`: 미국 주식 주문
- `get_balance`: 잔고 조회
- `get_token`: OAuth2 토큰 발급

## 확장 방법

`.claude/mcp-servers/kis_api_validator.py`의 `KIS_API_SPECS` 딕셔너리에 새로운 API 추가:

```python
KIS_API_SPECS["new_api"] = {
    "method": "POST",
    "endpoint": "/uapi/...",
    "tr_id": "XXX",
    "required_params": {
        "param1": {"type": "string", "description": "..."},
    }
}
```

## 문제 해결

### MCP 서버가 시작되지 않음
```bash
# 수동 실행 테스트
python .claude/mcp-servers/kis_api_validator.py

# 로그 확인
tail -f ~/.claude/logs/mcp-kis-api.log
```

### API 스펙 업데이트
KIS API 공식 문서가 변경되면:
1. `KIS_API_SPECS` 딕셔너리 수정
2. MCP 서버 재시작: `claude mcp restart kis-api`

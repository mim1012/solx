#!/bin/bash
# PreToolUse Hook: 위험한 명령 차단
# 사용법: Bash 도구 실행 전 자동 호출

# 명령어 파라미터 (Claude가 전달)
COMMAND="$1"

# 위험한 패턴 목록
DANGEROUS_PATTERNS=(
  "rm -rf /"
  "rm -rf \*"
  "DROP TABLE"
  "DELETE FROM.*WHERE 1=1"
  ":(){:|:&};:"  # Fork bomb
  "curl.*eval"
  "wget.*eval"
  "> /dev/sda"
  "dd if=/dev/zero"
  "mkfs\."
  "format "
)

# 실거래 관련 경고 패턴
TRADING_WARNING_PATTERNS=(
  "B15.*TRUE"  # 시스템 가동 활성화
  "phoenix_main.py"  # 실거래 스크립트 실행
  "KIS.*order"  # KIS 주문 실행
)

# 1. 위험 명령 차단
for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiE "$pattern"; then
    echo "❌ [보안 훅] 위험한 명령이 감지되었습니다!"
    echo "   패턴: $pattern"
    echo "   명령: $COMMAND"
    exit 2  # 차단 (exit 2)
  fi
done

# 2. 실거래 경고 (차단하지는 않음)
for pattern in "${TRADING_WARNING_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiE "$pattern"; then
    echo "⚠️  [경고] 실거래 관련 작업이 감지되었습니다."
    echo "   명령: $COMMAND"
    echo "   계속하려면 Excel B15가 TRUE인지 확인하세요."
    # exit 1 = 경고 (계속 진행)
    exit 1
  fi
done

# 3. API 키 노출 검사
if echo "$COMMAND" | grep -qiE "(app_key|app_secret|api_key|password|token).*=.*[A-Za-z0-9]{20,}"; then
  echo "⚠️  [경고] API 키가 명령어에 포함되어 있을 수 있습니다."
  echo "   명령어에 민감 정보가 노출되지 않도록 주의하세요."
  exit 1
fi

# 모든 검사 통과
exit 0

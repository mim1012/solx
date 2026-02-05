#!/bin/bash
# PostToolUse Hook: 코드 스타일 + 타입 검증
# 사용법: Write/Edit 도구 실행 후 자동 호출

# 수정된 파일 경로 (Claude가 전달)
FILE_PATH="$1"

# Python 파일만 검사
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0  # Python 파일 아니면 스킵
fi

# 파일 존재 확인
if [ ! -f "$FILE_PATH" ]; then
  exit 0  # 파일 없으면 스킵
fi

echo "🔍 [코드 품질 훅] 검사 중: $FILE_PATH"

HAS_WARNINGS=0

# 1. PEP 8 스타일 검사 (flake8)
if command -v flake8 &> /dev/null; then
  echo "   - PEP 8 스타일 검사..."
  flake8 "$FILE_PATH" --max-line-length=120 --ignore=E501,W503
  if [ $? -ne 0 ]; then
    HAS_WARNINGS=1
    echo "   ⚠️  스타일 경고 발견 (수정 권장)"
  else
    echo "   ✅ PEP 8 통과"
  fi
else
  echo "   ⚪ flake8 미설치 (스타일 검사 스킵)"
fi

# 2. 타입 힌트 검사 (mypy)
if command -v mypy &> /dev/null; then
  echo "   - 타입 힌트 검사..."
  mypy "$FILE_PATH" --ignore-missing-imports --no-error-summary 2>/dev/null
  if [ $? -ne 0 ]; then
    HAS_WARNINGS=1
    echo "   ⚠️  타입 경고 발견"
  else
    echo "   ✅ 타입 힌트 통과"
  fi
else
  echo "   ⚪ mypy 미설치 (타입 검사 스킵)"
fi

# 3. 보안 검사 (bandit)
if command -v bandit &> /dev/null; then
  echo "   - 보안 취약점 검사..."
  bandit "$FILE_PATH" -q -ll 2>/dev/null
  if [ $? -ne 0 ]; then
    HAS_WARNINGS=1
    echo "   ⚠️  보안 경고 발견"
  else
    echo "   ✅ 보안 검사 통과"
  fi
else
  echo "   ⚪ bandit 미설치 (보안 검사 스킵)"
fi

# 4. 금지된 패턴 검사
echo "   - 금지된 패턴 검사..."

# 하드코딩된 API 키
if grep -qE "(app_key|app_secret|api_key|password|token)\s*=\s*['\"][A-Za-z0-9]{20,}['\"]" "$FILE_PATH"; then
  echo "   ❌ 하드코딩된 API 키 발견!"
  HAS_WARNINGS=1
fi

# TODO/FIXME 주석 (경고만)
if grep -qE "(TODO|FIXME|XXX|HACK)" "$FILE_PATH"; then
  echo "   ⚠️  TODO/FIXME 주석 발견"
  HAS_WARNINGS=1
fi

# print() 디버그 (src/ 폴더 내에서만)
if [[ "$FILE_PATH" =~ ^src/ ]] && grep -qE "^\s*print\(" "$FILE_PATH"; then
  echo "   ⚠️  print() 디버그 코드 발견 (logger 사용 권장)"
  HAS_WARNINGS=1
fi

# 결과
if [ $HAS_WARNINGS -eq 0 ]; then
  echo "✅ [코드 품질 훅] 모든 검사 통과!"
  exit 0  # 성공
else
  echo "⚠️  [코드 품질 훅] 경고 발견 (수정 권장하지만 계속 진행)"
  exit 1  # 경고 (차단 X)
fi

---
name: excel-check
description: Phoenix Trading Excel 템플릿 (B12-B22) 필드 완전성 검증 및 리포트 생성
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
---

# Excel 검증 스킬

**사용법:** `/excel-check` 또는 `excel-check`를 입력하면 실행됩니다.

## 검증 대상 필드

### 필수 인증 정보 (KIS API)
- **B12**: KIS APP KEY (필수, 36자 문자열)
- **B13**: KIS APP SECRET (필수, 문자열)
- **B14**: 계좌번호 (필수, 형식: 12345678-01)
- **B15**: 시스템 가동 여부 (필수, TRUE/FALSE)

### Tier 매도가 설정
- **B16**: Tier 1 매도가 (필수, 숫자)
- **B17**: Tier 2 매도가 (선택, 숫자)
- **B18**: Tier 3 매도가 (선택, 숫자)
- **B19**: Tier 4 매도가 (선택, 숫자)
- **B20**: Tier 5 매도가 (선택, 숫자)

### 추가 설정
- **B22**: Tier 1 매수 비율 (필수, 숫자)

## 실행 단계

### 1단계: Python 검증 스크립트 실행
```bash
python .claude/scripts/excel_validator.py phoenix_grid_template_v3.xlsx
```

### 2단계: 검증 결과 분석
- ✅ 모든 필수 필드가 채워졌는지 확인
- ⚠️ 기본값(placeholder)이 남아있는지 확인
- ❌ 타입 오류가 있는지 확인

### 3단계: 리포트 생성
검증 결과를 `.claude/logs/Excel-Validation-Report.md`에 저장합니다.

## 성공 조건
- [ ] B12 APP KEY 존재 (None 아님)
- [ ] B13 APP SECRET 존재 (기본값 아님)
- [ ] B14 계좌번호 형식 유효 (8자리-2자리)
- [ ] B15 시스템 가동 = TRUE
- [ ] B16 Tier 1 매도가 > 0
- [ ] B22 Tier 1 매수% > 0

## 자동 수정 기능
이 스킬은 검증만 수행합니다. 수정이 필요하면 사용자에게 알립니다.

# Phoenix Trading 자동화 시스템

**Claude Code 기반 자동화 시스템**

---

## 빠른 시작 (Quick Start)

### 1분 만에 시작하기

```bash
# 1. Excel 검증
excel-check

# 2. KIS API 헬스체크
kis-health

# 3. 테스트 실행
테스트 돌려줘

# 완료!
```

---

## 시스템 구성

| 기능 | 명령어/키워드 | 파일 |
|------|--------------|------|
| **스킬** | | |
| Excel 검증 | `excel-check` | `skills/excel-check/` |
| KIS API 헬스체크 | `kis-health` | `skills/kis-health/` |
| **에이전트** | | |
| 테스트 실행 | "테스트 돌려줘" | `agents/TestRunner.md` |
| 코드 리뷰 | "코드 리뷰해줘" | `agents/CodeReviewer.md` |
| 통합 테스트 | "통합 테스트" | `agents/QA_Tester.md` |
| **MCP** | | |
| KIS API 검증 | (자동) | `mcp-servers/kis_api_validator.py` |
| **훅** | | |
| 보안 검증 | (Bash 실행 전) | `hooks/security-check.sh` |
| 코드 품질 | (Write/Edit 후) | `hooks/code-quality-check.sh` |

---

## 폴더 구조

```
.claude/
├── README.md                          # 이 파일
├── AUTOMATION_GUIDE.md                # 상세 가이드 (필독!)
│
├── skills/                            # 스킬 (재사용 가능한 명령어)
│   ├── excel-check/
│   │   └── SKILL.md
│   └── kis-health/
│       └── SKILL.md
│
├── agents/                            # 서브에이전트 (자동화 봇)
│   ├── TestRunner.md
│   ├── CodeReviewer.md
│   └── QA_Tester.md
│
├── mcp-servers/                       # MCP 플러그인
│   ├── kis_api_validator.py
│   └── README.md
│
├── hooks/                             # 자동 검증 훅
│   ├── security-check.sh
│   ├── code-quality-check.sh
│   └── hooks-config-example.json
│
├── scripts/                           # 유틸리티 스크립트
│   ├── excel_validator.py
│   └── kis_health_check.py
│
└── logs/                              # 자동 생성된 리포트
    ├── Excel-Validation-Report.md
    ├── KIS-Health-Report.md
    ├── Test-Report-*.md
    ├── Code-Review-*.md
    └── QA-Integration-Report-*.md
```

---

## 주요 기능

### ✅ Excel 자동 검증
- B12-B22 필드 완전성 검증
- API 키, 계좌번호, Tier 설정 자동 확인
- 실거래 전 필수 체크리스트

**사용법:**
```bash
excel-check
```

---

### ✅ KIS API 헬스체크
- 토큰 발급 확인
- 계좌 조회 테스트
- API 응답 시간 측정

**사용법:**
```bash
kis-health
```

---

### ✅ 자동 테스트 실행 (TestRunner)
- pytest 자동 실행
- 실패 원인 분석
- 커버리지 리포트

**사용법:**
```
테스트 돌려줘
```

---

### ✅ 코드 리뷰 (CodeReviewer)
- 보안 취약점 분석
- PEP 8 준수 확인
- 리팩토링 제안

**사용법:**
```
코드 리뷰해줘
```

---

### ✅ 통합 테스트 (QA_Tester)
- 5가지 시나리오 검증
- 버그 리포트 자동 생성
- Release 품질 게이트

**사용법:**
```
통합 테스트 실행
```

---

### ✅ KIS API 파라미터 검증 (MCP)
- 실시간 API 스펙 확인
- 파라미터 타입/Enum 검증
- 코드 작성 시 자동 검증

**설치:**
```bash
claude mcp add --transport stdio kis-api \
  -- python D:\Project\SOLX\.claude\mcp-servers\kis_api_validator.py
```

---

### ✅ 보안 검증 훅
- 위험 명령 차단 (rm -rf, DROP TABLE)
- API 키 노출 방지
- 실거래 명령 경고

**자동 실행:** Bash 도구 사용 전

---

### ✅ 코드 품질 훅
- PEP 8 스타일 (flake8)
- 타입 힌트 (mypy)
- 보안 취약점 (bandit)

**자동 실행:** Write/Edit 도구 사용 후

---

## 일일 워크플로우

### 거래 시작 전 체크리스트

```bash
# ✅ 1. Excel 검증
excel-check

# ✅ 2. API 연결 확인
kis-health

# ✅ 3. 테스트 실행
테스트 돌려줘

# ✅ 4. 리뷰 (선택)
코드 리뷰해줘
```

### 코드 변경 시

```bash
# 1. 코드 작성 (자동으로 훅 실행)
# 2. 테스트 (자동으로 TestRunner 실행)
# 3. 커밋
```

---

## 설치 & 설정

### 필수 사항

1. **Python 스크립트 실행 권한**
   ```bash
   chmod +x .claude/scripts/*.py
   chmod +x .claude/hooks/*.sh
   ```

2. **MCP 서버 등록** (선택)
   ```bash
   claude mcp add --transport stdio kis-api \
     -- python D:\Project\SOLX\.claude\mcp-servers\kis_api_validator.py
   ```

### 선택 사항

**코드 품질 도구 설치 (훅 사용 시):**
```bash
pip install flake8 mypy bandit
```

---

## 리포트 확인

모든 리포트는 `.claude/logs/`에 자동 저장됩니다:

```bash
# 최신 리포트 목록
ls -lt .claude/logs/

# Excel 검증 리포트
cat .claude/logs/Excel-Validation-Report.md

# KIS API 헬스체크
cat .claude/logs/KIS-Health-Report.md

# 테스트 리포트
cat .claude/logs/Test-Report-*.md
```

---

## 문제 해결

### 스킬이 작동하지 않음
```bash
# 파일 확인
ls -la .claude/skills/*/SKILL.md

# YAML 헤더 확인 (name, user-invocable)
```

### 에이전트가 트리거되지 않음
```bash
# trigger 키워드 확인
cat .claude/agents/TestRunner.md | grep "trigger:"
```

### 훅이 실행되지 않음
```bash
# 수동 테스트
bash .claude/hooks/security-check.sh "rm -rf /"
echo $?  # 2 = 차단
```

---

## 더 알아보기

📖 **상세 가이드:** [AUTOMATION_GUIDE.md](./AUTOMATION_GUIDE.md)
- 각 기능의 상세 사용법
- 고급 설정 방법
- 커스터마이징 가이드

📚 **Claude Code 문서:** https://docs.anthropic.com/claude-code

🔌 **MCP 프로토콜:** https://modelcontextprotocol.io/

---

## 기여

새로운 스킬, 에이전트, 훅을 추가하려면:

1. 해당 폴더에 파일 생성
2. YAML 헤더 작성
3. 기능 구현
4. 이 README 업데이트

---

**버전:** 1.0
**최종 업데이트:** 2026-01-23
**작성:** Claude Code Automation System

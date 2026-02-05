# Phoenix Trading System - 빌드 및 배포 가이드

**버전:** v4.1 (KIS REST API)
**업데이트:** 2026-01-20

---

## 📋 목차

1. [개발 환경 빌드](#1-개발-환경-빌드)
2. [EXE 배포 패키지 생성](#2-exe-배포-패키지-생성)
3. [배포 패키지 구조](#3-배포-패키지-구조)
4. [사용자 설치 가이드](#4-사용자-설치-가이드)
5. [문제 해결](#5-문제-해결)

---

## 1. 개발 환경 빌드

### 1.1. 사전 요구사항

```bash
# Python 3.8+ (64비트 권장)
python --version

# Git (선택)
git --version
```

### 1.2. 의존성 설치

```bash
# 프로젝트 루트로 이동
cd D:\Project\SOLX

# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 의존성 설치
pip install -r requirements.txt
```

### 1.3. 개발 모드 실행

```bash
# Excel 템플릿 생성 (최초 1회)
python create_excel_template.py

# .env 파일 설정 (또는 Excel 파일에 직접 입력)
copy .env.example .env
notepad .env

# 메인 시스템 실행
python phoenix_main.py
```

---

## 2. EXE 배포 패키지 생성

### 2.1. 빌드 스크립트 실행

```bash
# 프로젝트 루트에서 실행
python build_exe.py
```

**빌드 프로세스:**
1. 이전 빌드 산출물 정리 (`build/`, `dist/`)
2. PyInstaller 설치 확인 (없으면 자동 설치)
3. EXE 파일 빌드
4. 배포 패키지 생성 (`release/`)

### 2.2. 빌드 완료 후 확인

```bash
# release 폴더 구조 확인
dir release
```

**예상 출력:**
```
release/
├── PhoenixTrading.exe              ← 실행 파일
├── phoenix_grid_template_v3.xlsx   ← Excel 설정 파일
├── README_사용방법.txt              ← 사용자 가이드
├── 배포_전_확인사항.txt             ← 배포 체크리스트
└── logs/                           ← 로그 폴더 (빈 폴더)
```

### 2.3. 빌드 옵션 커스터마이징 (선택)

`build_exe.py` 파일을 편집하여 빌드 옵션 변경 가능:

```python
# 아이콘 추가 (원하는 경우)
"--icon=icon.ico",

# 윈도우 모드 (콘솔 창 숨김, 권장하지 않음)
"--windowed",

# 추가 데이터 파일 포함
"--add-data=docs;docs",
```

---

## 3. 배포 패키지 구조

### 3.1. 최종 배포 파일

```
release/
│
├── PhoenixTrading.exe              # 메인 실행 파일 (~30MB)
│   ├── Python 인터프리터 내장
│   ├── 모든 의존성 라이브러리 포함
│   └── src/ 폴더 내장
│
├── phoenix_grid_template_v3.xlsx   # Excel 제어 파일 (필수!)
│   ├── 시트 1: 01_매매전략_기준설정
│   │   └── B15 셀: TRUE/FALSE (시작/중지)
│   └── 시트 2: 02_운용로그_히스토리
│
├── README_사용방법.txt              # 사용자 가이드
├── 배포_전_확인사항.txt             # 개발자용 체크리스트
└── logs/                           # 로그 저장 폴더
```

### 3.2. 필수 파일 의존성

| 파일 | 위치 | 필수 여부 | 설명 |
|------|------|-----------|------|
| `PhoenixTrading.exe` | 같은 폴더 | ✅ 필수 | 메인 실행 파일 |
| `phoenix_grid_template_v3.xlsx` | 같은 폴더 | ✅ 필수 | Excel 설정 파일 |
| `logs/` | 같은 폴더 | 자동 생성 | 로그 저장 폴더 |

---

## 4. 사용자 설치 가이드

### 4.1. 사용자에게 전달할 파일

```bash
# release 폴더를 ZIP으로 압축
# 방법 1: Windows 탐색기
release 폴더 우클릭 → "보내기" → "압축(ZIP) 폴더"

# 방법 2: PowerShell
Compress-Archive -Path release -DestinationPath PhoenixTrading_v4.1.zip
```

### 4.2. 사용자 설치 절차

**Step 1: 압축 해제**
```
PhoenixTrading_v4.1.zip을 원하는 위치에 압축 해제
예: C:\PhoenixTrading\
```

**Step 2: Excel 파일 설정**
```
phoenix_grid_template_v3.xlsx 열기
시트: "01_매매전략_기준설정"

[필수 입력 항목]
B12: KIS APP KEY (한국투자증권에서 발급)
B13: KIS APP SECRET
B14: KIS 계좌번호 (예: 12345678-01)
B15: FALSE (처음엔 중지 상태로 유지)

[선택 입력 항목]
B2: 계좌번호 (B14와 동일)
B3: SOXL (고정)
B4: 투자금 (USD, 예: 10000)
B13: 텔레그램 채팅 ID
B14: 텔레그램 봇 토큰
B15: 알림 활성화 (TRUE/FALSE)

저장 (Ctrl+S)
```

**Step 3: 프로그램 실행**
```
PhoenixTrading.exe 더블클릭

[예상 출력]
╔══════════════════════════════════════════╗
║  Phoenix Trading System v4.1             ║
║  SOXL 자동매매 시스템                     ║
╚══════════════════════════════════════════╝

⚠️  경고: 실제 자금으로 거래합니다.

[OK] Excel 설정 로드 중...
[OK] 시스템 실행: OFF (B15=FALSE)

⚠️  시스템이 중지 상태입니다
자동 거래를 시작하려면:
  1. Excel 파일 열기
  2. B15 셀을 TRUE로 변경
  3. 저장 후 프로그램 재시작
```

**Step 4: 자동 거래 시작**
```
1. Excel 파일 열기
2. B15 셀을 TRUE로 변경
3. 저장 (Ctrl+S)
4. PhoenixTrading.exe 다시 실행

[예상 출력]
✅ KIS API 로그인 성공
✅ SOXL 초기 시세: $28.50
✅ 계좌 잔고: $10,500.00
✅ 시스템 초기화 완료!

메인 거래 루프 시작...
종료하려면 Ctrl+C를 누르세요.
```

**Step 5: 중지**
```
방법 1: Ctrl+C (콘솔 창에서)
방법 2: Excel B15를 FALSE로 변경 후 재시작
방법 3: 콘솔 창 닫기 (비권장, 데이터 손실 가능)
```

---

## 5. 문제 해결

### 5.1. 빌드 단계 문제

#### 문제 1: PyInstaller 설치 실패
```
❌ PyInstaller 설치 실패
```

**해결:**
```bash
# 수동 설치
pip install pyinstaller

# 업그레이드
pip install --upgrade pyinstaller
```

---

#### 문제 2: 빌드 중 "ModuleNotFoundError"
```
ModuleNotFoundError: No module named 'openpyxl'
```

**해결:**
```bash
# 의존성 재설치
pip install -r requirements.txt

# 또는 개별 설치
pip install openpyxl requests websockets python-dotenv
```

---

#### 문제 3: EXE 파일 크기가 너무 큼 (>50MB)
```
PhoenixTrading.exe: 80MB
```

**해결:**
`build_exe.py` 파일에서 제외 모듈 추가:
```python
"--exclude-module=matplotlib",
"--exclude-module=numpy",
"--exclude-module=pandas",
# 추가:
"--exclude-module=PIL",
"--exclude-module=tkinter",
```

---

### 5.2. 실행 단계 문제

#### 문제 4: "Excel 템플릿을 찾을 수 없습니다"
```
[ERROR] Excel 파일을 찾을 수 없음: phoenix_grid_template_v3.xlsx
```

**해결:**
```
Excel 파일을 PhoenixTrading.exe와 같은 폴더에 배치
```

---

#### 문제 5: "VCRUNTIME140.dll이 없습니다"
```
VCRUNTIME140.dll이 컴퓨터에 없어 프로그램을 시작할 수 없습니다.
```

**해결:**
Visual C++ 재배포 패키지 설치:
```
https://aka.ms/vs/17/release/vc_redist.x64.exe
```

---

#### 문제 6: Windows Defender 경고
```
Windows에서 PC를 보호했습니다
```

**해결:**
```
1. "추가 정보" 클릭
2. "실행" 클릭
3. (선택) Windows Defender 예외 추가:
   설정 → 업데이트 및 보안 → Windows 보안 → 바이러스 및 위협 방지 → 설정 관리 → 제외 추가
```

---

#### 문제 7: KIS API 로그인 실패
```
[ERROR] KIS API 로그인 실패!
```

**해결:**
1. Excel 파일에서 B12/B13 값 확인 (정확히 복사/붙여넣기)
2. KIS 개발자센터에서 API 승인 상태 확인
3. 인터넷 연결 확인
4. 방화벽 확인

---

## 6. 추가 정보

### 6.1. 빌드 환경 권장사항

| 항목 | 권장 사양 |
|------|----------|
| OS | Windows 10/11 64비트 |
| Python | 3.8 ~ 3.11 (64비트) |
| RAM | 8GB 이상 |
| 디스크 | 10GB 여유 공간 |

### 6.2. 배포 시 체크리스트

- [ ] `python build_exe.py` 실행 성공
- [ ] `release/PhoenixTrading.exe` 생성 확인
- [ ] `release/phoenix_grid_template_v3.xlsx` 존재 확인
- [ ] EXE 파일 실행 테스트 (개발 PC에서)
- [ ] Excel B15=FALSE 상태에서 정상 작동 확인
- [ ] Excel B15=TRUE 상태에서 KIS API 연결 확인
- [ ] 로그 파일 정상 생성 확인 (`logs/`)
- [ ] release 폴더 ZIP 압축
- [ ] 사용자 가이드 문서 포함 확인

### 6.3. 버전 관리

```bash
# Git 태그로 버전 관리
git tag -a v4.1 -m "KIS REST API Migration Complete"
git push origin v4.1

# 릴리즈 파일 명명 규칙
PhoenixTrading_v4.1_20260120.zip
```

---

## 📞 지원

**문제 발생 시:**
1. 로그 파일 확인: `logs/phoenix_*.log`
2. Excel 파일 설정 재확인
3. 이 문서의 "문제 해결" 섹션 참조

**긴급 상황:**
- Excel B15를 FALSE로 변경하여 즉시 중지
- Ctrl+C로 프로그램 종료
- 한국투자증권 HTS에서 수동 청산

---

**최종 업데이트:** 2026-01-20
**문서 버전:** 1.0

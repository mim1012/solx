# Phoenix Trading System v4.1 - 빠른 시작 가이드

## 📋 시스템 요구사항

- **운영체제**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+
- **Python**: 3.8 이상 (64비트)
- **메모리**: 4GB RAM 이상
- **저장공간**: 500MB 이상

## 🚀 5분 안에 시작하기

### 1단계: 파일 다운로드
1. PhoenixTrading_v4.1.zip 파일 다운로드
2. 원하는 폴더에 압축 해제

### 2단계: 환경 설정 (Windows)
```
1. setup.bat 더블클릭 실행
2. .env 파일 편집 (메모장으로 열기)
3. phoenix_grid_template_v3.xlsx 편집
```

### 2단계: 환경 설정 (macOS/Linux)
```bash
1. 터미널 열기
2. cd /path/to/phoenix-trading
3. ./setup.sh 실행
4. .env 파일 편집
5. phoenix_grid_template_v3.xlsx 편집
```

### 3단계: .env 파일 설정
```ini
# 필수 설정
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_ACCOUNT_NO=12345678-01
KIS_API_MODE=REAL  # 또는 PAPER (모의투자)

# 미국 시장 설정 (SOXL 기본값)
US_MARKET_TICKER=SOXL
US_MARKET_EXCHANGE=AMS
US_MARKET_CURRENCY=USD

# 선택 설정
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
LOG_LEVEL=INFO
BALANCE_SYNC_INTERVAL=60
```

### 4단계: Excel 설정
1. `phoenix_grid_template_v3.xlsx` 파일 열기
2. `01_매매전략_기준설정` 시트에서:
   - 계좌번호: 한국투자증권 계좌번호
   - 종목코드: SOXL (고정)
   - 투자금 (USD): 총 투자 금액
   - 1티어 금액 (USD): 티어당 투자 금액
3. 저장 (Ctrl + S)

### 5단계: 테스트 실행
```bash
# 설정 테스트
python test_config.py

# KIS API 연결 테스트
python test_kis_fix.py

# 문제 해결 테스트
python test_kis_fix.py > test_log.txt 2>&1
```

### 6단계: 메인 실행
```bash
# 일반 실행
python phoenix_main.py

# 상세 로그 모드
python phoenix_main.py 2>&1 | tee trading_log.txt
```

## 🔧 주요 문제 해결

### 문제 1: "잔고 부족으로 배치 매수 중단"
```
원인: USD 예수금이 $0.00으로 조회됨
해결:
1. test_kis_fix.py 실행하여 진단
2. .env 파일에서 US_MARKET_EXCHANGE=AMS 확인
3. 증권사 앱에서 USD 잔고 확인
```

### 문제 2: "KIS API 로그인 실패"
```
원인: API 키 또는 계좌번호 오류
해결:
1. .env 파일의 KIS_APP_KEY, KIS_APP_SECRET 확인
2. 계좌번호 형식 확인 (12345678-01)
3. KIS 개발자센터에서 앱키 권한 확인
```

### 문제 3: "Python을 찾을 수 없습니다"
```
해결:
1. Python 3.8+ 설치: https://www.python.org/downloads/
2. 설치 시 "Add Python to PATH" 체크
3. 재시작 후 setup.bat 다시 실행
```

## 📊 모니터링 방법

### 로그 확인
```
logs/phoenix_YYYYMMDD_HHMMSS.log 파일 확인
```

### 실시간 모니터링
```bash
# Windows
type logs\latest.log

# macOS/Linux
tail -f logs/latest.log
```

### 상태 확인
1. Excel 파일 실시간 업데이트 확인
2. 텔레그램 알림 수신 확인
3. 콘솔 창 로그 모니터링

## ⚡ 고급 설정

### 다른 종목 거래 설정
```ini
# .env 파일에서 수정
US_MARKET_TICKER=AAPL
US_MARKET_EXCHANGE=NAS  # AAPL은 나스닥
```

### 잔고 동기화 간격 조정
```ini
# 더 빠른 동기화 (30초)
BALANCE_SYNC_INTERVAL=30

# 더 느린 동기화 (5분)
BALANCE_SYNC_INTERVAL=300
```

### 디버그 모드 활성화
```ini
LOG_LEVEL=DEBUG
DEBUG_MODE=true
```

## 📞 지원

문제 발생 시:
1. `logs/` 폴더의 로그 파일 확인
2. `test_kis_fix.py` 실행 결과 공유
3. README_배포용.txt 참조

## ⚠️ 주의사항

1. **실거래 시스템** - 실제 자금 사용
2. **고위험 상품** - SOXL은 3배 레버리지 ETF
3. **소액 테스트** - $1,000~$5,000로 시작 권장
4. **지속적 모니터링** - 시스템 상태 주기적 확인

---

**버전**: v4.1 (2026-02-04)
**문서**: README_배포용.txt 참조
**테스트**: test_config.py, test_kis_fix.py 실행 권장
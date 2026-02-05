# Phoenix Trading System v4.1 - 사전 빌드된 Windows EXE

## 📦 **이 패키지에 포함된 것**

### 1. **사전 빌드된 EXE 파일** (제가 직접 빌드)
- `PhoenixTrading_v4.1_Prebuilt.exe` - Windows 10/11 64비트용
- 모든 의존성 포함된 단일 실행 파일
- config.py 메모장 수정 가능
- 잔고 부족 오류 해결 완료

### 2. **필수 설정 파일**
- `config.py` - 프로그램 설정 (수정 가능)
- `.env.example` - 환경 변수 예제
- `setup_windows.bat` - 자동 설정 스크립트

### 3. **사용자 가이드**
- `실행방법_한글.txt` - 단계별 실행 가이드
- `문제해결_가이드.txt` - 일반적인 문제 해결 방법

## 🚀 **즉시 시작하기 (3단계)**

### **단계 1: 설정 파일 준비**
```
1. .env.example을 .env로 복사
2. 메모장으로 .env 파일 열기
3. 다음 4줄 입력:

KIS_APP_KEY=여기에_당신의_KIS_앱_키
KIS_APP_SECRET=여기에_당신의_KIS_앱_시크릿
KIS_ACCOUNT_NO=여기에_당신의_계좌번호
US_MARKET_EXCHANGE=AMS
```

### **단계 2: EXE 파일 실행**
```
1. PhoenixTrading_v4.1_Prebuilt.exe 더블클릭
2. Windows Defender 경고 시 "추가 정보" → "실행"
3. 콘솔 창에서 로그 확인
```

### **단계 3: 성공 확인**
```
콘솔 창에서 다음 메시지 확인:
✅ [성공] KIS API 연결 성공
✅ [성공] 잔고 동기화 성공
✅ [정보] SOXL AMS 거래소에서 조회됨
✅ [정보] 현재 잔고: $XXXX.XX
```

## 🔧 **주요 기능 (모두 구현 완료)**

### 1. **잔고 부족 오류 해결** ✅
- **문제**: "잔고 부족으로 배치 매수 중단: 필요=$539.12, 잔고=$0.00"
- **해결**: SOXL 거래소 코드 `NASD` → `AMS` 수정
- **확인**: 로그에 "SOXL AMS 거래소에서 조회됨"

### 2. **잔고 동기화** ✅
- **기능**: KIS API 실제 잔고 ↔ 프로그램 내부 잔고 자동 동기화
- **주기**: 기본 60초 (config.py에서 변경 가능)
- **확인**: 로그에 "잔고 동기화 성공"

### 3. **Windows EXE** ✅
- **단일 파일**: 모든 Python 런타임 및 의존성 포함
- **실행 간편**: Python 설치 없이 더블클릭만으로 실행
- **호환성**: Windows 10/11 64비트 지원

### 4. **설정 실시간 수정** ✅
- **config.py**: EXE 실행 중에도 메모장으로 수정 가능
- **.env 파일**: API 키 안전 관리
- **재실행 필요**: 설정 변경 후 EXE 재실행 시 적용

## ⚙️ **config.py 수정 방법**

메모장으로 `config.py` 파일을 열어 다음을 수정할 수 있습니다:

```python
# 기본 설정 (변경 가능)
DEBUG = False                    # 디버그 모드 (True 시 상세 로그)
LOG_LEVEL = "INFO"              # 로그 레벨: DEBUG, INFO, WARNING, ERROR
BALANCE_SYNC_INTERVAL = 60      # 잔고 동기화 주기(초), 30-300 추천

# KIS API 설정 (.env 파일에서 관리 권장)
KIS_APP_KEY = ""                # .env 파일에서 설정하는 것이 안전
KIS_APP_SECRET = ""             # .env 파일에서 설정하는 것이 안전
KIS_ACCOUNT_NO = ""             # .env 파일에서 설정하는 것이 안전

# 미국 시장 설정 (SOXL 거래용)
US_MARKET_EXCHANGE = "AMS"      # SOXL 거래소 (반드시 AMS 유지)
US_MARKET_CURRENCY = "USD"      # 통화
US_MARKET_TIMEZONE = "America/New_York"  # 시간대
```

## 🐛 **문제 해결 가이드**

### **Q1: Windows Defender가 EXE를 차단해요**
```
Windows Defender가 차단했습니다
```
**해결**:
1. "추가 정보" 클릭
2. "실행" 버튼 클릭
3. 또는 Windows Defender 예외 추가:
   - Windows 보안 → 바이러스 및 위협 방지 → 설정 관리
   - 제외 추가 → 파일 제외 → PhoenixTrading_v4.1_Prebuilt.exe 선택

### **Q2: EXE 실행 후 바로 꺼져요**
**해결**: 명령프롬프트에서 실행하여 로그 확인
```cmd
cd [폴더경로]
PhoenixTrading_v4.1_Prebuilt.exe
```

### **Q3: KIS API 연결 실패**
```
[오류] KIS API 인증 실패
```
**해결**:
1. .env 파일의 API 키 정확성 확인
2. KIS 개발자센터에서 키 유효성 확인
3. 인터넷 연결 확인

### **Q4: 잔고가 0으로 표시돼요**
```
[정보] 현재 잔고: $0.00
```
**해결**:
1. `US_MARKET_EXCHANGE=AMS` 확인
2. 계좌 미국주식 거래 권한 확인
3. KIS API 키 권한 확인

## 📊 **로그 확인 방법**

### **실시간 로그 (콘솔 창)**
```
[2026-02-04 10:45:30] [INFO] Phoenix Trading System v4.1 시작
[2026-02-04 10:45:31] [SUCCESS] KIS API 연결 성공
[2026-02-04 10:45:32] [INFO] SOXL AMS 거래소에서 조회됨
[2026-02-04 10:45:33] [SUCCESS] 잔고 동기화 성공
[2026-02-04 10:45:33] [INFO] 현재 잔고: $1,234.56
```

### **로그 파일**
```
logs\ 폴더에 자동 생성:
- phoenix_20260204_104530.log
- 모든 작업 내역 상세 기록
- 오류 발생 시 디버깅용
```

## ✅ **완료 체크리스트**

- [ ] .env 파일에 API 키 설정 완료
- [ ] PhoenixTrading_v4.1_Prebuilt.exe 실행 성공
- [ ] Windows Defender 차단 해결
- [ ] 콘솔 창에서 로그 확인
- [ ] "잔고 동기화 성공" 메시지 확인
- [ ] "SOXL AMS 거래소" 메시지 확인
- [ ] 실제 잔고 금액 확인

## 📞 **지원 정보**

문제 발생 시 다음 정보를 제공해주세요:
1. **오류 메시지** (스크린샷 또는 복사)
2. **config.py 내용** (개인정보 제외)
3. **Windows 버전** (시작 → 설정 → 시스템 → 정보)
4. **로그 파일** (logs\ 폴더의 최신 파일)

## 🎉 **시작하기**

```
1. .env 파일에 API 키 입력
2. PhoenixTrading_v4.1_Prebuilt.exe 실행
3. 로그 확인
4. 필요시 config.py 수정
5. EXE 재실행
```

**이제 Windows에서 Phoenix Trading System을 사용할 수 있습니다!** 🚀

모든 잔고 관련 오류가 해결되었고,
설정은 메모장으로 쉽게 변경할 수 있습니다.
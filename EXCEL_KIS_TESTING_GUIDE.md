# Phoenix Trading System - Excel 기반 KIS API 테스트 가이드

**마이그레이션 완료:** Kiwoom → Korea Investment & Securities (KIS)

---

## 📋 시스템 구조

```
Excel 파일 (사용자 제어)
    ↓
    B12: KIS APP KEY
    B13: KIS APP SECRET
    B14: KIS 계좌번호
    B15: 시스템 실행 (TRUE/FALSE) ← 시작/중지 제어
    ↓
ExcelBridge.load_settings()
    ↓
GridSettings (API 키 포함)
    ↓
KisRestAdapter
    ↓
KIS REST API (한국투자증권)
```

---

## ✅ 사전 준비사항

### 1. KIS API 신청
- 한국투자증권 계좌 개설
- [KIS Developers](https://apiportal.koreainvestment.com) 접속
- REST API 신청 및 승인 대기
- APP KEY, APP SECRET 발급받기

### 2. 필요한 정보
- ✅ KIS APP KEY (예: `PSxxx...`)
- ✅ KIS APP SECRET (예: `xxx...`)
- ✅ 계좌번호 (예: `12345678-01`)

---

## 🚀 실거래 테스트 절차

### **Step 1: Excel 파일 설정**

**파일:** `phoenix_grid_template_v3.xlsx`

**시트:** `01_매매전략_기준설정`

| 셀 위치 | 항목 | 입력 내용 | 비고 |
|---------|------|-----------|------|
| **B2** | 계좌번호 | (선택사항) | B14와 중복 가능 |
| **B3** | 종목코드 | `SOXL` | 고정값 |
| **B4** | 투자금 (USD) | `10000` | 초기 투자금 |
| **B12** | KIS APP KEY | `PSxxx...` | **필수** |
| **B13** | KIS APP SECRET | `xxx...` | **필수** |
| **B14** | KIS 계좌번호 | `12345678-01` | **필수** |
| **B15** | 시스템 실행 | `FALSE` | TRUE=시작, FALSE=중지 |

**⚠️ 중요:**
- B15를 `TRUE`로 변경하면 자동으로 거래가 시작됩니다
- 처음에는 **반드시 FALSE로 유지**하고 테스트하세요

---

### **Step 2: 설정 검증 테스트 (안전)**

```bash
python test_excel_kis_integration.py
```

**B15=FALSE일 때 (안전 모드):**
```
============================================================
Step 1: Excel 설정 읽기
============================================================
[OK] Account No:
[OK] Ticker: SOXL
[OK] Investment: $10,000.00
[OK] KIS APP KEY: PSxxx...
[OK] KIS APP SECRET: xxx...
[OK] KIS Account: 12345678-01
[OK] System Running: OFF (FALSE)

[INFO] System is STOPPED (B15=FALSE)
Set B15=TRUE in Excel to start trading system.

============================================================
Final Result
============================================================
[STOPPED] System is in stopped state (normal)
```

**✅ 이 상태에서는:**
- Excel 파일만 읽음
- KIS API 연결 안 함
- 자동 거래 안 함
- 안전한 설정 확인만 수행

---

### **Step 3: KIS API 연결 테스트 (실거래 전 필수)**

**Excel 파일에서 B15를 `TRUE`로 변경**

```bash
python test_excel_kis_integration.py
```

**B15=TRUE일 때 (실행 모드):**
```
============================================================
Step 1: Excel 설정 읽기
============================================================
[OK] Account No: 12345678-01
[OK] Ticker: SOXL
[OK] Investment: $10,000.00
[OK] KIS APP KEY: PSxxx...
[OK] KIS APP SECRET: xxx...
[OK] KIS Account: 12345678-01
[OK] System Running: ON (TRUE)

============================================================
Step 2: KIS API 연결 시도
============================================================
로그인 시도 중...
[OK] Login Success!
[OK] Access Token: eyJhbGciOiJIUzI1NiIsInR5cCI...
[OK] Approval Key: 12345678-abcd-efgh-ijkl...

============================================================
Step 3: SOXL 시세 조회
============================================================
[OK] Current Price: $28.50
[OK] Open: $27.80
[OK] High: $29.20
[OK] Low: $27.50
[OK] Volume: 15,432,100

============================================================
Step 4: 계좌 잔고 조회
============================================================
[OK] Cash Balance: $10,500.00

============================================================
Final Result
============================================================
[SUCCESS] All tests passed! Ready for real trading!
```

**✅ 성공 시:**
- KIS API 로그인 성공
- Access Token, Approval Key 발급 확인
- SOXL 실시간 시세 조회 성공
- 계좌 잔고 조회 성공
- **실거래 준비 완료!**

---

## ❌ 오류 해결

### 1. Login Failed
```
[ERROR] Login failed!
Possible causes:
  1. Wrong KIS APP KEY/SECRET
  2. API not approved yet
  3. Network connection issue
```

**해결방법:**
- KIS Developers 사이트에서 API 키 재확인
- API 승인 상태 확인 (보통 1~2일 소요)
- 네트워크 연결 확인

---

### 2. KIS APP KEY missing
```
[WARN] KIS APP KEY missing
[ERROR] KIS API keys not set in Excel!
```

**해결방법:**
- Excel 파일 열기
- B12에 KIS APP KEY 입력
- B13에 KIS APP SECRET 입력
- 파일 저장 후 다시 테스트

---

### 3. Price Query Failed
```
[ERROR] Price query failed
```

**가능한 원인:**
- 장 마감 시간 (한국 시간 새벽 6시~오후 1시)
- API Rate Limit 초과
- 종목코드 오류

---

## 🎯 실거래 시작 전 체크리스트

- [ ] KIS API 키 발급 완료
- [ ] Excel 파일에 API 키 입력 완료
- [ ] `B15=FALSE`로 설정 검증 테스트 통과
- [ ] `B15=TRUE`로 KIS API 연결 테스트 통과
- [ ] SOXL 시세 조회 성공
- [ ] 계좌 잔고 조회 성공
- [ ] **모의투자 서버로 먼저 테스트** (권장)

---

## 🔄 모의투자 vs 실거래

### 모의투자 서버 (권장)
```python
# kis_rest_adapter.py (line 73)
WS_URL = "ws://ops.koreainvestment.com:31000"  # 모의투자 포트
```

### 실거래 서버
```python
# kis_rest_adapter.py (line 73)
WS_URL = "ws://ops.koreainvestment.com:21000"  # 실거래 포트
```

**⚠️ 실거래 전 반드시 모의투자로 검증하세요!**

---

## 📞 지원

**문제 발생 시:**
1. 로그 파일 확인: `logs/` 폴더
2. Excel 파일 설정 재확인
3. KIS Developers 고객센터: 1544-5000

**테스트 파일:**
- `test_excel_kis_integration.py`: Excel → KIS API 연동 테스트
- `tests/test_kis_rest_adapter.py`: KIS API 단위 테스트 (29개)

---

## 📊 테스트 통과 기준

✅ **안전 모드 테스트 (B15=FALSE)**
- Excel 설정 읽기 성공
- API 키 존재 확인
- [STOPPED] 상태 정상 표시

✅ **연결 테스트 (B15=TRUE)**
- KIS API 로그인 성공
- Access Token 발급
- Approval Key 발급
- SOXL 시세 조회 성공
- 계좌 잔고 조회 성공

✅ **단위 테스트**
```bash
pytest tests/test_kis_rest_adapter.py -v
# 29 passed in 0.2s
```

---

**최종 업데이트:** 2026-01-19
**버전:** v4.1 (KIS Migration Complete)

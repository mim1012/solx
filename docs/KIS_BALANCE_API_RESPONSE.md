# 한국투자증권 잔고조회 API 응답 구조

## API 정보
- **TR_ID**: TTTS3012R (실전) / VTTS3012R (모의)
- **엔드포인트**: `/uapi/overseas-stock/v1/trading/inquire-balance`
- **Method**: GET

---

## 응답 구조 (Response Structure)

### 1️⃣ 성공 응답 (보유 종목 있을 때)

```json
{
  "rt_cd": "0",
  "msg_cd": "MCA00000",
  "msg1": "정상처리 되었습니다.",

  "output1": [
    {
      "cano": "12345678",                    // 계좌번호
      "acnt_prdt_cd": "01",                  // 계좌상품코드
      "prdt_type_cd": "512",                 // 상품유형코드
      "ovrs_pdno": "SOXL",                   // 해외상품번호 (종목코드)
      "ovrs_item_name": "DIREXION DAILY SEMICONDUCTOR BULL 3X SHARES",
      "frcr_evlu_pfls_rt": "5.23",          // 외화평가손익율 (%)
      "evlu_pfls_rt": "5.23",                // 평가손익율
      "pchs_avg_pric": "45.50",              // 매입평균가격
      "ovrs_cblc_qty": "100",                // 해외잔고수량
      "ord_psbl_qty": "100",                 // 주문가능수량
      "frcr_pchs_amt1": "4550.00",          // 외화매입금액
      "ovrs_stck_evlu_amt": "4788.00",      // 해외주식평가금액
      "frcr_evlu_pfls_amt": "238.00",       // 외화평가손익금액
      "evlu_pfls_amt": "317640",             // 평가손익금액 (원화)
      "tr_crcy_cd": "USD",                   // 거래통화코드
      "ovrs_excg_cd": "NASD",                // 해외거래소코드
      "loan_type_cd": "",                    // 대출유형코드
      "loan_dt": "",                          // 대출일자
      "expd_dt": ""                           // 만기일자
    },
    {
      "ovrs_pdno": "AAPL",
      "ovrs_item_name": "APPLE INC",
      "ovrs_cblc_qty": "50",
      "pchs_avg_pric": "180.25",
      "frcr_pchs_amt1": "9012.50",
      "ovrs_stck_evlu_amt": "9375.00",
      "frcr_evlu_pfls_amt": "362.50",
      ...
    }
  ],

  "output2": [
    {
      "frcr_pchs_amt1": "13562.50",           // 외화매입금액 합계
      "ovrs_rlze_pfls_amt": "0.00",           // 해외실현손익금액
      "ovrs_tot_pfls": "600.50",              // 해외총손익
      "rlze_erng_rt": "0.00",                 // 실현수익율
      "tot_evlu_pfls_amt": "801200",          // 총평가손익금액 (원화)
      "tot_pftrt": "4.43",                    // 총수익률 (%)
      "frcr_buy_amt_smtl1": "14163.00",      // 외화매수금액합계
      "ovrs_rlze_pfls_amt2": "0.00",         // 해외실현손익금액2
      "frcr_buy_amt_smtl2": "14163.00",      // 외화매수금액합계2
      "frcr_drwg_psbl_amt_1": "5837.50",     // ⭐ 외화출금가능금액 (USD 예수금)
      "frcr_evlu_tota": "20000.50",          // 외화평가합계
      "evlu_amt_smtl_amt": "26680000",       // 평가금액합계금액 (원화)
      "pchs_amt_smtl_amt": "26080000",       // 매입금액합계금액 (원화)
      "evlu_pfls_smtl_amt": "600000",        // 평가손익합계금액
      "evlu_erng_rt1": "2.30",               // 평가수익율
      "tot_dncl_amt": "0",                    // 총대출금액
      "sll_buy_dvsn_cd": "",                  // 매도매수구분코드
      "sll_buy_dvsn_cd_name": ""             // 매도매수구분코드명
    }
  ]
}
```

---

### 2️⃣ 성공 응답 (보유 종목 없을 때)

```json
{
  "rt_cd": "0",
  "msg_cd": "MCA00000",
  "msg1": "정상처리 되었습니다.",

  "output1": [],   // 빈 배열

  "output2": {     // ⚠️ list가 아닌 dict로 반환됨
    "frcr_pchs_amt1": "0.00",
    "frcr_drwg_psbl_amt_1": "10000.00",    // ⭐ USD 예수금
    "frcr_evlu_tota": "10000.00",
    "ovrs_tot_pfls": "0.00",
    "tot_pftrt": "0.00",
    ...
  }
}
```

---

### 3️⃣ 실패 응답

```json
{
  "rt_cd": "1",
  "msg_cd": "EGW00123",
  "msg1": "계좌번호 오류입니다.",
  "output1": [],
  "output2": null
}
```

---

## 주요 필드 설명

### **output1** (보유 종목 리스트)
| 필드명 | 설명 | 예시 |
|--------|------|------|
| `ovrs_pdno` | 종목코드 | "SOXL" |
| `ovrs_item_name` | 종목명 | "DIREXION DAILY..." |
| `ovrs_cblc_qty` | 보유 수량 | "100" |
| `pchs_avg_pric` | 매입 평균가 (USD) | "45.50" |
| `frcr_pchs_amt1` | 매입금액 (USD) | "4550.00" |
| `ovrs_stck_evlu_amt` | 평가금액 (USD) | "4788.00" |
| `frcr_evlu_pfls_amt` | 평가손익 (USD) | "238.00" |
| `frcr_evlu_pfls_rt` | 평가손익율 (%) | "5.23" |
| `ord_psbl_qty` | 주문가능수량 | "100" |
| `ovrs_excg_cd` | 거래소코드 | "NASD", "NYSE", "AMEX" |
| `tr_crcy_cd` | 통화코드 | "USD" |

### **output2** (계좌 요약 정보)
| 필드명 | 설명 | 예시 |
|--------|------|------|
| **`frcr_drwg_psbl_amt_1`** | ⭐ **USD 예수금 (출금가능금액)** | "5837.50" |
| `frcr_pchs_amt1` | 외화 매입금액 합계 | "13562.50" |
| `frcr_evlu_tota` | 외화 평가 합계 (예수금 + 보유주식) | "20000.50" |
| `ovrs_tot_pfls` | 총 손익 (USD) | "600.50" |
| `tot_pftrt` | 총 수익률 (%) | "4.43" |
| `evlu_amt_smtl_amt` | 평가금액 합계 (원화) | "26680000" |
| `tot_evlu_pfls_amt` | 총 평가손익 (원화) | "801200" |

---

## 코드에서의 응답 처리

### kis_rest_adapter.py:630-663

```python
if data.get("rt_cd") == "0":
    output1 = data.get("output1", [])     # 보유 종목 리스트
    output2 = data.get("output2")          # 계좌 요약 (dict 또는 list)

    # USD 예수금 추출
    cash = 0.0
    if output2:
        # 보유 종목 없을 때: dict
        if isinstance(output2, dict):
            cash = float(output2.get("frcr_drwg_psbl_amt_1", 0) or 0)

        # 보유 종목 있을 때: list[0]
        elif isinstance(output2, list) and len(output2) > 0:
            cash = float(output2[0].get("frcr_drwg_psbl_amt_1", 0) or 0)

    # 보유 종목 출력
    for item in output1:
        ticker = item.get("ovrs_pdno", "")
        qty = item.get("ovrs_cblc_qty", "0")
        logger.info(f"보유종목: {ticker} {qty}주")

    return cash  # USD 예수금 반환
```

---

## ⚠️ 중요 포인트

### 1. **output2 타입 변화**
- 보유 종목 **있을 때**: `output2`는 **list** (길이 1)
- 보유 종목 **없을 때**: `output2`는 **dict**
- **코드는 두 경우 모두 처리함** ✅

### 2. **예수금 필드**
- **`frcr_drwg_psbl_amt_1`**: 외화 출금가능금액 = **USD 예수금**
- 이 값이 **실제 거래 가능한 현금**입니다.

### 3. **연속조회**
- 보유 종목이 많을 경우 여러 페이지로 나뉨
- `CTX_AREA_FK200`, `CTX_AREA_NK200` 값이 응답에 포함됨
- 다음 페이지 조회 시 해당 값을 Query 파라미터로 전달

---

## 실제 사용 예시

```python
# 잔고 조회
adapter = KisRestAdapter(app_key, app_secret, account_no)
adapter.login()

# USD 예수금 조회
cash = adapter.get_balance()
print(f"USD 예수금: ${cash:,.2f}")
# 출력: USD 예수금: $5,837.50
```

---

## 디버그 로그 예시

```
2026-02-01 09:00:00 [INFO] KIS API 잔고조회 성공: output1 2건, output2 타입=<class 'list'>
2026-02-01 09:00:00 [INFO] [DEBUG] output2 내용: [{'frcr_drwg_psbl_amt_1': '5837.50', ...}]
2026-02-01 09:00:00 [INFO] USD 예수금 (list): $5,837.50
2026-02-01 09:00:00 [INFO]   보유종목: SOXL 100주
2026-02-01 09:00:00 [INFO]   보유종목: AAPL 50주
```

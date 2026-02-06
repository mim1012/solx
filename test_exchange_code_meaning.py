"""
거래소 코드의 의미 확인
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.kis_rest_adapter import KisRestAdapter
from src.excel_bridge import ExcelBridge

print("\n" + "="*80)
print("TTTS3007R API 파라미터 의미 확인")
print("="*80 + "\n")

print("API 이름: 해외주식 매매가능금액조회 (TTTS3007R)")
print()
print("파라미터:")
print("  CANO: 계좌번호 앞자리")
print("  ACNT_PRDT_CD: 계좌번호 뒷자리")
print("  OVRS_EXCG_CD: 해외거래소코드 <- 이게 핵심!")
print("  OVRS_ORD_UNPR: 주문단가")
print("  ITEM_CD: 종목코드")
print()
print("질문: OVRS_EXCG_CD는 무엇을 의미하는가?")
print()
print("답변: '조회하려는 종목이 상장된 거래소'를 지정")
print("      (USD가 어디 있는지가 아님!)")
print()
print("예시:")
print("  - SOXL → AMEX에 상장")
print("  - AAPL → NASD(나스닥)에 상장")
print("  - IBM → NYSE(뉴욕)에 상장")
print()
print("왜 AMS로 조회하면 실패했나?")
print("  → API가 'AMS 거래소에 SOXL이 있는지' 확인")
print("  → SOXL은 AMEX에만 상장되어 있음")
print("  → '상품이 없습니다' 오류 (rt_cd=7)")
print()
print("왜 AMEX로 조회하면 성공했나?")
print("  → API가 'AMEX 거래소에 SOXL이 있는지' 확인")
print("  → SOXL은 AMEX에 상장되어 있음 ✓")
print("  → 계좌의 USD 예수금 반환 (rt_cd=0)")
print()
print("="*80)
print("결론:")
print("  - USD는 한투증권 계좌에 보관 (거래소와 무관)")
print("  - 거래소 코드는 '종목 유효성 검증'용")
print("  - 잘못된 거래소 코드 → API가 종목을 찾지 못해 실패")
print("="*80)

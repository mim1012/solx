"""
KIS API 주문/체결 파라미터 상세 검증
"""

import openpyxl

KIS_DOC_PATH = r"C:\Users\PC_1M\Downloads\[해외주식] 주문_계좌.xlsx"


def check_order_params():
    """주문 API 파라미터 확인"""

    wb = openpyxl.load_workbook(KIS_DOC_PATH, data_only=True)

    print("=" * 80)
    print("[1] 해외주식 주문 API (매수: TTTT1002U, 매도: TTTT1006U)")
    print("=" * 80)
    print("URL: /uapi/overseas-stock/v1/trading/order")
    print()

    ws = wb['해외주식 주문']

    print("[Request Body Parameters]")
    for row_idx in range(30, 45):
        row = list(ws[row_idx])
        element = row[0].value if row[0].value else ""
        korean = row[1].value if row[1].value else ""
        req = row[3].value if row[3].value else ""
        desc = row[5].value if row[5].value else ""

        if element and element not in ["Request Body", "Response Header"]:
            if len(element) < 30 and element[0].isupper():
                print(f"  {element:20s} | {korean:15s} | Required: {req:3s}")
                if desc:
                    print(f"      -> {desc[:80]}")

    print("\n" + "=" * 80)
    print("[2] 해외주식 주문체결내역 API (TTTS3035R)")
    print("=" * 80)
    print("URL: /uapi/overseas-stock/v1/trading/inquire-ccnl")
    print()

    ws2 = wb['해외주식 주문체결내역']

    print("[Request Query Parameters]")
    for row_idx in range(30, 55):
        row = list(ws2[row_idx])
        element = row[0].value if row[0].value else ""
        korean = row[1].value if row[1].value else ""
        req = row[3].value if row[3].value else ""
        desc = row[5].value if row[5].value else ""

        if element and element not in ["Request Query Parameter", "Response Header", "Response Body"]:
            if len(element) < 30 and element[0].isupper():
                print(f"  {element:20s} | {korean:15s} | Required: {req:3s}")
                if desc and len(desc) < 100:
                    print(f"      -> {desc[:80]}")

    wb.close()


if __name__ == "__main__":
    try:
        check_order_params()
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

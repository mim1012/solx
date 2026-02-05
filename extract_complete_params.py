"""
KIS API 전체 파라미터 추출 (Row 30부터)
"""

import openpyxl

KIS_DOC_PATH = r"C:\Users\PC_1M\Downloads\[해외주식] 주문_계좌.xlsx"


def extract_params_from_row(sheet_name, start_row=30, max_rows=40):
    """시트의 특정 행부터 파라미터 추출"""

    wb = openpyxl.load_workbook(KIS_DOC_PATH, data_only=True)
    ws = wb[sheet_name]

    print("=" * 80)
    print(f"[{sheet_name}] API 파라미터")
    print("=" * 80)

    # start_row부터 max_rows개 읽기
    for row_idx in range(start_row, start_row + max_rows):
        row = list(ws[row_idx])

        # 값 추출 (첫 7개 컬럼)
        values = [cell.value for cell in row[:7]]

        # 빈 행은 건너뛰기
        if all(v is None or str(v).strip() == "" for v in values):
            continue

        # 섹션 헤더나 Response가 나오면 종료
        if values[0] and isinstance(values[0], str):
            if "Response" in values[0] or "Example" in values[0]:
                break

        # 파라미터 행 출력
        element = values[0] or ""
        korean = values[1] or ""
        type_val = values[2] or ""
        required = values[3] or ""
        length = values[4] or ""
        desc = values[5] or ""

        if element and element not in ["Request Query Parameter", "Request Body", "Request Parameters"]:
            print(f"\n{element}")
            print(f"  한글명: {korean}")
            print(f"  타입: {type_val}, 필수: {required}, 길이: {length}")
            if desc:
                print(f"  설명: {desc}")

    wb.close()


if __name__ == "__main__":
    try:
        # 1. 해외주식 체결기준현재잔고
        print("\n\n")
        extract_params_from_row("해외주식 체결기준현재잔고", start_row=30, max_rows=50)

        print("\n\n")
        print("=" * 80)
        print("=" * 80)

        # 2. 해외주식 잔고
        print("\n\n")
        extract_params_from_row("해외주식 잔고", start_row=30, max_rows=50)

        print("\n\n")
        print("=" * 80)
        print("=" * 80)

        # 3. 해외주식 주문
        print("\n\n")
        extract_params_from_row("해외주식 주문", start_row=30, max_rows=50)

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

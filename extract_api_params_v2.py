"""
KIS API 파라미터 추출 v2 - 전체 행 스캔
"""

import openpyxl

KIS_DOC_PATH = r"C:\Users\PC_1M\Downloads\[해외주식] 주문_계좌.xlsx"


def scan_sheet_for_params(sheet_name, keyword="CANO"):
    """시트 전체를 스캔하여 특정 키워드 포함 행 찾기"""

    wb = openpyxl.load_workbook(KIS_DOC_PATH, data_only=True)
    ws = wb[sheet_name]

    print("=" * 80)
    print(f"[{sheet_name}] 시트 파라미터 스캔")
    print("=" * 80)

    # 전체 행 스캔
    found_params = []
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        # CANO, ACNT_PRDT_CD 등 주요 파라미터 검색
        for cell_idx, cell in enumerate(row):
            if cell and isinstance(cell, str):
                if keyword in cell.upper():
                    # 해당 행 전체 출력
                    found_params.append((row_idx, row[:10]))
                    break

    # 결과 출력
    if found_params:
        print(f"\n'{keyword}' 키워드 발견: {len(found_params)}건\n")
        for row_idx, row_data in found_params[:30]:  # 최대 30개
            print(f"Row {row_idx}: {' | '.join([str(c)[:40] if c else '' for c in row_data])}")
    else:
        print(f"\n'{keyword}' 키워드를 찾을 수 없습니다.\n")

    wb.close()


if __name__ == "__main__":
    try:
        # 1. 해외주식 체결기준현재잔고 (현재 사용 중)
        scan_sheet_for_params("해외주식 체결기준현재잔고", "CANO")
        print("\n\n")

        # 2. 해외주식 잔고
        scan_sheet_for_params("해외주식 잔고", "CANO")
        print("\n\n")

        # 3. 해외주식 주문
        scan_sheet_for_params("해외주식 주문", "CANO")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

# -*- coding: utf-8 -*-
"""
파일 인코딩 수정 및 AAPL을 SOXL로 변경
"""
import os
import sys

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

files_to_fix = [
    r"docs\자동매매 시스템 _Phoenix_ 제품 요구사항 문서 (PRD).md",
    r"docs\자동매매 시스템 _Phoenix_ 기술 요구사항 문서 (TRD).md",
    r"create_excel_template.py"
]

base_dir = r"D:\Project\SOLX"

for file_path in files_to_fix:
    full_path = os.path.join(base_dir, file_path)

    if not os.path.exists(full_path):
        print(f"[SKIP] {file_path}")
        continue

    try:
        # 여러 인코딩으로 시도
        content = None
        used_encoding = None
        for encoding in ['utf-8', 'utf-16', 'cp949', 'latin-1']:
            try:
                with open(full_path, 'r', encoding=encoding) as f:
                    content = f.read()
                used_encoding = encoding
                break
            except:
                continue

        if content is None:
            print(f"[FAIL] {file_path} - cannot read")
            continue

        # AAPL을 SOXL로 변경
        original_count = content.count('AAPL')
        content = content.replace('AAPL', 'SOXL')

        # UTF-8로 저장
        with open(full_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)

        print(f"[OK] {file_path} - {used_encoding} -> utf-8, AAPL({original_count}) -> SOXL")

    except Exception as e:
        print(f"[ERROR] {file_path}: {e}")

print("\nDone!")

#!/usr/bin/env python3
"""
설정 테스트 스크립트
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import config

def test_config():
    print("=" * 60)
    print("Phoenix Trading System v4.1 - 설정 테스트")
    print("=" * 60)
    
    # 기본 설정 테스트
    print("\n[기본 설정]")
    print(f"프로젝트 루트: {config.PROJECT_ROOT}")
    print(f"Excel 템플릿: {config.EXCEL_TEMPLATE_PATH}")
    print(f"종목: {config.TICKER}")
    print(f"거래소: {config.US_MARKET_EXCHANGE}")
    print(f"통화: {config.US_MARKET_CURRENCY}")
    print(f"API 모드: {config.KIS_API_MODE}")
    print(f"버전: {config.VERSION} ({config.VERSION_DATE})")
    
    # 환경 변수 테스트
    print("\n[환경 변수 테스트]")
    print(f"US_MARKET_TICKER: {os.getenv('US_MARKET_TICKER', '없음')}")
    print(f"US_MARKET_EXCHANGE: {os.getenv('US_MARKET_EXCHANGE', '없음')}")
    print(f"US_MARKET_CURRENCY: {os.getenv('US_MARKET_CURRENCY', '없음')}")
    print(f"KIS_API_MODE: {os.getenv('KIS_API_MODE', '없음')}")
    print(f"BALANCE_SYNC_INTERVAL: {os.getenv('BALANCE_SYNC_INTERVAL', '없음')}")
    
    # 설정 검증
    print("\n[설정 검증]")
    valid, errors = config.validate_config()
    
    if valid:
        print("✅ 모든 설정이 정상입니다.")
    else:
        print("❌ 설정 오류 발견:")
        for error in errors:
            print(f"  - {error}")
    
    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    test_config()
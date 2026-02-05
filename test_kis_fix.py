#!/usr/bin/env python3
"""
KIS API 예수금 조회 문제 해결 테스트
"""
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 환경 변수 설정 (테스트용)
os.environ["US_MARKET_TICKER"] = "SOXL"
os.environ["US_MARKET_EXCHANGE"] = "AMS"
os.environ["US_MARKET_CURRENCY"] = "USD"
os.environ["KIS_API_MODE"] = "REAL"

import config
from src.kis_rest_adapter import KisRestAdapter

def test_kis_balance():
    print("=" * 60)
    print("KIS API 예수금 조회 테스트")
    print("=" * 60)
    
    # 환경 변수 확인
    print("\n[환경 변수 확인]")
    print(f"KIS_APP_KEY: {'설정됨' if config.KIS_APP_KEY else '없음'}")
    print(f"KIS_APP_SECRET: {'설정됨' if config.KIS_APP_SECRET else '없음'}")
    print(f"KIS_ACCOUNT_NO: {'설정됨' if config.KIS_ACCOUNT_NO else '없음'}")
    
    if not config.KIS_APP_KEY or not config.KIS_APP_SECRET or not config.KIS_ACCOUNT_NO:
        print("\n❌ KIS API 자격 증명이 설정되지 않았습니다.")
        print("다음 방법 중 하나로 설정하세요:")
        print("1. .env 파일 생성 (예: cp .env.example .env)")
        print("2. 환경 변수 직접 설정")
        print("3. config.py 직접 수정")
        return False
    
    # KIS 어댑터 초기화
    print("\n[KIS API 초기화]")
    try:
        kis = KisRestAdapter(
            app_key=config.KIS_APP_KEY,
            app_secret=config.KIS_APP_SECRET,
            account_no=config.KIS_ACCOUNT_NO
        )
        print("✅ KIS 어댑터 초기화 성공")
    except Exception as e:
        print(f"❌ KIS 어댑터 초기화 실패: {e}")
        return False
    
    # 로그인 테스트
    print("\n[로그인 테스트]")
    try:
        if kis.login():
            print("✅ KIS API 로그인 성공")
        else:
            print("❌ KIS API 로그인 실패")
            return False
    except Exception as e:
        print(f"❌ 로그인 중 예외 발생: {e}")
        return False
    
    # 시세 조회 테스트
    print("\n[시세 조회 테스트]")
    try:
        ticker = os.getenv("US_MARKET_TICKER", config.TICKER)
        price_data = kis.get_overseas_price(ticker)
        
        if price_data:
            print(f"✅ {ticker} 시세 조회 성공")
            print(f"  - 현재가: ${price_data['price']:.2f}")
            print(f"  - 거래소: {price_data.get('exchange', '알 수 없음')}")
            current_price = price_data['price']
        else:
            print(f"❌ {ticker} 시세 조회 실패")
            return False
    except Exception as e:
        print(f"❌ 시세 조회 중 예외 발생: {e}")
        return False
    
    # 예수금 조회 테스트 (get_cash_balance)
    print("\n[예수금 조회 테스트 - get_cash_balance()]")
    try:
        exchange_code = os.getenv("US_MARKET_EXCHANGE", config.US_MARKET_EXCHANGE)
        print(f"사용할 거래소 코드: {exchange_code}")
        
        cash_balance = kis.get_cash_balance(
            ticker=ticker,
            price=current_price
        )
        
        print(f"✅ USD 예수금 조회 성공")
        print(f"  - 잔고: ${cash_balance:.2f}")
        print(f"  - 거래소: {exchange_code}")
        
        if cash_balance == 0.0:
            print("\n⚠️  주의: USD 예수금이 $0.00입니다.")
            print("다음 중 하나일 수 있습니다:")
            print("1. 계좌에 USD 잔고가 없음")
            print("2. 해당 계좌에서 해외주식 거래 이력이 없음")
            print("3. 거래소 코드가 잘못됨")
        else:
            print(f"\n✅ 정상적인 USD 예수금이 확인되었습니다.")
            
    except Exception as e:
        print(f"❌ 예수금 조회 중 예외 발생: {e}")
        return False
    
    # 전체 잔고 조회 테스트 (get_balance)
    print("\n[전체 잔고 조회 테스트 - get_balance()]")
    try:
        full_balance = kis.get_balance()
        print(f"✅ 전체 잔고 조회 성공")
        print(f"  - 잔고: ${full_balance:.2f}")
        
        # 두 방법 비교
        if abs(cash_balance - full_balance) > 0.01:
            print(f"\n⚠️  주의: 두 조회 방법 간 차이 발견")
            print(f"  - get_cash_balance(): ${cash_balance:.2f}")
            print(f"  - get_balance(): ${full_balance:.2f}")
            print(f"  - 차이: ${abs(cash_balance - full_balance):.2f}")
        else:
            print(f"\n✅ 두 조회 방법 결과 일치")
            
    except Exception as e:
        print(f"❌ 전체 잔고 조회 중 예외 발생: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 모든 테스트 통과")
    print("=" * 60)
    
    # 문제 해결 팁
    print("\n[문제 해결 팁]")
    print("1. 예수금이 $0.00인 경우:")
    print("   - 증권사 앱에서 USD 입금 확인")
    print("   - 해외주식 거래 권한 확인")
    print("   - 거래소 코드 확인 (SOXL → AMS)")
    print("\n2. API 오류인 경우:")
    print("   - KIS 개발자센터에서 앱키 권한 확인")
    print("   - 모의투자/실전 계정 구분 확인")
    print("   - 계좌번호 형식 확인 (12345678-01)")
    
    return True

if __name__ == "__main__":
    success = test_kis_balance()
    sys.exit(0 if success else 1)
"""환경 변수 확인 스크립트"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
env_path = Path(__file__).parent / ".env"
print(f".env 파일 경로: {env_path}")
print(f".env 파일 존재 여부: {env_path.exists()}")

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print("\n.env 파일 로드 완료")
else:
    print("\n.env 파일이 없습니다!")

# 환경 변수 확인
kis_app_key = os.getenv("KIS_APP_KEY", "")
kis_app_secret = os.getenv("KIS_APP_SECRET", "")
kis_account_no = os.getenv("KIS_ACCOUNT_NO", "")

print("\n환경 변수 확인:")
print(f"  KIS_APP_KEY 설정 여부: {'YES' if kis_app_key else 'NO'}")
if kis_app_key:
    print(f"  KIS_APP_KEY 길이: {len(kis_app_key)} 자")
    print(f"  KIS_APP_KEY 앞 4자: {kis_app_key[:4]}****")

print(f"  KIS_APP_SECRET 설정 여부: {'YES' if kis_app_secret else 'NO'}")
if kis_app_secret:
    print(f"  KIS_APP_SECRET 길이: {len(kis_app_secret)} 자")

print(f"  KIS_ACCOUNT_NO 설정 여부: {'YES' if kis_account_no else 'NO'}")
if kis_account_no:
    print(f"  KIS_ACCOUNT_NO: {kis_account_no[:4]}****{kis_account_no[-2:]}")

# 실전/모의투자 판별 (AppKey 길이로 추정)
if kis_app_key:
    if len(kis_app_key) == 36:
        print("\n계정 유형: 실전 투자 (AppKey 길이 36자)")
    else:
        print(f"\n계정 유형: 모의투자 또는 기타 (AppKey 길이 {len(kis_app_key)}자)")

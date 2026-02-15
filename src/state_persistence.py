"""
Phoenix Trading System - State Persistence
JSON 기반 상태 저장/복원 (시스템 재시작 시 포지션 유실 방지)

저장 항목: tier1_price, account_balance, total_tiers, filled_tiers
저장 시점: 매수/매도 체결 후, 시스템 종료 시
복원 시점: 시스템 초기화 시
"""

import json
import hashlib
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 프로젝트 루트 결정 (PyInstaller 빌드 호환)
import sys
if getattr(sys, 'frozen', False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent.parent

STATE_FILE = _BASE_DIR / "phoenix_state.json"
BACKUP_FILE = _BASE_DIR / "phoenix_state.backup.json"


def _compute_checksum(data: dict) -> str:
    """체크섬 계산 (checksum, saved_at 필드 제외)"""
    filtered = {k: v for k, v in data.items() if k not in ("checksum", "saved_at")}
    raw = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]


class StatePersistence:
    """JSON 기반 상태 저장/복원"""

    def __init__(self, state_file: Path = None, backup_file: Path = None):
        self.state_file = state_file or STATE_FILE
        self.backup_file = backup_file or BACKUP_FILE

    def save_state(self, data: dict) -> bool:
        """
        상태를 JSON 파일로 저장 (atomic write)

        Args:
            data: 저장할 상태 딕셔너리 (export_state() 결과)

        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 체크섬 추가
            data["checksum"] = _compute_checksum(data)
            data["saved_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            # 백업: 기존 파일이 있으면 백업으로 복사
            if self.state_file.exists():
                try:
                    import shutil
                    shutil.copy2(str(self.state_file), str(self.backup_file))
                except Exception as e:
                    logger.warning(f"백업 파일 생성 실패: {e}")

            # Atomic write: tmp 파일에 쓴 후 rename
            dir_path = self.state_file.parent
            fd, tmp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix="phoenix_state_",
                dir=str(dir_path)
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Windows: 대상 파일이 있으면 먼저 삭제 후 rename
                if self.state_file.exists():
                    os.remove(str(self.state_file))
                os.rename(tmp_path, str(self.state_file))
            except Exception:
                # tmp 파일 정리
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise

            logger.info(
                f"상태 저장 완료: {self.state_file.name} "
                f"(filled_tiers={len(data.get('filled_tiers', []))}개, "
                f"checksum={data['checksum']})"
            )
            return True

        except Exception as e:
            logger.error(f"상태 저장 실패: {e}")
            return False

    def load_state(self, ticker: str, version: str) -> Optional[dict]:
        """
        저장된 상태 로드 + 검증

        Args:
            ticker: 현재 종목 코드 (일치 확인)
            version: 현재 시스템 버전 (호환성 확인)

        Returns:
            dict: 검증된 상태 데이터, 실패 시 None
        """
        if not self.state_file.exists():
            logger.info("저장된 상태 파일 없음 (첫 실행)")
            return None

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"상태 파일 손상: {e} (초기 시작)")
            return None
        except Exception as e:
            logger.warning(f"상태 파일 읽기 실패: {e} (초기 시작)")
            return None

        # 1. 체크섬 검증
        saved_checksum = data.get("checksum", "")
        expected_checksum = _compute_checksum(data)
        if saved_checksum != expected_checksum:
            logger.warning(
                f"체크섬 불일치: 저장={saved_checksum}, 계산={expected_checksum} (초기 시작)"
            )
            return None

        # 2. ticker 일치 확인
        saved_ticker = data.get("ticker", "")
        if saved_ticker != ticker:
            logger.warning(
                f"종목 불일치: 저장={saved_ticker}, 현재={ticker} (초기 시작)"
            )
            return None

        # 3. 버전 호환성 확인 (메이저.마이너 일치)
        #    버전 불일치 시에도 tier1_price(신고가)는 보존 (포지션만 제거)
        saved_version = data.get("version", "")
        if saved_version:
            saved_parts = saved_version.split(".")[:2]
            current_parts = version.split(".")[:2]
            if saved_parts != current_parts:
                logger.warning(
                    f"버전 호환성 불일치: 저장={saved_version}, 현재={version}"
                )
                logger.info(
                    f"[HWM] tier1_price=${data.get('tier1_price', 0):.2f} 보존, "
                    f"포지션 {len(data.get('filled_tiers', []))}개는 버전 호환성 문제로 제거"
                )
                data["filled_tiers"] = []  # 포지션은 버전 호환성 문제로 제거
                # tier1_price는 보존하여 반환

        # 4. 필수 필드 확인
        required_fields = ["tier1_price", "total_tiers", "filled_tiers"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"필수 필드 누락: {field} (초기 시작)")
                return None

        filled_count = len(data.get("filled_tiers", []))
        saved_at = data.get("saved_at", "알 수 없음")
        logger.info(
            f"상태 복원 로드: {self.state_file.name} "
            f"(저장 시각={saved_at}, tier1=${data['tier1_price']:.2f}, "
            f"filled_tiers={filled_count}개)"
        )
        return data

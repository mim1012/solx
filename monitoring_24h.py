"""
Phoenix 자동매매 시스템 24시간 모니터링 스크립트

1분마다 시스템 상태를 체크하고 JSON Lines 형식으로 기록합니다.
"""

import psutil
import time
import json
import os
from datetime import datetime


def check_system_health():
    """
    시스템 상태 체크

    Returns:
        dict: 시스템 상태 정보
    """
    process_name = "python.exe"
    phoenix_processes = []

    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'create_time']):
        try:
            if proc.info['name'] == process_name:
                # Phoenix 프로세스인지 확인 (main.py 실행 중인 프로세스)
                cmdline = proc.cmdline()
                if any('main.py' in arg for arg in cmdline):
                    phoenix_processes.append({
                        "pid": proc.info['pid'],
                        "memory_mb": round(proc.info['memory_info'].rss / 1024 / 1024, 2),
                        "cpu_percent": proc.info['cpu_percent'],
                        "uptime_hours": round((time.time() - proc.info['create_time']) / 3600, 2)
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if phoenix_processes:
        # 메모리 사용량이 가장 큰 프로세스 선택 (Phoenix 메인 프로세스)
        main_process = max(phoenix_processes, key=lambda x: x['memory_mb'])

        return {
            "timestamp": datetime.now().isoformat(),
            "status": "running",
            "pid": main_process["pid"],
            "memory_mb": main_process["memory_mb"],
            "cpu_percent": main_process["cpu_percent"],
            "uptime_hours": main_process["uptime_hours"],
            "total_processes": len(phoenix_processes)
        }
    else:
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "not_running",
            "pid": None,
            "memory_mb": 0,
            "cpu_percent": 0,
            "uptime_hours": 0,
            "total_processes": 0
        }


def check_log_files():
    """
    로그 파일 크기 및 개수 확인

    Returns:
        dict: 로그 파일 정보
    """
    logs_dir = "logs"

    if not os.path.exists(logs_dir):
        return {
            "total_size_mb": 0,
            "file_count": 0,
            "latest_log": None
        }

    total_size = 0
    log_files = []

    for filename in os.listdir(logs_dir):
        if filename.endswith('.log'):
            filepath = os.path.join(logs_dir, filename)
            size = os.path.getsize(filepath)
            total_size += size
            log_files.append({
                "name": filename,
                "size_mb": round(size / 1024 / 1024, 2),
                "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
            })

    latest_log = max(log_files, key=lambda x: x['modified']) if log_files else None

    return {
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "file_count": len(log_files),
        "latest_log": latest_log['name'] if latest_log else None
    }


def check_excel_file(excel_path="phoenix_grid_template_v3.xlsx"):
    """
    Excel 파일 존재 여부 및 크기 확인

    Returns:
        dict: Excel 파일 정보
    """
    if os.path.exists(excel_path):
        size = os.path.getsize(excel_path)
        modified = datetime.fromtimestamp(os.path.getmtime(excel_path))

        # 마지막 수정 시간이 5초 이상 경과했으면 업데이트 중지 의심
        time_since_update = (datetime.now() - modified).total_seconds()
        update_status = "recent" if time_since_update < 10 else "stale"

        return {
            "exists": True,
            "size_mb": round(size / 1024 / 1024, 2),
            "last_modified": modified.isoformat(),
            "seconds_since_update": round(time_since_update, 1),
            "update_status": update_status
        }
    else:
        return {
            "exists": False,
            "size_mb": 0,
            "last_modified": None,
            "seconds_since_update": None,
            "update_status": "missing"
        }


def analyze_health_trend(log_file="monitoring_log.jsonl", window=10):
    """
    최근 N개 기록을 분석하여 메모리/CPU 추세 판단

    Args:
        log_file: 모니터링 로그 파일 경로
        window: 분석할 최근 기록 개수

    Returns:
        dict: 추세 분석 결과
    """
    if not os.path.exists(log_file):
        return {
            "memory_trend": "unknown",
            "cpu_trend": "unknown",
            "alert": None
        }

    # 최근 N개 기록 읽기
    records = []
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[-window:]:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if len(records) < 2:
        return {
            "memory_trend": "insufficient_data",
            "cpu_trend": "insufficient_data",
            "alert": None
        }

    # 메모리 추세 분석
    memory_values = [r['memory_mb'] for r in records if r['status'] == 'running']
    if len(memory_values) >= 2:
        memory_increase = memory_values[-1] - memory_values[0]
        memory_increase_rate = memory_increase / (len(memory_values) * 1)  # MB/분

        if memory_increase_rate > 1.0:  # 1MB/분 이상 증가
            memory_trend = "increasing_fast"
        elif memory_increase_rate > 0.5:
            memory_trend = "increasing"
        elif memory_increase_rate < -0.5:
            memory_trend = "decreasing"
        else:
            memory_trend = "stable"
    else:
        memory_trend = "unknown"

    # CPU 추세 분석
    cpu_values = [r['cpu_percent'] for r in records if r['status'] == 'running']
    if len(cpu_values) >= 2:
        avg_cpu = sum(cpu_values) / len(cpu_values)

        if avg_cpu > 50:
            cpu_trend = "high"
        elif avg_cpu > 20:
            cpu_trend = "medium"
        else:
            cpu_trend = "low"
    else:
        cpu_trend = "unknown"

    # 알림 생성
    alert = None
    if memory_trend == "increasing_fast":
        alert = "⚠️ 메모리 급격히 증가 중! 메모리 누수 의심"
    elif memory_values and memory_values[-1] > 1000:  # 1GB 초과
        alert = "🔴 메모리 1GB 초과! 즉시 확인 필요"
    elif cpu_trend == "high":
        alert = "⚠️ CPU 사용률 높음! 성능 저하 가능성"

    return {
        "memory_trend": memory_trend,
        "cpu_trend": cpu_trend,
        "avg_memory_mb": round(sum(memory_values) / len(memory_values), 2) if memory_values else 0,
        "avg_cpu_percent": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0,
        "alert": alert
    }


def main():
    """
    메인 모니터링 루프
    """
    log_file = "monitoring_log.jsonl"
    print(f"Phoenix 24시간 모니터링 시작")
    print(f"로그 파일: {log_file}")
    print(f"Ctrl+C로 종료\n")

    iteration = 0

    try:
        while True:
            iteration += 1

            # 시스템 상태 체크
            health = check_system_health()
            logs_info = check_log_files()
            excel_info = check_excel_file()

            # 추세 분석 (10분마다)
            trend = None
            if iteration % 10 == 0:
                trend = analyze_health_trend(log_file)

            # 통합 정보
            monitoring_data = {
                "iteration": iteration,
                **health,
                "logs": logs_info,
                "excel": excel_info,
                "trend": trend
            }

            # 파일에 기록 (JSON Lines 형식)
            with open(log_file, "a", encoding='utf-8') as f:
                f.write(json.dumps(monitoring_data, ensure_ascii=False) + "\n")

            # 콘솔 출력
            status_emoji = "🟢" if health['status'] == 'running' else "🔴"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {status_emoji} "
                  f"메모리: {health['memory_mb']:.1f}MB | "
                  f"CPU: {health['cpu_percent']:.1f}% | "
                  f"가동: {health['uptime_hours']:.1f}h | "
                  f"로그: {logs_info['total_size_mb']:.1f}MB | "
                  f"Excel: {excel_info['update_status']}")

            # 추세 알림 출력
            if trend and trend.get('alert'):
                print(f"  {trend['alert']}")

            # 1분 대기
            time.sleep(60)

    except KeyboardInterrupt:
        print("\n\n모니터링 종료")
        print(f"총 {iteration}회 체크 완료")

        # 최종 통계 출력
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                records = [json.loads(line) for line in f if line.strip()]

            running_records = [r for r in records if r['status'] == 'running']

            if running_records:
                max_memory = max(r['memory_mb'] for r in running_records)
                avg_memory = sum(r['memory_mb'] for r in running_records) / len(running_records)
                max_cpu = max(r['cpu_percent'] for r in running_records)
                avg_cpu = sum(r['cpu_percent'] for r in running_records) / len(running_records)

                print(f"\n📊 최종 통계:")
                print(f"  메모리: 평균 {avg_memory:.1f}MB, 최대 {max_memory:.1f}MB")
                print(f"  CPU: 평균 {avg_cpu:.1f}%, 최대 {max_cpu:.1f}%")
                print(f"  총 가동 시간: {running_records[-1]['uptime_hours']:.1f}시간")


if __name__ == "__main__":
    main()

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

DATE = "2025-08-27"   # <-- 여기만 바꾸면 됨 (YYYY-MM-DD)

# 이 파일 위치
HERE = Path(__file__).resolve()
# 런처가 collector 안에 있으면 프로젝트 루트는 한 단계 위, 아니면 현재 폴더
PROJECT_ROOT = HERE.parent.parent if HERE.parent.name == "collector" else HERE.parent

# 실행할 스크립트들(절대경로)
SCRIPTS = [
    # PROJECT_ROOT / "collector" / "step1_select_top200.py",
    PROJECT_ROOT / "collector" / "step2_koapy_filter.py",
    PROJECT_ROOT / "collector" / "step3_foreigner.py",
]

def run(script):
    print(f"\n[RUN] {script} --date {DATE}")
    # env 로도 같이 넘김(혹시 스크립트가 환경변수 읽게 해둔 경우 대비)
    env = os.environ.copy()
    env["PIPELINE_DATE"] = DATE
    # 현재 파이썬 인터프리터로 실행
    result = subprocess.run(
        [sys.executable, script, "--date", DATE],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
        text=True
    )
    if result.returncode != 0:
        raise SystemExit(f"[ERR] {script} 실패 (exit={result.returncode})")

def main():
    for sc in SCRIPTS:
        run(sc)
    print("\n[OK] 파이프라인 완료!")

if __name__ == "__main__":
    main()

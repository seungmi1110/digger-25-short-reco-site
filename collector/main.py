# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

# 기본 날짜(미지정 시 오늘 날짜로 대체됨)
DEFAULT_DATE = "2025-08-27"   # <-- 필요시 바꿔쓰기 (YYYY-MM-DD)

# 이 파일 위치
HERE = Path(__file__).resolve()
# 런처가 collector 안에 있으면 프로젝트 루트는 한 단계 위, 아니면 현재 폴더
PROJECT_ROOT = HERE.parent.parent if HERE.parent.name == "collector" else HERE.parent

# 실행할 스크립트들(절대경로)
SCRIPTS = [
    PROJECT_ROOT / "collector" / "step1_select_top200.py",
    PROJECT_ROOT / "collector" / "step2_koapy_filter.py",
    PROJECT_ROOT / "collector" / "step3_foreigner.py",
]

def parse_args_date() -> str:
    """--date(YYYY-MM-DD) > PIPELINE_DATE > DEFAULT_DATE > today 순으로 결정"""
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=None, help="YYYY-MM-DD")
    args, _ = p.parse_known_args()

    date = args.date or os.environ.get("PIPELINE_DATE") or DEFAULT_DATE
    # 포맷 검증/보정
    try:
        _ = datetime.strptime(date, "%Y-%m-%d")
    except Exception:
        date = datetime.now().strftime("%Y-%m-%d")
    return date

def run(script: Path, date: str):
    print(f"\n[RUN] {script} --date {date}")
    env = os.environ.copy()
    env["PIPELINE_DATE"] = date
    # 현재 파이썬 인터프리터로 실행
    result = subprocess.run(
        [sys.executable, str(script), "--date", date],
        cwd=str(PROJECT_ROOT / "collector"),
        env=env,
        text=True
    )
    if result.returncode != 0:
        raise SystemExit(f"[ERR] {script} 실패 (exit={result.returncode})")

def update_index_json(date: str):
    """
    public/data/index.json 갱신 + meta.json( latest / 해당 날짜 폴더 )
    구조:
      {
        "available_dates": ["2025-08-18", "2025-08-27", ...],
        "latest_run_date": "2025-08-27"
      }
    """
    data_root = PROJECT_ROOT / "public" / "data"
    data_root.mkdir(parents=True, exist_ok=True)

    # YYYY-MM-DD 폴더만 수집
    date_dirs = []
    for name in os.listdir(data_root):
        p = data_root / name
        if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", name):
            date_dirs.append(name)

    # 현재 실행 날짜가 목록에 없으면 포함시킴(방금 생성됐을 가능성)
    if date not in date_dirs:
        date_dirs.append(date)

    date_dirs = sorted(set(date_dirs))
    latest = date_dirs[-1] if date_dirs else None

    index_obj = {
        "available_dates": date_dirs,
        "latest_run_date": latest
    }

    # index.json 저장
    (data_root / "index.json").write_text(
        json.dumps(index_obj, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # meta.json 저장 (latest, 그리고 해당 날짜 폴더)
    def write_meta(path: Path, run_date: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"run_date": run_date}, ensure_ascii=False, indent=2), encoding="utf-8")

    if latest:
        write_meta(data_root / "latest" / "meta.json", latest)
    write_meta(data_root / date / "meta.json", date)

    print(f"[OK] index.json 갱신 — latest_run_date={latest}, dates={len(date_dirs)}")

def main():
    date = parse_args_date()

    for sc in SCRIPTS:
        run(sc, date)

    # === 파이프라인 종료 후 index.json/meta.json 갱신 ===
    update_index_json(date)

    print("\n[OK] 파이프라인 완료!")

if __name__ == "__main__":
    main()

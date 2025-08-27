# check_investors_step3.py
# -*- coding: utf-8 -*-

import os
import pandas as pd
from koapy import KiwoomOpenApiPlusEntrypoint
from datetime import datetime

# ====== 사용자 설정 ======
# 공통: --date 또는 환경변수 PIPELINE_DATE 받기
import argparse, os
from datetime import datetime

def get_date_arg() -> str:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--date", help="YYYY-MM-DD", default=None)
    args, _ = p.parse_known_args()
    date = args.date or os.environ.get("PIPELINE_DATE")
    if not date:
        # 기본: 오늘 날짜
        date = datetime.now().strftime("%Y-%m-%d")
    return date

date = get_date_arg()

FROMDATE = datetime.strptime(date, '%Y-%m-%d').strftime('%Y%m%d')

# ====== 경로 ======
# latest / dated 폴더
BASE_DIR = r"digger-25-short-reco-site\public\data\latest"
DATA_DIR = os.path.join(
    r"digger-25-short-reco-site\public\data",
    date
)
os.makedirs(DATA_DIR, exist_ok=True)

# 입력: latest의 1차 필터 결과
IN_FILTER1 = os.path.join(BASE_DIR, "candidates_filtered1.csv")

# 출력: 최종 추천(latest/dated)
OUT_RECO_LATEST = os.path.join(BASE_DIR, "recommendations.csv")
OUT_RECO_DATED  = os.path.join(DATA_DIR, "recommendations.csv")

# 갱신 대상: metrics_all (latest/dated)
METRICS_LATEST = os.path.join(BASE_DIR, "metrics_all.csv")
METRICS_DATED  = os.path.join(DATA_DIR, "metrics_all.csv")

# 투자자 내역 개별 저장 폴더(선택)
PER_STOCK_INV_LATEST = os.path.join(BASE_DIR, "per_stock", "investors")
PER_STOCK_INV_DATED  = os.path.join(DATA_DIR,  "per_stock", "investors")
os.makedirs(PER_STOCK_INV_LATEST, exist_ok=True)
os.makedirs(PER_STOCK_INV_DATED,  exist_ok=True)

# 결과 컬럼명
COL_FLAG = "외인기관3일연속순매도"

# ====== Kiwoom 로그인 정보 ======
credentials = {
    'user_id': 'asdf2262',
    'user_password': '990523ok',
    'cert_password': '990523ok',
    'is_simulation': True,
    'account_passwords': {'0000000000': '0000'}
}

# ====== 투자자 연속 순매도 체크 함수 ======
def check_fi_3day_netsell_and_save(ep, code: str, fromdate: str) -> bool:
    """
    외국인/기관 모두 순매도(<0)가 3일 연속인지 판단.
    조회 결과를 latest/dated 투자자 폴더에 CSV로 저장.
    """
    inputs = {
        "일자": fromdate, "종목코드": code,
        "금액수량구분": "1",  # 1: 수량
        "매매구분": "0",      # 0: 순매수
        "단위구분": "1"       # 1: 주식수
    }

    data_frames = []
    for event in ep.TransactionCall("종목별투자자기관별요청", "opt10059", "0001", inputs):
        columns = event.multi_data.names
        records = [values.values for values in event.multi_data.values]
        df = pd.DataFrame.from_records(records, columns=columns)
        data_frames.append(df)

    if not data_frames:
        return False

    data = pd.concat(data_frames, axis=0).reset_index(drop=True)

    # 원본 저장 (latest/dated 둘 다)
    for base in (PER_STOCK_INV_LATEST, PER_STOCK_INV_DATED):
        outp = os.path.join(base, f"{code}_investors.csv")
        data.to_csv(outp, index=False, encoding="utf-8-sig")

    # 수치화
    data['외국인투자자'] = pd.to_numeric(data['외국인투자자'].astype(str).str.replace(',', ''), errors='coerce')
    data['기관계']     = pd.to_numeric(data['기관계'].astype(str).str.replace(',', ''), errors='coerce')

    # 순매수 기준이므로 < 0이면 순매도
    cond = (data['외국인투자자'] < 0) & (data['기관계'] < 0)

    # "연속 3일" 체크 (데이터가 최신→과거인지/과거→최신인지에 상관없이, 연속성만 확인)
    # opt10059 결과는 일반적으로 과거→최신 순. 연속성만 확인하므로 그대로 순회.
    streak = 0
    for flag in cond:
        if bool(flag):
            streak += 1
            if streak >= 3:
                return True
        else:
            streak = 0
    return False

def main():
    # 1) 1차 필터 목록 읽기 (latest/candidates_filtered1.csv)
    df_filt1 = pd.read_csv(IN_FILTER1, encoding="utf-8-sig")
    if "종목코드" not in df_filt1.columns:
        raise KeyError("candidates_filtered1.csv 에 '종목코드' 컬럼이 없습니다.")
    df_filt1["종목코드"] = df_filt1["종목코드"].astype(str).str.zfill(6)

    # 2) 해당 리스트에 대해서만 투자자 조건 평가
    flags = []  # [{"종목코드": "005930", COL_FLAG: True/False}, ...]
    with KiwoomOpenApiPlusEntrypoint() as ep:
        ep.EnsureConnected(credentials)

        total = len(df_filt1)
        done  = 0
        for _, row in df_filt1.iterrows():
            code = row["종목코드"]
            try:
                ok = check_fi_3day_netsell_and_save(ep, code, FROMDATE)
                flags.append({"종목코드": code, COL_FLAG: bool(ok)})
                msg = "✅ 통과" if ok else "❌ 미통과"
                print(f"[{code}] {msg}")
            except Exception as e:
                print(f"[WARN] {code} 처리 오류: {e}")
                flags.append({"종목코드": code, COL_FLAG: None})
            done += 1
            if done % 5 == 0 or done == total:
                print(f"[진행] {done}/{total}")

    flags_df = pd.DataFrame(flags)

    # 3) metrics_all(latest/dated)에 컬럼 추가
    #    - candidates_filtered1에 있는 종목만 True/False 채워지고
    #    - 나머지는 None으로 둠
    for path in (METRICS_LATEST, METRICS_DATED):
        if not os.path.exists(path):
            print(f"[SKIP] metrics_all 없음 → {path}")
            continue
        met = pd.read_csv(path, encoding="utf-8-sig")
        if "종목코드" not in met.columns:
            print(f"[SKIP] '종목코드' 컬럼 없음 → {path}")
            continue
        met["종목코드"] = met["종목코드"].astype(str).str.zfill(6)

        # 기본 None으로 두고, 후보에만 값을 채움
        met[COL_FLAG] = None
        # map 으로 채우기
        map_dict = dict(zip(flags_df["종목코드"], flags_df[COL_FLAG]))
        met.loc[met["종목코드"].isin(map_dict.keys()), COL_FLAG] = met["종목코드"].map(map_dict)

        met.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[UPDATED] 투자자 컬럼 추가 → {path}")

    # 4) 최종 recommendations.csv 생성 (latest/dated)
    #    - candidates_filtered1에 투자자 컬럼 merge
    #    - 투자자 조건 True 인 종목만 필터
    df_merge = df_filt1.merge(flags_df, on="종목코드", how="left")
    df_final = df_merge.loc[df_merge[COL_FLAG] == True].reset_index(drop=True)

    df_final.to_csv(OUT_RECO_LATEST, index=False, encoding="utf-8-sig")
    df_final.to_csv(OUT_RECO_DATED,  index=False, encoding="utf-8-sig")
    print(f"[DONE] recommendations (latest) → {OUT_RECO_LATEST} (rows={len(df_final)})")
    print(f"[DONE] recommendations (dated)  → {OUT_RECO_DATED}  (rows={len(df_final)})")

if __name__ == "__main__":
    main()

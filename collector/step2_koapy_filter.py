# -*- coding: utf-8 -*-

import os
import pandas as pd
from koapy import KiwoomOpenApiPlusEntrypoint

# ====== 로그인 정보 ======
credentials = {
    'user_id': os.getenv('KIWOOM_ID'),
    'user_password': os.getenv('KIWOOM_PW'),
    'cert_password': os.getenv('KIWOOM_CERT_PW'),
    'is_simulation': True,
    'account_passwords': { os.getenv('KIWOOM_ACCT','0000000000'): os.getenv('KIWOOM_ACCT_PW') }
}

# ====== 기준 날짜(데이터 보관 폴더명) ======

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

# ====== 경로 & 임계값 ======
# 최신 데이터 폴더
BASE_DIR = r"digger-25-short-reco-site\public\data\latest"
DATA_DIR = os.path.join(
    r"digger-25-short-reco-site\public\data",
    date
)
os.makedirs(DATA_DIR, exist_ok=True)

# 입력/출력 경로
CAND_PATH = os.path.join(BASE_DIR, "candidates.csv")  # latest의 후보군 입력

# 1) Step1 전체 + 계산열
OUT_ALL          = os.path.join(BASE_DIR, "metrics_all.csv")        # latest
METRICS_ALL_DATA = os.path.join(DATA_DIR, "metrics_all.csv")        # dated

# 2) 필터 1,2 추천 리스트 (필터 통과본)
OUT_FINAL = os.path.join(BASE_DIR, "candidates_filtered1.csv")           # latest
OUT_DATA  = os.path.join(DATA_DIR, "candidates_filtered1.csv")           # dated

# 임계값
TH_SHORT_RATIO = 2.5
TH_RET14       = 20.0
TH_RSI         = 70.0

# ----- Step1: 공매도 압력 필터 -----
def filter_by_short_pressure(df: pd.DataFrame) -> pd.DataFrame:
    need = ["종목코드","공매도 비중","공매도 거래대금 증가배율","공매도 비중 증가배율"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"필수 컬럼 없음: {missing}")

    mask = (pd.to_numeric(df["공매도 비중"], errors="coerce") >= TH_SHORT_RATIO)
    out = df.loc[mask].copy()
    out["종목코드"] = out["종목코드"].astype(str).str.zfill(6)
    out.reset_index(drop=True, inplace=True)
    return out

# ----- Step2: 일봉 → 14일 수익률 & RSI(14) -----
def calc_ret14_and_rsi_from_chart(chart_data: pd.DataFrame):
    # KOApy 일봉이 최신→과거 순서라고 가정
    prices_desc = pd.to_numeric(
        chart_data["현재가"].astype(str).str.replace(",", ""),
        errors="coerce"
    ).dropna().reset_index(drop=True)

    if len(prices_desc) < 14:
        return None, None, None  # ret, rsi, rsi_series

    # 14일 수익률
    close_today = prices_desc.iloc[0]
    close_14ago = prices_desc.iloc[13]
    ret14_pct = None if close_14ago == 0 else (close_today / close_14ago - 1.0) * 100.0

    # RSI(14): 오름차순으로 계산 후 다시 내림차순으로 맞춤
    prices_asc = prices_desc.iloc[::-1].reset_index(drop=True)
    delta = prices_asc.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.rolling(window=14, min_periods=14).mean()
    avg_loss = loss.rolling(window=14, min_periods=14).mean()
    rs = avg_gain / avg_loss
    rsi_asc = 100.0 - (100.0 / (1.0 + rs))
    rsi_desc = rsi_asc.iloc[::-1].reset_index(drop=True)  # chart_data 정렬(최신→과거)에 맞춤
    rsi14_latest = float(rsi_desc.iloc[0]) if pd.notna(rsi_desc.iloc[0]) else None

    return (float(ret14_pct) if ret14_pct is not None else None), rsi14_latest, rsi_desc

def main():
    # 후보군 로드 (scraper가 UTF-8-SIG로 저장했다고 가정)
    df = pd.read_csv(CAND_PATH, encoding="utf-8-sig")
    if "종목코드" not in df.columns:
        raise KeyError("CSV에 '종목코드' 컬럼이 없습니다.")
    df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)

    # Step1
    df_step1 = filter_by_short_pressure(df)
    print(f"[Step1] 원본 {len(df)}개 → 공매도 압력 통과 {len(df_step1)}개")
    if len(df_step1) == 0:
        print("[종료] 공매도 조건 통과 종목이 없습니다.")
        return

    # Step2: ret14 / rsi 계산
    metrics_rows = []  # Step1 전체에 대한 계산치
    with KiwoomOpenApiPlusEntrypoint() as ep:
        ep.EnsureConnected(credentials)

        total2 = len(df_step1)
        done2  = 0

        for _, row in df_step1.iterrows():
            code = row["종목코드"]
            try:
                chart = ep.GetDailyStockDataAsDataFrame(code)
                if chart is None or len(chart) < 14:
                    print(f"[{code}] 일봉 데이터 부족 → 건너뜀")
                    done2 += 1
                    continue

                chart = chart.copy()
                chart["현재가_num"] = pd.to_numeric(
                    chart["현재가"].astype(str).str.replace(",", ""),
                    errors="coerce"
                )

                ret14, rsi14, _ = calc_ret14_and_rsi_from_chart(chart)

                m = row.copy()  # 기존 candidates 정보 보존
                m["ret14_pct"] = ret14
                m["rsi14"]     = rsi14
                metrics_rows.append(m)

                if ret14 is not None and rsi14 is not None:
                    print(f"[{code}] 14일 수익률: {ret14:.2f}% | RSI(14): {rsi14:.2f}")
                else:
                    print(f"[{code}] 계산 불가 (데이터 부족/NaN)")

            except Exception as e:
                print(f"[WARN] Step2 오류 ({code}): {e}")

            done2 += 1
            if done2 % 5 == 0 or done2 == total2:
                print(f"[Step2] 진행: {done2}/{total2}")

    # --- 저장 파트 ---
    if not metrics_rows:
        print("[WARN] metrics_rows 비어있음: Step2 계산 결과가 없습니다.")
        return

    metrics_df = pd.DataFrame(metrics_rows)

    # 1) metrics_all.csv : Step1 전체 + 계산열(ret14_pct, rsi14) + 기존 candidates 정보
    metrics_df.to_csv(OUT_ALL,          index=False, encoding="utf-8-sig")  # latest
    metrics_df.to_csv(METRICS_ALL_DATA, index=False, encoding="utf-8-sig")  # dated
    print(f"[SAVED] metrics_all (latest) → {OUT_ALL} (rows={len(metrics_df)})")
    print(f"[SAVED] metrics_all (dated)  → {METRICS_ALL_DATA} (rows={len(metrics_df)})")

    # 2) recommendations.csv : 필터링된 종목 (ret14_pct ≥ TH_RET14 and rsi14 ≥ TH_RSI)
    cond = (
        (metrics_df["ret14_pct"] >= TH_RET14) &
        (metrics_df["rsi14"]     >= TH_RSI)
    )
    df_reco = metrics_df.loc[cond].reset_index(drop=True)

    df_reco.to_csv(OUT_FINAL, index=False, encoding="utf-8-sig")  # latest
    df_reco.to_csv(OUT_DATA,  index=False, encoding="utf-8-sig")  # dated
    print(f"[SAVED] recommendations (latest) → {OUT_FINAL} (rows={len(df_reco)})")
    print(f"[SAVED] recommendations (dated)  → {OUT_DATA}  (rows={len(df_reco)})")

if __name__ == "__main__":
    main()

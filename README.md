
---

# 디거랩2025 — 공매도 Top200 추천 파이프라인

**하루 한 번** 로컬에서 파이프라인을 돌려 `public/data/`에 결과 CSV를 채우고, 깃헙에 푸시하면, 사이트가 최신 추천을 보여줍니다.

* 라이브 사이트: **[https://seungmi1110.github.io/digger-25-short-reco-site/](https://seungmi1110.github.io/digger-25-short-reco-site/)**
* 소스: [https://github.com/seungmi1110/digger-25-short-reco-site](https://github.com/seungmi1110/digger-25-short-reco-site)

---

## 개요

파이프라인은 3단계로 구성됩니다.

1. **step1\_select\_top200.py**

   * KRX에서 KOSPI/KOSDAQ 상위 후보 데이터를 수집 → `public/data/latest/candidates.csv` 및 날짜 폴더에 저장

2. **step2\_koapy\_filter.py**

   * KOApy(키움 API) 일봉으로 **14일 수익률 / RSI(14)** 계산
   * Step1 통과 전체 + 계산열 → `metrics_all.csv`
   * **ret14 ≥ TH\_RET14, RSI ≥ TH\_RSI** 통과본 → `candidates_filtered1.csv` (latest/날짜)

3. **step3\_foreigner.py**

   * `candidates_filtered1.csv` 대상만 **외국인+기관 3일 연속 순매도** 조건 체크
   * 결과 플래그를 `metrics_all.csv`에 열로 추가
   * 최종 통과본 → `recommendations.csv` (latest/날짜)

웹은 `index.html`이 `public/data/**/recommendations.csv`를 읽어 표로 보여줍니다.

---

## 실행 방법 (매일 1회)

### 0) 사전 준비 (필수)

* **키움증권 OpenAPI+** 사용 가능한 **계좌/인증서**가 있어야 합니다.
* **Windows + 관리자 권한**으로 개발환경 실행 (예: VSCode “관리자 모드로 실행”)

  * KOApy/COM 연동, 키움 로그인 팝업 등 권한 이슈 방지

### 1) 환경 설치

#### (A) conda 재현(권장)

```powershell
# 레포 루트
cd "C:\Users\seung\OneDrive\바탕 화면\dig_ss25_pro\digger-25-short-reco-site"

# koapy32 같은 32bit 환경 사용을 권장
conda env create -f environment.yml
conda activate koapy32
```

#### (B) pip (requirements.txt)

```powershell
pip install -r requirements.txt
```

### 2) 크리덴셜 설정

**옵션 1 – 파일 직접 수정(간단):**
`collector/step2_koapy_filter.py`, `collector/step3_foreigner.py`의 `credentials` 값을 본인 계정으로 수정

**옵션 2 – 환경변수(권장):**
아래처럼 환경변수로 설정하고 코드에서 읽도록 바꿔 쓰는 것을 추천

```powershell
setx KIWOOM_ID        "YOUR_ID"
setx KIWOOM_PW        "YOUR_PW"
setx KIWOOM_CERT_PW   "YOUR_CERT_PW"
setx KIWOOM_ACCT      "0000000000"
setx KIWOOM_ACCT_PW   "0000"
```

### 3) 파이프라인 실행

런처(순차 실행기): `collector/main.py`

```powershell
# 오늘 날짜로 실행
python collector/main.py

# 특정 날짜로 실행 (YYYY-MM-DD)
python collector/main.py --date 2025-08-27
```

> 각 스텝은 `--date` 또는 환경변수 `PIPELINE_DATE`를 받습니다.
> 실행이 끝나면 `public/data/latest/`와 `public/data/{YYYY-MM-DD}/`에 CSV가 저장됩니다.

### 4) 사이트 확인

* 로컬에서 `index.html`을 열거나
* 깃헙 푸시 후: **[https://seungmi1110.github.io/digger-25-short-reco-site/](https://seungmi1110.github.io/digger-25-short-reco-site/)** 접속

### 5) 깃헙 푸시

```powershell
git add -A
git commit -m "chore: update data for $(Get-Date -Format yyyy-MM-dd)"
git push
```

> 대용량(`per_stock` 원자료) 등은 `.gitignore`로 제외하는 것을 권장.

---

## 스케줄링(자동 실행)

**Windows 작업 스케줄러**로 매일 08:40 실행 예시:

```powershell
schtasks /Create /SC DAILY /ST 08:40 /TN "digger25_daily" `
/TR "\"C:\ProgramData\Anaconda3\envs\koapy32\python.exe\" \"C:\Users\seung\OneDrive\바탕 화면\dig_ss25_pro\digger-25-short-reco-site\collector\main.py\"" `
/RL HIGHEST
```

> 실행 후 자동 푸시까지 원하면 배치 파일에서 `git add/commit/push`를 이어서 호출하세요.

---

## 폴더 구조

```
digger-25-short-reco-site/
├─ collector/
│  ├─ main.py                  # 3단계 순차 실행 런처 ( --date 지원 )
│  ├─ step1_select_top200.py   # Step1: KRX 후보 수집 → candidates.csv
│  ├─ step2_koapy_filter.py    # Step2: ret14/RSI 계산 → metrics_all.csv, candidates_filtered1.csv
│  └─ step3_foreigner.py       # Step3: 외/기관 3일 연속 순매도 → recommendations.csv
│
├─ public/
│  └─ data/
│     ├─ latest/
│     │  ├─ candidates.csv
│     │  ├─ candidates_filtered1.csv
│     │  ├─ metrics_all.csv
│     │  ├─ recommendations.csv
│     │  └─ per_stock/            # (대용량 원자료: 업로드 제외 권장)
│     ├─ 2025-08-27/              # 날짜별 스냅샷 (히스토리)
│     │  ├─ candidates.csv
│     │  ├─ candidates_filtered1.csv
│     │  ├─ metrics_all.csv
│     │  ├─ recommendations.csv
│     │  └─ per_stock/
│     └─ index.json               # (옵션) 사이트가 날짜 목록/최신 날짜를 읽을 때 사용
│
├─ index.html                     # 프론트(추천 테이블)
├─ README.md
├─ requirements.txt
└─ environment.yml
```

---

## 데이터 파일 설명

* **candidates.csv** (latest/dated)
  Step1 결과: KRX 수집 원천(또는 정제본). 종목 메타 + 공매도 관련 지표 포함.

* **metrics\_all.csv** (latest/dated)
  Step1 통과 **전체** + 계산열

  * `ret14_pct` : 14일 수익률(%)
  * `rsi14` : RSI(14)
  * (Step3 후) `외인기관3일연속순매도` : True/False/None (후보에만 값 존재)

* **candidates\_filtered1.csv** (latest/dated)
  Step2 임계값 통과본

  * 필터: `ret14_pct ≥ TH_RET14` **AND** `rsi14 ≥ TH_RSI`

* **recommendations.csv** (latest/dated)
  최종 추천: `candidates_filtered1.csv` 중 **외국인+기관 3일 연속 순매도** 통과본

  * 웹에서 이 파일을 표시

* **per\_stock/** (latest/dated)
  디버깅/근거용 개별 종목 원자료(CSV).

  * 가격/RSI 시계열, 투자자 매매동향 등
  * **레포 용량 때문에 업로드 제외 권장**

---

## 코드 파일 설명

* `collector/main.py`

  * 세 스크립트를 순서대로 실행 (`--date YYYY-MM-DD` 지원)
  * 내부에서 `PIPELINE_DATE` 환경변수도 함께 전달

* `collector/step1_select_top200.py`

  * KRX 페이지 자동화로 `candidates.csv` 생성
  * 최신/날짜 폴더 동시 저장

* `collector/step2_koapy_filter.py`

  * `candidates.csv` 로드 → 공매도 비중 ≥ `TH_SHORT_RATIO` 로 Step1 필터
  * KOApy로 일봉 가져와 `ret14_pct`, `rsi14` 계산
  * `metrics_all.csv`(전체) + `candidates_filtered1.csv`(임계 통과본) 저장

* `collector/step3_foreigner.py`

  * `candidates_filtered1.csv` 대상만 키움 TR `opt10059`로 **외/기관** 일별 순매수/순매도 집계
  * **연속 3일 순매도** True/False 산출
  * `metrics_all.csv`에 열 추가, 최종 **`recommendations.csv`** 생성

---

## 트러블슈팅

* **키움 로그인 팝업/권한 오류** → VSCode/터미널을 **관리자 권한**으로 실행
* **인코딩 깨짐** → CSV 읽기는 `encoding="utf-8-sig"`(또는 KRX 원본은 `cp949`) 확인
* **빈 결과** → 장마감/휴장일엔 데이터가 부족할 수 있음. 날짜(`--date`)를 전날로 지정
* **대용량/푸시 실패** → `per_stock/` 등 원자료는 `.gitignore`로 제외 추천

---

## 라이선스 / 주의

* 데이터는 KRX/키움 OpenAPI+ 정책을 따르세요.
* 계정/비밀번호는 **절대 커밋 금지**. `.env` 사용 또는 로컬 환경변수로 관리하세요.

---


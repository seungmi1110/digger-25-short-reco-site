# -*- coding: utf-8 -*-

import os, time
import pandas as pd
from datetime import datetime, timedelta, timezone

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import shutil

# ===================== 설정 =====================
HEADLESS = False
START_URL = "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC02030204"

# 저장 루트 경로
DATA_ROOT = r"digger-25-short-reco-site\public\data"

# 다운로드 임시 폴더
DOWNLOAD_DIR = os.path.join(DATA_ROOT, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 테이블 로우 셀렉터(표가 떴는지 확인용)
ROW_SELECTOR = "tbody.CI-GRID-BODY-TABLE-TBODY > tr"

# 버튼 XPATH
KOSDAQ_BTN_XPATH = '//*[@id="MDCSTAT304_FORM"]/div[1]/div/table/tbody/tr[1]/td/label[2]'
SEARCH_BTN_XPATH  = '//*[@id="jsSearchButton"]'
DOWNLOAD_BTN_XPATH = '//*[@id="UNIT-WRAP0"]/div/p[2]/button[2]/img'

# 팝업 안 CSV 버튼 (시장별)
CSV_BTN_XPATH = {
    "KOSPI":  '//*[@id="ui-id-1"]/div/div[2]/a',
    "KOSDAQ": '//*[@id="ui-id-3"]/div/div[2]/a'
}

KST = timezone(timedelta(hours=9))
now_kst = lambda: datetime.now(KST)

# ===================== Selenium 드라이버 준비 =====================
opts = Options()
if HEADLESS:
    opts.add_argument("--headless=new")
prefs = {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "profile.default_content_setting_values.automatic_downloads": 1
}
opts.add_experimental_option("prefs", prefs)
opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
opts.add_argument("--window-size=1500,1000")

driver = webdriver.Chrome(options=opts)
driver.set_page_load_timeout(60)

try:
    # ===================== 페이지 열고 iframe 진입 =====================
    driver.get(START_URL)
    time.sleep(1.0)

    # trdDd(기준일 입력박스)가 들어있는 iframe을 찾아 들어감
    found_iframe = False
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for f in frames:
        driver.switch_to.default_content()
        driver.switch_to.frame(f)
        if driver.find_elements(By.ID, "trdDd"):
            found_iframe = True
            break
    if not found_iframe:
        driver.switch_to.default_content()

    wait = WebDriverWait(driver, 15)

    # 수집 결과 담을 리스트
    dfs = []

    # ===================== KOSPI 수집 =====================
    # 조회 버튼 클릭 → 표 뜰 때까지 대기
    search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, SEARCH_BTN_XPATH)))
    driver.execute_script("arguments[0].click();", search_btn)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ROW_SELECTOR)))

    # 다운로드 직전 디렉토리 스냅샷
    before = set(os.listdir(DOWNLOAD_DIR))

    # 다운로드 버튼 클릭
    dl_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, DOWNLOAD_BTN_XPATH)))
    driver.execute_script("arguments[0].click();", dl_btn)

    # 팝업 내 KOSPI CSV 버튼 클릭
    kospi_csv_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CSV_BTN_XPATH["KOSPI"])))
    driver.execute_script("arguments[0].click();", kospi_csv_btn)

    # 새 파일이 생길 때까지 대기 → .crdownload 끝날 때까지 대기 → 파일명 고정
    timeout = time.time() + 40
    kospi_save_name = "kospi.csv"
    kospi_dst_path = os.path.join(DOWNLOAD_DIR, kospi_save_name)
    while True:
        after = set(os.listdir(DOWNLOAD_DIR))
        new_files = list(after - before)
        if new_files:
            candidate = new_files[0]
            if candidate.endswith(".crdownload"):
                if time.time() > timeout:
                    raise RuntimeError("KOSPI CSV 다운로드 타임아웃(.crdownload 유지)")
                time.sleep(0.5)
                continue
            src_path = os.path.join(DOWNLOAD_DIR, candidate)
            # 기존 동일 파일 있으면 교체
            if os.path.exists(kospi_dst_path):
                os.remove(kospi_dst_path)
            os.rename(src_path, kospi_dst_path)
            break
        if time.time() > timeout:
            raise RuntimeError("KOSPI CSV 다운로드 실패(새 파일 미발견)")
        time.sleep(0.5)

    # CSV 읽기
    kospi_df = pd.read_csv(kospi_dst_path, encoding="euc-kr")
    kospi_df["market"] = "KOSPI"
    dfs.append(kospi_df)

    # ===================== KOSDAQ 수집 =====================
    # 코스닥 버튼 클릭
    kosdaq_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, KOSDAQ_BTN_XPATH)))
    driver.execute_script("arguments[0].click();", kosdaq_btn)

    # 조회 버튼 클릭 → 표 뜰 때까지 대기
    search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, SEARCH_BTN_XPATH)))
    driver.execute_script("arguments[0].click();", search_btn)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ROW_SELECTOR)))

    # 다운로드 직전 디렉토리 스냅샷
    before = set(os.listdir(DOWNLOAD_DIR))

    # 다운로드 버튼 클릭
    dl_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, DOWNLOAD_BTN_XPATH)))
    driver.execute_script("arguments[0].click();", dl_btn)

    # 팝업 내 KOSDAQ CSV 버튼 클릭
    kosdaq_csv_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CSV_BTN_XPATH["KOSDAQ"])))
    driver.execute_script("arguments[0].click();", kosdaq_csv_btn)

    # 새 파일 → .crdownload 종료 → 파일명 고정
    timeout = time.time() + 40
    kosdaq_save_name = "kosdaq.csv"
    kosdaq_dst_path = os.path.join(DOWNLOAD_DIR, kosdaq_save_name)
    while True:
        after = set(os.listdir(DOWNLOAD_DIR))
        new_files = list(after - before)
        if new_files:
            candidate = new_files[0]
            if candidate.endswith(".crdownload"):
                if time.time() > timeout:
                    raise RuntimeError("KOSDAQ CSV 다운로드 타임아웃(.crdownload 유지)")
                time.sleep(0.5)
                continue
            src_path = os.path.join(DOWNLOAD_DIR, candidate)
            if os.path.exists(kosdaq_dst_path):
                os.remove(kosdaq_dst_path)
            os.rename(src_path, kosdaq_dst_path)
            break
        if time.time() > timeout:
            raise RuntimeError("KOSDAQ CSV 다운로드 실패(새 파일 미발견)")
        time.sleep(0.5)

    # CSV 읽기
    kosdaq_df = pd.read_csv(kosdaq_dst_path, encoding="euc-kr")
    kosdaq_df["market"] = "KOSDAQ"
    dfs.append(kosdaq_df)

    # ===================== 합치고 저장 =====================
    combined = pd.concat(dfs, ignore_index=True)

    # 현재 선택된 기준일
    latest = driver.execute_script("return document.getElementById('trdDd').value;")
    source_date_iso = f"{latest[:4]}-{latest[4:6]}-{latest[6:]}"

    print(f"[OK] 기준일: {source_date_iso}, rows: {len(combined)}")

    save_dir = os.path.join(DATA_ROOT, source_date_iso)
    os.makedirs(save_dir, exist_ok=True)

    # 개별 파일 이동(덮어쓰기)
    final_kospi = os.path.join(save_dir, "kospi.csv")
    final_kosdaq = os.path.join(save_dir, "kosdaq.csv")
    if os.path.exists(final_kospi):
        os.remove(final_kospi)
    if os.path.exists(final_kosdaq):
        os.remove(final_kosdaq)
    os.replace(os.path.join(DOWNLOAD_DIR, "kospi.csv"),  final_kospi)
    os.replace(os.path.join(DOWNLOAD_DIR, "kosdaq.csv"), final_kosdaq)

    # 합친 파일 저장
    combined_path = os.path.join(save_dir, "candidates.csv")
    combined.to_csv(combined_path, index=False, encoding="utf-8-sig")
    print(f"[SAVED] {combined_path}")

    # === latest 폴더에도 동일 파일 복사 ===
    latest_dir = os.path.join(DATA_ROOT, "latest")
    os.makedirs(latest_dir, exist_ok=True)
    latest_path = os.path.join(latest_dir, "candidates.csv")
    # 기존 파일 있으면 덮어쓰기
    if os.path.exists(latest_path):
        os.remove(latest_path)
    shutil.copy2(combined_path, latest_path)
    print(f"[SAVED] {latest_path}")

finally:
    driver.quit()

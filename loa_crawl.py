from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

df = pd.read_excel("Port-MIS (Raw).xlsx")

# '선명' 컬럼에서 고유한 선박 이름 추출
ship_names = df["선명"].unique().tolist()
print(f"추출된 선박 이름: {ship_names}")

# Selenium WebDriver 설정
options = Options()
# options.add_argument("--headless")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

# ChromeDriver 경로 명시
service = Service('/opt/homebrew/bin/chromedriver')
driver = webdriver.Chrome(service=service, options=options)

# 결과 저장 리스트
ship_loa_data = []
failed_ships = []  # 크롤링 실패한 선박 리스트


# VesselFinder에서 선박별 LOA 크롤링
for ship_name in ship_names:
    try:
        # VesselFinder 검색 페이지로 이동 (띄어쓰기 포함)
        search_url = f"https://www.vesselfinder.com/vessels?name={ship_name}"
        driver.get(search_url)

        # "Size (m)" 열에서 LOA 추출 (최대 10초 대기)
        size_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//tr[td/a[contains(@href, '/vessels/details/')]]/td[5]"))
        )
        size_text = size_element.text.strip()  # 예: "280 / 40"

        # "Size (m)"에서 LOA (첫 번째 숫자) 추출
        loa = size_text.split("/")[0].strip()  # "280 / 40" -> "280"

        # 결과 저장
        ship_loa_data.append({"선명": ship_name, "LOA": float(loa) if loa.replace(".", "").isdigit() else ""})
        print(f"{ship_name}: LOA = {loa} m")

        # 요청 간 딜레이 (크롤링 방지 우회)
        time.sleep(3)

    except Exception as e:
        print(f"{ship_name} 크롤링 실패: {e}")
        ship_loa_data.append({"선명": ship_name, "LOA": ""})  # 실패 시 LOA를 공백으로 저장
        failed_ships.append(ship_name)  # 실패한 선박 이름 저장
        time.sleep(3)

# 드라이버 종료
driver.quit()

# 결과 DataFrame 생성 및 CSV 저장
result_df = pd.DataFrame(ship_loa_data)
result_df.to_csv("ship_lengths_vesselfinder.csv", index=False, encoding="utf-8-sig")

# 크롤링 실패한 선박 리스트 출력 및 CSV 저장
if failed_ships:
    print("\n크롤링 실패한 선박 목록:")
    print(failed_ships)
    failed_df = pd.DataFrame({"크롤링 실패 선박": failed_ships})
    failed_df.to_csv("failed_ships.csv", index=False, encoding="utf-8-sig")
else:
    print("\n모든 선박 크롤링 성공!")

print("크롤링 완료! 결과가 'ship_lengths_vesselfinder.csv'에 저장되었습니다.")
if failed_ships:
    print("크롤링 실패한 선박 목록은 'failed_ships.csv'에 저장되었습니다.")
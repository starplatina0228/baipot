
import pandas as pd
from crawl_hpnt import PortScheduleCrawler
from datetime import datetime, timedelta

def find_and_save_new_ships(
    start_date,
    end_date,
    existing_ships_file='ship_info.csv',
    output_csv_file='new_ships.csv'
):
    """
    Crawls ship schedules, finds ships not in the existing list,
    and saves their '선사' and '선명' to a CSV file.
    """
    print(f"Reading existing ships from {existing_ships_file}...")
    try:
        ship_info_df = pd.read_csv(existing_ships_file)
        existing_ship_names = set(ship_info_df['선명'].unique())
        print(f"Found {len(existing_ship_names)} unique existing ships.")
    except FileNotFoundError:
        print(f"Warning: {existing_ships_file} not found. Assuming no existing ships.")
        existing_ship_names = set()
    except Exception as e:
        print(f"Error reading {existing_ships_file}: {e}")
        return

    print(f"Crawling ship schedule from {start_date} to {end_date}...")
    crawler = PortScheduleCrawler()
    crawled_data = crawler.get_schedule_data(start_date, end_date, output_format='list')

    if not crawled_data:
        print("No data was crawled. Exiting.")
        # Create an empty file with headers
        pd.DataFrame(columns=['선사', '선명']).to_csv(output_csv_file, index=False, encoding='utf-8-sig')
        return

    # Create a dictionary to store {선명: 선사} to keep the associated company
    crawled_ships_dict = {ship['선명']: ship['선사'] for ship in crawled_data if '선명' in ship and '선사' in ship}
    crawled_ship_names = set(crawled_ships_dict.keys())
    print(f"Found {len(crawled_ship_names)} unique ships in the crawled data.")

    # Find the names of new ships
    new_ship_names = crawled_ship_names - existing_ship_names

    if new_ship_names:
        print(f"Found {len(new_ship_names)} new ships. Saving to {output_csv_file}...")
        # Prepare data for the CSV file
        new_ships_list = []
        for name in sorted(list(new_ship_names)):
            new_ships_list.append({
                '선사': crawled_ships_dict[name],
                '선명': name
            })
        
        # Create a DataFrame and save to CSV
        new_ships_df = pd.DataFrame(new_ships_list)
        new_ships_df.to_csv(output_csv_file, index=False, encoding='utf-8-sig')
        print(f"Successfully saved new ships to {output_csv_file}.")
    else:
        print("No new ships were found. An empty CSV file with headers will be created.")
        # Create an empty file with headers if no new ships are found
        pd.DataFrame(columns=['선사', '선명']).to_csv(output_csv_file, index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    # --- 설정 ---
    # 시작 날짜와 종료 날짜를 원하는 기간으로 변경하세요.
    # 예: 30일 전부터 오늘까지
    start_day = (datetime.now() - timedelta(days=335)).strftime('%Y-%m-%d')
    end_day = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    # --- 설정 끝 ---

    find_and_save_new_ships(start_date=start_day, end_date=end_day)

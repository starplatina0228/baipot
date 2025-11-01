import os
import shutil
from datetime import datetime, timedelta
import pandas as pd
import logging

# Import functions from other scripts
from crawl_hpnt import get_work_plan_data
from check_new_ships import find_and_save_new_ships
from lgbm import predict_work_time
from baipot_milp import run_milp_model

# --- Configuration ---
EXISTING_SHIPS_FILE = 'ship_info.csv'
LGBM_MODEL_FILE = 'best_lgbm_model.pkl' # Not directly used here, but good to note
SOURCE_GANTT_CHART_NAME = 'berth_gantt_chart.png' # Hardcoded in baipot_milp.py

def setup_logging(log_dir, date_str):
    log_file = os.path.join(log_dir, f"workflow_{date_str}.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler() # 콘솔에도 출력
        ]
    )
    return logging.getLogger(__name__)

def main_workflow():
    today = datetime.now()
    date_str = today.strftime('%Y%m%d')
    output_dir = f"results_{date_str}"

    # 1. Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    else:
        print(f"Output directory already exists: {output_dir}")
    
    logger = setup_logging(output_dir, date_str)
    logger.info(f"Starting daily berth planning workflow for {date_str}")

    # --- Step 1: Data Crawling ---
    logger.info("Step 1: Starting data crawling...")
    start_date_crawl = today.strftime('%Y-%m-%d')
    end_date_crawl = "2025-11-06"
    crawled_data_output_path = os.path.join(output_dir, f"hpnt_crawled_data_{date_str}.csv")

    try:
        df_crawled = get_work_plan_data(start_date=start_date_crawl, end_date=end_date_crawl, output_format='list')
        if df_crawled is not None and not df_crawled.empty:
            df_crawled.to_csv(crawled_data_output_path, index=False, encoding='utf-8-sig')
            logger.info(f"Crawled data saved to {crawled_data_output_path}")
        else:
            logger.warning("No data crawled or DataFrame is empty. Skipping further steps.")
            return
    except Exception as e:
        logger.error(f"Error during data crawling: {e}")
        return

    # --- Step 2: Identify Missing Ships ---
    logger.info("Step 2: Identifying new ships...")
    missing_ships_output_path = os.path.join(output_dir, f"missing_ships_{date_str}.csv")
    
    try:
        # find_and_save_new_ships는 내부적으로 크롤러를 호출하므로 동일한 날짜를 전달
        find_and_save_new_ships(
            start_date=start_date_crawl,
            end_date=end_date_crawl,
            existing_ships_file=EXISTING_SHIPS_FILE,
            output_csv_file=missing_ships_output_path
        )
        logger.info(f"New ship identification completed. Results saved to {missing_ships_output_path}")
    except Exception as e:
        logger.error(f"Error during new ship identification: {e}")
        # 이 단계에서 오류가 발생해도 다음 예측 단계는 진행될 수 있음

    # --- Step 3: Predict Work Times ---
    logger.info("Step 3: Predicting work times using LGBM model...")
    predicted_data_output_path = os.path.join(output_dir, f"work_time_predictions_{date_str}.csv")
    missing_info_log_source = 'missing_info.log' # lgbm.py는 이 파일을 루트에 작성
    missing_info_log_dest = os.path.join(output_dir, f"missing_info_{date_str}.log")

    try:
        # find_and_save_new_ships가 내부적으로 크롤링을 다시 할 수 있으므로, 예측을 위해 크롤링된 데이터를 다시 로드
        df_crawled_for_prediction = pd.read_csv(crawled_data_output_path)
        
        df_predicted = predict_work_time(df_crawled_for_prediction.copy())
        
        if df_predicted is not None and not df_predicted.empty:
            df_predicted.to_csv(predicted_data_output_path, index=False, encoding='utf-8-sig')
            logger.info(f"Work time predictions saved to {predicted_data_output_path}")
        else:
            logger.warning("Prediction resulted in an empty or None DataFrame. Skipping MILP.")
            return

        if os.path.exists(missing_info_log_source):
            shutil.move(missing_info_log_source, missing_info_log_dest)
            logger.info(f"Moved {missing_info_log_source} to {missing_info_log_dest}")

    except Exception as e:
        logger.error(f"Error during work time prediction: {e}")
        return

    # --- Step 4: Generate Berth Plan (MILP) ---
    logger.info("Step 4: Generating berth plan using MILP model...")
    berth_plan_csv_output_path = os.path.join(output_dir, f"berth_plan_{date_str}.csv")
    gantt_chart_output_path = os.path.join(output_dir, f"gantt_chart_{date_str}.png")

    try:
        # '접안예정일시' 컬럼이 datetime 형식인지 확인
        df_predicted['접안예정일시'] = pd.to_datetime(df_predicted['접안예정일시'])
        
        df_berth_plan = run_milp_model(df_predicted.copy())

        if df_berth_plan is not None and not df_berth_plan.empty:
            df_berth_plan.to_csv(berth_plan_csv_output_path, index=False, encoding='utf-8-sig')
            logger.info(f"Berth plan table saved to {berth_plan_csv_output_path}")
        else:
            logger.warning("MILP model did not return a valid berth plan.")

        if os.path.exists(SOURCE_GANTT_CHART_NAME):
            shutil.move(SOURCE_GANTT_CHART_NAME, gantt_chart_output_path)
            logger.info(f"Gantt chart moved and renamed to {gantt_chart_output_path}")
        else:
            logger.warning(f"Gantt chart '{SOURCE_GANTT_CHART_NAME}' not found. Was it generated by baipot_milp.py?")

    except Exception as e:
        logger.error(f"An error occurred during MILP model execution: {e}")
        return

    logger.info(f"Daily berth planning workflow completed for {date_str}.")

if __name__ == "__main__":
    main_workflow()

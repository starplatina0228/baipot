import time
import pandas as pd
from utils import get_work_plan_data
from utils import predict_work_time
from utils import run_milp_model
from datetime import datetime, timedelta

def main():
    """
    데이터 크롤링, 작업소요시간 예측, MILP 최적화를 수행 메인 함수

    전체 데이터 흐름:
    1. [Crawling] `crawl_hpnt.get_work_plan_data()`
       - HPNT 웹사이트에서 선박 스케줄 데이터를 크롤링하여 pandas DataFrame 형태로 수집 (`work_plan_df`)

    2. [Prediction] `lgbm.predict_work_time(work_plan_df)`
       - 크롤링된 `work_plan_df`를 받아 전처리 후, 작업소요시간을 예측
       - `lgbm_model.pkl` 모델을 사용하며, 예측 결과가 포함된 DataFrame을 반환 (`predicted_df`)

    3. [Optimization] `baipot_milp.run_milp_model(predicted_df)`
       - 작업 시간이 예측된 `predicted_df`를 Gurobi MILP 모델에 전달
       - 최적의 선석 배정 스케줄을 계산, solution_df를 생성.

    4. [Output] 최종 결과 출력
       - 최적화된 스케줄(`solution_df`)을 바탕으로 최종 출항 예정 시간(ETD)을 계산하여 출력
    """
    print("HPNT data crawlling...")
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    # start_date = '2025-11-02'
    # end_date = '2025-11-04'

    try:
        work_plan_df = get_work_plan_data(start_date, end_date)
        if work_plan_df is None:
            print("No data was crawled. Exiting.")
            return
        print(f"{len(work_plan_df)} crawled data found.")
    except Exception as e:
        print(f"error : {e}")
        return

    predicted_df = predict_work_time(work_plan_df.copy())

    if 'predicted_work_time' not in predicted_df.columns:
        print("no predicted_work_time column in predicted_df. Exiting.")
        return

    print(predicted_df[['선명', '접안예정일시', 'predicted_work_time', 'LOA']].head())

    print("\n optimizing with MILP model...")
    try:
        required_cols_for_milp = ['predicted_work_time', '접안예정일시', '선명', 'LOA']
        if not all(col in predicted_df.columns for col in required_cols_for_milp):
            print(f"parameter error : ({required_cols_for_milp})")
            return
        
        start_time = time.time()
        solution_df = run_milp_model(predicted_df)
        end_time = time.time()

        print(f"computation time : {end_time - start_time:.2f} sec")

        if solution_df is not None:
            print("\n--- ETD ---")
            start_time_ref = predicted_df['접안예정일시'].min()
            
            #'Completion_h'를 시간(h)에서 timedelta로 변환
            solution_df['etd_timedelta'] = pd.to_timedelta(solution_df['Completion_h'], unit='h')
            
            # 기준 시간에 timedelta를 더해 ETD 계산
            solution_df['ETD'] = start_time_ref + solution_df['etd_timedelta']
            
            #포맷팅
            solution_df['ETD'] = solution_df['ETD'].dt.strftime('%Y-%m-%d %H:%M')
            
            print(solution_df[['Ship', 'ETD']])

            compare_etd(solution_df, work_plan_df)

    except Exception as e:
        print(f"error : {e}")

def compare_etd(solution_df, work_plan_df):
    """
    예측된 ETD와 크롤링된 ETD를 비교하여 출력합니다.

    Args:
        solution_df (pd.DataFrame): 최적화 결과 DataFrame. 'Ship'과 'ETD' 컬럼 포함.
        work_plan_df (pd.DataFrame): 크롤링된 원본 DataFrame. '선명'과 '출항예정일시' 컬럼 포함.
    """
    # '선명'을 기준으로 두 데이터프레임 병합
    merged_df = pd.merge(solution_df, work_plan_df, left_on='Ship', right_on='선명', how='left')

    # 비교 결과 출력
    print("\n--- ETD Comparison ---")
    print(merged_df[['Ship', '출항예정일시', 'ETD']])


if __name__ == '__main__':
    main()

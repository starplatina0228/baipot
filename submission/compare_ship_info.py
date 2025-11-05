
import time
import pandas as pd
from utils import predict_work_time, run_milp_model
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pickle

def preprocess_for_prediction(df, ship_info_path):
    """
    LGBM 모델 예측을 위해 데이터를 전처리합니다.
    """
    ship_info_df = pd.read_csv(ship_info_path)
    ship_info_df['merge_key'] = ship_info_df['선사'].astype(str) + '_' + ship_info_df['선명'].str.replace(r'\s+', '', regex=True)
    ship_info_df.drop_duplicates(subset=['merge_key'], inplace=True)
    df['merge_key'] = df['선사'].astype(str) + '_' + df['선명'].str.replace(r'\s+', '', regex=True)
    
    # merge_key와 모선항차를 기반으로 병합
    df = pd.merge(df, ship_info_df[['merge_key', '총톤수', 'LOA']], on='merge_key', how='left')
    df.drop(columns=['merge_key'], inplace=True)

    # 총톤수 또는 LOA 정보가 없는 경우, 해당 선박 정보 출력 및 평균값으로 대체
    missing_info_rows = df[df['총톤수'].isnull() | df['LOA'].isnull()]
    if not missing_info_rows.empty:
        print(f"({ship_info_path}) 일부 선박의 '총톤수' 또는 'LOA' 정보가 없어 평균값으로 대체합니다.")
        # for index, row in missing_info_rows.iterrows():
        #     print(f"- 선사: {row['선사']}, 선명: {row['선명']}")
        
        # 평균값으로 결측치 대체
        df['총톤수'].fillna(df['총톤수'].mean(), inplace=True)
        df['LOA'].fillna(df['LOA'].mean(), inplace=True)

    df = df.rename(columns={'Shift': 'shift'})
    df['접안예정일시'] = pd.to_datetime(df['접안예정일시'], errors='coerce')
    df['양하'] = pd.to_numeric(df['양하'], errors='coerce').fillna(0)
    df['적하'] = pd.to_numeric(df['적하'], errors='coerce').fillna(0)
    df['양적하물량'] = df['양하'] + df['적하']

    dt_series = df['접안예정일시']
    df['입항시간'] = dt_series.dt.hour
    df['입항요일'] = dt_series.dt.dayofweek
    df['입항분기'] = dt_series.dt.quarter
    df['입항계절'] = dt_series.dt.month.map({
        1:'겨울', 2:'겨울', 3:'봄', 4:'봄', 5:'봄', 6:'여름',
        7:'여름', 8:'여름', 9:'가을', 10:'가을', 11:'가을', 12:'겨울'
    })

    # Feature-specific type conversion for the new model
    numeric_cols = ['shift', '양적하물량', '총톤수', 'LOA', '입항시간', '입항분기']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    categorical_cols = ['입항요일', '입항계절']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')
            
    return df

def predict_work_time_custom(crawled_df, ship_info_path):
    processed_df = preprocess_for_prediction(crawled_df, ship_info_path)

    with open('lgbm_weight.pkl', 'rb') as f:
        lgbm_model = pickle.load(f)

    # Features for the new model (without '선사')
    features = ['입항시간', '입항요일', '입항분기', '입항계절', '총톤수', '양적하물량', 'shift']
    
    if not all(f in processed_df.columns for f in features):
        missing_features = [f for f in features if f not in processed_df.columns]
        raise ValueError(f"missing values :  {missing_features}")

    X_predict = processed_df[features]
        
    predicted_time = lgbm_model.predict(X_predict)
    processed_df['predicted_work_time'] = predicted_time

    return processed_df

def run_scenario(date_str, ship_info_path, results_base_path):
    """지정된 시나리오(ship_info)에 따라 실험을 실행하고 결과를 반환합니다."""
    print(f"--- Running Scenario for {date_str} with {ship_info_path} ---")

    # 1. 크롤링된 데이터 파일 읽기
    output_dir = os.path.join(results_base_path, f"results_{date_str}")
    crawled_data_filename = f"hpnt_crawled_data_{date_str}.csv"
    crawled_data_path = os.path.join(output_dir, crawled_data_filename)

    if not os.path.exists(crawled_data_path):
        print(f"Crawled data file not found: {crawled_data_path}")
        return None

    work_plan_df = pd.read_csv(crawled_data_path)
    
    # 2. 작업 소요 시간 예측
    predicted_df = predict_work_time_custom(work_plan_df.copy(), ship_info_path)

    if 'predicted_work_time' not in predicted_df.columns:
        print("'predicted_work_time' column not found. Exiting.")
        return None

    # 3. MILP 최적화 실행
    try:
        solution_df_results_only = run_milp_model(predicted_df)

        if solution_df_results_only is not None and not solution_df_results_only.empty:
            solution_df = pd.merge(
                solution_df_results_only, 
                predicted_df, 
                left_on=['Ship', '모선항차'], 
                right_on=['선명', '모선항차'], 
                how='left'
            )

            start_time_ref = pd.to_datetime(predicted_df['접안예정일시'].min())
            solution_df['ETD'] = start_time_ref + pd.to_timedelta(solution_df['Completion_h'], unit='h')
            solution_df['ETD'] = solution_df['ETD'].dt.strftime('%Y-%m-%d %H:%M')
            
            return solution_df[['Ship', '모선항차', '출항예정일시', 'predicted_work_time', 'ETD']]
        else:
            print("MILP solver did not return a valid solution.")
            return None

    except Exception as e:
        print(f"An error occurred during processing: {e}")
        return None

def main():
    # 시나리오 설정
    scenarios = {
        "incomplete": {
            "ship_info_path": "ship_info_X/ship_info copy.csv",
            "results_base_path": "ship_info_X"
        },
        "complete": {
            "ship_info_path": "ship_info.csv",
            "results_base_path": "."
        }
    }

    # 날짜 설정
    dates_to_run = [
        "20251030", "20251031", "20251101", 
        "20251102", "20251103", "20251104", "20251105"
    ]

    all_results = []

    for date_str in dates_to_run:
        results_incomplete = run_scenario(date_str, scenarios['incomplete']['ship_info_path'], scenarios['incomplete']['results_base_path'])
        results_complete = run_scenario(date_str, scenarios['complete']['ship_info_path'], scenarios['complete']['results_base_path'])

        if results_incomplete is not None and results_complete is not None:
            # 결과 병합
            merged_df = pd.merge(
                results_incomplete,
                results_complete,
                on=['Ship', '모선항차'],
                suffixes=('_incomplete', '_complete')
            )
            merged_df['date'] = date_str
            all_results.append(merged_df)

    if all_results:
        final_comparison_df = pd.concat(all_results, ignore_index=True)
        
        # 컬럼 순서 정리
        final_comparison_df = final_comparison_df[[
            'date', 'Ship', '모선항차', 
            'predicted_work_time_incomplete', 'predicted_work_time_complete',
            'ETD_incomplete', 'ETD_complete'
        ]]

        output_filename = 'prediction_comparison_summary.csv'
        final_comparison_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
        print(f"\nFinal comparison results saved to {output_filename}")
        print(final_comparison_df)

if __name__ == '__main__':
    main()

import time
import pandas as pd
from datetime import datetime, timedelta
from utils import get_work_plan_data, predict_work_time, run_milp_model

def run_single_process(start_date, end_date):
    """
    한 번의 완전한 데이터 처리 사이클(크롤링, 예측, 최적화)을 실행하고 
    결과 데이터프레임을 반환합니다.
    """
    print(f"HPNT data crawling for {start_date} to {end_date}...")
    try:
        work_plan_df = get_work_plan_data(start_date, end_date)
        if work_plan_df is None or work_plan_df.empty:
            print("No data was crawled. Skipping.")
            return None
        print(f"{len(work_plan_df)} crawled data found.")
    except Exception as e:
        print(f"Crawling error: {e}")
        return None

    predicted_df = predict_work_time(work_plan_df.copy())

    if 'predicted_work_time' not in predicted_df.columns:
        print("no predicted_work_time column in predicted_df. Exiting.")
        return None

    print("Optimizing with MILP model...")
    try:
        required_cols_for_milp = ['predicted_work_time', '접안예정일시', '선명', 'LOA']
        if not all(col in predicted_df.columns for col in required_cols_for_milp):
            print(f"Parameter error: missing columns ({required_cols_for_milp})")
            return None
        
        solution_df = run_milp_model(predicted_df)

        if solution_df is not None:
            start_time_ref = predicted_df['접안예정일시'].min()
            solution_df['etd_timedelta'] = pd.to_timedelta(solution_df['Completion_h'], unit='h')
            solution_df['ETD'] = start_time_ref + solution_df['etd_timedelta']
            solution_df['ETD'] = solution_df['ETD'].dt.strftime('%Y-%m-%d %H:%M')
            
            # ETD 비교를 위해 원본 데이터와 병합
            merged_df = pd.merge(solution_df, work_plan_df, left_on=['Ship', '모선항차'], right_on=['선명', '모선항차'], how='left')
            return merged_df

    except Exception as e:
        print(f"Optimization error: {e}")
    
    return None

def run_scenario(base_date_str, total_days):
    """
    지정된 기간 동안 매일 예측을 실행하고 결과를 CSV 파일로 저장합니다.
    """
    try:
        base_date = datetime.strptime(base_date_str, '%Y-%m-%d')
    except ValueError:
        print("오류: 날짜 형식이 잘못되었습니다. 'YYYY-MM-DD' 형식으로 입력해주세요.")
        return

    final_end_date = base_date + timedelta(days=total_days - 1)
    all_results = []

    for i in range(total_days):
        current_start_date = base_date + timedelta(days=i)
        
        print(f"--- 시나리오 실행: {current_start_date.strftime('%Y-%m-%d')} ~ {final_end_date.strftime('%Y-%m-%d')} ---")
        
        result_df = run_single_process(current_start_date.strftime('%Y-%m-%d'), final_end_date.strftime('%Y-%m-%d'))
        
        if result_df is not None:
            result_df['호출일'] = current_start_date.strftime('%Y-%m-%d')
            all_results.append(result_df)

    if not all_results:
        print("처리된 결과가 없습니다.")
        return

    final_df = pd.concat(all_results, ignore_index=True)

    output_filename = f"moving_window_etd_comparison_{base_date_str}_for_{total_days}days.csv"
    final_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print(f"\n모든 시나리오 결과가 '{output_filename}' 파일로 저장되었습니다.")
    print("저장된 파일의 상위 5개 행:")
    print(final_df.head())

# if __name__ == '__main__':
#     base_date_input = '2025-02-01'
#     total_days_input = 7

#     total_days_num = int(total_days_input)
#     run_scenario(base_date_input, total_days_num)

if __name__ == '__main__':
    # 1. 실행하고 싶은 날짜 범위를 문자열로 지정합니다.
    start_date_input = '2025-02-01'
    end_date_input = '2025-02-28'
    total_days_input = 10

    # 2. 문자열 날짜를 datetime 객체로 변환합니다.
    start_date = datetime.strptime(start_date_input, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_input, '%Y-%m-%d')

    # 3. 현재 날짜를 추적할 변수를 시작 날짜로 초기화합니다.
    current_date = start_date

    # 4. while 루프를 사용하여 시작 날짜부터 종료 날짜까지 반복합니다.
    while current_date <= end_date:
        # datetime 객체를 다시 문자열('YYYY-MM-DD')로 변환하여 함수에 전달
        date_str_for_function = current_date.strftime('%Y-%m-%d')
        
        # run_scenario 함수 실행
        run_scenario(date_str_for_function, total_days_input)
        
        # 현재 날짜에 하루를 더해 다음 날짜로 넘어갑니다.
        current_date += timedelta(days=1)
        


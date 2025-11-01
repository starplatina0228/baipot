import pandas as pd
from datetime import datetime, timedelta
from utils import get_work_plan_data, predict_work_time, run_milp_model

# 분석하고 싶은 선박 및 항차 정보
TARGET_SHIP_NAME = 'AS CHRISTIANA'
TARGET_VOYAGE = 'ASCR007' # 모선항차

def debug_single_day_process(call_date_str, target_end_date_str):
    """
    특정 호출일에 대한 데이터 처리 과정을 단계별로 디버깅하고 중간 결과를 출력합니다.
    """
    print(f"\n{'='*20} 디버깅 시작: 호출일 {call_date_str} {'='*20}")

    # --- 1. 데이터 수집 ---
    print(f"\n[1] 데이터 수집 (기간: {call_date_str} ~ {target_end_date_str}) ")
    try:
        work_plan_df = get_work_plan_data(call_date_str, target_end_date_str)
        if work_plan_df is None or work_plan_df.empty:
            print("-> 데이터를 수집할 수 없습니다.")
            return
        
        target_ship_raw_data = work_plan_df[
            (work_plan_df['선명'] == TARGET_SHIP_NAME) & 
            (work_plan_df['모선항차'] == TARGET_VOYAGE)
        ]
        
        if target_ship_raw_data.empty:
            print(f"-> {TARGET_SHIP_NAME} ({TARGET_VOYAGE}) 데이터를 찾을 수 없습니다.")
        else:
            print(f"-> {TARGET_SHIP_NAME} ({TARGET_VOYAGE}) 원본 데이터:")
            print(target_ship_raw_data[['접안예정일시', '출항예정일시', '양하', '적하', 'Shift', '상태']].to_string(index=False))

    except Exception as e:
        print(f"-> 데이터 수집 중 오류: {e}")
        return

    # --- 2. ML 모델 예측 ---
    print(f"\n[2] ML 모델 작업시간 예측")
    # preprocess_for_prediction 함수는 predict_work_time 내에서 호출됨
    predicted_df = predict_work_time(work_plan_df.copy())

    target_ship_predicted_data = predicted_df[
        (predicted_df['선명'] == TARGET_SHIP_NAME) & 
        (predicted_df['모선항차'] == TARGET_VOYAGE)
    ]

    if target_ship_predicted_data.empty:
        print(f"-> {TARGET_SHIP_NAME} ({TARGET_VOYAGE}) 예측 데이터를 찾을 수 없습니다.")
    else:
        features_for_ml = ['입항시간', '입항요일', '입항분기', '입항계절', '총톤수', '양적하물량', 'shift']
        print(f"-> {TARGET_SHIP_NAME} ({TARGET_VOYAGE}) ML 모델 입력 피처:")
        print(target_ship_predicted_data[features_for_ml].to_string(index=False))
        
        predicted_time = target_ship_predicted_data['predicted_work_time'].iloc[0]
        print(f"\n-> ML 모델 예측 작업 시간: {predicted_time:.2f} 분 ({predicted_time/60:.2f} 시간)")

    # --- 3. MILP 최적화 ---
    print(f"\n[3] MILP 선석 최적화")
    try:
        solution_df = run_milp_model(predicted_df)

        if solution_df is not None:
            # ETD 계산
            start_time_ref = predicted_df['접안예정일시'].min()
            solution_df['Start_Time'] = start_time_ref + pd.to_timedelta(solution_df['Start_h'], unit='h')
            solution_df['ETD'] = start_time_ref + pd.to_timedelta(solution_df['Completion_h'], unit='h')
            solution_df.rename(columns={'Ship': '선명'}, inplace=True)

            target_ship_solution = solution_df[solution_df['선명'] == TARGET_SHIP_NAME]
            
            if target_ship_solution.empty:
                print(f"-> {TARGET_SHIP_NAME} ({TARGET_VOYAGE}) 최종 스케줄을 찾을 수 없습니다.")
            else:
                print(f"-> {TARGET_SHIP_NAME} ({TARGET_VOYAGE}) 최종 스케줄 결과:")
                final_etd = target_ship_solution['ETD'].iloc[0]
                print(f"  - 최종 계산된 ETD: {final_etd.strftime('%Y-%m-%d %H:%M')}")

    except Exception as e:
        print(f"-> 최적화 중 오류: {e}")

if __name__ == '__main__':
    # ASCR007 항차의 출항예정일은 2025-02-21 12:00 입니다.
    target_voyage_end_date = '2025-02-21'

    # 비교할 두 호출일
    call_date_1 = '2025-02-13' # D-8 (실제로는 9일전), 오차 컸던 날
    call_date_2 = '2025-02-14' # D-7 (실제로는 8일전), 오차 작아진 날

    # 각 호출일에 대해 디버깅 함수 실행
    debug_single_day_process(call_date_1, target_voyage_end_date)
    debug_single_day_process(call_date_2, target_voyage_end_date)

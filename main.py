import pandas as pd
from crawl_hpnt import get_work_plan_data
from lgbm import predict_work_time
from baipot_milp import run_milp_model
from datetime import datetime, timedelta

def main():
    """
    데이터 크롤링, 작업소요시간 예측, MILP 최적화를 수행하는 메인 파이프라인입니다.

    전체 데이터 흐름:
    1. [Crawling] `crawl_hpnt.get_work_plan_data()`
       - HPNT 웹사이트에서 선박 스케줄 데이터를 크롤링하여 pandas DataFrame 형태로 가져옵니다. (`work_plan_df`)

    2. [Prediction] `lgbm.predict_work_time(work_plan_df)`
       - 크롤링된 `work_plan_df`를 받아 전처리 후, 작업소요시간을 예측합니다.
       - `lgbm_model.pkl` 모델을 사용하며, 예측 결과가 포함된 DataFrame을 반환합니다. (`predicted_df`)

    3. [Optimization] `baipot_milp.run_milp_model(predicted_df)`
       - 작업 시간이 예측된 `predicted_df`를 Gurobi MILP 모델에 전달합니다.
       - 최적의 선석 배정 스케줄을 계산하고, Gantt 차트(`berth_gantt_chart.png`)를 생성합니다.

    4. [Output] 최종 결과 출력
       - 최적화된 스케줄(`solution_df`)을 바탕으로 최종 출항 예정 시간(ETD)을 계산하여 출력합니다.
    """
    print("1. HPNT에서 작업 계획 데이터 크롤링을 시작합니다...")
    # start_date = datetime.now().strftime('%Y-%m-%d')
    # end_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    start_date = '2025-09-18'
    end_date = '2025-09-24'

    try:
        work_plan_df = get_work_plan_data(start_date, end_date)
        if work_plan_df is None:
            print("크롤링된 데이터가 없습니다. 프로그램을 종료합니다.")
            return
        print(f"✅ {len(work_plan_df)}개의 선박 데이터를 크롤링했습니다.")
    except Exception as e:
        print(f"❌ 크롤링 중 오류 발생: {e}")
        return

    # 2. lgbm.py의 함수를 사용하여 작업소요시간 예측
    predicted_df = predict_work_time(work_plan_df.copy())

    if 'predicted_work_time' not in predicted_df.columns:
        print("❌ 예측된 작업소요시간 컬럼이 없습니다. 프로그램을 종료합니다.")
        return

    print(predicted_df[['선명', '접안예정일시', 'predicted_work_time', 'LOA']].head())

    print("\n4. Gurobi MILP 모델을 이용한 최적화를 시작합니다...")
    try:
        required_cols_for_milp = ['predicted_work_time', '접안예정일시', '선명', 'LOA']
        if not all(col in predicted_df.columns for col in required_cols_for_milp):
            print(f"❌ MILP 모델 실행에 필요한 컬럼이 부족합니다. ({required_cols_for_milp}) 프로그램 종료.")
            return

        solution_df = run_milp_model(predicted_df)

        print("✅ 최적화 완료.")

        if solution_df is not None:
            print("\n--- 최종 ETD 예측 결과 ---")
            start_time_ref = predicted_df['접안예정일시'].min()
            
            # 'Completion_h'를 시간(h)에서 timedelta로 변환
            solution_df['etd_timedelta'] = pd.to_timedelta(solution_df['Completion_h'], unit='h')
            
            # 기준 시간에 timedelta를 더해 ETD 계산
            solution_df['ETD'] = start_time_ref + solution_df['etd_timedelta']
            
            # 보기 좋게 포맷팅
            solution_df['ETD'] = solution_df['ETD'].dt.strftime('%Y-%m-%d %H:%M')
            
            print(solution_df[['Ship', 'ETD']])

    except Exception as e:
        print(f"❌ MILP 모델 실행 중 오류 발생: {e}")

if __name__ == '__main__':
    main()

import pandas as pd
import pickle
from crawl_hpnt import get_work_plan_data
from baipot_milp import run_milp_model
import lightgbm as lgb
from datetime import datetime, timedelta
import numpy as np

def preprocess_data(df):
    """
    크롤링된 데이터를 LGBM 모델 예측 및 MILP 입력을 위해 전처리합니다.
    - 총톤수 데이터 병합
    - 피처 엔지니어링 (양적하물량, 시간 관련 피처)
    - 데이터 타입 변환 (숫자, 범주, 날짜)
    """
    # --- 1. 총톤수 데이터 읽기 및 병합 ---
    try:
        tonnage_df = pd.read_csv('tonnage.csv')
        df = pd.merge(df, tonnage_df, on='선명', how='left')
        df['총톤수'].fillna(df['총톤수'].mean(), inplace=True) # 평균값으로 결측치 채우기
        print("✅ tonnage.csv에서 총톤수 정보를 병합했습니다.")
    except FileNotFoundError:
        print("⚠️ 경고: tonnage.csv 파일을 찾을 수 없습니다. '총톤수' 피처를 제외하고 진행합니다.")
        df['총톤수'] = 0 # 총톤수 컬럼이 없을 경우를 대비해 0으로 채운다

    # --- 2. 컬럼명 및 데이터 클리닝 ---
    df = df.rename(columns={'Shift': 'shift'})

    # --- 3. 데이터 타입 변환 (날짜 우선) ---
    for col in ['반입마감시한', '접안예정일시', '출항예정일시']:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # --- 4. 피처 엔지니어링 ---
    # 양하, 적하 -> 양적하물량
    df['양하'] = pd.to_numeric(df['양하'], errors='coerce').fillna(0)
    df['적하'] = pd.to_numeric(df['적하'], errors='coerce').fillna(0)
    df['양적하물량'] = df['양하'] + df['적하']

    # 시간 관련 피처 (접안예정일시 기준)
    dt_series = df['접안예정일시']
    df['입항시간'] = dt_series.dt.hour
    df['입항요일'] = dt_series.dt.dayofweek # 0:월요일, 6:일요일
    df['입항분기'] = dt_series.dt.quarter
    df['입항계절'] = dt_series.dt.month.map({1:'겨울', 2:'겨울', 3:'봄', 4:'봄', 5:'봄', 6:'여름', 
                                           7:'여름', 8:'여름', 9:'가을', 10:'가을', 11:'가을', 12:'겨울'})
    df['입항계절'].fillna('Unknown', inplace=True)

    print("✅ 시간 관련 피처 엔지니어링 완료.")

    # --- 5. 데이터 타입 변환 (나머지) ---
    numeric_cols = ['shift', 'AMP', '양적하물량', '총톤수', '입항시간']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    categorical_cols = ['선석', '선사', '모선항차', '선사항차', '선명', '항로', '상태', 
                        '입항요일', '입항분기', '입항계절']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).astype('category')

    print("✅ 데이터 전처리 완료.")
    return df

def main():
    """
    데이터 크롤링, 작업소요시간 예측, MILP 최적화를 수행하는 메인 함수
    """
    print("1. HPNT에서 작업 계획 데이터 크롤링을 시작합니다...")
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    work_plan_df = get_work_plan_data(start_date, end_date)

    if work_plan_df is None:
        print("크롤링 실패. 프로그램을 종료합니다.")
        return

    print("\n2. LGBM 모델 예측을 위한 데이터 전처리를 시작합니다...")
    processed_df = preprocess_data(work_plan_df.copy())

    print("\n3. LGBM 모델로 작업소요시간 예측을 시작합니다...")
    try:
        with open('lgbm_model.pkl', 'rb') as f:
            lgbm_model = pickle.load(f)
        print("✅ lgbm_best_model v0.6.pkl 모델 로드 완료.")

        features = ['입항시간', '입항요일', '입항분기', '입항계절', '선사', '총톤수', '양적하물량', 'shift']
        print(f"사용할 피처: {features}")

        X_predict = processed_df[features]
        predicted_time = lgbm_model.predict(X_predict)
        processed_df['predicted_work_time'] = predicted_time
        print("✅ 작업소요시간 예측 완료.")

    except FileNotFoundError:
        print("⚠️ 경고: lgbm_best_model v0.6.pkl 파일을 찾을 수 없습니다.")
        print("임시로 작업소요시간을 8~48시간 사이의 임의의 값으로 생성합니다.")
        processed_df['predicted_work_time'] = np.random.uniform(8, 48, size=len(processed_df))
    except Exception as e:
        print(f"❌ 예측 중 오류 발생: {e}")
        print("임시로 작업소요시간을 8~48시간 사이의 임의의 값으로 생성합니다.")
        processed_df['predicted_work_time'] = np.random.uniform(8, 48, size=len(processed_df))

    print(processed_df[['선명', '접안예정일시', 'predicted_work_time']].head())

    print("\n4. Gurobi MILP 모델을 이용한 최적화를 시작합니다...")
    try:
        required_cols_for_milp = ['predicted_work_time', '접안예정일시', '선명']
        if not all(col in processed_df.columns for col in required_cols_for_milp):
            print(f"❌ MILP 모델 실행에 필요한 컬럼이 부족합니다. ({required_cols_for_milp}) 프로그램 종료.")
            return

        solution_df = run_milp_model(processed_df)
        print("✅ 최적화 완료.")

        if solution_df is not None:
            print("\n--- 최종 ETD 예측 결과 ---")
            start_time_ref = processed_df['접안예정일시'].min()
            
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

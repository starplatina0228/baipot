import pandas as pd
import pickle
from crawl_hpnt import get_work_plan_data
from baipot_milp import run_milp_model
import lightgbm as lgb
from datetime import datetime

def preprocess_data(df):
    """
    크롤링된 데이터를 LGBM 모델 예측 및 MILP 입력을 위해 전처리합니다.
    - 총톤수 데이터 병합
    - 피처 엔지니어링 (양적하물량)
    - 데이터 타입 변환 (숫자, 범주, 날짜)
    """
    # --- 1. 총톤수 데이터 읽기 및 병합 ---
    try:
        tonnage_df = pd.read_csv('vessel_tonnage.csv')
        df = pd.merge(df, tonnage_df, on='선명', how='left')
        # 총톤수 정보가 없는 선박은 0 또는 평균값으로 채울 수 있습니다.
        df['총톤수'].fillna(0, inplace=True)
        print("✅ vessel_tonnage.csv에서 총톤수 정보를 병합했습니다.")
    except FileNotFoundError:
        print("⚠️ 경고: vessel_tonnage.csv 파일을 찾을 수 없습니다. '총톤수' 피처를 제외하고 진행합니다.")

    # --- 2. 컬럼명 및 데이터 클리닝 ---
    # 컬럼명에 포함된 공백이나 특수문자 제거, 소문자화
    df = df.rename(columns={'Shift': 'shift'})

    # --- 3. 피처 엔지니어링 ---
    # 양하, 적하를 숫자 타입으로 변환 (변환할 수 없는 값은 0으로 처리)
    df['양하'] = pd.to_numeric(df['양하'], errors='coerce').fillna(0)
    df['적하'] = pd.to_numeric(df['적하'], errors='coerce').fillna(0)
    
    # 양적하물량 계산
    df['양적하물량'] = df['양하'] + df['적하']

    # --- 4. 데이터 타입 변환 ---
    # 날짜/시간 컬럼 변환
    for col in ['반입마감시한', '접안예정일시', '출항예정일시']:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # 숫자형 컬럼 변환
    numeric_cols = ['shift', 'AMP', '양적하물량']
    if '총톤수' in df.columns:
        numeric_cols.append('총톤수')
        
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 범주형 컬럼 변환
    categorical_cols = ['선석', '선사', '모선항차', '선사항차', '선명', '항로', '상태']
    for col in categorical_cols:
        df[col] = df[col].astype('category')

    print("✅ 데이터 전처리 완료.")
    return df

def main():
    """
    데이터 크롤링, 작업소요시간 예측, MILP 최적화를 수행하는 메인 함수
    """
    print("1. HPNT에서 작업 계획 데이터 크롤링을 시작합니다...")
    # 크롤링 기간 설정
    start_date = "2025-07-22"
    end_date = "2025-08-25"
    
    work_plan_df = get_work_plan_data(start_date, end_date)

    if work_plan_df is None:
        print("크롤링 실패. 프로그램을 종료합니다.")
        return

    print("\n2. LGBM 모델 예측을 위한 데이터 전처리를 시작합니다...")
    processed_df = preprocess_data(work_plan_df.copy())

    print("\n3. LGBM 모델로 작업소요시간 예측을 시작합니다...")
    try:
        with open('lgbm_best_model.pkl', 'rb') as f:
            lgbm_model = pickle.load(f)
        print("lgbm_best_model.pkl 모델 로드 완료.")
    except FileNotFoundError:
        print("오류: lgbm_best_model.pkl 파일을 찾을 수 없습니다. 예측을 건너뜁니다.")
        return

    # 예측에 사용할 Feature 선택 (요청 기반)
    features = ['선석', '선사', '모선항차', '선사항차', '선명', '항로', '반입마감시한', 
                '접안예정일시', '출항예정일시', '양하', '적하', 'shift', 'AMP', '상태']
    
    # 총톤수 피처가 존재하면 추가
    if '총톤수' in processed_df.columns:
        features.append('총톤수')
        print("'총톤수'를 예측 피처에 추가합니다.")

    # 모델에 없는 피처가 데이터에 있을 수 있으므로, 모델의 피처만 사용
    model_features = lgbm_model.feature_name_
    X_predict = processed_df[model_features]

    # 예측 수행
    predicted_time = lgbm_model.predict(X_predict)
    processed_df['predicted_work_time'] = predicted_time
    print("작업소요시간 예측 완료.")
    print(processed_df[['선명', '접안예정일시', 'predicted_work_time']])

    print("\n4. Gurobi MILP 모델을 이용한 최적화를 시작합니다...")
    try:
        run_milp_model(processed_df)
        print("최적화 완료.")
    except Exception as e:
        print(f"MILP 모델 실행 중 오류 발생: {e}")

if __name__ == '__main__':
    main()

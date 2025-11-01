
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timedelta
import warnings
import logging
from crawl_hpnt_departed import get_work_plan_data

warnings.filterwarnings('ignore')

# lgbm.py 전용 로거 생성
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 핸들러 생성 및 포맷 설정
fh = logging.FileHandler('missing_info.log')
formatter = logging.Formatter('%(asctime)s - %(message)s')
fh.setFormatter(formatter)

# 로거에 핸들러 추가
if not logger.handlers:
    logger.addHandler(fh)

def preprocess_for_prediction(df):
    """
    LGBM 모델 예측을 위해 데이터를 전처리합니다.
    """
    ship_info_df = pd.read_csv('ship_info.csv')
    df['merge_key'] = df['선사'].astype(str) + '_' + df['선명'].str.replace(r'\s+', '', regex=True)
    ship_info_df['merge_key'] = ship_info_df['선사'].astype(str) + '_' + ship_info_df['선명'].str.replace(r'\s+', '', regex=True)
    ship_info_df = ship_info_df.drop_duplicates(subset='merge_key', keep='last')
    df = pd.merge(df, ship_info_df[['merge_key', '총톤수', 'LOA']], on='merge_key', how='left')
    df.drop(columns=['merge_key'], inplace=True)

    if '총톤수_x' in df.columns:
        df.rename(columns={'총톤수_x': '총톤수', 'LOA_x': 'LOA'}, inplace=True)
        df.drop(columns=['총톤수_y', 'LOA_y'], inplace=True)

    # 총톤수 또는 LOA 정보가 없는 경우, 해당 선박 정보 출력 및 평균값으로 대체
    missing_info_rows = df[df['총톤수'].isnull() | df['LOA'].isnull()]
    if not missing_info_rows.empty:
        logger.info("일부 선박의 '총톤수' 또는 'LOA' 정보가 없어 평균값으로 대체:")
        for index, row in missing_info_rows.iterrows():
            logger.info(f"- 선사: {row['선사']}, 선명: {row['선명']}")
        
        # 평균값으로 결측치 대체
        df['총톤수'].fillna(df['총톤수'].mean(), inplace=True)
        df['LOA'].fillna(df['LOA'].mean(), inplace=True)

    df = df.rename(columns={'Shift': 'shift'})
    df['접안예정일시'] = pd.to_datetime(df['접안예정일시'], errors='coerce')
    df['출항예정일시'] = pd.to_datetime(df['출항예정일시'])
    df['작업시간'] = (df['출항예정일시'] - df['접안예정일시']).dt.total_seconds() / 3600
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

def validate_model_with_ships(ship_names):
    """
    특정 선박에 대한 모델 예측을 수행합니다.
    """
    # 1. 과거 3개월 데이터 크롤링
    end_date = datetime.now()
    start_date = end_date - timedelta(days=330)
    
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    print(f"데이터 크롤링 시작: {start_date_str} ~ {end_date_str}")
    
    try:
        departed_df = get_work_plan_data(start_date=start_date_str, end_date=end_date_str)
        if departed_df.empty:
            print("크롤링된 데이터가 없습니다.")
            return
    except Exception as e:
        print(f"데이터 크롤링 중 오류 발생: {e}")
        return
        
    print(f"총 {len(departed_df)}건의 출항 데이터 수집")

    # 2. 특정 선박 데이터 필터링
    ship_names_no_space = [name.replace(' ', '') for name in ship_names]
    filtered_df = departed_df[departed_df['선명'].str.replace(' ', '').isin(ship_names_no_space)]

    if filtered_df.empty:
        print("주어진 선박에 대한 데이터를 크롤링 데이터에서 찾을 수 없습니다.")
        return

    # 3. 데이터 전처리
    processed_df = preprocess_for_prediction(filtered_df.copy())

    # 4. 모델 로드
    try:
        model = joblib.load('best_lgbm_model.pkl')
    except FileNotFoundError:
        print("모델 파일('best_lgbm_model.pkl')을 찾을 수 없습니다.")
        return

    # 5. 예측에 사용할 피처 선택
    features = ['입항시간', '입항요일', '입항분기', '입항계절', '총톤수', '양적하물량', 'shift']
    
    # Check for missing features
    missing_features = [f for f in features if f not in processed_df.columns]
    if missing_features:
        raise ValueError(f"Missing features in the processed data: {missing_features}")

    X_predict = processed_df[features]

    # 6. 예측 수행
    predictions_in_minutes = model.predict(X_predict)
    predictions_in_hours = predictions_in_minutes / 60

    # 7. 결과 출력
    result_df = pd.DataFrame({
        '선명': processed_df['선명'],
        '실제작업시간': processed_df['작업시간'],
        '예측작업시간': predictions_in_hours
    })
    result_df['시간차이'] = result_df['실제작업시간'] - result_df['예측작업시간']
    result_df['절대시간차이'] = np.abs(result_df['시간차이'])

    print("--- 예측 결과 ---")
    print(result_df)

    mae = result_df['절대시간차이'].mean()
    print(f"\n평균 절대 오차 (MAE): {mae:.2f} 시간")

    # 결과 저장
    result_df.to_csv('model_validation_results.csv', index=False, encoding='utf-8-sig')
    print("\n비교 결과를 'model_validation_results.csv' 파일로 저장했습니다.")

if __name__ == "__main__":
    # 예측을 원하는 선박 리스트
    ships_to_validate = ["HMM RUBY", "HMM HOPE", "ONE HANGZHOU BAY", "AS CHRISTIANA", "HMM AMETHYST"]
    validate_model_with_ships(ships_to_validate)

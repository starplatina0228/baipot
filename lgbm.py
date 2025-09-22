import pandas as pd
import pickle
import numpy as np
import logging

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

    # 총톤수 또는 LOA 정보가 없는 경우, 해당 선박 정보 출력 및 평균값으로 대체
    missing_info_rows = df[df['총톤수'].isnull() | df['LOA'].isnull()]
    if not missing_info_rows.empty:
        logger.info("[lgbm.py] 일부 선박의 '총톤수' 또는 'LOA' 정보가 없어 평균값으로 대체합니다:")
        for index, row in missing_info_rows.iterrows():
            logger.info(f"- 선사: {row['선사']}, 선명: {row['선명']}")
        
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
    # df['입항계절'].fillna('Unknown', inplace=True)

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

def predict_work_time(crawled_df):
    """
    크롤링된 데이터프레임을 받아 전처리 후, 작업소요시간을 예측하여 반환합니다.

    데이터 흐름:
    1. `preprocess_for_prediction(crawled_df)`를 호출하여 LGBM 모델에 필요한 형태로 데이터를 가공합니다.
       - `hpnt_tonnage_loa.csv` 파일에서 선박의 '총톤수'와 'LOA' 정보를 가져와 병합합니다.
       - 날짜/시간 관련 피처(입항시간, 요일, 분기, 계절)를 생성합니다.
       - '양적하물량' 등 모델에 사용될 피처를 계산합니다.
    2. 전처리된 데이터프레임(`processed_df`)이 생성됩니다.
    3. `lgbm_model.pkl` 파일을 로드하여 예측 모델을 준비합니다.
    4. `processed_df`에서 모델이 학습한 피처들을 선택하여 예측을 수행합니다.
    5. 예측 결과를 `processed_df`에 'predicted_work_time'이라는 새로운 컬럼으로 추가하여 반환합니다.

    Args:
        crawled_df (pd.DataFrame): `crawl_hpnt.get_work_plan_data()`를 통해 얻은, 크롤링된 원본 데이터프레임.

    Returns:
        pd.DataFrame: 원본 데이터에 'predicted_work_time' 컬럼이 추가된 데이터프레임.
                      예측 실패 시, 해당 컬럼은 임의의 값으로 채워집니다.
    """
    print("\n2. [lgbm.py] 작업소요시간 예측을 시작합니다...")
    
    processed_df = preprocess_for_prediction(crawled_df)

    try:
        with open('best_lgbm_model.pkl', 'rb') as f:
            lgbm_model = pickle.load(f)
        print("[lgbm.py] best_lgbm_model.pkl 모델 로드 완료.")

        # Features for the new model (without '선사')
        features = ['입항시간', '입항요일', '입항분기', '입항계절', '총톤수', '양적하물량', 'shift']
        
        if not all(f in processed_df.columns for f in features):
            missing_features = [f for f in features if f not in processed_df.columns]
            raise ValueError(f"예측에 필요한 피처가 전처리된 데이터에 없습니다: {missing_features}")

        X_predict = processed_df[features]
        
        # The new model does not require special handling for unseen categories,
        # as the problematic '선사' feature has been removed.
        
        predicted_time = lgbm_model.predict(X_predict)
        processed_df['predicted_work_time'] = predicted_time
        print("[lgbm.py] 작업소요시간 예측 완료.")

    except FileNotFoundError:
        print("[lgbm.py] 경고: 'lgbm_model.pkl' 파일을 찾을 수 없습니다. 임의의 값으로 대체합니다.")
        processed_df['predicted_work_time'] = np.random.uniform(8, 48, size=len(processed_df))
    except Exception as e:
        print(f"[lgbm.py] 예측 중 오류 발생: {e}")
        processed_df['predicted_work_time'] = np.random.uniform(8, 48, size=len(processed_df))

    return processed_df
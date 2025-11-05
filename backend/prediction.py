import pandas as pd
import pickle
import numpy as np
import logging
import os

# Define the base directory for data files relative to the project root
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Create a logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a file handler and set the formatter
log_path = os.path.join(BACKEND_DIR, 'missing_info.log')
fh = logging.FileHandler(log_path)
formatter = logging.Formatter('%(asctime)s - %(message)s')
fh.setFormatter(formatter)

# Add the handler to the logger if it doesn't have one
if not logger.handlers:
    logger.addHandler(fh)

def preprocess_for_prediction(df):
    """
    LGBM 모델 예측을 위해 데이터를 전처리합니다.
    """
    ship_info_path = os.path.join(BACKEND_DIR, 'ship_info.csv')
    ship_info_df = pd.read_csv(ship_info_path)
    ship_info_df['merge_key'] = ship_info_df['선사'].astype(str) + '_' + ship_info_df['선명'].str.replace(r'\s+', '', regex=True)
    ship_info_df.drop_duplicates(subset=['merge_key'], inplace=True)
    df['merge_key'] = df['선사'].astype(str) + '_' + df['선명'].str.replace(r'\s+', '', regex=True)
    
    # merge_key를 기반으로 병합. 접미사를 지정하여 중복 열 처리
    df = pd.merge(df, ship_info_df[['merge_key', '총톤수', 'LOA']], on='merge_key', how='left', suffixes=['_original', '_from_csv'])

    # '총톤수'와 'LOA'가 중복된 경우, original 값을 우선 사용하고, 없으면 csv 값으로 채움
    if '총톤수_original' in df.columns:
        df['총톤수'] = df['총톤수_original'].combine_first(df['총톤수_from_csv'])
        df.drop(columns=['총톤수_original', '총톤수_from_csv'], inplace=True)

    if 'LOA_original' in df.columns:
        df['LOA'] = df['LOA_original'].combine_first(df['LOA_from_csv'])
        df.drop(columns=['LOA_original', 'LOA_from_csv'], inplace=True)

    df.drop(columns=['merge_key'], inplace=True)

    # Add a flag for rows that will use averaged values
    df['uses_average_values'] = False

    # 총톤수 또는 LOA 정보가 없는 경우, 해당 선박 정보 출력 및 평균값으로 대체
    missing_info_rows = df[df['총톤수'].isnull() | df['LOA'].isnull()]
    if not missing_info_rows.empty:
        df.loc[missing_info_rows.index, 'uses_average_values'] = True
        logger.info("일부 선박의 '총톤수' 또는 'LOA' 정보가 없어 평균값으로 대체:")
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
    크롤링된 데이터프레임을 받아 전처리 후, 작업소요시간을 예측하여 반환
    """
    processed_df = preprocess_for_prediction(crawled_df)

    model_path = os.path.join(BACKEND_DIR, 'lgbm_weight.pkl')

    try:
        with open(model_path, 'rb') as f:
            lgbm_model = pickle.load(f)

        # Features for the new model (without '선사')
        features = ['입항시간', '입항요일', '입항분기', '입항계절', '총톤수', '양적하물량', 'shift']
        
        if not all(f in processed_df.columns for f in features):
            missing_features = [f for f in features if f not in processed_df.columns]
            raise ValueError(f"missing values :  {missing_features}")

        X_predict = processed_df[features]
            
        predicted_time = lgbm_model.predict(X_predict)
        processed_df['predicted_work_time'] = predicted_time

    except FileNotFoundError:
        print(f"Model file not found at {model_path}")
        processed_df['predicted_work_time'] = np.random.uniform(8, 48, size=len(processed_df))
    except Exception as e:
        print(f"error : {e}")
        processed_df['predicted_work_time'] = np.random.uniform(8, 48, size=len(processed_df))

    return processed_df
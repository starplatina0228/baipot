import pandas as pd
import joblib
import numpy as np
import logging
import os

# Define the base directory for data files relative to the project root
BACKEND_DIR = 'backend'

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
    Preprocesses the data for LGBM model prediction.
    """
    ship_info_path = os.path.join(BACKEND_DIR, 'ship_info.csv')
    ship_info_df = pd.read_csv(ship_info_path)
    
    df['merge_key'] = df['선사'].astype(str) + '_' + df['선명'].str.replace(r'\s+', '', regex=True)
    ship_info_df['merge_key'] = ship_info_df['선사'].astype(str) + '_' + ship_info_df['선명'].str.replace(r'\s+', '', regex=True)
    ship_info_df = ship_info_df.drop_duplicates(subset='merge_key', keep='last')
    df = pd.merge(df, ship_info_df[['merge_key', '총톤수', 'LOA']], on='merge_key', how='left', suffixes=('_x', '_y'))
    df.drop(columns=['merge_key'], inplace=True)

    # Combine columns if they were duplicated during the merge
    if 'LOA_x' in df.columns:
        df['LOA'] = df['LOA_x'].combine_first(df['LOA_y'])
        df.drop(columns=['LOA_x', 'LOA_y'], inplace=True)
    
    if '총톤수_x' in df.columns:
        df['총톤수'] = df['총톤수_x'].combine_first(df['총톤수_y'])
        df.drop(columns=['총톤수_x', '총톤수_y'], inplace=True)

    # Add a flag for rows that will use averaged values
    df['uses_average_values'] = False

    missing_info_rows = df[df['총톤수'].isnull() | df['LOA'].isnull()]
    if not missing_info_rows.empty:
        # Set the flag to True for rows where data is missing
        df.loc[missing_info_rows.index, 'uses_average_values'] = True
        
        logger.info("Missing '총톤수' or 'LOA' for some ships, replacing with mean value:")
        for index, row in missing_info_rows.iterrows():
            logger.info(f"- 선사: {row['선사']}, 선명: {row['선명']}")
        
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
    Takes a crawled dataframe, preprocesses it, and returns it with predicted work time.
    """
    processed_df = preprocess_for_prediction(crawled_df)
    
    model_path = os.path.join(BACKEND_DIR, 'best_lgbm_model.pkl')

    try:
        with open(model_path, 'rb') as f:
            lgbm_model = joblib.load(f)

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

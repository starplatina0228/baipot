import pandas as pd
import pickle
import numpy as np

def preprocess_for_prediction(df):
    """
    LGBM 모델 예측을 위해 데이터를 전처리합니다.
    """
    try:
        ship_info_df = pd.read_csv('hpnt_tonnage_loa.csv')
        df['merge_key'] = df['선명'].str.replace(r'\s+', '', regex=True)
        ship_info_df['merge_key'] = ship_info_df['선명'].str.replace(r'\s+', '', regex=True)
        ship_info_df = ship_info_df.drop_duplicates(subset='merge_key', keep='last')
        df = pd.merge(df, ship_info_df[['merge_key', '총톤수', 'LOA']], on='merge_key', how='left')
        df.drop(columns=['merge_key'], inplace=True)

        if df['총톤수'].isnull().any():
            df['총톤수'].fillna(df['총톤수'].mean(), inplace=True)
        if df['LOA'].isnull().any():
            df['LOA'].fillna(df['LOA'].mean(), inplace=True)
        print("✅ [lgbm.py] hpnt_tonnage_loa.csv에서 데이터 병합 완료.")
    except FileNotFoundError:
        print("⚠️ [lgbm.py] 경고: hpnt_tonnage_loa.csv 파일을 찾을 수 없어, 기본값으로 대체합니다.")
        df['총톤수'] = 30000
        df['LOA'] = 150

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
    df['입항계절'].fillna('Unknown', inplace=True)

    # Feature-specific type conversion for the new model
    numeric_cols = ['shift', '양적하물량', '총톤수', 'LOA', '입항시간', '입항분기']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    categorical_cols = ['입항요일', '입항계절']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')
            
    print("✅ [lgbm.py] 데이터 전처리 완료.")
    return df

def predict_work_time(crawled_df):
    """
    크롤링된 데이터프레임을 받아 전처리 후, 작업소요시간을 예측하여 반환합니다.
    """
    print("\n2. [lgbm.py] 작업소요시간 예측을 시작합니다...")
    
    processed_df = preprocess_for_prediction(crawled_df)

    try:
        with open('lgbm_model.pkl', 'rb') as f:
            lgbm_model = pickle.load(f)
        print("✅ [lgbm.py] lgbm_model.pkl 모델 로드 완료.")

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
        print("✅ [lgbm.py] 작업소요시간 예측 완료.")

    except FileNotFoundError:
        print("⚠️ [lgbm.py] 경고: 'lgbm_model.pkl' 파일을 찾을 수 없습니다. 임의의 값으로 대체합니다.")
        processed_df['predicted_work_time'] = np.random.uniform(8, 48, size=len(processed_df))
    except Exception as e:
        print(f"❌ [lgbm.py] 예측 중 오류 발생: {e}")
        processed_df['predicted_work_time'] = np.random.uniform(8, 48, size=len(processed_df))

    return processed_df
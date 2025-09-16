
import pandas as pd
import json
import pickle
import lightgbm as lgb
from datetime import datetime, timedelta

def train_lgbm_model():

    params = {
        'feature_fraction': 0.6,
        'learning_rate': 0.01,
        'max_depth': 10,
        'min_samples_leaf': 35,
        'min_split_gain': 0.8,
        'n_estimators': 1200,
        'objective': 'regression',
        'metric': 'r2',
        'verbose': -1
    }
    
    print(f"사용 피처: {features}")
    print(f"사용 하이퍼파라미터: {params}")

    model = lgb.LGBMRegressor(**params)
    model.fit(X_train, y_train)

    print("✅ 모델 훈련 완료.")

    print("\n4. 훈련된 모델을 저장합니다...")
    try:
        with open('lgbm_model.pkl', 'wb') as f:
            pickle.dump(model, f)
        print("✅ 모델이 lgbm_model.pkl 로 성공적으로 저장되었습니다.")
    except Exception as e:
        print(f"❌ 에러: 모델 저장 중 오류 발생: {e}")

if __name__ == '__main__':
    train_lgbm_model()

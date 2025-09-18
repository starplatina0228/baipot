import pandas as pd
import numpy as np
import lightgbm as lgb
from tqdm import tqdm
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib   # ← 추가

# 데이터 로드
data = pd.read_excel('HPNT.xlsx')
features = ['입항시간', '입항요일', '입항분기', '입항계절','총톤수', '양적하물량', 'shift']
target = '작업소요시간_1'

X = data[features].copy()
y = data[target].copy()

# 범주형 컬럼 지정
categorical_cols = ['입항요일', '입항계절']
for col in categorical_cols:
    X[col] = X[col].astype('category')

# train/validation 분할
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 파라미터 불러오기
df_expanded = pd.read_excel('HPNT parameters.xlsx')

# 컬럼명 숫자형 변환
for col in ['feature_fraction', 'learning_rate', 'max_depth', 'min_samples_leaf', 'min_split_gain', 'n_estimators']:
    if col in df_expanded.columns:
        df_expanded[col] = pd.to_numeric(df_expanded[col], errors='coerce')

records = []

for idx, row in tqdm(df_expanded.iterrows(), total=len(df_expanded)):
    # 모델 학습용 파라미터
    model_params = {
        'feature_fraction': float(row['feature_fraction']),
        'learning_rate': float(row['learning_rate']),
        'max_depth': int(row['max_depth']),
        'min_child_samples': int(row['min_samples_leaf']),
        'min_split_gain': float(row['min_split_gain']),
        'n_estimators': int(row['n_estimators'])
    }
    
    # 저장용 파라미터
    record_params = {
        'feature_fraction': float(row['feature_fraction']),
        'learning_rate': float(row['learning_rate']),
        'max_depth': int(row['max_depth']),
        'min_samples_leaf': int(row['min_samples_leaf']),
        'min_split_gain': float(row['min_split_gain']),
        'n_estimators': int(row['n_estimators'])
    }
    
    # 모델 학습
    model = lgb.LGBMRegressor(**model_params)
    model.fit(X_train, y_train, categorical_feature=categorical_cols)
    
    # 예측 및 지표 계산
    preds = model.predict(X_val)
    mse = mean_squared_error(y_val, preds)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_val, preds)
    
    records.append({
        'idx': idx,
        **record_params,
        'MSE': mse,
        'RMSE': rmse,
        'R2': r2
    })
    
    print(f"[{idx+1}/{len(df_expanded)}] "
          f"MSE: {mse:.6f}, RMSE: {rmse:.6f}, R2: {r2:.6f}  "
          f"params: {record_params}")

# 결과 저장
results_df = pd.DataFrame(records)
results_df.to_csv('LGBM_results v0.6.csv', index=False, float_format='%.17g')
print('\nLGBM_results v0.6.csv에 저장했습니다')

# 상위 5개 출력
top5 = results_df.sort_values('R2', ascending=False).head(5)
print('\nR2 상위 5개 결과:')
print(top5.to_string(index=False))

# 최적 파라미터 선택 후 전체 데이터로 다시 학습 → .pkl 저장
best_row = results_df.sort_values('R2', ascending=False).iloc[0]
best_params = {
    'feature_fraction': best_row['feature_fraction'],
    'learning_rate': best_row['learning_rate'],
    'max_depth': int(best_row['max_depth']),
    'min_child_samples': int(best_row['min_samples_leaf']),
    'min_split_gain': best_row['min_split_gain'],
    'n_estimators': int(best_row['n_estimators'])
}

final_model = lgb.LGBMRegressor(**best_params)
final_model.fit(X, y, categorical_feature=categorical_cols)  # 전체 데이터로 재학습

# .pkl로 저장
joblib.dump(final_model, "lgbm_best_model v0.6.pkl")
print("\n최적 모델을 전체 데이터로 학습 완료 및 lgbm_best_model v0.6.pkl로 저장했습니다")
import pandas as pd
import numpy as np
import lightgbm as lgb
import optuna
from sklearn.model_selection import train_test_split, cross_validate
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import joblib
import os

# --- 1. 데이터 준비 ---
print("데이터를 로드하고 전처리를 시작합니다...")
# 파일 경로 설정
file_path = os.path.join(os.path.dirname(__file__), 'hpnt.csv')
data = pd.read_csv(file_path)

# 피처 및 타겟 변수 정의
features = ['입항시간', '입항요일', '입항분기', '입항계절','총톤수', '양적하물량', 'shift']
target = '작업소요시간_1'

X = data[features].copy()
y = data[target].copy()

# 범주형 피처 처리
categorical_cols = ['입항요일', '입항계절']
for col in categorical_cols:
    X[col] = X[col].astype('category')

# 훈련/테스트 데이터 분할
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print("데이터 준비가 완료되었습니다.")

# --- 2. 하이퍼파라미터 튜닝 (Optuna) ---

def objective(trial):
    """Optuna가 최적화할 목적 함수"""
    # 하이퍼파라미터 탐색 공간 정의
    params = {
        'objective': 'regression_l1', # 학습 시 사용할 손실 함수
        'metric': 'rmse',             # 학습 중 모니터링할 평가지표
        'random_state': 42,
        'n_estimators': trial.suggest_int('n_estimators', 100, 1000, step=100),
        'learning_rate': trial.suggest_float('learning_rate', 1e-3, 1e-1, log=True),
        'num_leaves': trial.suggest_int('num_leaves', 20, 100),
        'max_depth': trial.suggest_int('max_depth', 3, 15),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 50),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.5, 1.0),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
        'lambda_l1': trial.suggest_float('lambda_l1', 1e-8, 10.0, log=True),
        'lambda_l2': trial.suggest_float('lambda_l2', 1e-8, 10.0, log=True),
    }

    model = lgb.LGBMRegressor(**params)

    # 교차 검증으로 여러 지표 동시 평가
    scoring = {
        'mae': 'neg_mean_absolute_error',
        'mse': 'neg_mean_squared_error',
        'r2': 'r2'
    }
    scores = cross_validate(model, X_train, y_train, cv=5, scoring=scoring)

    # 각 지표의 평균 계산
    mae = -np.mean(scores['test_mae'])
    mse = -np.mean(scores['test_mse'])
    rmse = np.sqrt(mse)
    r2 = np.mean(scores['test_r2'])

    # Optuna trial에 사용자 속성으로 모든 지표 저장
    trial.set_user_attr("MAE", mae)
    trial.set_user_attr("MSE", mse)
    trial.set_user_attr("RMSE", rmse)
    trial.set_user_attr("R2", r2)

    # 최적화 대상 지표로 R2 반환
    return r2

print("\nOptuna를 사용한 베이지안 최적화를 시작합니다 (n_trials=50)...")
# Optuna 스터디 생성 및 최적화 실행 (R2를 최대화하는 방향으로)
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50, show_progress_bar=True)

print("하이퍼파라미터 튜닝이 완료되었습니다.")

# --- 3. 결과 저장 및 분석 ---
print(f"\n최적 시도: Trial {study.best_trial.number}")
print(f"  Value (R2 Score): {study.best_trial.value:.4f}")
print("  Params: ")
for key, value in study.best_trial.params.items():
    print(f"    {key}: {value}")

# 튜닝 결과 데이터프레임으로 변환 및 저장
results_df = study.trials_dataframe()
results_df = results_df.sort_values(by='value', ascending=False)
results_output_path = os.path.join(os.path.dirname(__file__), 'optuna_tuning_results.csv')
results_df.to_csv(results_output_path, index=False)
print(f"\n튜닝 결과가 '{results_output_path}'에 저장되었습니다.")

# --- 4. 최적 모델 저장 및 평가 ---
# 최적 파라미터로 최종 모델 학습
print("최적 파라미터로 최종 모델을 학습합니다...")
final_params = study.best_trial.params
final_model = lgb.LGBMRegressor(**final_params, random_state=42, objective='regression_l1', metric='rmse')
final_model.fit(X_train, y_train, categorical_feature=categorical_cols)

# 최적 모델 저장
model_output_path = os.path.join(os.path.dirname(__file__), 'best_lgbm_model.pkl')
joblib.dump(final_model, model_output_path)
print(f"최적 모델이 '{model_output_path}'에 저장되었습니다.")

# 테스트 데이터로 최종 모델 평가
y_pred = final_model.predict(X_test)
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)

print("\n--- 최종 모델 성능 평가 (테스트 데이터) ---")
print(f"MAE: {mae:.4f}")
print(f"MSE: {mse:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R-squared: {r2:.4f}")
print("-----------------------------------------")
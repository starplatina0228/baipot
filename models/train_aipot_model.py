import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import pickle
import os
from datetime import datetime
import matplotlib.pyplot as plt
import optuna
import warnings
warnings.filterwarnings('ignore')

# CUDA 설정 및 호환성 체크
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA 버전: {torch.version.cuda}")
    print(f"PyTorch 버전: {torch.__version__}")
    
    # RTX 5090 호환성 체크
    try:
        test_tensor = torch.randn(10, 10).cuda()
        test_result = test_tensor.sum()
        device = torch.device('cuda')
        print(f"✅ CUDA 정상 작동")
    except Exception as e:
        print(f"❌ CUDA 에러 감지: {e}")
        print("CPU 모드로 전환합니다...")
        device = torch.device('cpu')
else:
    device = torch.device('cpu')

print(f"사용 중인 디바이스: {device}")

class ANNModel(nn.Module):
    def __init__(self, input_size, layer_config, dropout_rate=0.2, l1_reg=0.01, l2_reg=0.01):
        super(ANNModel, self).__init__()
        
        layers = []
        prev_size = input_size
        
        # 히든 레이어 구성
        for i, layer_size in enumerate(layer_config):
            layers.append(nn.Linear(prev_size, layer_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout_rate))
            prev_size = layer_size
        
        # 출력 레이어
        layers.append(nn.Linear(prev_size, 1))
        
        self.model = nn.Sequential(*layers)
        self.l1_reg = l1_reg
        self.l2_reg = l2_reg
    
    def forward(self, x):
        return self.model(x)
    
    def get_l1_l2_loss(self):
        l1_loss = 0
        l2_loss = 0
        for param in self.parameters():
            l1_loss += torch.sum(torch.abs(param))
            l2_loss += torch.sum(param ** 2)
        return self.l1_reg * l1_loss + self.l2_reg * l2_loss

class AdvancedHyperparameterOptimizer:
    def __init__(self, data_path='HPNT_IQR_VIF5.xlsx'):
        self.data_path = data_path
        self.X_train = None
        self.X_val = None
        self.y_train = None
        self.y_val = None
        self.scaler = StandardScaler()
        self.best_model = None
        self.best_params = None
        self.best_score = float('inf')
        self.all_results = []
        
    def load_and_preprocess_data(self):
        """데이터 로드 및 전처리"""
        print("데이터 로드 및 전처리 중...")
        
        df = pd.read_excel(self.data_path)
        print(f"원본 데이터 크기: {df.shape}")
        
        # 결측치 제거
        df = df.dropna(subset=['작업소요시간_1'])
        
        # 특성 선택
        numeric_features = [
            '입항시간', '입항월', '입항분기', '입항년도', '입항횟수',
            '총톤수', '선석', '양하', '적하', '양적하물량', 'shift'
        ]
        
        categorical_features = ['선사', '입항요일', '입항계절', 'ROUTE', '예선', '도선']
        target = '작업소요시간_1'
        
        # 수치형 특성 처리
        X_numeric = df[numeric_features].fillna(0)
        
        # 범주형 특성 처리 (원핫 인코딩)
        X_categorical = pd.DataFrame()
        for feature in categorical_features:
            if feature in df.columns:
                df[feature] = df[feature].fillna('Unknown')
                dummies = pd.get_dummies(df[feature], prefix=feature)
                X_categorical = pd.concat([X_categorical, dummies], axis=1)
        
        # 특성 결합
        X = pd.concat([X_numeric, X_categorical], axis=1)
        y = df[target].values
        
        print(f"전처리 후 특성 수: {X.shape[1]}")
        
        # 훈련/검증 분할
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # 정규화
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # 텐서로 변환
        self.X_train = torch.FloatTensor(X_train_scaled).to(device)
        self.X_val = torch.FloatTensor(X_val_scaled).to(device)
        self.y_train = torch.FloatTensor(y_train.reshape(-1, 1)).to(device)
        self.y_val = torch.FloatTensor(y_val.reshape(-1, 1)).to(device)
        
        self.input_size = X_train_scaled.shape[1]
        print(f"훈련 데이터: {self.X_train.shape}, 검증 데이터: {self.X_val.shape}")
        
    def train_model(self, config, verbose=False):
        """단일 모델 학습"""
        model = ANNModel(
            input_size=self.input_size,
            layer_config=config['layer_config'],
            dropout_rate=config['dropout_rate'],
            l1_reg=config['l1_reg'],
            l2_reg=config['l2_reg']
        ).to(device)
        
        optimizer = optim.Adam(model.parameters(), lr=config['learning_rate'])
        criterion = nn.MSELoss()
        
        train_dataset = TensorDataset(self.X_train, self.y_train)
        train_loader = DataLoader(train_dataset, batch_size=config['batch_size'], shuffle=True)
        
        best_val_loss = float('inf')
        patience = 20
        patience_counter = 0
        
        for epoch in range(config['epochs']):
            model.train()
            train_loss = 0
            
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y) + model.get_l1_l2_loss()
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
            
            # 검증
            model.eval()
            with torch.no_grad():
                val_outputs = model(self.X_val)
                val_loss = criterion(val_outputs, self.y_val).item()
            
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                best_model_state = model.state_dict().copy()
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    break
            
            if verbose and (epoch + 1) % 50 == 0:
                print(f'에포크 [{epoch+1}/{config["epochs"]}], 검증 손실: {val_loss:.4f}')
        
        # 최고 모델 상태 복원
        model.load_state_dict(best_model_state)
        
        # 최종 평가
        model.eval()
        with torch.no_grad():
            val_pred = model(self.X_val).cpu().numpy()
            val_y_np = self.y_val.cpu().numpy()
            
            val_mse = mean_squared_error(val_y_np, val_pred)
            val_mae = mean_absolute_error(val_y_np, val_pred)
            val_r2 = r2_score(val_y_np, val_pred)
        
        return model, {'val_mse': val_mse, 'val_mae': val_mae, 'val_r2': val_r2}
    
    def optuna_optimization(self, n_trials=100):
        """Optuna를 사용한 베이지안 최적화"""
        print(f"\n🔬 Optuna 베이지안 최적화 시작 ({n_trials}회 시도)...")
        
        def objective(trial):
            # 하이퍼파라미터 샘플링
            n_layers = trial.suggest_int('n_layers', 1, 4)
            
            layer_config = []
            for i in range(n_layers):
                if i == 0:
                    layer_size = trial.suggest_categorical(f'layer_{i+1}', [16, 32, 64, 128, 256])
                else:
                    prev_size = layer_config[i-1]
                    max_size = min(prev_size, 256)
                    layer_size = trial.suggest_categorical(f'layer_{i+1}', [16, 32, 64, 128, 256])
                layer_config.append(layer_size)
            
            config = {
                'layer_config': layer_config,
                'learning_rate': trial.suggest_categorical('learning_rate', [0.001, 0.01, 0.1]),
                'dropout_rate': trial.suggest_categorical('dropout_rate', [0.1, 0.2, 0.3, 0.4, 0.5]),
                'l1_reg': trial.suggest_categorical('l1_reg', [0.0001, 0.001, 0.01]),
                'l2_reg': trial.suggest_categorical('l2_reg', [0.0001, 0.001, 0.01]),
                'batch_size': trial.suggest_categorical('batch_size', [32, 64, 128]),
                'epochs': trial.suggest_categorical('epochs', [200, 300, 400, 500])
            }
            
            try:
                model, metrics = self.train_model(config)
                
                # 결과 저장
                result = {'config': config.copy(), 'metrics': metrics, 'method': 'optuna'}
                self.all_results.append(result)
                
                # 최고 모델 업데이트
                if metrics['val_mse'] < self.best_score:
                    self.best_score = metrics['val_mse']
                    self.best_params = config.copy()
                    self.best_model = model
                    print(f"🎉 새로운 최고 모델! MSE: {self.best_score:.4f}, R²: {metrics['val_r2']:.4f}")
                
                # GPU 메모리 정리
                del model
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
                
                return metrics['val_mse']
                
            except Exception as e:
                print(f"시도 실패: {e}")
                return float('inf')
        
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials)
        
        print(f"Optuna 최적화 완료! 최고 MSE: {study.best_value:.4f}")
        
    def grid_search_fast(self):
        """빠른 그리드 서치 (주요 조합만)"""
        print("\n🔍 빠른 그리드 서치 시작...")
        
        # 핵심 조합만 선택
        configs = [
            # 1 layer
            {'layer_config': [256], 'learning_rate': 0.01, 'dropout_rate': 0.2, 'l1_reg': 0.01, 'l2_reg': 0.01, 'batch_size': 64, 'epochs': 300},
            {'layer_config': [128], 'learning_rate': 0.01, 'dropout_rate': 0.2, 'l1_reg': 0.01, 'l2_reg': 0.01, 'batch_size': 32, 'epochs': 400},
            
            # 2 layers  
            {'layer_config': [256, 128], 'learning_rate': 0.01, 'dropout_rate': 0.2, 'l1_reg': 0.01, 'l2_reg': 0.01, 'batch_size': 64, 'epochs': 300},
            {'layer_config': [128, 64], 'learning_rate': 0.01, 'dropout_rate': 0.3, 'l1_reg': 0.01, 'l2_reg': 0.01, 'batch_size': 32, 'epochs': 400},
            
            # 3 layers
            {'layer_config': [128, 64, 32], 'learning_rate': 0.01, 'dropout_rate': 0.2, 'l1_reg': 0.01, 'l2_reg': 0.01, 'batch_size': 64, 'epochs': 400},
            {'layer_config': [64, 32, 16], 'learning_rate': 0.01, 'dropout_rate': 0.3, 'l1_reg': 0.01, 'l2_reg': 0.01, 'batch_size': 32, 'epochs': 500},
            
            # 4 layers
            {'layer_config': [32, 32, 16, 16], 'learning_rate': 0.01, 'dropout_rate': 0.2, 'l1_reg': 0.01, 'l2_reg': 0.01, 'batch_size': 32, 'epochs': 500},
        ]
        
        for i, config in enumerate(configs):
            print(f"그리드 서치 진행: {i+1}/{len(configs)} - {config['layer_config']}")
            
            try:
                model, metrics = self.train_model(config, verbose=True)
                
                result = {'config': config.copy(), 'metrics': metrics, 'method': 'grid_search'}
                self.all_results.append(result)
                
                if metrics['val_mse'] < self.best_score:
                    self.best_score = metrics['val_mse']
                    self.best_params = config.copy()
                    self.best_model = model
                    print(f"🎉 새로운 최고 모델! MSE: {self.best_score:.4f}")
                
                del model
                torch.cuda.empty_cache()
                
            except Exception as e:
                print(f"에러: {e}")
                continue
    
    def random_search(self, n_trials=30):
        """랜덤 서치"""
        print(f"\n🎲 랜덤 서치 시작 ({n_trials}회)...")
        
        layer_options = [
            [256], 
            [128, 256], 
            [64, 128, 256], 
            [32, 64, 128], 
            [16, 32, 64, 128]
        ]
        
        for i in range(n_trials):
            # numpy.random.choice 대신 random.choice 사용
            import random
            config = {
                'layer_config': random.choice(layer_options),
                'learning_rate': random.choice([0.001, 0.01, 0.1]),
                'dropout_rate': random.choice([0.1, 0.2, 0.3, 0.4, 0.5]),
                'l1_reg': random.choice([0.0001, 0.001, 0.01]),
                'l2_reg': random.choice([0.0001, 0.001, 0.01]),
                'batch_size': random.choice([32, 64, 128]),
                'epochs': random.choice([200, 300, 400, 500])
            }
            
            print(f"랜덤 서치: {i+1}/{n_trials}")
            
            try:
                model, metrics = self.train_model(config)
                
                result = {'config': config.copy(), 'metrics': metrics, 'method': 'random_search'}
                self.all_results.append(result)
                
                if metrics['val_mse'] < self.best_score:
                    self.best_score = metrics['val_mse']
                    self.best_params = config.copy()
                    self.best_model = model
                    print(f"🎉 새로운 최고 모델! MSE: {self.best_score:.4f}")
                
                del model
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
                
            except Exception as e:
                print(f"에러: {e}")
                continue
    
    def run_all_optimizations(self):
        """모든 최적화 방법 실행"""
        print("🚀 모든 최적화 방법 실행 시작!")
        
        # 1. 빠른 그리드 서치
        self.grid_search_fast()
        
        # 2. 랜덤 서치  
        self.random_search(30)
        
        # 3. Optuna 베이지안 최적화
        try:
            self.optuna_optimization(50)
        except ImportError:
            print("Optuna가 설치되지 않음. pip install optuna로 설치하세요.")
        except Exception as e:
            print(f"Optuna 실행 실패: {e}")
        
        self.print_final_results()
    
    def print_final_results(self):
        """최종 결과 출력"""
        if not self.all_results:
            print("결과가 없습니다.")
            return
        
        print("\n" + "="*100)
        print("🏆 최종 최적화 결과")
        print("="*100)
        
        # 결과 정렬
        sorted_results = sorted(self.all_results, key=lambda x: x['metrics']['val_mse'])
        
        print(f"\n🥇 최고 성능 모델들 (상위 10개):")
        print("-" * 100)
        
        for i, result in enumerate(sorted_results[:10]):
            config = result['config']
            metrics = result['metrics']
            method = result.get('method', 'unknown')
            
            print(f"{i+1:2d}. [{method:12s}] 레이어: {str(config['layer_config']):20s} "
                  f"MSE: {metrics['val_mse']:8.4f} "
                  f"MAE: {metrics['val_mae']:8.4f} "
                  f"R²: {metrics['val_r2']:7.4f}")
        
        print(f"\n🎯 최종 우승 모델:")
        print(f"   방법: {sorted_results[0].get('method', 'unknown')}")
        print(f"   구조: {self.best_params['layer_config']}")
        print(f"   학습률: {self.best_params['learning_rate']}")
        print(f"   드롭아웃: {self.best_params['dropout_rate']}")
        print(f"   배치크기: {self.best_params['batch_size']}")
        print(f"   에포크: {self.best_params['epochs']}")
        print(f"   성능 - MSE: {self.best_score:.4f}")
        
        # 방법별 성능 비교
        methods_performance = {}
        for result in self.all_results:
            method = result.get('method', 'unknown')
            mse = result['metrics']['val_mse']
            if method not in methods_performance:
                methods_performance[method] = []
            methods_performance[method].append(mse)
        
        print(f"\n📊 방법별 평균 성능:")
        for method, mses in methods_performance.items():
            avg_mse = np.mean(mses)
            min_mse = np.min(mses)
            print(f"   {method:15s}: 평균 MSE {avg_mse:.4f}, 최고 MSE {min_mse:.4f}")
    
    def save_best_model(self, save_dir='models'):
        """최고 모델 저장"""
        if self.best_model is None:
            print("저장할 모델이 없습니다.")
            return
        
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 모델 저장
        model_path = os.path.join(save_dir, f'best_ann_model_{timestamp}.pth')
        torch.save({
            'model_state_dict': self.best_model.state_dict(),
            'config': self.best_params,
            'scaler': self.scaler,
            'input_size': self.input_size,
            'best_score': self.best_score
        }, model_path)
        
        # 결과 저장
        results_path = os.path.join(save_dir, f'all_results_{timestamp}.pkl')
        with open(results_path, 'wb') as f:
            pickle.dump({
                'all_results': self.all_results,
                'best_params': self.best_params,
                'best_score': self.best_score
            }, f)
        
        print(f"\n✅ 저장 완료:")
        print(f"   모델: {model_path}")
        print(f"   결과: {results_path}")
        
        return model_path, results_path

def main():
    """메인 실행"""
    optimizer = AdvancedHyperparameterOptimizer('HPNT_IQR_VIF5.xlsx')
    
    # 데이터 로드
    optimizer.load_and_preprocess_data()
    
    # 모든 최적화 방법 실행
    optimizer.run_all_optimizations()
    
    # 자동으로 최고 모델 저장
    optimizer.save_best_model()
    
    print("\n🎉 모든 작업 완료!")

if __name__ == "__main__":
    main()
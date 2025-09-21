import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle
import seaborn as sns
import random

def run_milp_model(processed_df):
    """
    Gurobi MILP 모델을 실행하여 최적의 선석 배정 계획을 도출합니다.

    데이터 흐름:
    1. `processed_df`에서 MILP 모델에 필요한 입력 데이터를 추출합니다.
       - 작업 소요 시간 (s_i): `predicted_work_time` 컬럼 (분으로 변환)
       - 선박 도착 시간 (a_i): `접안예정일시` 컬럼 (가장 이른 시간을 기준으로 시간 단위로 변환)
       - 선박 길이 (l_i): `LOA` 컬럼
    2. Gurobi 모델을 생성하고, 결정 변수(t, p, w, x, y)를 정의합니다.
       - t: 작업 시작 시간, p: 선석 위치, w: 대기 시간 등
    3. 목적 함수(총 대기 시간 최소화)와 제약 조건을 설정합니다.
       - 제약 조건: 도착 시간, 선석 길이, 선박 간 겹침 방지 등
    4. Gurobi 옵티마이저를 실행하여 최적해를 찾습니다.
    5. 최적해가 발견되면, 결과를 pandas DataFrame으로 정리합니다.
       - DataFrame에는 각 선박의 최적 시작 시간, 종료 시간, 대기 시간, 선석 위치 등의 정보가 포함됩니다.
    6. 최종적으로 최적화된 스케줄을 Gantt 차트로 시각화하여 `berth_gantt_chart.png` 파일로 저장합니다.

    Args:
        processed_df (pd.DataFrame): `lgbm.predict_work_time()`을 거친 데이터프레임.
                                     'predicted_work_time', '접안예정일시', 'LOA', '선명' 컬럼을 포함해야 합니다.

    Returns:
        pd.DataFrame: 최적화된 선석 배정 결과. 각 선박의 ID, 시작/종료 시간, 위치 등 상세 정보 포함.
                      최적해를 찾지 못하면 None을 반환합니다.
    """
    """
    Gurobi MILP 모델을 실행하여 최적의 선석 배정 계획을 도출합니다.

    Args:
        processed_df (pd.DataFrame): 전처리된 데이터프레임.
                                     'predicted_work_time', '접안예정일시' 컬럼을 포함해야 합니다.
    """
    print("MILP 모델 입력을 준비합니다...")

    # --- 1. 입력 데이터 추출 및 변환 ---
    # 작업소요시간 (predicted_work_time은 시간 단위로 가정, 분으로 변환)
    s_i = (processed_df['predicted_work_time'] * 60).tolist()

    # 입항시간 (가장 이른 시간을 기준으로 시간(hour) 단위로 변환)
    start_time_ref = processed_df['접안예정일시'].min()
    a_i = ((processed_df['접안예정일시'] - start_time_ref).dt.total_seconds() / 3600).tolist()

    # 선박길이 (LOA)
    l_i = processed_df['LOA'].tolist()
    N = len(processed_df)

    L = 1150  # 부두길이 (m) - 고정값
    print(f"총 {N}척의 선박, 부두 길이 {L}m에 대한 최적화를 시작합니다.")

    # 입항시간을 분 단위로 변환
    a_i_minutes = [a * 60 for a in a_i]

    # --- 2. Gurobi 모델 생성 ---
    model = gp.Model("BAIPOT")

    # --- 3. 결정 변수 ---
    t = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, name="start_time")
    p = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, ub=L, name="position")
    w = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, name="waiting_time")
    x = model.addVars(N, N, vtype=GRB.BINARY, name="left_of")
    y = model.addVars(N, N, vtype=GRB.BINARY, name="before")

    # --- 4. 목적 함수 ---
    model.setObjective(gp.quicksum(w[i] for i in range(N)), GRB.MINIMIZE)

    # --- 5. 제약 조건 ---
    model.addConstrs((w[i] == t[i] - a_i_minutes[i] for i in range(N)), name="waiting_time")
    model.addConstrs((t[i] >= a_i_minutes[i] for i in range(N)), name="arrival_constraints")
    model.addConstrs((p[i] + l_i[i] <= L for i in range(N)), name="berth_length_constraints")

    M_time = sum(s_i) + max(a_i_minutes) if a_i_minutes else sum(s_i)
    M_space = 2 * L

    for i in range(N):
        for j in range(N):
            if i != j:
                model.addConstr(p[i] + l_i[i] <= p[j] + M_space * (1 - x[i,j]), name=f"spatial_left_{i}_{j}")
                model.addConstr(p[j] + l_i[j] <= p[i] + M_space * (1 - x[j,i]), name=f"spatial_right_{i}_{j}")
                model.addConstr(t[i] + s_i[i] <= t[j] + M_time * (1 - y[i,j]), name=f"temporal_before_{i}_{j}")
                model.addConstr(t[j] + s_i[j] <= t[i] + M_time * (1 - y[j,i]), name=f"temporal_after_{i}_{j}")

    model.addConstrs((x[i,j] + x[j,i] + y[i,j] + y[j,i] >= 1 for i in range(N) for j in range(i + 1, N)), name="separation_required")

    # --- 6. 모델 최적화 ---
    print("Gurobi 최적화를 시작합니다...")
    model.optimize()

    # --- 7. 결과 처리 및 시각화 ---
    if model.status == GRB.OPTIMAL:
        print("✅ 최적해를 찾았습니다!")
        solution = []
        for i in range(N):
            start_minutes = t[i].x
            start_hours = start_minutes / 60
            waiting_minutes = w[i].x
            waiting_hours = waiting_minutes / 60
            completion_minutes = start_minutes + s_i[i]
            completion_hours = completion_minutes / 60
            position_m = p[i].x

            solution.append({
                'Ship': processed_df.iloc[i]['선명'],
                'Ship_ID': i + 1,
                'Arrival_h': a_i[i],
                'Start_h': start_hours,
                'Completion_h': completion_hours,
                'Waiting_h': waiting_hours,
                'Service_min': s_i[i],
                'Service_h': s_i[i] / 60,
                'Length_m': l_i[i],
                'Position_m': position_m,
                'End_Position_m': position_m + l_i[i]
            })

        df_solution = pd.DataFrame(solution)
        df_solution = df_solution.sort_values('Ship_ID').reset_index(drop=True)

        print("\n--- 최적화 결과 ---")
        print(df_solution[['Ship', 'Start_h', 'Completion_h', 'Waiting_h', 'Position_m']].round(2))

        # Gantt Chart 시각화
        print("\nGantt Chart를 생성합니다...")
        fig, ax = plt.subplots(figsize=(16, 9))
        colors = plt.cm.get_cmap('tab20', N)

        for i, sol in df_solution.iterrows():
            rect = Rectangle((sol['Start_h'], sol['Position_m']),
                             sol['Service_h'], sol['Length_m'],
                             facecolor=colors(i),
                             alpha=0.8, edgecolor='black', linewidth=1)
            ax.add_patch(rect)
            ax.text(sol['Start_h'] + sol['Service_h'] / 2,
                    sol['Position_m'] + sol['Length_m'] / 2,
                    f"{sol['Ship']}", ha='center', va='center',
                    fontweight='bold', fontsize=9, color='white')

        ax.set_xlabel('Time (hours)', fontsize=12)
        ax.set_ylabel('Berth Position (m)', fontsize=12)
        ax.set_title('Optimal Berth Allocation Schedule', fontsize=16, fontweight='bold')
        
        makespan = df_solution['Completion_h'].max()
        ax.set_xlim(0, makespan + 2)
        ax.set_ylim(0, L)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        chart_filename = 'berth_gantt_chart.png'
        plt.savefig(chart_filename, dpi=300)
        print(f"✅ Gantt Chart를 '{chart_filename}' 파일로 저장했습니다.")
        # plt.show() # 로컬 실행 시 활성화
        
        return df_solution

    elif model.status == GRB.INFEASIBLE:
        print("❌ 모델이 비현실적입니다. 제약 조건을 확인하세요.")
        model.computeIIS()
        for c in model.getConstrs():
            if c.IISConstr:
                print(f"  Infeasible constraint: {c.constrName}")
        return None
    else:
        print(f"Gurobi 최적화가 다른 상태로 종료되었습니다: {model.status}")
        return None

if __name__ == '__main__':
    # 테스트용 데이터프레임 생성
    print("테스트 모드로 baipot_milp.py를 실행합니다.")
    
    # main.py의 전처리 로직과 유사하게 테스트 데이터 생성
    data = {
        '선명': [f'Ship-{i}' for i in range(5)],
        '접안예정일시': pd.to_datetime(['2025-07-22 10:00', '2025-07-22 12:00', '2025-07-22 14:00', '2025-07-22 16:00', '2025-07-22 18:00']),
        'predicted_work_time': [10.5, 12.0, 8.2, 15.0, 9.5] # 시간 단위
    }
    test_df = pd.DataFrame(data)
    
    run_milp_model(test_df)

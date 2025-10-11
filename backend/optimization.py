import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import re

def run_milp_model(processed_df, cancel_event, fixed_ship_merge_keys=None):
    """
    Gurobi MILP 모델을 실행하여 최적의 선석 배정 계획 데이터를 반환합니다.
    
    Args:
        processed_df (pd.DataFrame): 전처리 및 예측이 완료된 데이터프레임.
        cancel_event (threading.Event): 최적화 중단을 위한 이벤트 객체.
        fixed_ship_merge_keys (list, optional): 스케줄을 고정할 선박의 merge_key 리스트.

    Returns:
        pd.DataFrame: 최적화된 선석 배정 결과. 최적해를 찾지 못하거나 중단되면 None을 반환합니다.
    """
    # --- 1. 입력 데이터 추출 및 변환 ---
    s_i = (processed_df['predicted_work_time'] * 60).tolist()
    start_time_ref = processed_df['접안예정일시'].min()
    a_i_minutes = ((processed_df['접안예정일시'] - start_time_ref).dt.total_seconds() / 60).tolist()
    a_i = [m / 60 for m in a_i_minutes]
    l_i = processed_df['LOA'].tolist()
    N = len(processed_df)
    L = 1150  # 부두길이 (m)
    buffer_minutes = 60

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
                model.addConstr(t[i] + s_i[i] + buffer_minutes <= t[j] + M_time * (1 - y[i,j]), name=f"temporal_before_{i}_{j}")
                model.addConstr(t[j] + s_i[j] + buffer_minutes <= t[i] + M_time * (1 - y[j,i]), name=f"temporal_after_{i}_{j}")

    model.addConstrs((x[i,j] + x[j,i] + y[i,j] + y[j,i] >= 1 for i in range(N) for j in range(i + 1, N)), name="separation_required")

    if fixed_ship_merge_keys:
        # Create merge keys to identify ships to be fixed
        df_merge_keys = (processed_df['선사'].astype(str) + '_' + processed_df['선명'].str.replace(r'\s+', '', regex=True)).tolist()
        fixed_indices = [i for i, key in enumerate(df_merge_keys) if key in fixed_ship_merge_keys]
        
        if fixed_indices:
            # Forcing start time to be arrival time for fixed ships
            model.addConstrs((t[i] == a_i_minutes[i] for i in fixed_indices), name="fix_start_time")

    # --- 6. 모델 최적화 (콜백 포함) ---
    def optimization_callback(model, where):
        if where == GRB.Callback.POLLING:
            if cancel_event.is_set():
                model.terminate()

    model.optimize(optimization_callback)

    # --- 7. 결과 처리 ---
    if model.status == GRB.OPTIMAL:
        solution = []
        for i in range(N):
            start_minutes = t[i].x
            start_hours = start_minutes / 60
            waiting_minutes = w[i].x
            waiting_hours = waiting_minutes / 60
            completion_minutes = start_minutes + s_i[i]
            completion_hours = completion_minutes / 60
            position_m = p[i].x
            
            cleaned_ship_name = re.sub(r'\s+', '', processed_df.iloc[i]['선명'])
            merge_key = f"{processed_df.iloc[i]['선사']}_{cleaned_ship_name}"

            solution.append({
                'Ship': processed_df.iloc[i]['선명'],
                'merge_key': merge_key,
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
        
        return df_solution

    elif model.status == GRB.INFEASIBLE:
        model.computeIIS()
        for c in model.getConstrs():
            if c.IISConstr:
                print(f"  Infeasible constraint: {c.constrName}")
        return None
    elif model.status == GRB.INTERRUPTED:
        print("Optimization was interrupted.")
        return None
    else:
        return None

import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle
import seaborn as sns

s_i = [1236, 2094, 1374, 1560, 1794, 1584, 852, 696, 540, 1980, 1428, 2100, 712, 630, 1230, 954, 2232, 1188, 1440, 240, 1902, 1852, 1428, 2448, 2460, 822, 600, 900, 2022, 956]
a_i = [14, 1, 14, 3, 15, 8, 8, 5, 16, 5, 11, 12, 13, 20, 1, 6, 0, 19, 23, 16, 23, 1, 7, 9, 10, 10, 3, 15, 5, 5,]
l_i = [366, 336, 366, 209, 366, 333, 142, 213, 171, 324, 222, 366, 172, 143, 366, 210, 368, 231, 209, 172, 334, 293, 303, 324, 333, 142, 175, 172, 367, 199] 

# s_i = [1236, 2094, 1374, 1560, 1794, 1584, 852, 696, 540, 1980, 1428, 2100, 712, 630, 1230, 954, 2232, 1188, 1440, 240] # 작업소요시간 (분)
# a_i = [14, 1, 14, 3, 15, 8, 8, 5, 16, 5, 11, 12, 13, 20, 1, 6, 0, 19, 23 ,16]  # 입항시간 (시간)
# l_i = [366, 336, 366, 209, 366, 333, 142, 213, 171, 324, 222, 366, 172, 143, 366, 210, 368, 231, 209, 172]  # 선박길이 (m)
L = 1150  # 부두길이 (m)
N = len(s_i)  # 선박 수 정의 추가

# Convert arrival times to minutes for consistency
a_i_minutes = [a * 60 for a in a_i]

# Create model
model = gp.Model("BAIPOT")

# Decision Variables
# t[i] = start time of ship i (in minutes)
t = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, name="start_time")

# p[i] = berth position of ship i (starting position along the berth)
p = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, ub=L, name="position")

# w[i] = waiting time of ship i (in minutes)
w = model.addVars(N, vtype=GRB.CONTINUOUS, lb=0, name="waiting_time")

# Binary variables for spatial conflicts
# x[i,j] = 1 if ship i is to the left of ship j
x = model.addVars(N, N, vtype=GRB.BINARY, name="left_of")

# Binary variables for temporal conflicts  
# y[i,j] = 1 if ship i finishes before ship j starts
y = model.addVars(N, N, vtype=GRB.BINARY, name="before")

# Objective: Minimize total waiting time
model.setObjective(
    gp.quicksum(w[i] for i in range(N)),
    GRB.MINIMIZE
)

# Constraints

# 1. Waiting time definition
model.addConstrs((w[i] == t[i] - a_i_minutes[i] for i in range(N)), name="waiting_time")

# 2. Start time must be at least arrival time
model.addConstrs((t[i] >= a_i_minutes[i] for i in range(N)), name="arrival_constraints")

# 3. Position constraints - ships must fit within berth
model.addConstrs((p[i] + l_i[i] <= L for i in range(N)), name="berth_length_constraints")

# 4. Non-overlapping constraints
M_time = sum(s_i) + max(a_i_minutes)  # Big M for time
M_space = 2 * L  # Big M for space (increased)

model.addConstrs((p[i] + l_i[i] <= p[j] + M_space * (1 - x[i,j]) 
                 for i in range(N) for j in range(N) if i != j), 
                 name="spatial_left")

model.addConstrs((p[j] + l_i[j] <= p[i] + M_space * (1 - x[j,i]) 
                 for i in range(N) for j in range(N) if i != j), 
                 name="spatial_right")

model.addConstrs((t[i] + s_i[i] <= t[j] + M_time * (1 - y[i,j]) 
                 for i in range(N) for j in range(N) if i != j), 
                 name="temporal_before")

model.addConstrs((t[j] + s_i[j] <= t[i] + M_time * (1 - y[j,i]) 
                 for i in range(N) for j in range(N) if i != j), 
                 name="temporal_after")

model.addConstrs((x[i,j] + x[j,i] + y[i,j] + y[j,i] >= 1 
                 for i in range(N) for j in range(i+1, N)), 
                 name="separation_required")

model.optimize()

# Process results
if model.status == GRB.OPTIMAL:
    
    # Extract solution
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
            'Ship': f'Ship_{i+1}',
            'Ship_ID': i+1,
            'Arrival_h': a_i[i],
            'Start_h': start_hours,
            'Completion_h': completion_hours,
            'Waiting_h': waiting_hours,
            'Service_min': s_i[i],
            'Service_h': s_i[i]/60,
            'Length_m': l_i[i],
            'Position_m': position_m,
            'End_Position_m': position_m + l_i[i]
        })
    
    # ========================================
    # Create DataFrame for easy access
    # ========================================
    df_solution = pd.DataFrame(solution)
    df_solution = df_solution.sort_values('Ship_ID').reset_index(drop=True)
    
    print(df_solution[['Ship_ID', 'Start_h', 'Position_m', 'End_Position_m', 'Completion_h', 'Waiting_h']].round(2))
    
    # ========================================
    # GANTT CHART VISUALIZATION
    # ========================================
    
    # Set up matplotlib style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Create figure for gantt chart
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Colors for each ship
    colors = plt.cm.Set3(np.linspace(0, 1, N))
    
    # Space-Time Gantt Chart
    for i, sol in enumerate(solution):
        # Draw rectangle for each ship in space-time
        rect = Rectangle((sol['Start_h'], sol['Position_m']), 
                        sol['Service_h'], sol['Length_m'],
                        facecolor=colors[sol['Ship_ID']-1], 
                        alpha=0.7, edgecolor='black', linewidth=1)
        ax.add_patch(rect)
        
        # Add ship label
        ax.text(sol['Start_h'] + sol['Service_h']/2, 
                sol['Position_m'] + sol['Length_m']/2,
                f"Ship{sol['Ship_ID']}", ha='center', va='center', 
                fontweight='bold', fontsize=10)
    
    ax.set_xlabel('Time (h)', fontsize=12)
    ax.set_ylabel('Berthin Position (m)', fontsize=12)
    ax.set_title('', fontsize=14, fontweight='bold')
    ax.set_xlim(0, makespan + 2)
    ax.set_ylim(0, L)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('berth_gantt_chart.png', dpi=300, bbox_inches='tight')
    plt.show()
        
else:
    if model.status == GRB.INFEASIBLE:
        model.computeIIS()
        for c in model.getConstrs():
            if c.IISConstr:
                print(f"  {c.constrName}")
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np

# Set default font
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

def draw_gantt_chart(ax, df, title, start_col, end_col, color_map, xlim_min, xlim_max, is_baipot=False):
    """Draws a Gantt chart on the specified axis (ax)."""
    
    df = df.copy()
    df[start_col] = pd.to_datetime(df[start_col])
    df[end_col] = pd.to_datetime(df[end_col])
    df['duration'] = df[end_col] - df[start_col]

    # BAIPOT Chart (Continuous Position)
    if is_baipot:
        ax.set_ylabel("Quay Position (m)")
        ax.set_ylim(0, 1150)
        for _, task in df.iterrows():
            ship_color = color_map.get(task['선명'], '#808080') # Default to gray

            # Draw buffer
            buffer_start = task[start_col] - timedelta(hours=1)
            buffer_duration = task['duration'] + timedelta(hours=2)
            ax.barh(y=task['Position_m'], width=buffer_duration, left=buffer_start,
                    height=task['Length_m'], align='edge', color='blue', alpha=0.5, edgecolor='blue')

            ax.barh(y=task['Position_m'], width=task['duration'], left=task[start_col], 
                    height=task['Length_m'], align='edge', edgecolor='black', alpha=0.8, color=ship_color)
            ax.text(task[start_col] + task['duration'] / 2, task['Position_m'] + task['Length_m'] / 2, 
                    task['선명'], ha='center', va='center', color='black', fontsize=8, fontweight='bold')
    
    # HPNT Chart (Discrete Berths)
    else:
        berth_col = '선석'
        y_labels = sorted(df[berth_col].unique(), key=lambda x: str(x))
        y_pos = np.arange(len(y_labels))
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(y_labels)
        ax.set_ylim(-0.5, len(y_labels) - 0.5)
        ax.set_ylabel("Berth")

        for i, berth in enumerate(y_labels):
            berth_df = df[df[berth_col] == berth]
            for _, task in berth_df.iterrows():
                ship_color = color_map.get(task['선명'], '#808080') # Default to gray
                ax.barh(i, task['duration'], left=task[start_col], height=0.6, align='center', edgecolor='black', color=ship_color)
                ax.text(task[start_col] + task['duration'] / 2, i, task['선명'], 
                        ha='center', va='center', color='black', fontsize=8, fontweight='bold')

    # Common Formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=10))
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.grid(True, which='major', axis='x', linestyle='--')
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_xlim(xlim_min, xlim_max) # Set synchronized X-axis limits

def generate_comparison_charts(start_date_str, end_date_str):
    """
    Generates and compares HPNT and BAIPOT Gantt charts for the specified period.
    """
    from utils import get_work_plan_data, predict_work_time, run_milp_model

    print(f"\n--- Generating Gantt chart for period: {start_date_str} ~ {end_date_str} ---")

    try:
        work_plan_df = get_work_plan_data(start_date_str, end_date_str)
        if work_plan_df is None or work_plan_df.empty:
            print(f"Error: Could not retrieve HPNT data for the period {start_date_str} ~ {end_date_str}.")
            return
        
        predicted_df = predict_work_time(work_plan_df.copy())
        solution_df = run_milp_model(predicted_df)
        
        if solution_df is None or solution_df.empty:
            print("Error: Could not generate BAIPOT optimization results.")
            return

    except Exception as e:
        print(f"Error during data processing: {e}")
        return

    # Add time and name info to BAIPOT results
    start_time_ref = predicted_df['접안예정일시'].min()
    solution_df['Start_Time'] = start_time_ref + pd.to_timedelta(solution_df['Start_h'], unit='h')
    solution_df['ETD'] = start_time_ref + pd.to_timedelta(solution_df['Completion_h'], unit='h')
    solution_df.rename(columns={'Ship': '선명'}, inplace=True)

    # ETD 비교표 생성
    etd_comparison_df = pd.merge(
        solution_df[['선명', '모선항차', 'ETD']],
        work_plan_df[['선명', '모선항차', '출항예정일시']],
        on=['선명', '모선항차'],
        how='left'
    )
    etd_comparison_df.rename(columns={
        'ETD': '예상 ETD',
        '출항예정일시': 'HPNT 출항 예정시간'
    }, inplace=True)
    etd_comparison_df['예상 ETD'] = pd.to_datetime(etd_comparison_df['예상 ETD'])
    etd_comparison_df['HPNT 출항 예정시간'] = pd.to_datetime(etd_comparison_df['HPNT 출항 예정시간'])
    etd_comparison_df['차이'] = (etd_comparison_df['예상 ETD'] - etd_comparison_df['HPNT 출항 예정시간']).dt.total_seconds() / 3600
    
    etd_comparison_table = etd_comparison_df[['선명', '모선항차', '예상 ETD', 'HPNT 출항 예정시간', '차이']]
    
    output_csv_filename = f"etd_comparison_{start_date_str}_to_{end_date_str}.csv"
    etd_comparison_table.to_csv(output_csv_filename, index=False, encoding='utf-8-sig')
    print(f"Success: ETD comparison table saved to '{output_csv_filename}'.")

    # Create a color map for unique ships
    all_ships = pd.concat([work_plan_df['선명'], solution_df['선명']]).unique()
    colors = plt.cm.get_cmap('tab20', len(all_ships))
    color_map = {ship: colors(i) for i, ship in enumerate(all_ships)}

    # Determine overall min/max time for X-axis synchronization
    min_time_hpnt = pd.to_datetime(work_plan_df['접안예정일시']).min()
    max_time_hpnt = pd.to_datetime(work_plan_df['출항예정일시']).max()
    min_time_baipot = pd.to_datetime(solution_df['Start_Time']).min()
    max_time_baipot = pd.to_datetime(solution_df['ETD']).max()

    overall_min_time = min(min_time_hpnt, min_time_baipot)
    overall_max_time = max(max_time_hpnt, max_time_baipot)

    # Add some padding to the time axis
    time_padding = timedelta(hours=6) # 6 hours padding
    overall_min_time -= time_padding
    overall_max_time += time_padding

    # Draw charts
    fig, axes = plt.subplots(2, 1, figsize=(20, 14))
    fig.suptitle(f'Berth Allocation Plan Comparison: {start_date_str} ~ {end_date_str}', fontsize=18)

    # HPNT Actual Data Gantt Chart
    draw_gantt_chart(axes[0], work_plan_df, "HPNT Actual Berth Plan", '접안예정일시', '출항예정일시', color_map, overall_min_time, overall_max_time, is_baipot=False)

    # BAIPOT Predicted Data Gantt Chart
    draw_gantt_chart(axes[1], solution_df, "BAIPOT Predicted Berth Plan", 'Start_Time', 'ETD', color_map, overall_min_time, overall_max_time, is_baipot=True)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    output_filename = f"gantt_comparison_{start_date_str}_to_{end_date_str}.png"
    plt.savefig(output_filename)
    print(f"Success: Comparison chart saved to '{output_filename}'.")
    plt.close(fig)

if __name__ == '__main__':
    periods_to_generate = [
        ('2025-02-01', '2025-02-03'),
        ('2025-02-01', '2025-02-05'),
        ('2025-02-01', '2025-02-07'),
        ('2025-02-01', '2025-02-10'),
        ('2025-02-11', '2025-02-14'),
        ('2025-02-11', '2025-02-16'),
        ('2025-02-11', '2025-02-18'),
        ('2025-02-11', '2025-02-21'),
        ('2025-02-22', '2025-02-24'),
        ('2025-02-22', '2025-02-26'),
        ('2025-02-22', '2025-02-28'),
    ]

    for start_date, end_date in periods_to_generate:
        generate_comparison_charts(start_date, end_date)

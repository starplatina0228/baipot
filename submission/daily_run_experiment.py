import os
import logging
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

from utils import get_work_plan_data, predict_work_time, run_milp_model

plt.rcParams['font.family'] = 'sans-serif' 
plt.rcParams['axes.unicode_minus'] = False

def draw_gantt_chart(ax, df, title, start_col, end_col, color_map, xlim_min, xlim_max, is_baipot=False):
    df = df.copy()
    df[start_col] = pd.to_datetime(df[start_col])
    df[end_col] = pd.to_datetime(df[end_col])
    df['duration'] = df[end_col] - df[start_col]

    if is_baipot:
        ax.set_ylabel("Quay Position (m)")
        ax.set_ylim(0, 1150)
        for _, task in df.iterrows():
            ship_color = color_map.get(task['선명'], '#808080')
            # Draw buffer
            buffer_start = task[start_col] - timedelta(hours=1)
            buffer_duration = task['duration'] + timedelta(hours=2)
            ax.barh(y=task['Position_m'], width=buffer_duration, left=buffer_start,
                    height=task['Length_m'], align='edge', color='blue', alpha=0.5, edgecolor='blue')

            ax.barh(y=task['Position_m'], width=task['duration'], left=task[start_col], 
                    height=task['Length_m'], align='edge', edgecolor='black', alpha=0.8, color=ship_color)
            ax.text(task[start_col] + task['duration'] / 2, task['Position_m'] + task['Length_m'] / 2, 
                    task['선명'], ha='center', va='center', color='black', fontsize=8, fontweight='bold')
    else:
        berth_col = '선석'
        y_labels = sorted(df[berth_col].dropna().unique(), key=lambda x: str(x))
        y_pos = {berth: i for i, berth in enumerate(y_labels)}
        ax.set_yticks(list(y_pos.values()))
        ax.set_yticklabels(list(y_pos.keys()))
        ax.set_ylim(-0.5, len(y_labels) - 0.5)
        ax.set_ylabel("Berth")
        for _, task in df.iterrows():
            if pd.notna(task[berth_col]):
                berth_y_pos = y_pos[task[berth_col]]
                ship_color = color_map.get(task['선명'], '#808080')
                ax.barh(berth_y_pos, task['duration'], left=task[start_col], height=0.6, align='center', edgecolor='black', color=ship_color)
                ax.text(task[start_col] + task['duration'] / 2, berth_y_pos, task['선명'], 
                        ha='center', va='center', color='black', fontsize=8, fontweight='bold')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=10, maxticks=20))
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Time")
    ax.grid(True, which='major', axis='x', linestyle='--')
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_xlim(xlim_min, xlim_max)

def plot_gantt_charts_for_date(work_plan_df, solution_df, output_dir, date_str):
    all_ships = pd.concat([work_plan_df['선명'], solution_df['선명']]).unique()
    colors = plt.cm.get_cmap('tab20', len(all_ships))
    color_map = {ship: colors(i) for i, ship in enumerate(all_ships)}

    min_time_hpnt = pd.to_datetime(work_plan_df['접안예정일시']).min()
    max_time_hpnt = pd.to_datetime(work_plan_df['출항예정일시']).max()
    min_time_baipot = pd.to_datetime(solution_df['Start_Time']).min()
    max_time_baipot = pd.to_datetime(solution_df['ETD']).max()
    overall_min_time = min(min_time_hpnt, min_time_baipot) - timedelta(hours=3)
    overall_max_time = max(max_time_hpnt, max_time_baipot) + timedelta(hours=3)

    fig, axes = plt.subplots(2, 1, figsize=(20, 14), constrained_layout=True)
    fig.suptitle(f'Berth Allocation Plan Comparison ({date_str})', fontsize=18, fontweight='bold')

    draw_gantt_chart(axes[0], work_plan_df, "HPNT Berth Plan", '접안예정일시', '출항예정일시', color_map, overall_min_time, overall_max_time, is_baipot=False)
    
    if '선명' not in solution_df.columns and 'Ship' in solution_df.columns:
        solution_df.rename(columns={'Ship': '선명'}, inplace=True)
    draw_gantt_chart(axes[1], solution_df, "BAIPOT Berth Plan", 'Start_Time', 'ETD', color_map, overall_min_time, overall_max_time, is_baipot=True)

    output_path = os.path.join(output_dir, f"gantt_comparison_{date_str}.png")
    plt.savefig(output_path)
    logging.info(f"Gantt chart comparison saved to '{output_path}'.")
    plt.close(fig)


def setup_logging(output_dir, date_str):
    log_file = os.path.join(output_dir, f"daily_run_{date_str}.log")
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def compare_etd(solution_df_with_all_info, output_path):
    """모든 정보가 포함된 DataFrame을 받아 ETD 비교 CSV 파일로 저장합니다."""
    desired_columns = ['Ship', '선사', '모선항차', '선사항차', '접안예정일시', '출항예정일시', 'ETD']
    columns_to_include = [col for col in desired_columns if col in solution_df_with_all_info.columns]
    comparison_df = solution_df_with_all_info[columns_to_include]
    
    print("\n--- ETD Comparison ---")
    print(comparison_df)
    comparison_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"ETD comparison results saved to {output_path}")


def main():
    today = datetime.now()
    date_str = today.strftime('%Y%m%d')
    output_dir = f"results_{date_str}"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    setup_logging(output_dir, date_str)
    logging.info(f"Starting daily berth planning workflow for {date_str}")

    # --- Step 1: 데이터 크롤링 ---
    logging.info("Step 1: Starting data crawling...")
    start_date_crawl = today.strftime('%Y-%m-%d')
    # end_date_crawl = (today + timedelta(days=4)).strftime('%Y-%m-%d')
    end_date_crawl = '2025-11-06'
    
    try:
        df_crawled = get_work_plan_data(start_date=start_date_crawl, end_date=end_date_crawl)
        if df_crawled is None or df_crawled.empty:
            logging.warning("No data crawled. Skipping further steps.")
            return
        crawled_data_output_path = os.path.join(output_dir, f"hpnt_crawled_data_{date_str}.csv")
        df_crawled.to_csv(crawled_data_output_path, index=False, encoding='utf-8-sig')
        logging.info(f"Crawled data saved to {crawled_data_output_path}")
    except Exception as e:
        logging.error(f"Error during data crawling: {e}")
        return

    # --- Step 2: 작업 시간 예측 ---
    logging.info("Step 2: Predicting work time...")
    try:
        predicted_df = predict_work_time(df_crawled.copy())
        if 'predicted_work_time' not in predicted_df.columns:
            logging.error("'predicted_work_time' column not found after prediction.")
            return
        predicted_work_time_output_path = os.path.join(output_dir, f"work_time_predictions_{date_str}.csv")
        predicted_df.to_csv(predicted_work_time_output_path, index=False, encoding='utf-8-sig')
        logging.info(f"Work time predictions saved to {predicted_work_time_output_path}")
    except Exception as e:
        logging.error(f"Error during work time prediction: {e}")
        return

    # --- Step 3: MILP 최적화 및 결과 처리 ---
    logging.info("Step 3: Running MILP optimization...")
    try:
        solution_df_results_only = run_milp_model(predicted_df)
        
        if solution_df_results_only is not None and not solution_df_results_only.empty:
            logging.info("MILP optimization completed successfully.")
            
            # --- Step 4: 결과 병합 및 시간 계산 ---
            solution_df = pd.merge(solution_df_results_only, predicted_df, left_on=['Ship', '모선항차'], right_on=['선명', '모선항차'], how='left')
            
            # 시각화 및 저장을 위한 시간 컬럼 계산
            start_time_ref = pd.to_datetime(predicted_df['접안예정일시'].min())
            solution_df['Start_Time'] = start_time_ref + pd.to_timedelta(solution_df['Start_h'], unit='h')
            solution_df['ETD'] = start_time_ref + pd.to_timedelta(solution_df['Completion_h'], unit='h')
            
            # --- Step 5: 간트 차트 생성 ---
            logging.info("Step 5: Generating Gantt chart comparison...")
            plot_gantt_charts_for_date(df_crawled, solution_df.copy(), output_dir, date_str)
            
            # --- Step 6: ETD 비교 파일 저장 ---
            logging.info("Step 6: Calculating and comparing ETD for CSV...")
            solution_df_for_csv = solution_df.copy()
            solution_df_for_csv['ETD'] = solution_df_for_csv['ETD'].dt.strftime('%Y-%m-%d %H:%M')
            etd_comparison_path = os.path.join(output_dir, f"etd_comparison_{date_str}.csv")
            compare_etd(solution_df_for_csv, etd_comparison_path)
        else:
            logging.warning("MILP optimization did not return a solution.")
    except Exception as e:
        logging.error(f"An error occurred during MILP optimization or result processing: {e}")

if __name__ == '__main__':
    main()